"""Historique de traçabilité, limité au périmètre du compte : super administrateur (tout), chef de service (son service),
chef de division (sa division), agent (ce qui le concerne)."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_principal
from app.core.permissions import NIVEAU_AGENT, Principal
from app.schemas.historique import HistoriquePageOut, VerificationHistoriqueOut
from app.services import historique as svc

router = APIRouter(prefix="/historique", tags=["historique"])


@router.get("", response_model=HistoriquePageOut)
def lister(
    cible_type: str | None = None,
    action: str | None = None,
    division_id: int | None = None,
    service_id: int | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    principal: Principal = Depends(get_principal), db: Session = Depends(get_db),
):
    total, rows = svc.lister_historique(
        db, principal, cible_type=cible_type, action=action, division_id=division_id, service_id=service_id, limit=limit, offset=offset
    )
    return HistoriquePageOut(total=total, items=[svc.to_out(r) for r in rows])


@router.get("/verification", response_model=VerificationHistoriqueOut)
def verification(principal: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    """Recalcule toute la chaîne de hash (SHA-256) : toute ligne modifiée ou retirée au milieu est détectée."""
    if principal.niveau == NIVEAU_AGENT:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Réservé aux administrateurs.")
    res = svc.verifier_chaine(db)
    message = (
        f"Chaîne intacte : {res['total']} entrée(s) vérifiée(s)."
        if res["ok"] else f"Chaîne ALTÉRÉE à partir de l'entrée n°{res['premier_rang_invalide']}."
    )
    return VerificationHistoriqueOut(message=message, **res)
