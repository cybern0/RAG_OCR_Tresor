"""Règle d'accès hiérarchique aux dossiers et aux fichiers (la seule source de vérité des droits).

Pour un fichier, le rôle effectif est calculé à chaque requête :

  * membre de la division du fichier :
      GERANT   chef de division                      -> tout dans sa division
      AUTEUR   a déposé le fichier                   -> voir, modifier, versions, corbeille
      LECTEUR  un rôle commun avec le fichier, ou une exception ponctuelle valide -> lecture, commentaires
      sinon    403 (« Demander l'accès »)
  * autre division : administrateur SUPÉRIEUR (chef de service pour son service, super administrateur partout), en lecture seule,
    seulement si l'unité est déverrouillée (423 sinon). Si la division n'a plus de chef, l'intérimaire est GERANT (mais déverrouille).
  * tout le reste : 404 (l'existence n'est pas révélée).

Dossiers et sous-dossiers : visibles de tous les agents de la division (ils n'ont pas de rôle).
"""

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import ColumnElement, and_, exists, false, or_, select
from sqlalchemy.orm import Session

from app.core.permissions import (
    NIVEAU_DIVISION,
    NIVEAU_ROOT,
    NIVEAU_SERVICE,
    TITRE_CHEF_DIVISION,
    TITRE_CHEF_SERVICE,
    Principal,
)
from app.db.metier import (
    AccesException,
    Agent,
    Deverrouillage,
    Division,
    Dossier,
    DocumentRole,
    SecretUnite,
)
from app.db.vecteur import Document

# --- Rôles effectifs sur un fichier -----------------------------------------------------------------------------------

GERANT = "GERANT"
AUTEUR = "AUTEUR"
LECTEUR = "LECTEUR"
SUPERIEUR = "SUPERIEUR"

# Actions sur un fichier
VOIR = "voir"
APERCU = "apercu"
TELECHARGER = "telecharger"
CHAT = "chat"
COMMENTER = "commenter"
AJOUTER_VERSION = "ajouter_version"
MODIFIER = "modifier"  # titre, cases tableaux / images
SUPPRIMER = "supprimer"  # corbeille, restauration
PURGER = "purger"  # suppression définitive
CLASSER = "classer"  # rôles du fichier

ACTIONS_ECRITURE = frozenset({AJOUTER_VERSION, MODIFIER, SUPPRIMER, PURGER, CLASSER})

_LECTURE = frozenset({VOIR, APERCU, TELECHARGER, CHAT})
MATRICE: dict[str, frozenset[str]] = {
    GERANT: _LECTURE | {COMMENTER, AJOUTER_VERSION, MODIFIER, SUPPRIMER, PURGER, CLASSER},
    AUTEUR: _LECTURE | {COMMENTER, AJOUTER_VERSION, MODIFIER, SUPPRIMER},
    LECTEUR: _LECTURE | {COMMENTER},
    SUPERIEUR: _LECTURE,
}

# Actions sur un dossier
DOSSIER_VOIR = "dossier_voir"
DOSSIER_CREER = "dossier_creer"  # sous-dossier ou fichier : réservé aux membres de la division
DOSSIER_MODIFIER = "dossier_modifier"  # renommer, déplacer, archiver, supprimer : créateur ou gérant


def _maintenant() -> datetime:
    return datetime.now(timezone.utc)


# --- Postes, intérim, gestion -----------------------------------------------------------------------------------------

def chef_division_actif(db: Session, division_id: int) -> Agent | None:
    return db.scalars(
        select(Agent).where(Agent.division_id == division_id, Agent.titre == TITRE_CHEF_DIVISION, Agent.actif.is_(True))
    ).first()


def chef_service_actif(db: Session, service_id: int) -> Agent | None:
    return db.scalars(
        select(Agent).where(Agent.service_id == service_id, Agent.titre == TITRE_CHEF_SERVICE, Agent.actif.is_(True))
    ).first()


def _division(db: Session, division_id: int) -> Division:
    division = db.get(Division, division_id)
    if division is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Division introuvable.")
    return division


def est_membre(principal: Principal, division_id: int) -> bool:
    return principal.division_id is not None and principal.division_id == division_id


def est_superieur(principal: Principal, division: Division) -> bool:
    """Administrateur hiérarchiquement supérieur à la division (lecture avec déverrouillage)."""
    if principal.niveau == NIVEAU_ROOT:
        return True
    return principal.niveau == NIVEAU_SERVICE and principal.service_id == division.service_id


def est_chef_nominal(principal: Principal, division_id: int) -> bool:
    return principal.niveau == NIVEAU_DIVISION and principal.division_id == division_id


def peut_gerer_division(db: Session, principal: Principal, division: Division) -> bool:
    """Gérant d'une division : son chef ; à défaut le chef de service ; à défaut (service sans chef non plus) le super administrateur."""
    if est_chef_nominal(principal, division.id):
        return True
    if chef_division_actif(db, division.id) is not None:
        return False
    if principal.niveau == NIVEAU_SERVICE and principal.service_id == division.service_id:
        return True
    return principal.niveau == NIVEAU_ROOT and chef_service_actif(db, division.service_id) is None


