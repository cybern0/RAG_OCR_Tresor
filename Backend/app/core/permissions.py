"""Contrôle d'accès : permissions du rôle (tables _role, permission, role_permission).

Deux rôles seulement :
- ADMIN : toutes les permissions, tous les services ;
- UTILISATEUR : CRUD des documents de son propre service et chatbot ; ni agent, ni utilisateur, ni structure.

Le « service propre » d'un compte est celui de l'agent auquel il est rattaché.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.metier import Permission, User, role_permission

ROLE_ADMIN = "ADMIN"
ROLE_UTILISATEUR = "UTILISATEUR"
ROLES = (ROLE_ADMIN, ROLE_UTILISATEUR)

# Codes de permissions (identiques à database/04_seed_roles_permissions.sql)
DOCUMENT_LISTER = "document.lister"
DOCUMENT_CREER = "document.creer"
DOCUMENT_MODIFIER = "document.modifier"
DOCUMENT_SUPPRIMER = "document.supprimer"
CHAT_UTILISER = "chat.utiliser"
CHAT_TOUS_SERVICES = "chat.tous_services"
UTILISATEUR_LISTER = "utilisateur.lister"
UTILISATEUR_CREER = "utilisateur.creer"
UTILISATEUR_MODIFIER = "utilisateur.modifier"
STRUCTURE_GERER = "structure.gerer"
AUDIT_CONSULTER = "audit.consulter"


@dataclass(frozen=True)
class Principal:
    """L'utilisateur connecté avec ses permissions, calculé une fois par requête."""

    user: User
    permissions: frozenset[str]

    @property
    def role_code(self) -> str:
        return self.user.role.code

    @property
    def is_admin(self) -> bool:
        return self.role_code == ROLE_ADMIN

    @property
    def service_id(self) -> int | None:
        agent = self.user.agent
        return agent.service_id if agent else None

    def can(self, permission: str) -> bool:
        return permission in self.permissions

    def can_access_service(self, service_id: int) -> bool:
        """L'admin voit tous les services ; les autres uniquement le leur."""
        return self.is_admin or (self.service_id is not None and self.service_id == service_id)

    def chat_service_ids(self) -> list[int] | None:
        """Services interrogeables par le chat. None = tous ; liste vide = aucun (compte sans service)."""
        if self.can(CHAT_TOUS_SERVICES):
            return None
        return [self.service_id] if self.service_id is not None else []


def load_permissions(db: Session, user: User) -> frozenset[str]:
    rows = db.scalars(
        select(Permission.code)
        .join(role_permission, role_permission.c.permission_id == Permission.id)
        .where(role_permission.c.role_id == user.role_id)
    )
    return frozenset(rows)
