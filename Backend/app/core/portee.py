"""Périmètre administratif des COMPTES dans la hiérarchie (lecture et gestion).

Lecture  : ROOT tout ; chef de service les comptes de son service ; chef de division ceux de sa division.
Gestion  : ROOT tout ;
           chef de service -> les chefs de division de son service, et les agents des divisions dont il assure l'intérim ;
           chef de division (ou intérimaire) -> les agents SANS titre de sa division.
           Les chefs de service et les super administrateurs ne se gèrent que par un super administrateur.
Gérer un compte relève de l'identité, pas du contenu : aucun déverrouillage n'est demandé (contrairement aux rôles et fichiers).
"""

from fastapi import HTTPException, status
from sqlalchemy import ColumnElement, false
from sqlalchemy.orm import Session

from app.core.acces import peut_gerer_division
from app.core.permissions import (
    NIVEAU_DIVISION,
    NIVEAU_ROOT,
    NIVEAU_SERVICE,
    TITRE_CHEF_DIVISION,
    TITRE_CHEF_SERVICE,
    Principal,
)
from app.db.metier import Agent, Division, User


def filtre_comptes_visibles(principal: Principal) -> ColumnElement[bool] | None:
    """Condition à appliquer sur Agent (jointure externe depuis User). None = aucune restriction (ROOT)."""
    if principal.niveau == NIVEAU_ROOT:
        return None
    if principal.niveau == NIVEAU_SERVICE:
        return Agent.service_id == principal.service_id
    if principal.niveau == NIVEAU_DIVISION:
        return Agent.division_id == principal.division_id
    return false()


def voit_agent(principal: Principal, agent: Agent | None) -> bool:
    if principal.niveau == NIVEAU_ROOT:
        return True
    if agent is None:
        return False
    if principal.niveau == NIVEAU_SERVICE:
        return agent.service_id == principal.service_id
    if principal.niveau == NIVEAU_DIVISION:
        return agent.division_id is not None and agent.division_id == principal.division_id
    return False


def gere_agent(db: Session, principal: Principal, agent: Agent | None) -> bool:
    if principal.niveau == NIVEAU_ROOT:
        return True
    if agent is None or agent.titre == TITRE_CHEF_SERVICE:
        return False
    if agent.titre == TITRE_CHEF_DIVISION:
        return principal.niveau == NIVEAU_SERVICE and agent.service_id == principal.service_id
    division = db.get(Division, agent.division_id) if agent.division_id is not None else None
    return division is not None and peut_gerer_division(db, principal, division)


def exiger_gestion_compte(db: Session, principal: Principal, user: User) -> User:
    if not voit_agent(principal, user.agent):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Utilisateur introuvable.")
    if not gere_agent(db, principal, user.agent):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Ce compte n'est pas dans votre périmètre de gestion.")
    return user