def divisions_gerees(db: Session, principal: Principal) -> list[Division]:
    """Divisions dont le compte est gérant (la sienne s'il est chef, plus celles dont il assure l'intérim)."""
    if principal.niveau == NIVEAU_DIVISION and principal.division_id is not None:
        division = db.get(Division, principal.division_id)
        return [division] if division else []
    if principal.niveau == NIVEAU_SERVICE:
        candidates = db.scalars(select(Division).where(Division.service_id == principal.service_id)).all()
    elif principal.niveau == NIVEAU_ROOT:
        candidates = db.scalars(select(Division)).all()
    else:
        return []
    return [d for d in candidates if peut_gerer_division(db, principal, d)]


# --- Déverrouillage ---------------------------------------------------------------------------------------------------

def divisions_deverrouillees(db: Session, principal: Principal) -> set[int]:
    """Divisions que le compte a actuellement déverrouillées ET sur lesquelles il est encore supérieur (droit recalculé)."""
    if principal.niveau not in (NIVEAU_ROOT, NIVEAU_SERVICE):
        return set()
    rows = db.execute(
        select(SecretUnite.division_id, SecretUnite.service_id)
        .join(Deverrouillage, Deverrouillage.secret_unite_id == SecretUnite.id)
        .where(
            Deverrouillage.user_id == principal.user.id,
            SecretUnite.admin_user_id == principal.user.id,
            Deverrouillage.actif.is_(True),
            Deverrouillage.valide_jusqua > _maintenant(),
        )
    ).all()
    divisions = {d for d, _ in rows if d is not None}
    services = {s for _, s in rows if s is not None}
    if not divisions and not services:
        return set()
    query = select(Division.id).where(or_(Division.id.in_(divisions), Division.service_id.in_(services)))
    if principal.niveau == NIVEAU_SERVICE:
        query = query.where(Division.service_id == principal.service_id)
    return set(db.scalars(query))


def exiger_deverrouillage(db: Session, principal: Principal, division: Division) -> None:
    if division.id in divisions_deverrouillees(db, principal):
        return
    raise HTTPException(
        status.HTTP_423_LOCKED,
        detail={
            "code": "UNITE_VERROUILLEE",
            "message": f"La division « {division.nom} » est protégée : saisissez votre mot de passe de dossier.",
            "unite": {"type": "division", "id": division.id, "nom": division.nom, "service_id": division.service_id},
        },
    )


