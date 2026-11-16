"""Route de tableau de bord selon le niveau hiérarchique."""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_principal
from app.core.permissions import Principal
from app.db.metier import DemandeAcces, Division, Service
from app.db.vecteur import Document
from app.services.tableau_de_bord import build_dashboard

router = APIRouter(tags=["tableau_de_bord"])


@router.get("/tableau-de-bord")
def get_dashboard(
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    contexte: dict[str, object] = {
        "service_id": principal.service_id,
        "division_id": getattr(principal.user.agent, "division_id", None) if principal.user.agent else None,
        "total_fichiers": db.scalar(select(func.count()).select_from(Document)),
        "total_demandes": db.scalar(select(func.count()).select_from(DemandeAcces)),
    }
    if principal.is_admin:
        contexte["agences"] = db.scalars(select(Service).order_by(Service.nom)).all()
        contexte["divisions"] = db.scalars(select(Division).order_by(Division.nom)).all()
        contexte["fichiers_a_classement"] = db.scalars(select(Document).where(Document.division_id.is_(None)).limit(20)).all()
        niveau = "ROOT"
    else:
        contexte["agences"] = []
        contexte["divisions"] = []
        contexte["fichiers_a_classement"] = []
        niveau = "AGENT"
    dashboard = build_dashboard(niveau=niveau, contexte=contexte)
    return dashboard
