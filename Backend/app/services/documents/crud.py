"""Logique des fichiers (documents) déposés DIRECTEMENT dans une division, et de leurs versions :
- création d'un fichier : version 1, hash, dédoublonnage dans la division, CLASSEMENT PAR RÔLE, mise en file d'ingestion ;
- nouvelle version : AJOUT d'une version numérotée et datée, jamais de suppression de l'ancienne ;
- modification : titre et cases « tableaux / images » (la réindexation de la version courante suit un changement de case) ;
- rôles du fichier : réservés au gérant de la division ; suppression et purge selon la matrice de core/acces.py.

Droits : rôle effectif sur le fichier (core/acces.py) ; hors périmètre : 404 ; rôle insuffisant : 403 ;
division désactivée : 409. Toute modification est tracée dans l'historique (hash chaîné).
"""

import hashlib
import re
from datetime import UTC, datetime
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import delete, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from app.config import get_settings
from app.core import acces
from app.core.acces import (
    AJOUTER_VERSION, CLASSER, MATRICE, MODIFIER, PURGER, SUPPRIMER, VOIR,
    condition_acces_fichiers, est_chef_nominal, exiger_acces_document, exiger_depot_division,
)
from app.core.permissions import NIVEAU_DIVISION, NIVEAU_SERVICE, Principal
from app.db.metier import Division, DocumentRole, DocumentTag, RoleDivision
from app.db.vecteur import Document, DocumentVersion
from app.schemas.document import DocumentOut, RoleBrief, RoleFiltreOut, VersionOut
from app.services.audit import log_action
from app.services.documents import apercu, reindexation
from app.services.historique import ecrire_historique
from app.services.ingestion.parser import ALLOWED_EXT, apply_flags, forced_flags
from app.services.notifications import destinataires_gestion, notifier
from app.services import stockage
from app.services.roles_division import valider_roles
from app.workers import ingestion_worker

_CHUNK = 1024 * 1024


# --- Sérialisation ---------------------------------------------------------------------------------------------------

def _version_out(v: DocumentVersion, courante: int | None) -> VersionOut:
    return VersionOut(
        numero=v.numero, nom_fichier=v.nom_fichier, type_mime=v.type_mime, taille_octets=v.taille_octets,
        nb_pages=v.nb_pages, ocr_utilise=v.ocr_utilise, statut=v.statut, message_erreur=v.message_erreur,
        cree_par_nom=v.auteur.nom_utilisateur if v.auteur else None, cree_le=v.cree_le,
        est_courante=(v.numero == courante), apercu=apercu.apercu_mode(v.nom_fichier),
        tableaux_indexes=v.tableaux_indexes, images_indexes=v.images_indexes,
    )


def _courante(doc: Document) -> int | None:
    """Numéro de la version prête la plus récente (celle qui fait foi)."""
    ready = [v.numero for v in doc.versions if v.statut == "ready"]
    return max(ready) if ready else None


def roles_par_document(db: Session, document_ids: list[int]) -> dict[int, list[RoleBrief]]:
    sortie: dict[int, list[RoleBrief]] = {}
    if not document_ids:
        return sortie
    rows = db.execute(
        select(DocumentRole.document_id, RoleDivision.id, RoleDivision.code, RoleDivision.libelle)
        .join(RoleDivision, RoleDivision.id == DocumentRole.role_division_id)
        .where(DocumentRole.document_id.in_(document_ids))
        .order_by(RoleDivision.libelle)
    )
    for did, rid, code, libelle in rows:
        sortie.setdefault(did, []).append(RoleBrief(id=rid, code=code, libelle=libelle))
    return sortie


