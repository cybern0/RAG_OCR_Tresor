"""Routes de demandes d'accès et d'exception."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_principal
from app.core.permissions import Principal
from app.db.metier import DemandeAcces
from app.schemas.demande import DemandeAccesIn, DemandeAccesOut, DemandeDecisionIn

router = APIRouter(prefix="/demandes", tags=["demandes"])


@router.get("", response_model=list[DemandeAccesOut])
def list_demandes(
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    if principal.is_admin:
        rows = db.scalars(select(DemandeAcces).order_by(DemandeAcces.date_creation.desc())).all()
    else:
        rows = db.scalars(
            select(DemandeAcces)
            .where(DemandeAcces.demandeur_user_id == principal.user.id)
            .order_by(DemandeAcces.date_creation.desc())
        ).all()
    return rows


@router.post("", response_model=DemandeAccesOut, status_code=201)
def create_demande(
    payload: DemandeAccesIn,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    item = DemandeAcces(
        demandeur_user_id=principal.user.id,
        type_demande=payload.type_demande,
        cible_type=payload.cible_type,
        cible_id=payload.cible_id,
        motif=payload.motif,
        statut="en_attente",
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/{demande_id}/decision", response_model=DemandeAccesOut)
def decide_demande(
    demande_id: int,
    payload: DemandeDecisionIn,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    item = db.get(DemandeAcces, demande_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Demande introuvable.")
    if not principal.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Action non autorisée.")
    item.statut = payload.statut
    item.decisionnaire_user_id = principal.user.id
    item.reponse = payload.reponse
    item.date_decision = __import__("datetime").datetime.utcnow()
    db.commit()
    db.refresh(item)
    return item
