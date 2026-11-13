"""Primitives locales pour le partage de documents, les demandes d'accès et la collaboration.

La logique reste entièrement interne à l'application : aucun service distant, aucun lien public
persistant hors du système local. Les fonctions ci-dessous servent de couche de cohérence entre
les routes, la validation des rôles et les événements de collaboration.
"""

from __future__ import annotations

import hashlib
import re
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.metier import Commentaire, DemandeAcces, DocumentLienPartage, DocumentPartage, DossierMembre, Favori, NotificationInterne
from app.db.vecteur import Document

_ACCESS_ROLE_ALIASES: dict[str, str] = {
    "LECTEUR": "LECTEUR",
    "READER": "LECTEUR",
    "READ": "LECTEUR",
    "CONSULTATION": "LECTEUR",
    "CONTRIBUTEUR": "CONTRIBUTEUR",
    "EDITOR": "CONTRIBUTEUR",
    "WRITE": "CONTRIBUTEUR",
    "MODIFICATION": "CONTRIBUTEUR",
    "GESTIONNAIRE": "GESTIONNAIRE_DE_CONTENU",
    "GESTIONNAIRE_DE_CONTENU": "GESTIONNAIRE_DE_CONTENU",
    "GESTIONNAIRE DE CONTENU": "GESTIONNAIRE_DE_CONTENU",
    "MANAGER": "GESTIONNAIRE_DE_CONTENU",
    "ADMIN": "GESTIONNAIRE_DE_CONTENU",
    "OWNER": "GESTIONNAIRE_DE_CONTENU",
}

ACCESS_ROLES = ("LECTEUR", "CONTRIBUTEUR", "GESTIONNAIRE_DE_CONTENU")


def normalize_access_role(raw_role: str | None, default: str = "LECTEUR") -> str:
    """Normalise un rôle d'accès en valeur standardisée utilisée localement.

    Accepte les variantes courantes en français et en anglais, avec ou sans espaces, tirets ou
    underscores, et renvoie toujours une valeur de la liste autorisée.
    """
    if raw_role is None:
        return default

    cleaned = str(raw_role).strip()
    if not cleaned:
        return default

    normalized = re.sub(r"[\s\-_]+", "_", cleaned).upper()
    normalized = normalized.strip("_")
    role = _ACCESS_ROLE_ALIASES.get(normalized)
    if role is not None:
        return role

    if normalized in ACCESS_ROLES:
        return normalized

    return default


def normalize_access_decision(raw_value: str | None, default: str = "pending") -> str:
    """Normalise la décision d’une demande d’accès vers un statut interne stable."""
    if raw_value is None:
        return default
    cleaned = str(raw_value).strip().lower()
    if not cleaned:
        return default
    mapping = {
        "pending": "pending",
        "attente": "pending",
        "en_attente": "pending",
        "accepted": "accepted",
        "accept": "accepted",
        "accepte": "accepted",
        "accepté": "accepted",
        "approuve": "accepted",
        "approuvé": "accepted",
        "valide": "accepted",
        "validé": "accepted",
        "approved": "accepted",
        "rejected": "rejected",
        "reject": "rejected",
        "refused": "rejected",
        "refuse": "rejected",
        "refusé": "rejected",
        "refusee": "rejected",
        "refusée": "rejected",
        "denied": "rejected",
        "deny": "rejected",
    }
    return mapping.get(cleaned, default)


def hash_share_token(token: str) -> str:
    """Hash un jeton de lien de partage pour ne pas stocker le secret brut."""
    cleaned = (token or "").strip()
    digest = hashlib.sha256(cleaned.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def generate_share_token(length: int = 32) -> str:
    """Génère un jeton aléatoire de type local pour un lien de partage."""
    if length <= 0:
        raise ValueError("La longueur du jeton doit être positive.")
    return secrets.token_urlsafe(length)


def build_share_link(base_url: str | None, token: str, path_prefix: str = "/partage") -> str:
    """Construit une URL locale pour un lien de partage."""
    suffix = f"{path_prefix}/{token}"
    if not base_url or not str(base_url).strip():
        return suffix
    return f"{str(base_url).rstrip('/')}{suffix}"


@dataclass(frozen=True)
class ShareLink:
    token: str
    role: str = "LECTEUR"
    is_anonymous: bool = True
    expires_at: datetime | None = None
    created_at: datetime | None = None
    hash_value: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "role", normalize_access_role(self.role))
        object.__setattr__(self, "hash_value", hash_share_token(self.token))