def to_out(doc: Document, role: str, roles: list[RoleBrief] | None = None) -> DocumentOut:
    latest = doc.versions[-1]  # versions triées par numéro
    forced_t, forced_i = forced_flags(Path(latest.nom_fichier).suffix)
    roles = roles or []
    return DocumentOut(
        id=doc.id, titre=doc.titre, division_id=doc.division_id, division_nom=doc.division.nom,
        has_tabular=doc.has_tabular, has_image=doc.has_image, tableaux_imposes=forced_t, images_imposees=forced_i,
        nb_versions=len(doc.versions), version=_version_out(latest, _courante(doc)), mon_role=role,
        droits=sorted(MATRICE[role]), roles=roles, a_classer=not roles,
        cree_par_nom=doc.createur.nom_utilisateur if doc.createur else None,
        cree_le=doc.cree_le, modifie_le=doc.modifie_le,
        categorie_id=doc.categorie_id, categorie_nom=doc.categorie.nom if doc.categorie else None,
        type_document_id=doc.type_document_id, type_nom=doc.type_document.nom if doc.type_document else None,
        confidentialite=doc.confidentialite or "INTERNE",
        tags=sorted(lien.tag.nom for lien in doc.tag_liens), classement_source=doc.classement_source or "aucun",
        corbeille_le=doc.corbeille_le,
    )


def _fresh(db: Session, principal: Principal, document_id: int) -> DocumentOut:
    """Relit le fichier après une écriture (la session garde sinon l'ancienne liste de versions)."""
    db.expire_all()
    doc, role = get_document(db, principal, document_id, VOIR)
    return to_out(doc, role, roles_par_document(db, [doc.id]).get(doc.id))


def versions_out(doc: Document) -> list[VersionOut]:
    courante = _courante(doc)
    return [_version_out(v, courante) for v in reversed(doc.versions)]  # la plus récente d'abord


def _query():
    return select(Document).options(
        joinedload(Document.division), joinedload(Document.createur),
        joinedload(Document.categorie), joinedload(Document.type_document),
        selectinload(Document.tag_liens).joinedload(DocumentTag.tag),
        selectinload(Document.versions).joinedload(DocumentVersion.auteur),
    )


# --- Accès -----------------------------------------------------------------------------------------------------------

def get_document(db: Session, principal: Principal, document_id: int, action: str) -> tuple[Document, str]:
    """Le fichier et le rôle effectif ; 404 hors périmètre, 403 sans rôle."""
    doc = db.scalars(_query().where(Document.id == document_id)).unique().one_or_none()
    return exiger_acces_document(db, principal, doc, action)


def get_version(db: Session, principal: Principal, document_id: int, numero: int, action: str) -> DocumentVersion:
    doc, _ = get_document(db, principal, document_id, action)
    for v in doc.versions:
        if v.numero == numero:
            return v
    raise HTTPException(status.HTTP_404_NOT_FOUND, "Version introuvable.")


def _document_latest_version(doc: Document) -> DocumentVersion | None:
    return doc.versions[-1] if doc.versions else None


def _document_extension(doc: Document) -> str | None:
    version = _document_latest_version(doc)
    if version is None or not version.nom_fichier:
        return None
    return Path(version.nom_fichier).suffix.lower().lstrip('.')


def apply_document_filters(
    docs: list[Document],
    q: str | None = None,
    categorie_id: int | None = None,
    type_id: int | None = None,
    tag_ids: list[int] | None = None,
    confidentialite: str | None = None,
    statut: str | None = None,
    extension: str | None = None,
    du=None,
    au=None,
    auteur_id: int | None = None,
    tri: str = "date_desc",
    page: int | None = None,
    taille: int | None = None,
):
    """Applique les filtres métier sur une liste de documents et retourne une page paginée."""
    filtered = list(docs)

    if q:
        needle = q.strip().lower()
        if needle:
            filtered = [
                d for d in filtered
                if needle in (d.titre or "").lower()
                or any(needle in (v.nom_fichier or "").lower() for v in d.versions)
            ]

    if categorie_id is not None:
        filtered = [d for d in filtered if getattr(d, "categorie_id", None) == categorie_id]
    if type_id is not None:
        filtered = [d for d in filtered if getattr(d, "type_document_id", None) == type_id]
    if confidentialite:
        filtered = [d for d in filtered if getattr(d, "confidentialite", None) == confidentialite.upper()]
    if tag_ids:
        # tous les tags demandés doivent être présents sur le fichier
        wanted = set(tag_ids)
        filtered = [d for d in filtered if wanted <= {lien.tag_id for lien in getattr(d, "tag_liens", [])}]

    if extension:
        ext = extension.strip().lower().lstrip('.')
        filtered = [d for d in filtered if _document_extension(d) == ext]

    if statut:
        filtered = [d for d in filtered if (_document_latest_version(d) is not None and _document_latest_version(d).statut == statut)]

    if du is not None:
        filtered = [d for d in filtered if d.cree_le >= du]
    if au is not None:
        filtered = [d for d in filtered if d.cree_le <= au]
    if auteur_id is not None:
        filtered = [d for d in filtered if d.cree_par == auteur_id]

    if tri in {"titre_asc", "titre_desc"}:
        filtered.sort(key=lambda d: (d.titre or "").lower(), reverse=(tri == "titre_desc"))
    else:
        filtered.sort(key=lambda d: (d.cree_le, d.id), reverse=True)

    total = len(filtered)
    page = max(page or 1, 1)
    taille = max(taille or total or 20, 1)
    start = (page - 1) * taille
    end = start + taille
    return {
        "items": filtered[start:end],
        "total": total,
        "page": page,
        "taille": taille,
    }


