"""Logique du CRUD documents :
- création : hash du fichier, dédoublonnage, mise en file d'ingestion ;
- modification : titre, service (admin) ou remplacement du fichier (suppression des chunks puis réindexation) ;
- suppression : document, chunks (cascade) et fichier stocké.

Droits : l'ADMIN agit sur tous les services ; l'UTILISATEUR uniquement sur le service de son agent.
Aucune fonction ici ne renvoie le contenu d'un document.
"""

import hashlib
import re
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.core.permissions import Principal
from app.db.metier import Service
from app.db.vecteur import Chunk, Document
from app.schemas.document import DocumentOut
from app.services.audit import log_action
from app.services.ingestion.parser import ALLOWED_EXT
from app.workers import ingestion_worker

_CHUNK = 1024 * 1024


def to_out(doc: Document) -> DocumentOut:
    return DocumentOut(
        id=doc.id, titre=doc.titre, nom_fichier=doc.nom_fichier, type_mime=doc.type_mime,
        taille_octets=doc.taille_octets, nb_pages=doc.nb_pages, ocr_utilise=doc.ocr_utilise,
        has_tabular=doc.has_tabular, statut=doc.statut, message_erreur=doc.message_erreur,
        service_id=doc.service_id, service_nom=doc.service.nom,
        cree_par_nom=doc.createur.nom_utilisateur if doc.createur else None,
        cree_le=doc.cree_le, modifie_le=doc.modifie_le,
    )


def _query():
    return select(Document).options(joinedload(Document.service), joinedload(Document.createur))


def _get_accessible(db: Session, principal: Principal, document_id: int) -> Document:
    doc = db.scalars(_query().where(Document.id == document_id)).one_or_none()
    # 404 (et non 403) hors de son service : on ne révèle pas l'existence d'un document d'un autre service
    if doc is None or not principal.can_access_service(doc.service_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document introuvable.")
    return doc


def _clean_name(name: str | None) -> str:
    base = Path((name or "document").replace("\\", "/")).name
    return re.sub(r"[\x00-\x1f]", "", base)[:255] or "document"


def _save_upload(upload: UploadFile) -> tuple[Path, str, int, str]:
    """Écrit le fichier sous un nom généré (jamais le nom fourni par le client) en limitant sa taille.
    Renvoie (chemin, sha256, taille, nom d'affichage)."""
    settings = get_settings()
    name = _clean_name(upload.filename)
    ext = Path(name).suffix.lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            f"Type de fichier non accepté ({ext or 'sans extension'}). Acceptés : {', '.join(sorted(ALLOWED_EXT))}.",
        )
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    dest = settings.upload_dir / f"{uuid.uuid4().hex}{ext}"
    digest, size = hashlib.sha256(), 0
    try:
        with dest.open("wb") as out:
            while chunk := upload.file.read(_CHUNK):
                size += len(chunk)
                if size > settings.max_upload_bytes:
                    raise HTTPException(
                        status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, f"Fichier trop volumineux (max {settings.max_upload_mb} Mo)."
                    )
                digest.update(chunk)
                out.write(chunk)
        if size == 0:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Le fichier est vide.")
        if ext == ".pdf":
            with dest.open("rb") as f:
                if b"%PDF" not in f.read(1024):
                    raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Ce fichier n'est pas un PDF valide.")
    except Exception:
        dest.unlink(missing_ok=True)
        raise
    return dest, digest.hexdigest(), size, name


def _remove_file(path: str | Path) -> None:
    try:
        Path(path).unlink(missing_ok=True)
    except OSError:
        pass  # un fichier orphelin ne doit pas faire échouer l'opération


def _resolve_service(db: Session, principal: Principal, requested: int | None) -> int:
    """L'ADMIN choisit le service (par défaut le sien) ; l'UTILISATEUR est limité au sien."""
    if principal.is_admin:
        service_id = requested if requested is not None else principal.service_id
        if service_id is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Choisir le service du document.")
    else:
        if principal.service_id is None:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Votre compte n'est rattaché à aucun service.")
        if requested is not None and requested != principal.service_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Vous ne pouvez gérer que les documents de votre service.")
        service_id = principal.service_id
    service = db.get(Service, service_id)
    if service is None or not service.actif:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Service introuvable ou inactif.")
    return service_id


def list_documents(db: Session, principal: Principal, service_id: int | None = None) -> list[Document]:
    stmt = _query().order_by(Document.cree_le.desc())
    if principal.is_admin:
        if service_id is not None:
            stmt = stmt.where(Document.service_id == service_id)
    else:
        if principal.service_id is None:
            return []
        stmt = stmt.where(Document.service_id == principal.service_id)
    return list(db.scalars(stmt))


