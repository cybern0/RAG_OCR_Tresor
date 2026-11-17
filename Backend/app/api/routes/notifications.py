"""Notifications du compte connecté (cloche de l'interface)."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_principal
from app.core.permissions import Principal
from app.schemas.notification import NotificationOut, NotificationsOut
from app.services import notifications as svc

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=NotificationsOut)
def lister(
    non_lues: bool = False, limit: int = Query(default=50, ge=1, le=200),
    principal: Principal = Depends(get_principal), db: Session = Depends(get_db),
):
    nb, rows = svc.lister(db, principal.user.id, non_lues_seulement=non_lues, limit=limit)
    return NotificationsOut(non_lues=nb, items=[NotificationOut.model_validate(r) for r in rows])


@router.post("/lues", status_code=204)
def tout_lire(principal: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    svc.marquer_toutes_lues(db, principal.user.id)
    db.commit()


@router.post("/{notification_id}/lue", status_code=204)
def lire(notification_id: int, principal: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    if not svc.marquer_lue(db, principal.user.id, notification_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notification introuvable.")
    db.commit()