@dataclass
class AccessRequest:
    """Demande locale d'accès à un dossier ou à un document."""

    id: int | None = None
    subject_type: str = "document"
    subject_id: int = 0
    requested_by: int = 0
    requested_role: str = "LECTEUR"
    message: str = ""
    status: str = "pending"
    created_at: datetime | None = None

    def __post_init__(self) -> None:
        self.requested_role = normalize_access_role(self.requested_role)
        self.status = (self.status or "pending").lower()


@dataclass
class Comment:
    """Commentaire local associé à un document ou un dossier."""

    entity_type: str
    entity_id: int
    author_id: int
    content: str
    created_at: datetime | None = None
    parent_id: int | None = None

    def __post_init__(self) -> None:
        if not self.content or not self.content.strip():
            raise ValueError("Un commentaire ne peut pas être vide.")


@dataclass
class Notification:
    """Notification interne de collaboration ou d'accès."""

    user_id: int
    kind: str
    subject_type: str
    subject_id: int
    message: str
    is_read: bool = False
    created_at: datetime | None = None


@dataclass
class Favorite:
    """Favori local pour un document ou un dossier."""

    user_id: int
    entity_type: str
    entity_id: int
    created_at: datetime | None = None


def make_share_payload(
    document_id: int,
    *,
    role: str = "LECTEUR",
    expires_at: datetime | None = None,
    user_id: int | None = None,
    service_id: int | None = None,
    created_by: int | None = None,
    is_anonymous: bool = True,
    base_url: str | None = None,
    path_prefix: str = "/partage",
) -> dict[str, Any]:
    """Construit un payload de partage local, prêt à être sérialisé vers l'API ou l'audit."""
    normalized_role = normalize_access_role(role)
    if user_id is None and service_id is None:
        raise ValueError("Un partage local doit cibler un utilisateur ou un service.")
    token = generate_share_token()
    share = ShareLink(
        token=token,
        role=normalized_role,
        is_anonymous=is_anonymous,
        expires_at=expires_at,
        created_at=datetime.now(UTC),
    )
    return {
        "document_id": document_id,
        "user_id": user_id,
        "service_id": service_id,
        "role": share.role,
        "token": share.token,
        "token_hash": share.hash_value,
        "is_anonymous": share.is_anonymous,
        "expires_at": expires_at,
        "created_by": created_by,
        "created_at": share.created_at,
        "link": build_share_link(base_url, share.token, path_prefix),
    }


def is_share_active(expires_at: datetime | None) -> bool:
    """Vérifie si un accès de partage est encore valide."""
    if expires_at is None:
        return True
    return expires_at > datetime.now(UTC)


def request_access(
    *,
    subject_type: str,
    subject_id: int,
    requested_by: int,
    requested_role: str = "LECTEUR",
    message: str = "",
    status: str = "pending",
) -> AccessRequest:
    """Crée une demande locale d'accès pour un document ou un dossier."""
    return AccessRequest(
        subject_type=subject_type,
        subject_id=subject_id,
        requested_by=requested_by,
        requested_role=requested_role,
        message=message,
        status=status,
        created_at=datetime.now(UTC),
    )


def add_comment(
    *,
    entity_type: str,
    entity_id: int,
    author_id: int,
    content: str,
    parent_id: int | None = None,
) -> Comment:
    """Crée un commentaire local associé à un document ou un dossier."""
    return Comment(
        entity_type=entity_type,
        entity_id=entity_id,
        author_id=author_id,
        content=content,
        created_at=datetime.now(UTC),
        parent_id=parent_id,
    )


def add_notification(
    *,
    user_id: int,
    kind: str,
    subject_type: str,
    subject_id: int,
    message: str,
    is_read: bool = False,
) -> Notification:
    """Crée une notification locale interne."""
    return Notification(
        user_id=user_id,
        kind=kind,
        subject_type=subject_type,
        subject_id=subject_id,
        message=message,
        is_read=is_read,
        created_at=datetime.now(UTC),
    )


def list_document_shares(db: Session, document_id: int) -> list[DocumentPartage]:
    """Retourne tous les partages directs enregistrés sur un document."""
    return db.scalars(select(DocumentPartage).where(DocumentPartage.document_id == document_id)).all()


def create_document_share(
    db: Session,
    *,
    document_id: int,
    user_id: int | None = None,
    service_id: int | None = None,
    role: str = "LECTEUR",
    expires_at: datetime | None = None,
    created_by: int | None = None,
) -> DocumentPartage:
    """Crée un partage local sur un document."""
    if user_id is None and service_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Un partage local doit cibler un utilisateur ou un service.")
    doc = db.get(Document, document_id)
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Fichier introuvable.")
    share = DocumentPartage(
        document_id=document_id,
        user_id=user_id,
        service_id=service_id,
        role=normalize_access_role(role),
        expire_le=expires_at,
        cree_par=created_by,
    )
    db.add(share)
    db.commit()
    db.refresh(share)
    return share


