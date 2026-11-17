"""Tableau de bord du compte connecté (contenu et périmètre selon son niveau)."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_principal
from app.core.permissions import Principal
from app.schemas.tableau_de_bord import TableauDeBordOut
from app.services import tableau_de_bord as svc

router = APIRouter(prefix="/tableau-de-bord", tags=["tableau-de-bord"])


@router.get("", response_model=TableauDeBordOut)
def tableau_de_bord(principal: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    return svc.construire(db, principal)
