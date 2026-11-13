"""Logique des fichiers (documents) rangés dans des dossiers, et de leurs versions :
- création d'un fichier : version 1, hash du fichier, dédoublonnage dans le dossier, mise en file d'ingestion ;
- nouvelle version : AJOUT d'une version numérotée et datée, jamais de suppression de l'ancienne ;
- modification : titre et cases « tableaux / images » (la réindexation de la version courante suit un changement de case) ;
- suppression d'une version ou du fichier entier (réservée au gestionnaire de contenu).

Droits : rôle de l'utilisateur dans le DOSSIER du fichier (core/permissions.py) ; dossier inconnu ou hors des accès :
404 ; rôle insuffisant : 403 ; dossier archivé : 409.
"""

import hashlib
import re
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from app.config import get_settings
from app.core.permissions import (
    AJOUTER_FICHIER, AJOUTER_VERSION, MODIFIER, SUPPRIMER, VOIR, Principal, exiger_acces, roles_par_dossier,
)
from app.db.vecteur import Document, DocumentVersion
from app.schemas.document import DocumentOut, VersionOut
from app.services.audit import log_action
from app.services.documents import apercu
from app.services.ingestion.parser import ALLOWED_EXT, apply_flags, forced_flags
from app.workers import ingestion_worker

_CHUNK = 1024 * 1024


# --- Sérialisation ---------------------------------------------------------------------------------------------------

def _version_out(v: DocumentVersion, courante: int | None) -> VersionOut:
    return VersionOut(
        numero=v.numero, nom_fichier=v.nom_fichier, type_mime=v.type_mime, taille_octets=v.taille_octets,
        nb_pages=v.nb_pages, ocr_utilise=v.ocr_utilise, statut=v.statut, message_erreur=v.message_erreur,
        cree_par_nom=v.auteur.nom_utilisateur if v.auteur else None, cree_le=v.cree_le,
        est_courante=(v.numero == courante), apercu=apercu.apercu_mode(v.nom_fichier),
    )


def _courante(doc: Document) -> int | None:
    """Numéro de la version prête la plus récente (celle qui fait foi)."""
    ready = [v.numero for v in doc.versions if v.statut == "ready"]
    return max(ready) if ready else None


def to_out(doc: Document, role: str) -> DocumentOut:
    latest = doc.versions[-1]  # versions triées par numéro
    forced_t, forced_i = forced_flags(Path(latest.nom_fichier).suffix)
    return DocumentOut(
        id=doc.id, titre=doc.titre, dossier_id=doc.dossier_id, dossier_nom=doc.dossier.nom,
        has_tabular=doc.has_tabular, has_image=doc.has_image, tableaux_imposes=forced_t, images_imposees=forced_i,
        nb_versions=len(doc.versions), version=_version_out(latest, _courante(doc)), mon_role=role,
        cree_par_nom=doc.createur.nom_utilisateur if doc.createur else None,
        cree_le=doc.cree_le, modifie_le=doc.modifie_le,
    )


def _fresh(db: Session, principal: Principal, document_id: int, role: str) -> DocumentOut:
    """Relit le fichier après une écriture (la session garde sinon l'ancienne liste de versions)."""
    db.expire_all()
    return to_out(get_document(db, principal, document_id, VOIR)[0], role)


def versions_out(doc: Document) -> list[VersionOut]:
    courante = _courante(doc)
    return [_version_out(v, courante) for v in reversed(doc.versions)]  # la plus récente d'abord


def _query():
    return select(Document).options(
        joinedload(Document.dossier), joinedload(Document.createur),
        selectinload(Document.versions).joinedload(DocumentVersion.auteur),
    )


# --- Accès -----------------------------------------------------------------------------------------------------------

def get_document(db: Session, principal: Principal, document_id: int, action: str) -> tuple[Document, str]:
    """Le fichier et le rôle effectif, si l'action est permise dans son dossier (sinon 404 / 403 / 409)."""
    doc = db.scalars(_query().where(Document.id == document_id)).unique().one_or_none()
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Fichier introuvable.")
    _, role = exiger_acces(db, principal, doc.dossier_id, action)  # 404 si le dossier est hors des accès
    return doc, role


def get_version(db: Session, principal: Principal, document_id: int, numero: int, action: str) -> DocumentVersion:
    doc, _ = get_document(db, principal, document_id, action)
    for v in doc.versions:
        if v.numero == numero:
            return v
    raise HTTPException(status.HTTP_404_NOT_FOUND, "Version introuvable.")


