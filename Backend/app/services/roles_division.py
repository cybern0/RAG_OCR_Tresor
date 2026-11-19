"""Dictionnaire de rôles métier d'une division et attribution aux agents.

Défini par le chef de division (ou son intérimaire), référencé PAR IDENTIFIANT : renommer un rôle ne casse aucun accès.
Un rôle inactif n'est plus attribuable ni demandable ; les attributions existantes restent valables.
"""

import re
import unicodedata

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.acces import est_chef_nominal, est_membre, exiger_gestion_division
from app.core.permissions import Principal
from app.db.metier import Agent, Division, RoleDivision, User, UserRoleDivision
from app.schemas.roles_division import AgentDivisionBrief, RoleDivisionIn, RoleDivisionOut, RoleDivisionUpdate
from app.services.historique import ecrire_historique
from app.services.notifications import notifier


def code_depuis(libelle: str) -> str:
    sans_accents = unicodedata.normalize("NFKD", libelle).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Z0-9]+", "_", sans_accents.upper()).strip("_")[:60] or "ROLE"


def _division(db: Session, division_id: int) -> Division:
    division = db.get(Division, division_id)
    if division is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Division introuvable.")
    return division


def _out(db: Session, role: RoleDivision) -> RoleDivisionOut:
    nb_agents = db.scalar(select(func.count()).select_from(UserRoleDivision).where(UserRoleDivision.role_division_id == role.id)) or 0
    return RoleDivisionOut(
        id=role.id, division_id=role.division_id, code=role.code, libelle=role.libelle, actif=role.actif,
        nb_agents=nb_agents,
    )


def lister_agents(db: Session, principal: Principal, division_id: int) -> list[AgentDivisionBrief]:
    """Agents actifs d'une division, pour l'affectation manuelle des fichiers. Lisible par les membres de la
    division, par les chefs (de la division, ou du service qui la couvre) et par le super administrateur :
    mêmes seuils que le dictionnaire de rôles."""
    division = _division(db, division_id)
    if not (est_membre(principal, division_id) or est_chef_nominal(db, principal, division_id) or principal.is_admin):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Division introuvable.")
    agents = db.scalars(
        select(Agent).where(Agent.division_id == division_id, Agent.actif.is_(True)).order_by(Agent.nom, Agent.prenom)
    )
    return [AgentDivisionBrief(id=a.id, matricule=a.matricule, nom=a.nom, prenom=a.prenom, actif=a.actif) for a in agents]


def lister_roles(db: Session, principal: Principal, division_id: int, *, inclure_inactifs: bool = True) -> list[RoleDivisionOut]:
    """Lisible par les membres de la division, par les chefs (de la division, ou du service qui la couvre)
    et par le super administrateur : ce sont des noms de rôles, des métadonnées d'administration — jamais
    du contenu de fichier. Même seuil que la création (exiger_gestion_division), sinon un chef pourrait
    créer un rôle sans pouvoir lister le dictionnaire."""
    division = _division(db, division_id)
    if not (est_membre(principal, division_id) or est_chef_nominal(db, principal, division_id) or principal.is_admin):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Division introuvable.")
    stmt = select(RoleDivision).where(RoleDivision.division_id == division_id).order_by(RoleDivision.libelle)
    if not inclure_inactifs:
        stmt = stmt.where(RoleDivision.actif.is_(True))
    return [_out(db, r) for r in db.scalars(stmt)]


def creer_role(db: Session, actor: Principal, division_id: int, data: RoleDivisionIn) -> RoleDivisionOut:
    division = exiger_gestion_division(db, actor, division_id)
    code = (data.code or code_depuis(data.libelle)).strip()
    role = RoleDivision(division_id=division_id, code=code, libelle=data.libelle.strip())
    db.add(role)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, f"Le code de rôle « {code} » existe déjà dans cette division.") from None
    ecrire_historique(
        db, acteur=actor.user, cible_type="role_division", cible_id=role.id, action="role_cree",
        apres={"code": role.code, "libelle": role.libelle}, service_id=division.service_id, division_id=division.id,
    )
    db.commit()
    return _out(db, role)


def _role_de_division(db: Session, division_id: int, role_id: int) -> RoleDivision:
    role = db.get(RoleDivision, role_id)
    if role is None or role.division_id != division_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Rôle introuvable dans cette division.")
    return role


