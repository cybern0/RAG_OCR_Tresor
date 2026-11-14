"""Commentaires sur un fichier (côté UI : features/documents, fiche d'un fichier).

Réservés aux contributeurs et plus : même droit que modifier le fichier. Hors de ses accès, le fichier est un 404.
"""

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_db, get_principal
from app.core.permissions import MODIFIER, Principal
from app.db.metier import Commentaire
from app.services.documents import crud

router = APIRouter(prefix="/documents", tags=["commentaires"])


class CommentaireIn(BaseModel):
    contenu: str

    @field_validator("contenu")
    @classmethod
    def _non_vide(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Un commentaire ne peut pas être vide.")
        if len(v) > 2000:
            raise ValueError("Un commentaire ne peut pas dépasser 2000 caractères.")
        return v


class CommentaireOut(BaseModel):
    id: int
    auteur_nom: str
    contenu: str
    cree_le: datetime


def _out(c: Commentaire) -> CommentaireOut:
    return CommentaireOut(id=c.id, auteur_nom=c.auteur.nom_utilisateur, contenu=c.contenu, cree_le=c.cree_le)


@router.get("/{document_id}/commentaires", response_model=list[CommentaireOut])
def list_commentaires(document_id: int, principal: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    doc, _ = crud.get_document(db, principal, document_id, MODIFIER)
    rows = db.scalars(
        select(Commentaire).options(joinedload(Commentaire.auteur))
        .where(Commentaire.sujet_type == "document", Commentaire.sujet_id == doc.id)
        .order_by(Commentaire.cree_le.asc(), Commentaire.id.asc())
    ).all()
    return [_out(c) for c in rows]


@router.post("/{document_id}/commentaires", response_model=CommentaireOut, status_code=201)
def create_commentaire(
    document_id: int, data: CommentaireIn,
    principal: Principal = Depends(get_principal), db: Session = Depends(get_db),
):
    doc, _ = crud.get_document(db, principal, document_id, MODIFIER)
    comment = Commentaire(sujet_type="document", sujet_id=doc.id, auteur_id=principal.user.id, contenu=data.contenu)
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return _out(comment)