def exiger_gestion_division(db: Session, principal: Principal, division_id: int) -> Division:
    """Autorise la gestion du contenu d'une division (rôles, classement, demandes). 404 / 403 / 423."""
    division = _division(db, division_id)
    if not (est_membre(principal, division_id) or est_superieur(principal, division)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Division introuvable.")
    if not peut_gerer_division(db, principal, division):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Seul le chef de la division peut faire cette action.")
    if not est_chef_nominal(principal, division_id):
        exiger_deverrouillage(db, principal, division)
    return division


def exiger_ecriture_division(division: Division) -> None:
    if not division.actif:
        raise HTTPException(status.HTTP_409_CONFLICT, "Cette division est désactivée : elle est en lecture seule.")


# --- Fichiers ---------------------------------------------------------------------------------------------------------

def _exception_valide(db: Session, user_id: int, document_id: int) -> bool:
    return (
        db.scalars(
            select(AccesException.id).where(
                AccesException.user_id == user_id,
                AccesException.document_id == document_id,
                AccesException.active.is_(True),
                AccesException.expire_le > _maintenant(),
            )
        ).first()
        is not None
    )


def _a_un_role_commun(db: Session, principal: Principal, document_id: int) -> bool:
    if not principal.role_ids:
        return False
    return (
        db.scalars(
            select(DocumentRole.document_id).where(
                DocumentRole.document_id == document_id, DocumentRole.role_division_id.in_(principal.role_ids)
            )
        ).first()
        is not None
    )


def acces_refuse(document_id: int) -> HTTPException:
    return HTTPException(
        status.HTTP_403_FORBIDDEN,
        detail={
            "code": "ACCES_FICHIER_REFUSE",
            "message": "Vous n'avez pas le rôle requis pour ce fichier. Vous pouvez en demander l'accès.",
            "document_id": document_id,
        },
    )


def role_sur_document(db: Session, principal: Principal, document: Document) -> str | None:
    """Rôle effectif sans lever d'exception sur le verrouillage (None = aucun accès). Pour les usages internes."""
    division = db.get(Division, document.division_id)
    if division is None:
        return None
    if est_membre(principal, division.id):
        if est_chef_nominal(principal, division.id):
            return GERANT
        if document.cree_par == principal.user.id:
            return AUTEUR
        if _a_un_role_commun(db, principal, document.id) or _exception_valide(db, principal.user.id, document.id):
            return LECTEUR
        return None
    if est_superieur(principal, division) and division.id in divisions_deverrouillees(db, principal):
        return GERANT if peut_gerer_division(db, principal, division) else SUPERIEUR
    return None


def exiger_acces_document(db: Session, principal: Principal, document: Document | None, action: str) -> tuple[Document, str]:
    """Renvoie (fichier, rôle effectif) si l'action est permise, sinon 404 / 403 / 423 / 409."""
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Fichier introuvable.")
    division = db.get(Division, document.division_id)
    if division is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Fichier introuvable.")
    membre = est_membre(principal, division.id)
    if not membre and not est_superieur(principal, division):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Fichier introuvable.")
    if not membre:
        exiger_deverrouillage(db, principal, division)
    role = role_sur_document(db, principal, document)
    if role is None:
        raise acces_refuse(document.id)
    if action not in MATRICE[role]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Action non autorisée pour votre rôle sur ce fichier.")
    if action in ACTIONS_ECRITURE:
        exiger_ecriture_division(division)
        dossier = db.get(Dossier, document.dossier_id)
        if dossier is not None and dossier.archive:
            raise HTTPException(status.HTTP_409_CONFLICT, "Ce dossier est archivé : il est en lecture seule.")
    return document, role


def condition_acces_fichiers(db: Session, principal: Principal) -> ColumnElement[bool]:
    """Condition SQL « ce compte peut LIRE ce fichier » : sert aux listes, à la recherche vectorielle et au chat.
    Reprend exactement role_sur_document (fichiers de sa division selon son rôle ; autres divisions seulement si déverrouillées)."""
    clauses: list[ColumnElement[bool]] = []
    division_id = principal.division_id
    if division_id is not None:
        if principal.niveau == NIVEAU_DIVISION:
            clauses.append(Document.division_id == division_id)
        else:
            moi = principal.user.id
            sous: list[ColumnElement[bool]] = [Document.cree_par == moi]
            if principal.role_ids:
                sous.append(
                    exists().where(
                        DocumentRole.document_id == Document.id, DocumentRole.role_division_id.in_(principal.role_ids)
                    )
                )
            sous.append(
                exists().where(
                    AccesException.document_id == Document.id,
                    AccesException.user_id == moi,
                    AccesException.active.is_(True),
                    AccesException.expire_le > _maintenant(),
                )
            )
            clauses.append(and_(Document.division_id == division_id, or_(*sous)))
    externes = divisions_deverrouillees(db, principal)
    if externes:
        clauses.append(Document.division_id.in_(externes))
    return or_(*clauses) if clauses else false()


def ids_documents_accessibles(db: Session, principal: Principal, ids: list[int]) -> set[int]:
    """Parmi ces fichiers, ceux que le compte peut lire (corbeille comprise) : masquage des sources du chat."""
    if not ids:
        return set()
    return set(db.scalars(select(Document.id).where(Document.id.in_(ids), condition_acces_fichiers(db, principal))))


# --- Dossiers ---------------------------------------------------------------------------------------------------------

def exiger_acces_dossier(db: Session, principal: Principal, dossier_id: int | None, action: str) -> Dossier:
    """404 hors périmètre, 423 unité à déverrouiller, 403 action non permise, 409 archivé / division désactivée."""
    dossier = db.get(Dossier, dossier_id) if dossier_id is not None else None
    if dossier is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dossier introuvable.")
    division = _division(db, dossier.division_id)
    membre = est_membre(principal, division.id)
    if not membre and not est_superieur(principal, division):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dossier introuvable.")
    if not membre:
        exiger_deverrouillage(db, principal, division)
        if action != DOSSIER_VOIR:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Un administrateur supérieur consulte sans modifier.")
        return dossier
    if action == DOSSIER_MODIFIER and not (est_chef_nominal(principal, division.id) or dossier.cree_par == principal.user.id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Seul le créateur du dossier ou le chef de division peut le modifier.")
    if action != DOSSIER_VOIR:
        exiger_ecriture_division(division)
        if dossier.archive and action == DOSSIER_CREER:
            raise HTTPException(status.HTTP_409_CONFLICT, "Ce dossier est archivé : il est en lecture seule.")
    return dossier


def exiger_acces_division(db: Session, principal: Principal, division_id: int, *, ecriture: bool = False) -> Division:
    """Accès à la RACINE d'une division (liste de ses dossiers)."""
    division = _division(db, division_id)
    membre = est_membre(principal, division_id)
    if not membre and not est_superieur(principal, division):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Division introuvable.")
    if not membre:
        exiger_deverrouillage(db, principal, division)
        if ecriture:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Un administrateur supérieur consulte sans modifier.")
    elif ecriture:
        exiger_ecriture_division(division)
    return division


def detail_message(detail: Any) -> str:
    return detail.get("message", "") if isinstance(detail, dict) else str(detail)
