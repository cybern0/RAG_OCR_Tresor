"""Routes des fichiers (documents) rangés dans les dossiers d'une division, et de leurs versions.

Les droits se vérifient dans services/documents avec le rôle effectif (core/acces.py) : GERANT, AUTEUR, LECTEUR.
Hors périmètre : 404 ; sans rôle sur le fichier : 403 (« Demander l'accès »).
Ajouter une version AJOUTE : l'ancienne reste indexée, téléchargeable et interrogeable.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, File, Form, Query, Request, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import client_ip, get_db, get_principal
from app.core.acces import APERCU, MODIFIER, TELECHARGER, VOIR, exiger_acces_document
from app.core.permissions import Principal
from app.db.vecteur import Document
from app.schemas.document import ClasserLotIn, ClasserLotOut, DocumentOut, DocumentPageOut, RolesDocumentIn, VersionOut
from app.schemas.historique import HistoriqueOut
from app.services.historique import to_out as historique_to_out
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
    corbeille: bool = Query(default=False),
    a_classer: bool = Query(default=False),
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
        corbeille=corbeille,
        a_classer=a_classer,
    )


@router.post("", response_model=DocumentOut, status_code=201)
def create_document(
    request: Request,
    dossier_id: int = Form(...),
    fichier: UploadFile = File(...),
    titre: str = Form(""),
    contient_tableaux: bool = Form(False),
    contient_images: bool = Form(False),
    role_ids: list[int] | None = Form(None),
    roles_explicites: bool = Form(False),
    principal: Principal = Depends(get_principal), db: Session = Depends(get_db),
):
    """Dépose un fichier. Classement par rôle : un agent reçoit ses rôles par défaut (il peut en retirer) ;
    le chef de division choisit, sans choix le fichier est « à classer » (accès refusé par défaut)."""
    return crud.create_document(
        db, principal, fichier, titre, dossier_id, contient_tableaux, contient_images, client_ip(request),
        role_ids=role_ids, roles_explicites=roles_explicites,
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
    """Classement documentaire manuel (catégorie, type, étiquettes, confidentialité) : gérant ou auteur de chaque fichier."""
    result = {"ok": [], "not_found": [], "forbidden": []}
    for document_id in dict.fromkeys(data.ids):
        doc = db.get(Document, document_id)
        if doc is None:
            result["not_found"].append(document_id)
            continue
        try:
            exiger_acces_document(db, principal, doc, MODIFIER)
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
    return crud.to_out(doc, role, crud.roles_par_document(db, [doc.id]).get(doc.id))


@router.put("/{document_id}/roles", response_model=DocumentOut)
def definir_roles(
    document_id: int, data: RolesDocumentIn,
    principal: Principal = Depends(get_principal), db: Session = Depends(get_db),
):
    """Rôles de classement du fichier : gérant de la division uniquement. Liste vide = accès refusé par défaut."""
    return crud.definir_roles_document(db, principal, document_id, data.role_ids, data.motif)


@router.get("/{document_id}/historique", response_model=list[HistoriqueOut])
def historique(document_id: int, principal: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    return [historique_to_out(h) for h in crud.historique_document(db, principal, document_id)]


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
