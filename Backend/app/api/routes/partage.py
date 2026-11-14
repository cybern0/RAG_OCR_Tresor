"""Routes locales de partage, demandes d'accès et collaboration.

Ces endpoints gardent le fonctionnement 100 % interne à l'application : aucun service externe,
aucun tiers, aucun lien public hébergé hors du projet. Ils servent de fondation au plan GED local
et s'appuient sur les permissions et actions déjà en place.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_principal
from app.core.permissions import DOSSIER_GERER, MODIFIER, PARTAGER, Principal, exiger_acces
from app.db.metier import DemandeAcces, DocumentPartage, Dossier, User
from app.db.vecteur import Document
from app.schemas.document import (
    AccessRequestDecisionIn,
    CommentaireIn,
    DocumentLienPartageIn,
    DocumentLienPartageOut,
    DocumentPartageIn,
    DocumentPartageOut,
    FavoriIn,
    PartageRequestIn,
)
from app.services.documents import crud
from app.services.partage import (
    AccessRequest,
    Comment,
    Favorite,
    Notification,
    add_comment as add_comment_service,
    add_notification as add_notification_service,
    create_access_request as create_access_request_db,
    create_comment as create_comment_db,
    create_document_link_share,
    create_document_share,
    create_notification as create_notification_db,
    list_access_requests as list_access_requests_db,
    list_comments as list_comments_db,
    list_document_shares,
    list_notifications as list_notifications_db,
    make_share_payload,
    process_access_request,
    request_access,
    toggle_favorite,
)

router = APIRouter(prefix="/partage", tags=["partage"])


@router.get("/documents/{document_id}/partages", response_model=list[DocumentPartageOut])
def list_document_partages(document_id: int, principal: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    doc, _ = crud.get_document(db, principal, document_id, MODIFIER)
    rows = list_document_shares(db, doc.id)
    return [
        DocumentPartageOut(
            id=row.id,
            document_id=row.document_id,
            user_id=row.user_id,
            service_id=row.service_id,
            role=row.role,
            expire_le=row.expire_le,
            is_anonymous=True,
            token_hash=None,
            token=None,
            cree_le=row.cree_le,
        )
        for row in rows
    ]


@router.post("/documents/{document_id}/liens", response_model=DocumentLienPartageOut, status_code=201)
def create_document_link_share_route(
    document_id: int,
    data: DocumentLienPartageIn,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    doc, _ = crud.get_document(db, principal, document_id, PARTAGER)
    raw_token = data.token or make_share_payload(
        doc.id,
        role=data.role,
        expires_at=data.expire_le,
        user_id=principal.user.id,
        is_anonymous=data.est_anonyme,
        created_by=principal.user.id,
    )["token"]
    row = create_document_link_share(
        db,
        document_id=doc.id,
        token=raw_token,
        role=data.role,
        est_anonyme=data.est_anonyme,
        expire_le=data.expire_le,
        cree_par=principal.user.id,
    )
    return DocumentLienPartageOut(
        id=row.id,
        document_id=row.document_id,
        role=row.role,
        est_anonyme=row.est_anonyme,
        expire_le=row.expire_le,
        token_hash=row.token_hash,
        token=raw_token,
        cree_le=row.cree_le,
    )


@router.post("/documents/{document_id}/partages", response_model=DocumentPartageOut, status_code=201)
def create_document_partage(
    document_id: int,
    data: DocumentPartageIn,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    doc, _ = crud.get_document(db, principal, document_id, PARTAGER)
    if data.user_id is None and data.service_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Un partage local doit cibler un utilisateur ou un service.")
    payload = make_share_payload(
        doc.id,
        role=data.role,
        expires_at=data.expire_le,
        user_id=data.user_id,
        service_id=data.service_id,
        is_anonymous=data.is_anonymous,
        created_by=principal.user.id,
    )
    share = create_document_share(
        db,
        document_id=doc.id,
        user_id=data.user_id,
        service_id=data.service_id,
        role=payload["role"],
        expires_at=data.expire_le,
        created_by=principal.user.id,
    )
    return DocumentPartageOut(
        id=share.id,
        document_id=share.document_id,
        user_id=share.user_id,
        service_id=share.service_id,
        role=share.role,
        expire_le=share.expire_le,
        is_anonymous=data.is_anonymous,
        token_hash=payload["token_hash"],
        token=payload["token"],
        cree_le=share.cree_le,
    )


@router.delete("/documents/{document_id}/partages/{share_id}", status_code=204)
def delete_document_partage(
    document_id: int,
    share_id: int,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> Response:
    doc, _ = crud.get_document(db, principal, document_id, PARTAGER)
    share = db.get(DocumentPartage, share_id)
    if share is None or share.document_id != doc.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Partage introuvable.")
    db.delete(share)
    db.commit()
    return Response(status_code=204)


@router.get("/demandes-acces", response_model=list[AccessRequest])
def list_access_requests_route(
    subject_type: str | None = None,
    subject_id: int | None = None,
    status: str | None = None,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    if subject_type and subject_id is not None:
        if subject_type == "document":
            crud.get_document(db, principal, subject_id, PARTAGER)
        elif subject_type == "dossier":
            exiger_acces(db, principal, subject_id, PARTAGER)
    elif not principal.can(DOSSIER_GERER):
        # sans sujet précis, la liste couvre tout le système : réservée à qui gère les dossiers
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Action non autorisée pour votre rôle.")
    rows = list_access_requests_db(db, subject_type=subject_type, subject_id=subject_id, status=status)
    users = {u.id: u.nom_utilisateur for u in db.scalars(select(User).where(User.id.in_({r.user_id for r in rows})))} if rows else {}
    dossiers = {d.id: d.nom for d in db.scalars(select(Dossier))} if rows else {}
    documents = {d.id: d.titre for d in db.scalars(select(Document).where(Document.id.in_({r.sujet_id for r in rows if r.sujet_type == "document"})))} if rows else {}
    return [
        AccessRequest(
            id=row.id,
            subject_type=row.sujet_type,
            subject_id=row.sujet_id,
            requested_by=row.user_id,
            requested_role=row.role_demande,
            message=row.message or "",
            status=row.statut,
            created_at=row.cree_le,
            subject_name=(documents if row.sujet_type == "document" else dossiers).get(row.sujet_id),
            requester_name=users.get(row.user_id),
        )
        for row in rows
    ]


@router.post("/documents/{document_id}/demandes-acces", response_model=AccessRequest)
def create_access_request(
    document_id: int,
    data: PartageRequestIn,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    doc, _ = crud.get_document(db, principal, document_id, MODIFIER)
    item = create_access_request_db(
        db,
        subject_type="document",
        subject_id=doc.id,
        user_id=principal.user.id,
        requested_role=data.requested_role,
        message=data.message,
    )
    return AccessRequest(
        id=item.id,
        subject_type=item.sujet_type,
        subject_id=item.sujet_id,
        requested_by=item.user_id,
        requested_role=item.role_demande,
        message=item.message or "",
        status=item.statut,
        created_at=item.cree_le,
    )


@router.post("/dossiers/{dossier_id}/demandes-acces", response_model=AccessRequest)
def create_dossier_access_request(
    dossier_id: int,
    data: PartageRequestIn,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    dossier = db.get(Dossier, dossier_id)
    if dossier is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dossier introuvable.")
    item = create_access_request_db(
        db,
        subject_type="dossier",
        subject_id=dossier.id,
        user_id=principal.user.id,
        requested_role=data.requested_role,
        message=data.message,
    )
    return AccessRequest(
        id=item.id,
        subject_type=item.sujet_type,
        subject_id=item.sujet_id,
        requested_by=item.user_id,
        requested_role=item.role_demande,
        message=item.message or "",
        status=item.statut,
        created_at=item.cree_le,
    )


@router.patch("/demandes-acces/{request_id}", response_model=AccessRequest)
def resolve_access_request_route(
    request_id: int,
    data: AccessRequestDecisionIn,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    req = db.get(DemandeAcces, request_id)
    if req is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Demande d'accès introuvable.")
    if req.sujet_type == "document":
        crud.get_document(db, principal, req.sujet_id, PARTAGER)
    elif req.sujet_type == "dossier":
        exiger_acces(db, principal, req.sujet_id, PARTAGER)
    else:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Type de sujet invalide.")
    item = process_access_request(
        db,
        request_id=request_id,
        decision=data.decision,
        actor_id=principal.user.id,
        granted_role=data.granted_role,
    )
    return AccessRequest(
        id=item.id,
        subject_type=item.sujet_type,
        subject_id=item.sujet_id,
        requested_by=item.user_id,
        requested_role=item.role_demande,
        message=item.message or "",
        status=item.statut,
        created_at=item.cree_le,
    )


@router.post("/documents/{document_id}/commentaires", response_model=Comment)
def create_comment(
    document_id: int,
    data: CommentaireIn,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    doc, _ = crud.get_document(db, principal, document_id, MODIFIER)
    if not data.contenu.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Un commentaire ne peut pas être vide.")
    comment = create_comment_db(
        db,
        subject_type="document",
        subject_id=doc.id,
        author_id=principal.user.id,
        content=data.contenu,
        parent_id=data.parent_id,
    )
    return Comment(
        entity_type=comment.sujet_type,
        entity_id=comment.sujet_id,
        author_id=comment.auteur_id,
        content=comment.contenu,
        created_at=comment.cree_le,
        parent_id=comment.parent_id,
        author_name=principal.user.nom_utilisateur,
    )


@router.get("/documents/{document_id}/commentaires", response_model=list[Comment])
def list_comments(document_id: int, principal: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    doc, _ = crud.get_document(db, principal, document_id, MODIFIER)
    comments = list_comments_db(db, subject_type="document", subject_id=doc.id)
    names = {u.id: u.nom_utilisateur for u in db.scalars(select(User).where(User.id.in_({c.auteur_id for c in comments})))} if comments else {}
    return [
        Comment(
            entity_type=entry.sujet_type,
            entity_id=entry.sujet_id,
            author_id=entry.auteur_id,
            content=entry.contenu,
            created_at=entry.cree_le,
            parent_id=entry.parent_id,
            author_name=names.get(entry.auteur_id),
        )
        for entry in comments
    ]


@router.post("/documents/{document_id}/favoris", response_model=Favorite | None)
def toggle_document_favorite(
    document_id: int,
    payload: FavoriIn,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    doc, _ = crud.get_document(db, principal, document_id, MODIFIER)
    entity_type = payload.entity_type or "document"
    fav = toggle_favorite(db, user_id=principal.user.id, subject_type=entity_type, subject_id=doc.id)
    if fav is None:
        return None
    return Favorite(user_id=fav.user_id, entity_type=fav.sujet_type, entity_id=fav.sujet_id, created_at=fav.cree_le)


@router.get("/documents/{document_id}/notifications", response_model=list[Notification])
def list_notifications(document_id: int, principal: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    doc, _ = crud.get_document(db, principal, document_id, MODIFIER)
    notifications = [
        entry for entry in list_notifications_db(db, user_id=principal.user.id)
        if entry.sujet_type == "document" and entry.sujet_id == doc.id
    ]
    return [
        Notification(
            user_id=entry.user_id,
            kind=entry.type_notification,
            subject_type=entry.sujet_type,
            subject_id=entry.sujet_id,
            message=entry.message,
            is_read=entry.lu,
            created_at=entry.cree_le,
        )
        for entry in notifications
    ]
