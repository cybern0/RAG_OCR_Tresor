"""Logique de gestion des comptes.

Règles :
- le périmètre (qui voit, qui gère quel compte) est dans core/portee.py : super administrateur tout ; chef de
  service ET chef de division les comptes de leur service (le chef de division attribue des agents comme le
  chef de service) ;
- un UTILISATEUR est lié à un agent actif (son service et sa division en découlent) ; un agent n'a qu'un seul compte ;
- on ne change jamais un rôle au point de laisser le système sans super administrateur actif.
"""

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.core.acces import divisions_gerees
from app.core.permissions import ROLE_ADMIN, ROLE_UTILISATEUR, Principal, niveau_compte
from app.core.portee import exiger_gestion_compte, filtre_comptes_visibles, gere_agent, voit_agent
from app.core.security import hash_password, login_throttle, verify_password
from app.db.metier import Agent, Role, RoleDivision, User, UserRoleDivision
from app.schemas.user import AgentBrief, DivisionBrief, MeOut, ProfileUpdate, RoleDivisionBrief, UserCreate, UserOut, UserUpdate
from app.services import roles_division
from app.services.audit import log_action
from app.services.historique import ecrire_historique


def to_user_out(user: User, roles: list[RoleDivisionBrief] | None = None) -> UserOut:
    agent = None
    if user.agent:
        a = user.agent
        agent = AgentBrief(
            id=a.id, matricule=a.matricule, nom=a.nom, prenom=a.prenom,
            service_id=a.service_id, service_nom=a.service.nom if a.service else None,
            division_id=a.division_id, division_nom=a.division.nom if a.division else None, titre=a.titre,
        )
    return UserOut(
        id=user.id, nom_utilisateur=user.nom_utilisateur, role=user.role.code, niveau=niveau_compte(user),
        actif=user.actif, derniere_connexion=user.derniere_connexion,
        cree_le=user.cree_le, agent=agent, roles_division=roles or [],
    )


def _roles_par_user(db: Session, user_ids: list[int]) -> dict[int, list[RoleDivisionBrief]]:
    resultat: dict[int, list[RoleDivisionBrief]] = {}
    if not user_ids:
        return resultat
    rows = db.execute(
        select(UserRoleDivision.user_id, RoleDivision.id, RoleDivision.code, RoleDivision.libelle)
        .join(RoleDivision, RoleDivision.id == UserRoleDivision.role_division_id)
        .where(UserRoleDivision.user_id.in_(user_ids))
        .order_by(RoleDivision.libelle)
    )
    for uid, rid, code, libelle in rows:
        resultat.setdefault(uid, []).append(RoleDivisionBrief(id=rid, code=code, libelle=libelle))
    return resultat


def users_out(db: Session, users: list[User]) -> list[UserOut]:
    roles = _roles_par_user(db, [u.id for u in users])
    return [to_user_out(u, roles.get(u.id)) for u in users]


def user_out(db: Session, user: User) -> UserOut:
    return users_out(db, [user])[0]


def to_me_out(principal: Principal, db: Session) -> MeOut:
    base = user_out(db, principal.user)
    agent = principal.user.agent
    gerees = divisions_gerees(db, principal)
    return MeOut(
        **base.model_dump(),
        permissions=sorted(principal.permissions),
        service_id=principal.service_id,
        service_nom=agent.service.nom if agent and agent.service else None,
        division_id=principal.division_id,
        division_nom=agent.division.nom if agent and agent.division else None,
        titre=agent.titre if agent else None,
        divisions_gerees=[DivisionBrief(id=d.id, nom=d.nom) for d in gerees],
    )


def _query():
    return select(User).options(
        joinedload(User.role), joinedload(User.agent).joinedload(Agent.service), joinedload(User.agent).joinedload(Agent.division)
    )


def list_users(db: Session, principal: Principal) -> list[User]:
    """Comptes du périmètre : tous (super administrateur), son service (chef de service, chef de division)."""
    stmt = _query().outerjoin(Agent, Agent.id == User.agent_id)
    perimetre = filtre_comptes_visibles(principal)
    if perimetre is not None:
        stmt = stmt.where(perimetre)
    return list(db.scalars(stmt.order_by(User.nom_utilisateur)).unique())


def get_user(db: Session, user_id: int) -> User:
    user = db.scalars(_query().where(User.id == user_id)).unique().one_or_none()
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Utilisateur introuvable.")
    return user


def get_user_visible(db: Session, principal: Principal, user_id: int) -> User:
    user = get_user(db, user_id)
    if user.id != principal.user.id and not voit_agent(principal, user.agent):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Utilisateur introuvable.")
    return user


