"""Routes CRUD des documents : ajout (upload), modification, suppression, liste des métadonnées.
Pas de route de lecture du contenu : le contenu n'est consultable qu'à travers le chat.
Renvoie aussi le statut d'ingestion (pending, processing, ready, error).

Droits : ADMIN sur tous les services, UTILISATEUR sur le service de son agent (vérifié dans services/documents)."""

from fastapi import APIRouter, Depends, File, Form, Request, Response, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import client_ip, get_db, require
from app.core.permissions import (
    DOCUMENT_CREER, DOCUMENT_LISTER, DOCUMENT_MODIFIER, DOCUMENT_SUPPRIMER, Principal,
)
from app.schemas.document import DocumentOut
from app.services.documents import crud

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("", response_model=list[DocumentOut])
def list_documents(
    service_id: int | None = None,
    principal: Principal = Depends(require(DOCUMENT_LISTER)), db: Session = Depends(get_db),
):
    return [crud.to_out(d) for d in crud.list_documents(db, principal, service_id)]


@router.post("", response_model=DocumentOut, status_code=201)
def create_document(
    request: Request,
    fichier: UploadFile = File(...),
    titre: str = Form(""),
    service_id: int | None = Form(None),
    contient_tableaux: bool = Form(False),
    principal: Principal = Depends(require(DOCUMENT_CREER)), db: Session = Depends(get_db),
):
    doc = crud.create_document(db, principal, fichier, titre, service_id, contient_tableaux, client_ip(request))
    return crud.to_out(doc)


@router.patch("/{document_id}", response_model=DocumentOut)
def update_document(
    document_id: int, request: Request,
    titre: str | None = Form(None),
    service_id: int | None = Form(None),
    contient_tableaux: bool | None = Form(None),
    fichier: UploadFile | None = File(None),
    principal: Principal = Depends(require(DOCUMENT_MODIFIER)), db: Session = Depends(get_db),
):
    doc = crud.update_document(
        db, principal, document_id, titre, service_id, fichier, contient_tableaux, client_ip(request)
    )
    return crud.to_out(doc)


@router.delete("/{document_id}", status_code=204)
def delete_document(
    document_id: int, request: Request,
    principal: Principal = Depends(require(DOCUMENT_SUPPRIMER)), db: Session = Depends(get_db),
) -> Response:
    crud.delete_document(db, principal, document_id, client_ip(request))
    return Response(status_code=204)