def create_document_link_share(
    db: Session | None = None,
    *,
    document_id: int,
    token: str | None = None,
    role: str = "LECTEUR",
    est_anonyme: bool = True,
    expire_le: datetime | None = None,
    cree_par: int | None = None,
) -> DocumentLienPartage:
    """Crée un lien de partage local pour un document, avec jeton hashé et rôle normalisé."""
    effective_token = (token or generate_share_token()).strip()
    if not effective_token:
        raise ValueError("Le jeton de partage ne peut pas être vide.")
    normalized_role = normalize_access_role(role)
    if db is not None:
        doc = db.get(Document, document_id)
        if doc is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Fichier introuvable.")
        share = DocumentLienPartage(
            document_id=document_id,
            token_hash=hash_share_token(effective_token),
            role=normalized_role,
            est_anonyme=bool(est_anonyme),
            expire_le=expire_le,
            cree_par=cree_par,
        )
        db.add(share)
        db.commit()
        db.refresh(share)
        return share

    return DocumentLienPartage(
        document_id=document_id,
        token_hash=hash_share_token(effective_token),
        role=normalized_role,
        est_anonyme=bool(est_anonyme),
        expire_le=expire_le,
        cree_par=cree_par,
    )


def create_access_request(
    db: Session,
    *,
    subject_type: str,
    subject_id: int,
    user_id: int,
    requested_role: str = "LECTEUR",
    message: str = "",
    status: str = "pending",
) -> DemandeAcces:
    """Crée une demande locale d'accès pour un dossier ou un document."""
    if subject_type not in {"document", "dossier"}:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Type de sujet invalide.")
    request = DemandeAcces(
        sujet_type=subject_type,
        sujet_id=subject_id,
        user_id=user_id,
        role_demande=normalize_access_role(requested_role),
        message=message,
        statut=(status or "pending").lower(),
    )
    db.add(request)
    db.commit()
    db.refresh(request)
    return request


def list_access_requests(
    db: Session,
    *,
    subject_type: str | None = None,
    subject_id: int | None = None,
    status: str | None = None,
) -> list[DemandeAcces]:
    stmt = select(DemandeAcces)
    if subject_type is not None:
        stmt = stmt.where(DemandeAcces.sujet_type == subject_type)
    if subject_id is not None:
        stmt = stmt.where(DemandeAcces.sujet_id == subject_id)
    if status is not None:
        stmt = stmt.where(DemandeAcces.statut == str(status).lower())
    stmt = stmt.order_by(DemandeAcces.cree_le.desc())
    return db.scalars(stmt).all()


def resolve_access_request(
    request: DemandeAcces | AccessRequest,
    *,
    decision: str,
    granted_role: str | None = None,
) -> DemandeAcces | AccessRequest:
    """Normalise une décision d'accès et met à jour le statut attendu sans dépendre d'une base de données."""
    normalized_decision = normalize_access_decision(decision)
    if hasattr(request, "requested_role"):
        request.requested_role = normalize_access_role(granted_role or request.requested_role)
        request.status = normalized_decision
        return request

    if hasattr(request, "role_demande"):
        request.role_demande = normalize_access_role(granted_role or request.role_demande)
        request.statut = normalized_decision
        return request

    raise TypeError("La demande d'accès ne correspond ni au modèle métier ni au dataclass local.")


