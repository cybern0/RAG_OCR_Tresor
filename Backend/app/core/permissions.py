"""Identité et permissions du compte connecté.

Deux sources, évaluées à CHAQUE requête (aucun cache : un retrait de droit ou de rôle prend effet tout de suite) :

1. Le rôle GLOBAL du compte (tables _role, permission, role_permission) : ADMIN (super administrateur) ou UTILISATEUR.
2. Le NIVEAU, déduit du TITRE de l'agent (une seule source de vérité) :
   ROOT (rôle ADMIN) > SERVICE (CHEF_SERVICE) > DIVISION (CHEF_DIVISION) > AGENT.
   Le chef de service a le MÊME rôle que le chef de division, étendu à toutes les divisions de son service.
   Les niveaux SERVICE et DIVISION ajoutent les permissions utilisateur.* ; le SERVICE ajoute structure.gerer,
   limité à SON service (agents, divisions et postes de chef de division — le périmètre est appliqué par
   core/portee.py et services/structure). Pour la gestion des COMPTES (/admin/utilisateurs), le chef de
   division a le même périmètre que le chef de service : les comptes de son service (attribution d'agents,
   création, mots de passe, rôles de division) — cf. core/portee.py. Le chef de service peut aussi créer les
   comptes des chefs de division et réinitialiser leur mot de passe (un agent sans chef s'adresse à l'un ou à
   l'autre).
   Le super administrateur ADMINISTRE SEULEMENT : document.lister et chat.utiliser lui sont retirés
   (structure, comptes, dictionnaires de rôles, audit — ni fichiers ni IA).

La règle d'accès aux fichiers est dans core/acces.py.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.metier import Agent, Permission, User, UserRoleDivision, role_permission

ROLE_ADMIN = "ADMIN"
ROLE_UTILISATEUR = "UTILISATEUR"
ROLES = (ROLE_ADMIN, ROLE_UTILISATEUR)

NIVEAU_ROOT = "ROOT"
NIVEAU_SERVICE = "SERVICE"
NIVEAU_DIVISION = "DIVISION"
NIVEAU_AGENT = "AGENT"

TITRE_CHEF_DIVISION = "CHEF_DIVISION"
TITRE_CHEF_SERVICE = "CHEF_SERVICE"
TITRES = (TITRE_CHEF_DIVISION, TITRE_CHEF_SERVICE)

DOCUMENT_LISTER = "document.lister"
CHAT_UTILISER = "chat.utiliser"
UTILISATEUR_LISTER = "utilisateur.lister"
UTILISATEUR_CREER = "utilisateur.creer"
UTILISATEUR_MODIFIER = "utilisateur.modifier"
STRUCTURE_GERER = "structure.gerer"
CLASSEMENT_GERER = "classement.gerer"
STATISTIQUES_GLOBALES = "statistiques.globales"
AUDIT_CONSULTER = "audit.consulter"

_GESTION_COMPTES = frozenset({UTILISATEUR_LISTER, UTILISATEUR_CREER, UTILISATEUR_MODIFIER})
PERMISSIONS_DU_NIVEAU: dict[str, frozenset[str]] = {
    NIVEAU_ROOT: frozenset(),  # tout vient déjà du rôle ADMIN
    # le chef de service gère aussi les agents de son service (création, affectation, postes de chef de division)
    NIVEAU_SERVICE: _GESTION_COMPTES | {STRUCTURE_GERER},
    NIVEAU_DIVISION: _GESTION_COMPTES,
    NIVEAU_AGENT: frozenset(),
}
# Le super administrateur ne fait qu'administrer : il ne consulte pas les fichiers et n'utilise pas l'IA.
_INTERDITS_ROOT = frozenset({DOCUMENT_LISTER, CHAT_UTILISER})


def niveau_compte(user: User) -> str:
    if user.role.code == ROLE_ADMIN:
        return NIVEAU_ROOT
    agent = user.agent
    if agent is not None and agent.titre == TITRE_CHEF_SERVICE:
        return NIVEAU_SERVICE
    if agent is not None and agent.titre == TITRE_CHEF_DIVISION:
        return NIVEAU_DIVISION
    return NIVEAU_AGENT


@dataclass(frozen=True)
class Principal:
    """L'utilisateur connecté : permissions, niveau et rôles de division, calculés une fois par requête."""

    user: User
    permissions: frozenset[str]
    niveau: str = NIVEAU_AGENT
    role_ids: frozenset[int] = frozenset()

    @property
    def role_code(self) -> str:
        return self.user.role.code

    @property
    def is_admin(self) -> bool:
        return self.niveau == NIVEAU_ROOT

    @property
    def agent(self) -> Agent | None:
        return self.user.agent

    @property
    def service_id(self) -> int | None:
        return self.user.agent.service_id if self.user.agent else None

    @property
    def division_id(self) -> int | None:
        return self.user.agent.division_id if self.user.agent else None

    def can(self, permission: str) -> bool:
        return permission in self.permissions


def load_permissions(db: Session, user: User) -> frozenset[str]:
    rows = db.scalars(
        select(Permission.code)
        .join(role_permission, role_permission.c.permission_id == Permission.id)
        .where(role_permission.c.role_id == user.role_id)
    )
    codes = frozenset(rows) | PERMISSIONS_DU_NIVEAU[niveau_compte(user)]
    if niveau_compte(user) == NIVEAU_ROOT:
        codes -= _INTERDITS_ROOT
    return codes


def construire_principal(db: Session, user: User) -> Principal:
    role_ids = frozenset(db.scalars(select(UserRoleDivision.role_division_id).where(UserRoleDivision.user_id == user.id)))
    return Principal(user=user, permissions=load_permissions(db, user), niveau=niveau_compte(user), role_ids=role_ids)