def modifier_role(db: Session, actor: Principal, division_id: int, role_id: int, data: RoleDivisionUpdate) -> RoleDivisionOut:
    division = exiger_gestion_division(db, actor, division_id)
    role = _role_de_division(db, division_id, role_id)
    avant = {"code": role.code, "libelle": role.libelle, "actif": role.actif}
    if data.libelle is not None:
        role.libelle = data.libelle.strip()
    if data.code is not None:
        role.code = data.code.strip()
    if data.actif is not None:
        role.actif = data.actif
    apres = {"code": role.code, "libelle": role.libelle, "actif": role.actif}
    if apres != avant:
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            raise HTTPException(status.HTTP_409_CONFLICT, "Ce code de rôle existe déjà dans cette division.") from None
        ecrire_historique(
            db, acteur=actor.user, cible_type="role_division", cible_id=role.id, action="role_modifie",
            avant=avant, apres=apres, service_id=division.service_id, division_id=division.id,
        )
        db.commit()
    return _out(db, role)


def supprimer_role(db: Session, actor: Principal, division_id: int, role_id: int) -> None:
    division = exiger_gestion_division(db, actor, division_id)
    role = _role_de_division(db, division_id, role_id)
    out = _out(db, role)
    if out.nb_agents:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Ce rôle est utilisé par {out.nb_agents} agent(s) : réaffectez-les ou désactivez le rôle.",
        )
    ecrire_historique(
        db, acteur=actor.user, cible_type="role_division", cible_id=role.id, action="role_supprime",
        avant={"code": role.code, "libelle": role.libelle}, service_id=division.service_id, division_id=division.id,
    )
    db.delete(role)
    db.commit()


# --- Rôles d'un utilisateur -----------------------------------------------------------------------------------------

def roles_de_user(db: Session, user_id: int) -> list[RoleDivision]:
    return list(
        db.scalars(
            select(RoleDivision)
            .join(UserRoleDivision, UserRoleDivision.role_division_id == RoleDivision.id)
            .where(UserRoleDivision.user_id == user_id)
            .order_by(RoleDivision.libelle)
        )
    )


def valider_roles(db: Session, division_id: int, role_ids: list[int], *, deja_detenus: set[int] = frozenset()) -> list[RoleDivision]:
    """Les rôles existent, sont de la division et (s'ils sont nouveaux) actifs."""
    ids = list(dict.fromkeys(role_ids))
    roles = list(db.scalars(select(RoleDivision).where(RoleDivision.id.in_(ids)))) if ids else []
    if len(roles) != len(ids) or any(r.division_id != division_id for r in roles):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Rôle inconnu ou d'une autre division.")
    inactifs = [r.libelle for r in roles if not r.actif and r.id not in deja_detenus]
    if inactifs:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Rôle inactif : {', '.join(inactifs)}.")
    return roles


def definir_roles_utilisateur(db: Session, actor: Principal, user: User, role_ids: list[int], motif: str | None) -> list[RoleDivision]:
    """Remplace l'ensemble des rôles d'un agent. Réservé au gérant de sa division ; aucun fichier n'est reclassé (pas de rétroactivité)."""
    agent: Agent | None = user.agent
    if agent is None or agent.division_id is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Ce compte n'est rattaché à aucune division.")
    division = exiger_gestion_division(db, actor, agent.division_id)
    actuels = {r.id: r for r in roles_de_user(db, user.id)}
    cibles = valider_roles(db, division.id, role_ids, deja_detenus=set(actuels))
    ids_cibles = {r.id for r in cibles}
    ajoutes = [r for r in cibles if r.id not in actuels]
    retires = [r for rid, r in actuels.items() if rid not in ids_cibles]
    if retires:
        db.execute(delete(UserRoleDivision).where(UserRoleDivision.user_id == user.id, UserRoleDivision.role_division_id.in_([r.id for r in retires])))
    for r in ajoutes:
        db.add(UserRoleDivision(user_id=user.id, role_division_id=r.id))
    db.flush()
    for action, liste in (("roles_attribues", ajoutes), ("roles_retires", retires)):
        if liste:
            ecrire_historique(
                db, acteur=actor.user, cible_type="utilisateur", cible_id=user.id, action=action,
                apres=[r.libelle for r in liste] if action == "roles_attribues" else None,
                avant=[r.libelle for r in liste] if action == "roles_retires" else None,
                motif=motif, service_id=division.service_id, division_id=division.id, concerne_user_id=user.id,
            )
    if ajoutes or retires:
        notifier(
            db, [user.id], "roles_modifies", "Vos rôles de division ont été modifiés.",
            reference_type="utilisateur", reference_id=user.id, sauf_user_id=actor.user.id,
        )
    db.commit()
    return roles_de_user(db, user.id)