def process_access_request(
    db: Session,
    *,
    request_id: int,
    decision: str,
    actor_id: int | None = None,
    granted_role: str | None = None,
) -> DemandeAcces:
    """Traite une demande d'accès : statut, notification et accord immédiat si acceptée."""
    request = db.get(DemandeAcces, request_id)
    if request is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Demande d'accès introuvable.")
    final_role = normalize_access_role(granted_role or request.role_demande)
    request.role_demande = final_role
    request.statut = normalize_access_decision(decision)

    if request.statut == "accepted":
        if request.sujet_type == "document":
            existing = db.scalar(
                select(DocumentPartage).where(
                    DocumentPartage.document_id == request.sujet_id,
                    DocumentPartage.user_id == request.user_id,
                )
            )
            if existing is None:
                db.add(
                    DocumentPartage(
                        document_id=request.sujet_id,
                        user_id=request.user_id,
                        role=final_role,
                        cree_par=actor_id,
                    )
                )
            else:
                existing.role = final_role
        elif request.sujet_type == "dossier":
            existing = db.get(DossierMembre, (request.sujet_id, request.user_id))
            if existing is None:
                db.add(DossierMembre(dossier_id=request.sujet_id, user_id=request.user_id, role=final_role))
            else:
                existing.role = final_role
        else:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Type de sujet invalide pour une demande d'accès.")

        create_notification(
            db,
            user_id=request.user_id,
            kind="access_accepted",
            subject_type=request.sujet_type,
            subject_id=request.sujet_id,
            message=f"Votre demande d'accès a été acceptée avec le rôle {final_role}.",
        )
    elif request.statut == "rejected":
        create_notification(
            db,
            user_id=request.user_id,
            kind="access_rejected",
            subject_type=request.sujet_type,
            subject_id=request.sujet_id,
            message=f"Votre demande d'accès a été refusée pour le rôle {final_role}.",
        )

    db.commit()
    db.refresh(request)
    return request


def create_comment(
    db: Session,
    *,
    subject_type: str,
    subject_id: int,
    author_id: int,
    content: str,
    parent_id: int | None = None,
) -> Commentaire:
    """Crée un commentaire local lié à un document ou un dossier."""
    if subject_type not in {"document", "dossier"}:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Type de sujet invalide.")
    stripped = (content or "").strip()
    if not stripped:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Un commentaire ne peut pas être vide.")
    comment = Commentaire(
        sujet_type=subject_type,
        sujet_id=subject_id,
        auteur_id=author_id,
        contenu=stripped,
        parent_id=parent_id,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment


def list_comments(db: Session, *, subject_type: str, subject_id: int) -> list[Commentaire]:
    return db.scalars(
        select(Commentaire).where(Commentaire.sujet_type == subject_type, Commentaire.sujet_id == subject_id)
        .order_by(Commentaire.cree_le.desc())
    ).all()


def create_notification(
    db: Session,
    *,
    user_id: int,
    kind: str,
    subject_type: str,
    subject_id: int,
    message: str,
) -> NotificationInterne:
    """Crée une notification locale interne."""
    if subject_type not in {"document", "dossier"}:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Type de sujet invalide.")
    notification = NotificationInterne(
        user_id=user_id,
        type_notification=kind,
        sujet_type=subject_type,
        sujet_id=subject_id,
        message=message,
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification


def list_notifications(db: Session, *, user_id: int) -> list[NotificationInterne]:
    return db.scalars(
        select(NotificationInterne)
        .where(NotificationInterne.user_id == user_id)
        .order_by(NotificationInterne.cree_le.desc())
    ).all()


def toggle_favorite(
    db: Session | None = None,
    *,
    user_id: int,
    entity_type: str | None = None,
    entity_id: int | None = None,
    subject_type: str | None = None,
    subject_id: int | None = None,
) -> Favorite | Favori | None:
    """Fait basculer un favori local : crée-le s'il manque, sinon le supprime."""
    resolved_type = entity_type or subject_type
    resolved_id = entity_id if entity_id is not None else subject_id
    if resolved_type is None or resolved_id is None:
        raise ValueError("Le favori doit préciser un type et un identifiant.")
    if db is None:
        return Favorite(user_id=user_id, entity_type=resolved_type, entity_id=resolved_id, created_at=datetime.now(UTC))
    if resolved_type not in {"document", "dossier"}:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Type de sujet invalide.")
    existing = db.scalar(
        select(Favori).where(Favori.user_id == user_id, Favori.sujet_type == resolved_type, Favori.sujet_id == resolved_id)
    )
    if existing is not None:
        db.delete(existing)
        db.commit()
        return None
    fav = Favori(user_id=user_id, sujet_type=resolved_type, sujet_id=resolved_id)
    db.add(fav)
    db.commit()
    db.refresh(fav)
    return fav


__all__ = [
    "ACCESS_ROLES",
    "AccessRequest",
    "Comment",
    "Favorite",
    "Notification",
    "ShareLink",
    "add_comment",
    "add_notification",
    "build_share_link",
    "create_access_request",
    "create_comment",
    "create_document_link_share",
    "create_document_share",
    "create_notification",
    "generate_share_token",
    "hash_share_token",
    "is_share_active",
    "list_access_requests",
    "list_comments",
    "list_document_shares",
    "list_notifications",
    "make_share_payload",
    "normalize_access_decision",
    "normalize_access_role",
    "process_access_request",
    "request_access",
    "resolve_access_request",
    "toggle_favorite",
]