def _role_pour_liste(db: Session, principal: Principal, doc: Document, cache: dict[int, str]) -> str:
    """Rôle effectif d'un fichier déjà retenu par condition_acces_fichiers (aucune requête par fichier).
    La condition ne retient que les chefs et les membres de la division ; ce repli est défensif."""
    if est_chef_nominal(db, principal, doc.division_id):
        return acces.GERANT
    if acces.est_membre(principal, doc.division_id):
        return acces.AUTEUR if doc.cree_par == principal.user.id else acces.LECTEUR
    if doc.division_id not in cache:
        division = db.get(Division, doc.division_id)
        cache[doc.division_id] = acces.GERANT if acces.peut_gerer_division(db, principal, division) else acces.LECTEUR
    return cache[doc.division_id]


def list_documents(
    db: Session,
    principal: Principal,
    q: str | None = None,
    categorie_id: int | None = None,
    type_id: int | None = None,
    tag_ids: list[int] | None = None,
    confidentialite: str | None = None,
    statut: str | None = None,
    extension: str | None = None,
    du=None,
    au=None,
    auteur_id: int | None = None,
    tri: str = "date_desc",
    page: int | None = None,
    taille: int | None = None,
    corbeille: bool = False,
    a_classer: bool = False,
    role_id: int | None = None,
    division_id: int | None = None,
) -> list[DocumentOut] | dict:
    """Fichiers que le compte peut LIRE (condition SQL unique, la même que pour la recherche et le chat),
    à plat sur toutes ses divisions ; filtres facultatifs par rôle (classe) et par division."""
    doc_filter = [condition_acces_fichiers(db, principal)]
    doc_filter.append(Document.corbeille_le.is_not(None) if corbeille else Document.corbeille_le.is_(None))
    if a_classer:
        doc_filter.append(~select(DocumentRole.document_id).where(DocumentRole.document_id == Document.id).exists())
    if role_id is not None:
        doc_filter.append(select(DocumentRole.document_id).where(DocumentRole.document_id == Document.id, DocumentRole.role_division_id == role_id).exists())
    if division_id is not None:
        doc_filter.append(Document.division_id == division_id)

    ordered_docs = list(db.scalars(_query().where(*doc_filter).order_by(Document.cree_le.desc(), Document.id.desc())).unique().all())
    filtered = apply_document_filters(
        ordered_docs, q=q, categorie_id=categorie_id, type_id=type_id, tag_ids=tag_ids, confidentialite=confidentialite,
        statut=statut, extension=extension, du=du, au=au, auteur_id=auteur_id, tri=tri, page=page, taille=taille,
    )
    roles_docs = roles_par_document(db, [d.id for d in filtered["items"]])
    cache: dict[int, str] = {}
    items = [to_out(d, _role_pour_liste(db, principal, d, cache), roles_docs.get(d.id)) for d in filtered["items"]]
    if page is not None or taille is not None:
        return {"items": items, "total": filtered["total"], "page": filtered["page"], "taille": filtered["taille"]}
    return items


def list_versions(db: Session, principal: Principal, document_id: int) -> list[VersionOut]:
    doc, _ = get_document(db, principal, document_id, VOIR)
    return versions_out(doc)


