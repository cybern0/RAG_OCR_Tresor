"""Règle d'accès hiérarchique aux fichiers (la seule source de vérité des droits).

Pour un fichier, le rôle effectif est calculé à chaque requête :

  * chef de division (sa division) ou chef de service (toutes les divisions de son service, même rôle étendu) :
      GERANT   -> tout : contenu, versions, rôles des fichiers (les « classes »), classement, corbeille
  * membre de la division du fichier :
      AUTEUR   a déposé le fichier                   -> voir, modifier, versions, corbeille
      LECTEUR  un rôle commun avec le fichier, ou une exception ponctuelle valide -> lecture, commentaires
      sinon    403 (« Demander l'accès »)
  * tout le reste : 404 (l'existence n'est pas révélée) — y compris le super administrateur : il ne fait
    qu'administrer (structure, comptes, dictionnaires de rôles, audit) et n'accède ni aux fichiers ni à l'IA ;
    il n'assure l'intérim que d'une division sans chef pour sa gestion, pas pour son contenu.
  * Si la division n'a plus de chef, le super administrateur assure l'intérim de sa GESTION (rôles, classement
    du référentiel), sans jamais consulter les fichiers ni utiliser l'IA.

Les fichiers sont déposés DIRECTEMENT dans une division (plus de dossiers) : la division est la seule
frontière d'accès, et les rôles (les « classes ») décident qui lit quoi.
"""

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import ColumnElement, and_, exists, false, or_, select
from sqlalchemy.orm import Session

from app.core.permissions import NIVEAU_DIVISION, NIVEAU_ROOT, NIVEAU_SERVICE, TITRE_CHEF_DIVISION, TITRE_CHEF_SERVICE, Principal
from app.db.metier import (
    AccesException,
    Agent,
    Division,
    DocumentRole,
)
from app.db.vecteur import Document

# --- Rôles effectifs sur un fichier -----------------------------------------------------------------------------------

GERANT = "GERANT"
AUTEUR = "AUTEUR"
LECTEUR = "LECTEUR"
SUPERIEUR = "SUPERIEUR"  # conservé pour la matrice historique ; plus attribué depuis la refonte

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


def est_chef_nominal(db: Session, principal: Principal, division_id: int) -> bool:
    """Chef nominal d'une division : le chef de division (sa division) ou le chef de service
    (le même rôle que le chef de division, étendu à toutes les divisions de son service)."""
    if principal.niveau == NIVEAU_DIVISION:
        return principal.division_id == division_id
    if principal.niveau == NIVEAU_SERVICE and principal.service_id is not None:
        division = db.get(Division, division_id)
        return division is not None and division.service_id == principal.service_id
    return False


def peut_gerer_division(db: Session, principal: Principal, division: Division) -> bool:
    """Gérant d'une division : le chef de division, ou le chef de service (divisions de son service) ;
    à défaut le super administrateur (il assure l'intérim)."""
    if est_chef_nominal(db, principal, division.id):
        return True
    if chef_division_actif(db, division.id) is not None:
        return False
    return principal.niveau == NIVEAU_ROOT


def divisions_gerees(db: Session, principal: Principal) -> list[Division]:
    """Divisions dont le compte est gérant : celles de son service (chef de service), la sienne s'il est chef
    de division, plus celles dont le super administrateur assure l'intérim."""
    if principal.niveau == NIVEAU_SERVICE and principal.service_id is not None:
        return list(db.scalars(select(Division).where(Division.service_id == principal.service_id)))
    if principal.niveau == NIVEAU_DIVISION and principal.division_id is not None:
        division = db.get(Division, principal.division_id)
        return [division] if division else []
    if principal.niveau == NIVEAU_ROOT:
        candidates = db.scalars(select(Division)).all()
        return [d for d in candidates if peut_gerer_division(db, principal, d)]
    return []


# --- Gestion d'une division -------------------------------------------------------------------------------------------

def exiger_gestion_division(db: Session, principal: Principal, division_id: int) -> Division:
    """Autorise la gestion du contenu d'une division (rôles, classement, demandes). 404 / 403.
    Le super administrateur franchit le premier seuil (il administre) mais reste soumis au second :
    avec un chef en poste, la gestion du contenu revient au chef."""
    division = _division(db, division_id)
    if not (est_membre(principal, division_id) or est_chef_nominal(db, principal, division_id) or principal.is_admin):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Division introuvable.")
    if not peut_gerer_division(db, principal, division):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Seul le chef (de division ou de service) peut faire cette action.")
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
    """Rôle effectif du compte sur un fichier (None = aucun accès). Pour les usages internes.
    Le super administrateur n'y entre jamais : il n'administre pas le contenu."""
    division = db.get(Division, document.division_id)
    if division is None:
        return None
    if est_chef_nominal(db, principal, division.id):
        return GERANT
    if est_membre(principal, division.id):
        if document.cree_par == principal.user.id:
            return AUTEUR
        if _a_un_role_commun(db, principal, document.id) or _exception_valide(db, principal.user.id, document.id):
            return LECTEUR
        return None
    return None


def exiger_acces_document(db: Session, principal: Principal, document: Document | None, action: str) -> tuple[Document, str]:
    """Renvoie (fichier, rôle effectif) si l'action est permise, sinon 404 / 403 / 409."""
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Fichier introuvable.")
    division = db.get(Division, document.division_id)
    if division is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Fichier introuvable.")
    membre = est_membre(principal, division.id) or est_chef_nominal(db, principal, division.id)
    if not membre:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Fichier introuvable.")
    role = role_sur_document(db, principal, document)
    if role is None:
        raise acces_refuse(document.id)
    if action not in MATRICE[role]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Action non autorisée pour votre rôle sur ce fichier.")
    if action in ACTIONS_ECRITURE:
        exiger_ecriture_division(division)  # division désactivée : lecture seule
    return document, role


def condition_acces_fichiers(db: Session, principal: Principal) -> ColumnElement[bool]:
    """Condition SQL « ce compte peut LIRE ce fichier » : sert aux listes, à la recherche vectorielle et au chat.
    Reprend exactement role_sur_document : fichiers de sa division selon son rôle ; le chef de division voit sa
    division, le chef de service toutes les divisions de son service ; le super administrateur ne lit rien
    (il n'administre pas le contenu — ni fichiers, ni IA)."""
    clauses: list[ColumnElement[bool]] = []
    if principal.niveau == NIVEAU_SERVICE and principal.service_id is not None:
        clauses.append(
            Document.division_id.in_(select(Division.id).where(Division.service_id == principal.service_id))
        )
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
    return or_(*clauses) if clauses else false()


def ids_documents_accessibles(db: Session, principal: Principal, ids: list[int]) -> set[int]:
    """Parmi ces fichiers, ceux que le compte peut lire (corbeille comprise) : masquage des sources du chat."""
    if not ids:
        return set()
    return set(db.scalars(select(Document.id).where(Document.id.in_(ids), condition_acces_fichiers(db, principal))))


def exiger_depot_division(db: Session, principal: Principal, division_id: int) -> Division:
    """Déposer un fichier dans une division : membre de la division ou chef (de division ou de service).
    404 hors périmètre, 409 division désactivée."""
    division = _division(db, division_id)
    if not (est_membre(principal, division.id) or est_chef_nominal(db, principal, division.id)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Division introuvable.")
    exiger_ecriture_division(division)
    return division


def detail_message(detail: Any) -> str:
    return detail.get("message", "") if isinstance(detail, dict) else str(detail)