def create_document(
    db: Session, principal: Principal, upload: UploadFile, titre: str, service_id: int | None,
    contient_tableaux: bool, ip: str | None,
) -> Document:
    target_service = _resolve_service(db, principal, service_id)
    path, sha, size, name = _save_upload(upload)
    duplicate = db.scalar(
        select(Document.titre).where(Document.service_id == target_service, Document.hash_sha256 == sha)
    )
    if duplicate is not None:
        _remove_file(path)
        raise HTTPException(status.HTTP_409_CONFLICT, f"Ce fichier existe déjà dans ce service (« {duplicate} »).")
    doc = Document(
        service_id=target_service, titre=(titre.strip() or Path(name).stem)[:250], nom_fichier=name,
        type_mime=upload.content_type, taille_octets=size, hash_sha256=sha, chemin_stockage=str(path),
        has_tabular=contient_tableaux,  # indication de l'utilisateur, recalculée par l'ingestion
        statut="pending", cree_par=principal.user.id, modifie_par=principal.user.id,
    )
    db.add(doc)
    try:
        db.flush()
        log_action(db, principal.user.id, "document.creer", "document", doc.id,
                   {"titre": doc.titre, "service_id": target_service, "taille": size}, ip)
        db.commit()
    except IntegrityError:
        db.rollback()
        _remove_file(path)
        raise HTTPException(status.HTTP_409_CONFLICT, "Ce fichier existe déjà dans ce service.") from None
    ingestion_worker.enqueue(doc.id)
    return _get_accessible(db, principal, doc.id)


def update_document(
    db: Session, principal: Principal, document_id: int, titre: str | None, service_id: int | None,
    upload: UploadFile | None, contient_tableaux: bool | None, ip: str | None,
) -> Document:
    doc = _get_accessible(db, principal, document_id)
    if upload is not None and doc.statut == "processing":
        raise HTTPException(status.HTTP_409_CONFLICT, "Indexation en cours : attendre sa fin avant de remplacer le fichier.")
    changes: dict = {}

    if titre is not None and titre.strip() and titre.strip() != doc.titre:
        doc.titre = titre.strip()[:250]
        changes["titre"] = doc.titre
    if service_id is not None and service_id != doc.service_id:
        if not principal.is_admin:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Seul un administrateur peut changer le service d'un document.")
        doc.service_id = _resolve_service(db, principal, service_id)
        changes["service_id"] = doc.service_id

    old_path: str | None = None
    new_path: Path | None = None
    reindex = False
    if upload is not None:
        new_path, sha, size, name = _save_upload(upload)
        duplicate = db.scalar(
            select(Document.id).where(
                Document.service_id == doc.service_id, Document.hash_sha256 == sha, Document.id != doc.id
            )
        )
        if duplicate is not None:
            _remove_file(new_path)
            raise HTTPException(status.HTTP_409_CONFLICT, "Ce fichier existe déjà dans ce service.")
        old_path = doc.chemin_stockage
        doc.chemin_stockage, doc.hash_sha256, doc.taille_octets = str(new_path), sha, size
        doc.nom_fichier, doc.type_mime = name, upload.content_type
        doc.has_tabular = bool(contient_tableaux)
        doc.statut, doc.message_erreur, doc.nb_pages, doc.ocr_utilise = "pending", None, None, False
        changes["fichier"] = name
        db.execute(delete(Chunk).where(Chunk.document_id == doc.id))  # anciens passages retirés tout de suite
        reindex = True

    if changes:
        doc.modifie_par = principal.user.id
        log_action(db, principal.user.id, "document.modifier", "document", doc.id, changes, ip)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if new_path:
            _remove_file(new_path)
        raise HTTPException(status.HTTP_409_CONFLICT, "Modification impossible : doublon.") from None
    if old_path:
        _remove_file(old_path)
    if reindex:
        ingestion_worker.enqueue(doc.id)  # run_ingestion remplace les anciens chunks par les nouveaux
    return _get_accessible(db, principal, doc.id)


def delete_document(db: Session, principal: Principal, document_id: int, ip: str | None) -> None:
    doc = _get_accessible(db, principal, document_id)
    path, titre, service_id = doc.chemin_stockage, doc.titre, doc.service_id
    log_action(db, principal.user.id, "document.supprimer", "document", doc.id,
               {"titre": titre, "service_id": service_id}, ip)
    db.delete(doc)  # les chunks partent en cascade (ON DELETE CASCADE)
    db.commit()
    _remove_file(path)