def filtres_liste(db: Session, principal: Principal) -> dict:
    """Options des filtres de la liste des fichiers, selon le périmètre du compte :
    - roles : les rôles (« classes ») filtrables — les siens (agent), ceux de sa division (chef de division),
      ceux des divisions de son service (chef de service) ;
    - divisions : ses divisions (une seule pour un agent ou un chef de division, plusieurs pour un chef de service) ;
    - depot_divisions : où il peut déposer."""
    divisions = condition_divisions(db, principal)
    ids = [d.id for d in divisions]
    if principal.role_ids:
        rows = db.execute(
            select(RoleDivision.id, RoleDivision.code, RoleDivision.libelle, RoleDivision.division_id)
            .where(RoleDivision.id.in_(principal.role_ids)).order_by(RoleDivision.libelle)
        ).all()
    elif principal.niveau in (NIVEAU_DIVISION, NIVEAU_SERVICE):
        rows = db.execute(
            select(RoleDivision.id, RoleDivision.code, RoleDivision.libelle, RoleDivision.division_id)
            .where(RoleDivision.division_id.in_(ids or [-1]), RoleDivision.actif.is_(True)).order_by(RoleDivision.libelle)
        ).all()
    else:
        rows = []
    noms = {d.id: d.nom for d in divisions}
    return {
        "roles": [RoleFiltreOut(id=i, code=c, libelle=l, division_id=did, division_nom=noms.get(did)) for i, c, l, did in rows],
        "divisions": [{"id": d.id, "nom": d.nom} for d in divisions],
        "depot_divisions": [d.id for d in divisions if d.actif],
    }


def condition_divisions(db: Session, principal: Principal) -> list[Division]:
    """Divisions visibles dans la liste des fichiers : celle du compte (agent, chef de division),
    celles de son service (chef de service)."""
    if principal.niveau == NIVEAU_SERVICE and principal.service_id is not None:
        return list(db.scalars(select(Division).where(Division.service_id == principal.service_id).order_by(Division.nom)))
    if principal.division_id is not None:
        division = db.get(Division, principal.division_id)
        return [division] if division else []
    return []


# --- Dépôt de fichiers -----------------------------------------------------------------------------------------------

def _clean_name(name: str | None) -> str:
    base = Path((name or "document").replace("\\", "/")).name
    return re.sub(r"[\x00-\x1f]", "", base)[:255] or "document"


def _save_upload(upload: UploadFile) -> tuple[Path, str, int, str]:
    """Écrit le fichier sous un nom généré (jamais le nom fourni par le client) en limitant sa taille.
    Renvoie (chemin, sha256, taille, nom d'affichage). Le fichier vit à plat dans upload_dir —
    un seul emplacement géré par l'application (voir services/stockage.py)."""
    settings = get_settings()
    name = _clean_name(upload.filename)
    ext = Path(name).suffix.lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            f"Type de fichier non accepté ({ext or 'sans extension'}). Acceptés : {', '.join(sorted(ALLOWED_EXT))}.",
        )
    dest = stockage.chemin(ext)
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


def _roles_au_depot(
    db: Session, principal: Principal, division: Division, role_ids: list[int] | None, explicite: bool
) -> list[RoleDivision]:
    """Classement par rôle au dépôt.
    Agent : tous ses rôles par défaut ; il peut en retirer, jamais en ajouter un qu'il n'a pas.
    Chef de division ou de service : il choisit dans le dictionnaire de la division ; sans choix, le fichier est
    « à classer » (accès refusé par défaut)."""
    if est_chef_nominal(db, principal, division.id):
        return valider_roles(db, division.id, role_ids or [])
    demandes = list(principal.role_ids) if role_ids is None and not explicite else (role_ids or [])
    en_trop = set(demandes) - set(principal.role_ids)
    if en_trop:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Vous ne pouvez classer un fichier qu'avec vos propres rôles.")
    return valider_roles(db, division.id, demandes, deja_detenus=set(principal.role_ids))