def list_documents(db: Session, principal: Principal, dossier_id: int | None = None) -> list[DocumentOut]:
    roles = roles_par_dossier(db, principal)
    if dossier_id is not None:
        exiger_acces(db, principal, dossier_id, VOIR)  # 404 hors des accès
        roles = {dossier_id: roles[dossier_id]}
    if not roles:
        return []
    docs = db.scalars(
        _query().where(Document.dossier_id.in_(roles)).order_by(Document.cree_le.desc(), Document.id.desc())
    ).unique()
    return [to_out(d, roles[d.dossier_id]) for d in docs]


def list_versions(db: Session, principal: Principal, document_id: int) -> list[VersionOut]:
    doc, _ = get_document(db, principal, document_id, VOIR)
    return versions_out(doc)


# --- Dépôt de fichiers -----------------------------------------------------------------------------------------------

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
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Le fichier est vide.")
        if ext == ".pdf":
            with dest.open("rb") as f:
                if b"%PDF" not in f.read(1024):
                    raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Ce fichier n'est pas un PDF valide.")
    except Exception:
        dest.unlink(missing_ok=True)
        raise
    return dest, digest.hexdigest(), size, name


def _remove_file(path: str | Path) -> None:
    try:
        Path(path).unlink(missing_ok=True)
    except OSError:
        pass  # un fichier orphelin ne doit pas faire échouer l'opération


def _remove_version_files(version: DocumentVersion) -> None:
    _remove_file(version.chemin_stockage)
    apercu.remove_cache(version.id)


def create_document(
    db: Session, principal: Principal, upload: UploadFile, titre: str, dossier_id: int,
    contient_tableaux: bool, contient_images: bool, ip: str | None,
) -> DocumentOut:
    dossier, role = exiger_acces(db, principal, dossier_id, AJOUTER_FICHIER)
    path, sha, size, name = _save_upload(upload)
    duplicate = db.scalar(
        select(Document.titre).join(DocumentVersion, DocumentVersion.document_id == Document.id)
        .where(Document.dossier_id == dossier.id, DocumentVersion.hash_sha256 == sha).limit(1)
    )
    if duplicate is not None:
        _remove_file(path)
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Ce fichier existe déjà dans ce dossier (« {duplicate} »). Pour le faire évoluer, ajouter une nouvelle version.",
        )
    tableaux, images = apply_flags(path.suffix, contient_tableaux, contient_images)
    doc = Document(
        dossier_id=dossier.id, titre=(titre.strip() or Path(name).stem)[:250],
        has_tabular=tableaux, has_image=images, cree_par=principal.user.id, modifie_par=principal.user.id,
    )
    version = DocumentVersion(
        numero=1, nom_fichier=name, type_mime=upload.content_type, taille_octets=size, hash_sha256=sha,
        chemin_stockage=str(path), statut="pending", cree_par=principal.user.id,
    )
    doc.versions.append(version)
    db.add(doc)
    try:
        db.flush()
        log_action(db, principal.user.id, "document.creer", "document", doc.id,
                   {"titre": doc.titre, "dossier_id": dossier.id, "version": 1, "taille": size}, ip)
        db.commit()
    except IntegrityError:
        db.rollback()
        _remove_file(path)
        raise HTTPException(status.HTTP_409_CONFLICT, "Création impossible : doublon.") from None
    ingestion_worker.enqueue(version.id)
    return _fresh(db, principal, doc.id, role)


