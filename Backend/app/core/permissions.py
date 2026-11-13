"""Contrôle d'accès.

Deux niveaux :

1. Rôle GLOBAL du compte (tables _role, permission, role_permission) :
   - ADMIN : toutes les permissions ; crée les dossiers, gère les membres et les rôles de dossier, et peut tout faire
     dans tous les dossiers (contenu compris) ;
   - UTILISATEUR : n'a aucun droit propre sur les fichiers ; tout vient de ses appartenances à des dossiers.

2. Rôle de DOSSIER (LECTEUR, CONTRIBUTEUR, GESTIONNAIRE_DE_CONTENU), donné par l'admin :
   - directement à un utilisateur (dossier_membre) ;
   - ou à un service entier (dossier_service) : tous les agents actifs du service reçoivent ce rôle.
   Le rôle effectif est le plus élevé des deux. Il est recalculé à CHAQUE requête (aucun cache) : le retrait d'un membre
   ou le changement d'un rôle prend effet tout de suite.

Hors de ses dossiers, on ne voit rien : 404 (l'existence du dossier n'est pas révélée). Dans un dossier, une action
interdite par le rôle renvoie 403. La matrice ci-dessous est la seule source de vérité des droits de dossier.
"""

from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.metier import Dossier, DossierMembre, DossierService, Permission, User, role_permission

ROLE_ADMIN = "ADMIN"
ROLE_UTILISATEUR = "UTILISATEUR"
ROLES = (ROLE_ADMIN, ROLE_UTILISATEUR)

# Codes de permissions globales (identiques à database/04 et 05)
DOCUMENT_LISTER = "document.lister"
CHAT_UTILISER = "chat.utiliser"
UTILISATEUR_LISTER = "utilisateur.lister"
UTILISATEUR_CREER = "utilisateur.creer"
UTILISATEUR_MODIFIER = "utilisateur.modifier"
STRUCTURE_GERER = "structure.gerer"
AUDIT_CONSULTER = "audit.consulter"
DOSSIER_GERER = "dossier.gerer"

# --- Rôles de dossier -------------------------------------------------------------------------------------------------

LECTEUR = "LECTEUR"
CONTRIBUTEUR = "CONTRIBUTEUR"
GESTIONNAIRE = "GESTIONNAIRE_DE_CONTENU"
ROLES_DOSSIER = (LECTEUR, CONTRIBUTEUR, GESTIONNAIRE)
_RANG = {LECTEUR: 1, CONTRIBUTEUR: 2, GESTIONNAIRE: 3}

# Actions possibles dans un dossier
VOIR = "voir"  # le dossier, la liste de ses fichiers (métadonnées, historique des versions)
APERCU = "apercu"
TELECHARGER = "telecharger"
CHAT = "chat"
AJOUTER_FICHIER = "ajouter_fichier"
AJOUTER_VERSION = "ajouter_version"
MODIFIER = "modifier"  # titre et cases tableaux / images
SUPPRIMER = "supprimer"  # un fichier ou une version

ACTIONS_ECRITURE = frozenset({AJOUTER_FICHIER, AJOUTER_VERSION, MODIFIER, SUPPRIMER})

_LECTURE = frozenset({VOIR, APERCU, TELECHARGER, CHAT})
MATRICE: dict[str, frozenset[str]] = {
    LECTEUR: _LECTURE,
    CONTRIBUTEUR: _LECTURE | {AJOUTER_FICHIER, AJOUTER_VERSION, MODIFIER},
    GESTIONNAIRE: _LECTURE | {AJOUTER_FICHIER, AJOUTER_VERSION, MODIFIER, SUPPRIMER},
}


def plus_haut(a: str | None, b: str | None) -> str | None:
    """Le plus élevé de deux rôles de dossier (None = aucun accès)."""
    if a is None:
        return b
    if b is None:
        return a
    return a if _RANG[a] >= _RANG[b] else b


@dataclass(frozen=True)
class Principal:
    """L'utilisateur connecté avec ses permissions globales, calculé une fois par requête."""

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

    @property
    def service_actif_id(self) -> int | None:
        """Service dont le rôle de dossier s'applique : celui de l'agent, si l'agent et le service sont actifs."""
        agent = self.user.agent
        if agent is None or not agent.actif or agent.service_id is None:
            return None
        return agent.service_id if agent.service is not None and agent.service.actif else None

    def can(self, permission: str) -> bool:
        return permission in self.permissions


def load_permissions(db: Session, user: User) -> frozenset[str]:
    rows = db.scalars(
        select(Permission.code)
        .join(role_permission, role_permission.c.permission_id == Permission.id)
        .where(role_permission.c.role_id == user.role_id)
    )
    return frozenset(rows)


# --- Rôles effectifs ---------------------------------------------------------------------------------------------------

def roles_par_dossier(db: Session, principal: Principal) -> dict[int, str]:
    """Rôle effectif de l'utilisateur dans chaque dossier auquel il a accès (archivés compris).
    L'ADMIN a le rôle GESTIONNAIRE_DE_CONTENU partout."""
    if principal.is_admin:
        return {i: GESTIONNAIRE for i in db.scalars(select(Dossier.id))}
    roles: dict[int, str] = {}
    for dossier_id, role in db.execute(
        select(DossierMembre.dossier_id, DossierMembre.role).where(DossierMembre.user_id == principal.user.id)
    ):
        roles[dossier_id] = plus_haut(roles.get(dossier_id), role)
    service_id = principal.service_actif_id
    if service_id is not None:
        for dossier_id, role in db.execute(
            select(DossierService.dossier_id, DossierService.role).where(DossierService.service_id == service_id)
        ):
            roles[dossier_id] = plus_haut(roles.get(dossier_id), role)
    return roles


def ids_dossiers_accessibles(db: Session, principal: Principal, inclure_archives: bool = True) -> list[int]:
    ids = list(roles_par_dossier(db, principal))
    if inclure_archives or not ids:
        return sorted(ids)
    return sorted(db.scalars(select(Dossier.id).where(Dossier.id.in_(ids), Dossier.archive.is_(False))))


def ids_dossiers_interrogeables(db: Session, principal: Principal) -> list[int]:
    """Dossiers sur lesquels le chat et la recherche peuvent porter : accessibles et non archivés."""
    return ids_dossiers_accessibles(db, principal, inclure_archives=False)


def exiger_acces(db: Session, principal: Principal, dossier_id: int, action: str) -> tuple[Dossier, str]:
    """Renvoie (dossier, rôle effectif) si l'action est permise, sinon lève :
    404 (dossier inexistant OU hors des accès : on ne révèle pas son existence), 403 (rôle insuffisant),
    409 (dossier archivé : lecture seule)."""
    dossier = db.get(Dossier, dossier_id)
    role = roles_par_dossier(db, principal).get(dossier_id) if dossier is not None else None
    if dossier is None or role is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dossier introuvable.")
    if action not in MATRICE[role]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Action non autorisée pour votre rôle dans ce dossier.")
    if dossier.archive and action in ACTIONS_ECRITURE:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ce dossier est archivé : il est en lecture seule.")
    return dossier, role