def create_document(
    db: Session, principal: Principal, upload: UploadFile, titre: str, division_id: int,
    contient_tableaux: bool, contient_images: bool, ip: str | None,
    role_ids: list[int] | None = None, roles_explicites: bool = False,
) -> DocumentOut:
    division = exiger_depot_division(db, principal, division_id)  # membres et chefs de la division
    roles = _roles_au_depot(db, principal, division, role_ids, roles_explicites)
    path, sha, size, name = _save_upload(upload)  # à plat dans upload_dir (services/stockage.py)
    # Deux dépôts CONCURRENTS du même contenu (double-clic) : le test puis l'insertion sont sérialisés
    # par division et contenu, sinon les deux transactions passent le test avant que la première ne
    # commette et le fichier serait déposé en double. Verrou de transaction : libéré au commit/rollback.
    db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:cle))"), {"cle": f"document.{division.id}.{sha}"})
    duplicate = db.scalar(
        select(Document.titre).join(DocumentVersion, DocumentVersion.document_id == Document.id)
        .where(Document.division_id == division.id, DocumentVersion.hash_sha256 == sha).limit(1)
    )
    if duplicate is not None:
        _remove_file(path)
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Ce fichier existe déjà dans la division « {division.nom} » (« {duplicate} »). Pour le faire évoluer, ajouter une nouvelle version.",
        )
    tableaux, images = apply_flags(path.suffix, contient_tableaux, contient_images)
    doc = Document(
        division_id=division.id, cree_par_service_id=division.service_id,
        titre=(titre.strip() or Path(name).stem)[:250],
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
        for r in roles:
            db.add(DocumentRole(document_id=doc.id, role_division_id=r.id, division_id=division.id))
        db.flush()
        log_action(db, principal.user.id, "document.creer", "document", doc.id,
                   {"titre": doc.titre, "division_id": division.id, "version": 1, "taille": size}, ip)
        ecrire_historique(
            db, acteur=principal.user, cible_type="document", cible_id=doc.id, action="fichier_depose",
            apres={"titre": doc.titre, "fichier": name, "roles": [r.libelle for r in roles]},
            service_id=division.service_id, division_id=division.id,
        )
        if not roles:
            notifier(
                db, destinataires_gestion(db, division), "fichier_a_classer",
                f"Un fichier est à classer dans la division « {division.nom} » : « {doc.titre} ».",
                reference_type="document", reference_id=doc.id, sauf_user_id=principal.user.id,
            )
        db.commit()
    except IntegrityError as e:
        db.rollback()
        _remove_file(path)
        # Un doublon (SQLSTATE 23505) ne doit plus masquer une autre cause : sur une base migrée avec
        # l'ancienne version de migration_suppression_dossiers.sql, la colonne document.dossier_id
        # NOT NULL restait en place et le dépôt échouait en violation NOT NULL — annoncé à tort « doublon ».
        if getattr(getattr(e, "orig", None), "sqlstate", None) == "23505":
            raise HTTPException(status.HTTP_409_CONFLICT, "Création impossible : doublon.") from None
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "Création impossible : la base a refusé l'écriture (schéma obsolète ? appliquer database/migration_suppression_dossiers.sql).",
        ) from e
    ingestion_worker.enqueue(version.id)
    return _fresh(db, principal, doc.id)


def definir_roles_document(
    db: Session, principal: Principal, document_id: int, role_ids: list[int], motif: str | None
) -> DocumentOut:
    """Remplace les rôles de classement d'un fichier : réservé au gérant de la division. Sans rôle = accès refusé par défaut."""
    doc, _ = get_document(db, principal, document_id, CLASSER)
    division = db.get(Division, doc.division_id)
    actuels = roles_par_document(db, [doc.id]).get(doc.id, [])
    cibles = valider_roles(db, doc.division_id, role_ids, deja_detenus={r.id for r in actuels})
    if {r.id for r in cibles} != {r.id for r in actuels}:
        db.execute(delete(DocumentRole).where(DocumentRole.document_id == doc.id))
        db.flush()
        for r in cibles:
            db.add(DocumentRole(document_id=doc.id, role_division_id=r.id, division_id=doc.division_id))
        doc.modifie_par = principal.user.id
        db.flush()
        ecrire_historique(
            db, acteur=principal.user, cible_type="document", cible_id=doc.id, action="roles_fichier_modifies",
            avant=[r.libelle for r in actuels], apres=[r.libelle for r in cibles], motif=motif,
            service_id=division.service_id, division_id=division.id,
        )
        db.commit()
    return _fresh(db, principal, document_id)