def add_version(
    db: Session, principal: Principal, document_id: int, upload: UploadFile,
    contient_tableaux: bool | None, contient_images: bool | None, ip: str | None,
) -> DocumentOut:
    """Ajoute une version : l'ancienne reste, indexée et téléchargeable."""
    doc, role = get_document(db, principal, document_id, AJOUTER_VERSION)
    path, sha, size, name = _save_upload(upload)
    latest = doc.versions[-1]
    if sha == latest.hash_sha256:
        _remove_file(path)
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"Ce fichier est identique à la version {latest.numero} : rien à ajouter."
        )
    tableaux, images = apply_flags(
        path.suffix,
        doc.has_tabular if contient_tableaux is None else contient_tableaux,
        doc.has_image if contient_images is None else contient_images,
    )
    changes = {"version": latest.numero + 1, "fichier": name}
    version = DocumentVersion(
        document_id=doc.id, numero=latest.numero + 1, nom_fichier=name, type_mime=upload.content_type,
        taille_octets=size, hash_sha256=sha, chemin_stockage=str(path), statut="pending", cree_par=principal.user.id,
    )
    doc.has_tabular, doc.has_image = tableaux, images
    doc.modifie_par = principal.user.id
    db.add(version)
    try:
        db.flush()
        log_action(db, principal.user.id, "document.version_ajouter", "document", doc.id, changes, ip)
        db.commit()
    except IntegrityError:  # deux dépôts simultanés ont pris le même numéro
        db.rollback()
        _remove_file(path)
        raise HTTPException(status.HTTP_409_CONFLICT, "Une autre version vient d'être ajoutée : recommencer.") from None
    ingestion_worker.enqueue(version.id)
    return _fresh(db, principal, document_id, role)


# --- Modification et suppression --------------------------------------------------------------------------------------

def update_document(
    db: Session, principal: Principal, document_id: int, titre: str | None,
    contient_tableaux: bool | None, contient_images: bool | None, ip: str | None,
) -> DocumentOut:
    doc, role = get_document(db, principal, document_id, MODIFIER)
    latest = doc.versions[-1]
    changes: dict = {}
    if titre is not None and titre.strip() and titre.strip() != doc.titre:
        doc.titre = titre.strip()[:250]
        changes["titre"] = doc.titre

    tableaux, images = apply_flags(
        Path(latest.nom_fichier).suffix,
        doc.has_tabular if contient_tableaux is None else contient_tableaux,
        doc.has_image if contient_images is None else contient_images,
    )
    reindex = False
    if tableaux != doc.has_tabular:
        doc.has_tabular = changes["has_tabular"] = tableaux
        reindex = True
    if images != doc.has_image:
        doc.has_image = changes["has_image"] = images
        reindex = True
    # une case change la façon de lire le fichier : la version la plus récente est relue (les autres gardent leur index)
    if reindex and latest.statut in ("ready", "error"):
        latest.statut, latest.message_erreur = "pending", None
        changes["reindexation"] = latest.numero
    else:
        reindex = False

    if changes:
        doc.modifie_par = principal.user.id
        log_action(db, principal.user.id, "document.modifier", "document", doc.id, changes, ip)
        db.commit()
    if reindex:
        ingestion_worker.enqueue(latest.id)
    return _fresh(db, principal, document_id, role)


def delete_version(db: Session, principal: Principal, document_id: int, numero: int, ip: str | None) -> None:
    """Supprime une version (et ses chunks). Si c'était la plus récente, la précédente redevient la version courante."""
    doc, _ = get_document(db, principal, document_id, SUPPRIMER)
    target = next((v for v in doc.versions if v.numero == numero), None)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Version introuvable.")
    if len(doc.versions) == 1:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "C'est la seule version de ce fichier : supprimer le fichier entier."
        )
    if target.statut == "processing":
        raise HTTPException(status.HTTP_409_CONFLICT, "Indexation en cours : attendre sa fin avant de supprimer cette version.")
    version_id, path = target.id, target.chemin_stockage
    log_action(db, principal.user.id, "document.version_supprimer", "document", doc.id,
               {"version": numero, "fichier": target.nom_fichier}, ip)
    doc.modifie_par = principal.user.id
    db.delete(target)  # les chunks partent en cascade (ON DELETE CASCADE)
    db.commit()
    _remove_file(path)
    apercu.remove_cache(version_id)


def delete_document(db: Session, principal: Principal, document_id: int, ip: str | None) -> None:
    doc, _ = get_document(db, principal, document_id, SUPPRIMER)
    versions = [(v.id, v.chemin_stockage) for v in doc.versions]
    log_action(db, principal.user.id, "document.supprimer", "document", doc.id,
               {"titre": doc.titre, "dossier_id": doc.dossier_id, "versions": len(versions)}, ip)
    db.delete(doc)  # versions et chunks partent en cascade
    db.commit()
    for version_id, path in versions:
        _remove_file(path)
        apercu.remove_cache(version_id)


def count_versions(db: Session, document_id: int) -> int:
    return db.scalar(select(func.count(DocumentVersion.id)).where(DocumentVersion.document_id == document_id)) or 0
