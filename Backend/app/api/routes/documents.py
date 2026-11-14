"""Routes des fichiers (documents) rangés dans des dossiers, et de leurs versions.

- Liste, historique des versions, aperçu et téléchargement (toute version) : tout membre du dossier.
- Ajout d'un fichier, d'une nouvelle version, modification du titre et des cases : contributeur ou plus.
- Suppression d'un fichier ou d'une version : gestionnaire de contenu (ou admin).
Les droits se vérifient dans services/documents (rôle du dossier) ; dossier hors des accès : 404, rôle insuffisant : 403.
Ajouter une version AJOUTE : l'ancienne reste indexée, téléchargeable et interrogeable.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, File, Form, Query, Request, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import client_ip, get_db, get_principal
from app.core.permissions import APERCU, MODIFIER, TELECHARGER, VOIR, Principal, exiger_acces
from app.db.vecteur import Document
from app.schemas.document import ClasserLotIn, ClasserLotOut, DocumentOut, DocumentPageOut, VersionOut
from app.services.classement import definir_classement_manuel
from app.services.documents import apercu, crud

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("", response_model=list[DocumentOut] | DocumentPageOut)
def list_documents(
    dossier_id: int | None = None,
    q: str | None = None,
    categorie_id: int | None = Query(default=None),
    type_id: int | None = Query(default=None),
    tag_id: list[int] | None = Query(default=None),
    confidentialite: str | None = None,
    statut: str | None = None,
    extension: str | None = None,
    du: datetime | None = None,
    au: datetime | None = None,
    auteur_id: int | None = None,
    tri: str = "date_desc",
    page: int | None = Query(default=None),
    taille: int | None = Query(default=None),
    partages: bool = False,
    corbeille: bool = Query(default=False),
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    return crud.list_documents(
        db,
        principal,
        dossier_id,
        q=q,
        categorie_id=categorie_id,
        type_id=type_id,
        tag_ids=tag_id,
        confidentialite=confidentialite,
        statut=statut,
        extension=extension,
        du=du,
        au=au,
        auteur_id=auteur_id,
        tri=tri,
        page=page,
        taille=taille,
        partages=partages,
        corbeille=corbeille,
    )


@router.post("", response_model=DocumentOut, status_code=201)
def create_document(
    request: Request,
    dossier_id: int = Form(...),
    fichier: UploadFile = File(...),
    titre: str = Form(""),
    contient_tableaux: bool = Form(False),
    contient_images: bool = Form(False),
    principal: Principal = Depends(get_principal), db: Session = Depends(get_db),
):
    return crud.create_document(
        db, principal, fichier, titre, dossier_id, contient_tableaux, contient_images, client_ip(request)
    )


@router.patch("/{document_id}", response_model=DocumentOut)
def update_document(
    document_id: int, request: Request,
    titre: str | None = Form(None),
    contient_tableaux: bool | None = Form(None),
    contient_images: bool | None = Form(None),
    principal: Principal = Depends(get_principal), db: Session = Depends(get_db),
):
    return crud.update_document(
        db, principal, document_id, titre, contient_tableaux, contient_images, client_ip(request)
    )


@router.post("/classer-lot", response_model=ClasserLotOut)
def classer_lot(
    data: ClasserLotIn,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    """Classement manuel (catégorie, type, étiquettes, confidentialité) : rôle contributeur ou plus dans chaque dossier."""
    result = {"ok": [], "not_found": [], "forbidden": []}
    for document_id in dict.fromkeys(data.ids):
        doc = db.get(Document, document_id)
        if doc is None:
            result["not_found"].append(document_id)
            continue
        try:
            exiger_acces(db, principal, doc.dossier_id, MODIFIER)
        except HTTPException:
            result["forbidden"].append(document_id)
            continue
        definir_classement_manuel(
            db, doc, categorie_id=data.categorie_id, type_document_id=data.type_document_id,
            tags=data.tags, confidentialite=data.confidentialite,
        )
        result["ok"].append(document_id)
    db.commit()
    return result


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(document_id: int, principal: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    """Un fichier (lien profond de l'interface) ; hors des accès : 404."""
    doc, role = crud.get_document(db, principal, document_id, VOIR)
    return crud.to_out(doc, role)


@router.delete("/{document_id}", status_code=204)
def delete_document(
    document_id: int,
    request: Request,
    force: bool = False,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> Response:
    crud.delete_document(db, principal, document_id, client_ip(request), force=force)
    return Response(status_code=204)


@router.post("/{document_id}/restore", status_code=204)
def restore_document(
    document_id: int,
    request: Request,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> Response:
    crud.restore_document(db, principal, document_id, client_ip(request))
    return Response(status_code=204)


@router.get("/{document_id}/versions", response_model=list[VersionOut])
def list_versions(document_id: int, principal: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    return crud.list_versions(db, principal, document_id)


@router.post("/{document_id}/versions", response_model=DocumentOut, status_code=201)
def add_version(
    document_id: int, request: Request,
    fichier: UploadFile = File(...),
    contient_tableaux: bool | None = Form(None),
    contient_images: bool | None = Form(None),
    principal: Principal = Depends(get_principal), db: Session = Depends(get_db),
):
    return crud.add_version(
        db, principal, document_id, fichier, contient_tableaux, contient_images, client_ip(request)
    )


@router.delete("/{document_id}/versions/{numero}", status_code=204)
def delete_version(
    document_id: int, numero: int, request: Request,
    principal: Principal = Depends(get_principal), db: Session = Depends(get_db),
) -> Response:
    crud.delete_version(db, principal, document_id, numero, client_ip(request))
    return Response(status_code=204)


@router.get("/{document_id}/versions/{numero}/apercu")
def preview(
    document_id: int, numero: int, principal: Principal = Depends(get_principal), db: Session = Depends(get_db)
) -> FileResponse:
    return apercu.preview_response(crud.get_version(db, principal, document_id, numero, APERCU))


@router.get("/{document_id}/versions/{numero}/telecharger")
def download(
    document_id: int, numero: int, principal: Principal = Depends(get_principal), db: Session = Depends(get_db)
) -> FileResponse:
    return apercu.download_response(crud.get_version(db, principal, document_id, numero, TELECHARGER))