def historique_document(db: Session, principal: Principal, document_id: int):
    from app.services.historique import historique_cible

    doc, _ = get_document(db, principal, document_id, VOIR)
    return historique_cible(db, "document", doc.id)


def add_version(
    db: Session, principal: Principal, document_id: int, upload: UploadFile,
    contient_tableaux: bool | None, contient_images: bool | None, ip: str | None,
) -> DocumentOut:
    """Ajoute une version : l'ancienne reste, indexée et téléchargeable."""
    doc, role = get_document(db, principal, document_id, AJOUTER_VERSION)
    path, sha, size, name = _save_upload(upload)  # à plat dans upload_dir (services/stockage.py)
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
        division = db.get(Division, doc.division_id)
        ecrire_historique(
            db, acteur=principal.user, cible_type="document", cible_id=doc.id, action="version_ajoutee", apres=changes,
            service_id=division.service_id, division_id=division.id,
        )
        db.commit()
    except IntegrityError:  # deux dépôts simultanés ont pris le même numéro
        db.rollback()
        _remove_file(path)
        raise HTTPException(status.HTTP_409_CONFLICT, "Une autre version vient d'être ajoutée : recommencer.") from None
    ingestion_worker.enqueue(version.id)
    return _fresh(db, principal, document_id)


# --- Modification et suppression --------------------------------------------------------------------------------------

def _trace(db: Session, principal: Principal, doc: Document, action: str, avant=None, apres=None) -> None:
    division = db.get(Division, doc.division_id)
    ecrire_historique(
        db, acteur=principal.user, cible_type="document", cible_id=doc.id, action=action, avant=avant, apres=apres,
        service_id=division.service_id, division_id=division.id,
    )


def update_document(
    db: Session, principal: Principal, document_id: int, titre: str | None,
    contient_tableaux: bool | None, contient_images: bool | None, ip: str | None,
) -> DocumentOut:
    doc, role = get_document(db, principal, document_id, MODIFIER)
    latest = doc.versions[-1]
    changes: dict = {}
    avant: dict = {}
    if titre is not None and titre.strip() and titre.strip() != doc.titre:
        avant["titre"] = doc.titre
        doc.titre = titre.strip()[:250]
        changes["titre"] = doc.titre

    tableaux, images = apply_flags(
        Path(latest.nom_fichier).suffix,
        doc.has_tabular if contient_tableaux is None else contient_tableaux,
        doc.has_image if contient_images is None else contient_images,
    )
    reindex = False
    if tableaux != doc.has_tabular:
        avant["has_tabular"] = doc.has_tabular
        doc.has_tabular = changes["has_tabular"] = tableaux
        reindex = True
    if images != doc.has_image:
        avant["has_image"] = doc.has_image
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
        _trace(db, principal, doc, "fichier_modifie", avant=avant, apres=changes)
        db.commit()
    if reindex:
        ingestion_worker.enqueue(latest.id)
    return _fresh(db, principal, document_id)


