"""Routes des fichiers (documents) rangés dans des dossiers, et de leurs versions.

- Liste, historique des versions, aperçu et téléchargement (toute version) : tout membre du dossier.
- Ajout d'un fichier, d'une nouvelle version, modification du titre et des cases : contributeur ou plus.
- Suppression d'un fichier ou d'une version : gestionnaire de contenu (ou admin).
Les droits se vérifient dans services/documents (rôle du dossier) ; dossier hors des accès : 404, rôle insuffisant : 403.
Ajouter une version AJOUTE : l'ancienne reste indexée, téléchargeable et interrogeable.
"""

from fastapi import APIRouter, Depends, File, Form, Request, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import client_ip, get_db, get_principal
from app.core.permissions import APERCU, TELECHARGER, Principal
from app.schemas.document import DocumentOut, VersionOut
from app.services.documents import apercu, crud

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("", response_model=list[DocumentOut])
def list_documents(
    dossier_id: int | None = None, principal: Principal = Depends(get_principal), db: Session = Depends(get_db)
):
    return crud.list_documents(db, principal, dossier_id)


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


@router.delete("/{document_id}", status_code=204)
def delete_document(
    document_id: int, request: Request, principal: Principal = Depends(get_principal), db: Session = Depends(get_db)
) -> Response:
    crud.delete_document(db, principal, document_id, client_ip(request))
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