def agents_disponibles(db: Session, principal: Principal, pour_user_id: int | None = None) -> list[AgentBrief]:
    """Agents actifs sans compte que l'on peut doter d'un compte : c'est la liste du formulaire de création.

    `pour_user_id` (changement d'agent d'un compte existant) ajoute l'agent actuellement lié à ce compte, pour qu'il
    reste sélectionnable ; il doit être dans le périmètre de l'appelant, sinon il n'est pas ajouté.
    """
    condition_libre = User.id.is_(None)
    if pour_user_id is not None:
        agent_actuel = db.scalar(select(User.agent_id).where(User.id == pour_user_id))
        if agent_actuel is not None:
            condition_libre = or_(User.id.is_(None), Agent.id == agent_actuel)
    stmt = (
        select(Agent)
        .options(joinedload(Agent.service), joinedload(Agent.division))
        .outerjoin(User, User.agent_id == Agent.id)
        .where(condition_libre, Agent.actif.is_(True))
        .order_by(Agent.nom, Agent.prenom)
    )
    perimetre = filtre_comptes_visibles(principal)
    if perimetre is not None:
        stmt = stmt.where(perimetre)
    return [
        AgentBrief(
            id=a.id, matricule=a.matricule, nom=a.nom, prenom=a.prenom, service_id=a.service_id,
            service_nom=a.service.nom if a.service else None, division_id=a.division_id,
            division_nom=a.division.nom if a.division else None, titre=a.titre,
        )
        for a in db.scalars(stmt).unique()
        if gere_agent(principal, a)
    ]


def _role(db: Session, code: str) -> Role:
    role = db.scalar(select(Role).where(Role.code == code))
    if role is None:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"Rôle {code} absent : exécuter database/02_donnees_reference.sql.")
    return role


def _check_agent(db: Session, agent_id: int, ignore_user_id: int | None = None) -> Agent:
    agent = db.get(Agent, agent_id)
    if agent is None or not agent.actif:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Agent introuvable ou inactif.")
    taken = db.scalar(select(User.id).where(User.agent_id == agent_id, User.id != (ignore_user_id or 0)))
    if taken is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Cet agent a déjà un compte utilisateur.")
    return agent


def create_user(db: Session, actor: Principal, data: UserCreate, ip: str | None) -> User:
    if data.role == ROLE_ADMIN and not actor.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Seul un super administrateur crée un super administrateur.")
    if data.role == ROLE_UTILISATEUR and data.agent_id is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Un utilisateur doit être lié à un agent (son service et sa division en découlent).")
    if db.scalar(select(User.id).where(User.nom_utilisateur == data.nom_utilisateur)) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ce nom d'utilisateur existe déjà.")
    agent = None
    if data.agent_id is not None:
        agent = _check_agent(db, data.agent_id)
        if not voit_agent(actor, agent):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Agent introuvable ou inactif.")
        if not gere_agent(actor, agent):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Vous ne pouvez pas créer le compte de cet agent.")
    if data.role_ids and (agent is None or agent.division_id is None):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Des rôles de division exigent un agent rattaché à une division.")
    user = User(
        nom_utilisateur=data.nom_utilisateur,
        mot_de_passe_hash=hash_password(data.mot_de_passe),
        role_id=_role(db, data.role).id,
        agent_id=data.agent_id,
    )
    db.add(user)
    db.flush()
    if data.role_ids:
        roles_division.definir_roles_utilisateur(db, actor, get_user(db, user.id), data.role_ids, "Attribution à la création du compte")
    log_action(db, actor.user.id, "utilisateur.creer", "utilisateur", user.id, {"nom_utilisateur": user.nom_utilisateur, "role": data.role}, ip)
    ecrire_historique(
        db, acteur=actor.user, cible_type="utilisateur", cible_id=user.id, action="compte_cree",
        apres={"nom_utilisateur": user.nom_utilisateur, "role": data.role},
        service_id=agent.service_id if agent else None, division_id=agent.division_id if agent else None, concerne_user_id=user.id,
    )
    db.commit()
    return get_user(db, user.id)


def _active_admin_count(db: Session) -> int:
    return db.scalar(select(func.count(User.id)).join(Role).where(Role.code == ROLE_ADMIN, User.actif.is_(True))) or 0


