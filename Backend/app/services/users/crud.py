"""Logique de gestion des comptes.

Règles :
- seul un compte avec les permissions utilisateur.* peut créer ou modifier un compte (donc l'ADMIN) ;
- un UTILISATEUR doit être lié à un agent actif rattaché à un service : c'est ce service qu'il gère ;
- un agent n'a qu'un seul compte ;
- on ne désactive jamais un compte, on ne change jamais un rôle au point de laisser le système sans admin actif.
"""

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.core.permissions import ROLE_ADMIN, ROLE_UTILISATEUR, Principal
from app.core.security import hash_password
from app.db.metier import Agent, Role, User
from app.schemas.user import AgentBrief, MeOut, UserCreate, UserOut, UserUpdate
from app.services.audit import log_action


def to_user_out(user: User) -> UserOut:
    agent = None
    if user.agent:
        a = user.agent
        agent = AgentBrief(
            id=a.id, matricule=a.matricule, nom=a.nom, prenom=a.prenom,
            service_id=a.service_id, service_nom=a.service.nom if a.service else None,
        )
    return UserOut(
        id=user.id, nom_utilisateur=user.nom_utilisateur, role=user.role.code, actif=user.actif,
        derniere_connexion=user.derniere_connexion, cree_le=user.cree_le, agent=agent,
    )


def to_me_out(principal: Principal) -> MeOut:
    base = to_user_out(principal.user)
    agent = principal.user.agent
    return MeOut(
        **base.model_dump(),
        permissions=sorted(principal.permissions),
        service_id=principal.service_id,
        service_nom=agent.service.nom if agent and agent.service else None,
    )


def _query():
    return select(User).options(joinedload(User.role), joinedload(User.agent).joinedload(Agent.service))


def list_users(db: Session) -> list[User]:
    return list(db.scalars(_query().order_by(User.nom_utilisateur)).unique())


def get_user(db: Session, user_id: int) -> User:
    user = db.scalars(_query().where(User.id == user_id)).unique().one_or_none()
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Utilisateur introuvable.")
    return user


def _role(db: Session, code: str) -> Role:
    role = db.scalar(select(Role).where(Role.code == code))
    if role is None:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"Rôle {code} absent : exécuter database/04.")
    return role


def _check_agent(db: Session, agent_id: int, role_code: str, ignore_user_id: int | None = None) -> Agent:
    agent = db.get(Agent, agent_id)
    if agent is None or not agent.actif:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Agent introuvable ou inactif.")
    if role_code == ROLE_UTILISATEUR and agent.service_id is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "L'agent doit être rattaché à un service.")
    taken = db.scalar(select(User.id).where(User.agent_id == agent_id, User.id != (ignore_user_id or 0)))
    if taken is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Cet agent a déjà un compte utilisateur.")
    return agent


def create_user(db: Session, actor: Principal, data: UserCreate, ip: str | None) -> User:
    if db.scalar(select(User.id).where(User.nom_utilisateur == data.nom_utilisateur)) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ce nom d'utilisateur existe déjà.")
    if data.role == ROLE_UTILISATEUR and data.agent_id is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "Un utilisateur doit être lié à un agent (son service en découle)."
        )
    if data.agent_id is not None:
        _check_agent(db, data.agent_id, data.role)
    user = User(
        nom_utilisateur=data.nom_utilisateur,
        mot_de_passe_hash=hash_password(data.mot_de_passe),
        role_id=_role(db, data.role).id,
        agent_id=data.agent_id,
    )
    db.add(user)
    db.flush()
    log_action(db, actor.user.id, "utilisateur.creer", "utilisateur", user.id,
               {"nom_utilisateur": user.nom_utilisateur, "role": data.role}, ip)
    db.commit()
    return get_user(db, user.id)


def _active_admin_count(db: Session) -> int:
    return db.scalar(
        select(func.count(User.id)).join(Role).where(Role.code == ROLE_ADMIN, User.actif.is_(True))
    ) or 0


def update_user(db: Session, actor: Principal, user_id: int, data: UserUpdate, ip: str | None) -> User:
    user = get_user(db, user_id)
    changes: dict = {}
    new_role = data.role or user.role.code
    new_agent_id = None if data.retirer_agent else (data.agent_id if data.agent_id is not None else user.agent_id)

    if new_role == ROLE_UTILISATEUR and new_agent_id is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Un utilisateur doit être lié à un agent.")

    # garde-fous : pas d'auto-sabotage, pas de système sans admin
    loses_admin = user.role.code == ROLE_ADMIN and user.actif and (new_role != ROLE_ADMIN or data.actif is False)
    if loses_admin:
        if user.id == actor.user.id:
            raise HTTPException(status.HTTP_409_CONFLICT, "Vous ne pouvez pas retirer vos propres droits d'administrateur.")
        if _active_admin_count(db) <= 1:
            raise HTTPException(status.HTTP_409_CONFLICT, "Il doit rester au moins un administrateur actif.")
    if data.actif is False and user.id == actor.user.id:
        raise HTTPException(status.HTTP_409_CONFLICT, "Vous ne pouvez pas désactiver votre propre compte.")

    if new_agent_id is not None and new_agent_id != user.agent_id:
        _check_agent(db, new_agent_id, new_role, ignore_user_id=user.id)
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
        log_action(db, actor.user.id, "utilisateur.modifier", "utilisateur", user.id, changes, ip)
        db.commit()
    return get_user(db, user.id)
