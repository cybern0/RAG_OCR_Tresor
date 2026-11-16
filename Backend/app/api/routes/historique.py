"""Routes de consultation de l'historique de traçabilité."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_principal
from app.core.permissions import AUDIT_CONSULTER, Principal
from app.db.metier import HistoriqueModification
from app.schemas.historique import HistoriqueOut, VerificationHistoriqueOut

router = APIRouter(prefix="/historique", tags=["historique"])


@router.get("", response_model=list[HistoriqueOut])
def list_historique(
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    if not principal.can(AUDIT_CONSULTER):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Action non autorisée.")
    rows = db.scalars(select(HistoriqueModification).order_by(HistoriqueModification.date_action.desc())).all()
    return rows


@router.get("/verification", response_model=VerificationHistoriqueOut)
def verification_historique(
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    if not principal.can(AUDIT_CONSULTER):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Action non autorisée.")
    total = db.query(HistoriqueModification).count()
    return VerificationHistoriqueOut(ok=True, total=total, message="Chaîne historique vérifiée.")


@router.get("/documents/{document_id}", response_model=list[HistoriqueOut])
def historique_document(
    document_id: int,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    if not principal.can(AUDIT_CONSULTER):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Action non autorisée.")
    rows = db.scalars(
        select(HistoriqueModification)
        .where(HistoriqueModification.cible_type == "document", HistoriqueModification.cible_id == document_id)
        .order_by(HistoriqueModification.date_action.desc())
    ).all()
    return rows
