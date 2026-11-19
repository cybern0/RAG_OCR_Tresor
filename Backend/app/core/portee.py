"""Périmètre administratif des COMPTES dans la hiérarchie (lecture et gestion).

Lecture et Gestion : ROOT tout ; chef de service ET chef de division les comptes de LEUR SERVICE —
le chef de division attribue des agents comme le chef de service, qui fait comme le super
administrateur (seule l'étendue change : le service, pas toute l'organisation). Les deux chefs gèrent
les agents de leur service, y compris les CHEF DE DIVISION (création de compte, mot de passe, rôles),
mais pas le chef de service ; les comptes sans agent lié ne sont visibles que du super administrateur.
Les titres de chef et les super administrateurs ne se gèrent que par un super administrateur.
Gérer un compte relève de l'identité, pas du contenu.
"""

from fastapi import HTTPException, status
from sqlalchemy import ColumnElement, false

from app.core.permissions import (
    NIVEAU_DIVISION,
    NIVEAU_ROOT,
    NIVEAU_SERVICE,
    TITRE_CHEF_SERVICE,
    Principal,
)
from app.db.metier import Agent, User

_CHEFS_COMPTES = (NIVEAU_SERVICE, NIVEAU_DIVISION)


def filtre_comptes_visibles(principal: Principal) -> ColumnElement[bool] | None:
    """Condition à appliquer sur Agent (jointure externe depuis User). None = aucune restriction (ROOT)."""
    if principal.niveau == NIVEAU_ROOT:
        return None
    if principal.niveau in _CHEFS_COMPTES:
        return Agent.service_id == principal.service_id
    return false()


def voit_agent(principal: Principal, agent: Agent | None) -> bool:
    if principal.niveau == NIVEAU_ROOT:
        return True
    if agent is None:
        return False
    if principal.niveau in _CHEFS_COMPTES:
        return agent.service_id == principal.service_id
    return False


def gere_agent(principal: Principal, agent: Agent | None) -> bool:
    """Le chef de service ET le chef de division gèrent les comptes de leur service, y compris les
    chefs de division (création, mot de passe, rôles) — pas le chef de service ; les super
    administrateurs tout."""
    if principal.niveau == NIVEAU_ROOT:
        return True
    if agent is None:
        return False
    if principal.niveau in _CHEFS_COMPTES:
        return agent.service_id == principal.service_id and agent.titre != TITRE_CHEF_SERVICE
    return False


def exiger_gestion_compte(principal: Principal, user: User) -> User:
    if not voit_agent(principal, user.agent):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Utilisateur introuvable.")
    if not gere_agent(principal, user.agent):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Ce compte n'est pas dans votre périmètre de gestion.")
    return user