def reindexer_version(
    db: Session, principal: Principal, document_id: int, numero: int,
    contient_tableaux: bool | None, contient_images: bool | None, ip: str | None,
) -> DocumentOut:
    """Relit le fichier DÉJÀ stocké d'une version, sans créer de nouvelle version (règles : reindexation.py).

    Sert quand l'indexation a échoué, ou quand on avait oublié de signaler des tableaux / des images.
    """
    doc, _ = get_document(db, principal, document_id, MODIFIER)
    version = next((v for v in doc.versions if v.numero == numero), None)
    if version is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Version introuvable.")

    tableaux, images = apply_flags(
        Path(version.nom_fichier).suffix,
        doc.has_tabular if contient_tableaux is None else contient_tableaux,
        doc.has_image if contient_images is None else contient_images,
    )
    # inconnu (version indexée avant la migration) : on se rabat sur les cases actuelles du fichier
    deja = reindexation.Parametres(
        doc.has_tabular if version.tableaux_indexes is None else version.tableaux_indexes,
        doc.has_image if version.images_indexes is None else version.images_indexes,
    )
    message = reindexation.refus(version.statut, deja, reindexation.Parametres(tableaux, images))
    if message:
        raise HTTPException(status.HTTP_409_CONFLICT, message)
    if stockage.trouver(version.chemin_stockage) is None:
        raise HTTPException(
            status.HTTP_410_GONE,
            "Le fichier de cette version est introuvable sur le serveur : le redéposer comme nouvelle version.",
        )

    avant: dict = {"version": numero, "statut": version.statut}
    changes: dict = {"version": numero, "fichier": version.nom_fichier}
    if tableaux != doc.has_tabular:
        avant["has_tabular"], changes["has_tabular"] = doc.has_tabular, tableaux
        doc.has_tabular = tableaux
    if images != doc.has_image:
        avant["has_image"], changes["has_image"] = doc.has_image, images
        doc.has_image = images
    version.statut, version.message_erreur = "pending", None
    doc.modifie_par = principal.user.id
    log_action(db, principal.user.id, "document.reindexer", "document", doc.id, changes, ip)
    _trace(db, principal, doc, "version_reindexee", avant=avant, apres=changes)
    db.commit()
    ingestion_worker.enqueue(version.id)
    return _fresh(db, principal, document_id)


def delete_version(db: Session, principal: Principal, document_id: int, numero: int, ip: str | None) -> None:
    """Supprime une version (et ses chunks). Si c'était la plus récente, la précédente redevient la version courante."""
    doc, _ = get_document(db, principal, document_id, PURGER)
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
    _trace(db, principal, doc, "version_supprimee", avant={"version": numero, "fichier": target.nom_fichier})
    doc.modifie_par = principal.user.id
    db.delete(target)  # les chunks partent en cascade (ON DELETE CASCADE)
    db.commit()
    _remove_file(path)
    apercu.remove_cache(version_id)


def delete_document(db: Session, principal: Principal, document_id: int, ip: str | None, force: bool = False) -> None:
    """Met un document dans la corbeille par défaut (gérant ou auteur) ; force=true : purge définitive (gérant seulement)."""
    doc, _ = get_document(db, principal, document_id, PURGER if force else SUPPRIMER)
    versions = [(v.id, v.chemin_stockage) for v in doc.versions]
    if force:
        log_action(db, principal.user.id, "document.supprimer_definitivement", "document", doc.id,
                   {"titre": doc.titre, "division_id": doc.division_id, "versions": len(versions)}, ip)
        _trace(db, principal, doc, "fichier_purge", avant={"titre": doc.titre, "versions": len(versions)})
        db.delete(doc)  # versions et chunks partent en cascade
        db.commit()
        for version_id, path in versions:
            _remove_file(path)
            apercu.remove_cache(version_id)
        return

    if doc.corbeille_le is None:
        doc.corbeille_le = datetime.now(UTC)
        doc.modifie_par = principal.user.id
        log_action(db, principal.user.id, "document.corbeille", "document", doc.id,
                   {"titre": doc.titre, "division_id": doc.division_id, "versions": len(versions)}, ip)
        _trace(db, principal, doc, "fichier_corbeille", avant=doc.titre)
        db.commit()


def restore_document(db: Session, principal: Principal, document_id: int, ip: str | None) -> None:
    """Restaure un document depuis la corbeille."""
    doc, _ = get_document(db, principal, document_id, SUPPRIMER)
    if doc.corbeille_le is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Le document n'est pas dans la corbeille.")
    doc.corbeille_le = None
    doc.modifie_par = principal.user.id
    log_action(db, principal.user.id, "document.restaurer", "document", doc.id,
               {"titre": doc.titre, "division_id": doc.division_id}, ip)
    _trace(db, principal, doc, "fichier_restaure", apres=doc.titre)
    db.commit()


def count_versions(db: Session, document_id: int) -> int:
    return db.scalar(select(func.count(DocumentVersion.id)).where(DocumentVersion.document_id == document_id)) or 0