def update_user(db: Session, actor: Principal, user_id: int, data: UserUpdate, ip: str | None) -> User:
    user = get_user(db, user_id)
    change_agent = data.agent_id is not None or data.retirer_agent
    if user.id != actor.user.id or data.role is not None or change_agent:
        exiger_gestion_compte(actor, user)
    if not actor.is_admin and data.role is not None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Seul un super administrateur change le rôle d'un compte.")
    if not actor.is_admin and change_agent:
        # chef de service ET chef de division : l'agent des comptes de leur service, jamais le leur ni celui d'un super administrateur
        if user.id == actor.user.id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Vous ne pouvez pas changer votre propre agent.")
        if user.role.code == ROLE_ADMIN:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Seul un super administrateur modifie un super administrateur.")
    changes: dict = {}
    new_role = data.role or user.role.code
    new_agent_id = None if data.retirer_agent else (data.agent_id if data.agent_id is not None else user.agent_id)

    if new_role == ROLE_UTILISATEUR and new_agent_id is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Un utilisateur doit être lié à un agent.")

    # garde-fous : pas d'auto-sabotage, pas de système sans super administrateur
    loses_admin = user.role.code == ROLE_ADMIN and user.actif and (new_role != ROLE_ADMIN or data.actif is False)
    if loses_admin:
        if user.id == actor.user.id:
            raise HTTPException(status.HTTP_409_CONFLICT, "Vous ne pouvez pas retirer vos propres droits d'administrateur.")
        if _active_admin_count(db) <= 1:
            raise HTTPException(status.HTTP_409_CONFLICT, "Il doit rester au moins un super administrateur actif.")
    if data.actif is False and user.id == actor.user.id:
        raise HTTPException(status.HTTP_409_CONFLICT, "Vous ne pouvez pas désactiver votre propre compte.")
    if data.actif is not None and user.id == actor.user.id and data.mot_de_passe is not None:
        pass

    if new_agent_id is not None and new_agent_id != user.agent_id:
        nouvel_agent = _check_agent(db, new_agent_id, ignore_user_id=user.id)
        if not actor.is_admin:
            if not voit_agent(actor, nouvel_agent):
                raise HTTPException(status.HTTP_404_NOT_FOUND, "Agent introuvable ou inactif.")
            if not gere_agent(actor, nouvel_agent):
                raise HTTPException(status.HTTP_403_FORBIDDEN, "Vous ne pouvez pas affecter cet agent.")
    if new_agent_id != user.agent_id:
        user.agent_id = new_agent_id
        changes["agent_id"] = new_agent_id
    if new_role != user.role.code:
        user.role_id = _role(db, new_role).id
        changes["role"] = new_role
    if data.actif is not None and data.actif != user.actif:
        user.actif = data.actif
        changes["actif"] = data.actif
    if data.mot_de_passe is not None:
        user.mot_de_passe_hash = hash_password(data.mot_de_passe)  # invalide aussi les jetons déjà émis
        changes["mot_de_passe"] = "réinitialisé"

    if changes:
        agent = user.agent
        log_action(db, actor.user.id, "utilisateur.modifier", "utilisateur", user.id, changes, ip)
        if "actif" in changes:
            action = "compte_active" if changes["actif"] else "compte_desactive"
            ecrire_historique(
                db, acteur=actor.user, cible_type="utilisateur", cible_id=user.id, action=action,
                service_id=agent.service_id if agent else None, division_id=agent.division_id if agent else None, concerne_user_id=user.id,
            )
        autres = {k: v for k, v in changes.items() if k not in ("actif", "mot_de_passe")}
        if autres:
            ecrire_historique(
                db, acteur=actor.user, cible_type="utilisateur", cible_id=user.id, action="compte_modifie", apres=autres,
                service_id=agent.service_id if agent else None, division_id=agent.division_id if agent else None, concerne_user_id=user.id,
            )
        if "mot_de_passe" in changes:
            ecrire_historique(
                db, acteur=actor.user, cible_type="utilisateur", cible_id=user.id, action="mot_de_passe_reinitialise",
                service_id=agent.service_id if agent else None, division_id=agent.division_id if agent else None, concerne_user_id=user.id,
            )
        db.commit()
    return get_user(db, user.id)


def update_profile(db: Session, user: User, data: ProfileUpdate, ip: str | None) -> bool:
    """Modifie son propre profil. Retourne True si le mot de passe a changé (les anciens jetons ne valent alors plus rien).

    Le mot de passe actuel est exigé pour en définir un nouveau ; les échecs sont comptés comme ceux de la connexion
    (blocage temporaire), pour qu'une session volée ne serve pas à deviner le mot de passe.
    """
    changes: dict = {}
    password_changed = False

    if data.nom_utilisateur is not None and data.nom_utilisateur != user.nom_utilisateur:
        taken = db.scalar(select(User.id).where(User.nom_utilisateur == data.nom_utilisateur, User.id != user.id))
        if taken is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, "Ce nom d'utilisateur existe déjà.")
        changes["nom_utilisateur"] = {"ancien": user.nom_utilisateur, "nouveau": data.nom_utilisateur}

    if data.nouveau_mot_de_passe is not None:
        key = f"{ip}|{user.nom_utilisateur}"
        if login_throttle.is_blocked(key):
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Trop de tentatives. Réessayer dans quelques minutes.")
        if not verify_password(data.ancien_mot_de_passe or "", user.mot_de_passe_hash):
            login_throttle.record_failure(key)
            log_action(db, user.id, "profil.mot_de_passe_echec", "utilisateur", user.id, {}, ip)
            db.commit()
            # 400 et non 401 : un 401 déconnecterait l'interface comme une session expirée
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Le mot de passe actuel est incorrect.")
        if data.nouveau_mot_de_passe == data.ancien_mot_de_passe:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Le nouveau mot de passe doit être différent de l'actuel.")
        login_throttle.reset(key)
        password_changed = True
        changes["mot_de_passe"] = "modifié"

    if "nom_utilisateur" in changes:
        user.nom_utilisateur = data.nom_utilisateur
    if password_changed:
        user.mot_de_passe_hash = hash_password(data.nouveau_mot_de_passe)
    if changes:
        log_action(db, user.id, "profil.modifier", "utilisateur", user.id, changes, ip)
        db.commit()
    return password_changed
