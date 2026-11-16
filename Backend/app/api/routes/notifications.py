"""Routes des notifications internes."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_principal
from app.core.permissions import Principal
from app.db.metier import Notification
from app.schemas.notification import NotificationOut

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationOut])
def list_notifications(
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    return db.scalars(
        select(Notification)
        .where(Notification.destinataire_user_id == principal.user.id)
        .order_by(Notification.cree_le.desc())
    ).all()


@router.post("/{notification_id}/lue", response_model=NotificationOut)
def mark_read(
    notification_id: int,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    row = db.get(Notification, notification_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notification introuvable.")
    if row.destinataire_user_id != principal.user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Action non autorisée.")
    row.lu = True
    db.commit()
    db.refresh(row)
    return row


@router.post("/lues")
def mark_all_read(
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    db.query(Notification).filter(Notification.destinataire_user_id == principal.user.id, Notification.lu.is_(False)).update({"lu": True})
    db.commit()
    return {"ok": True, "count": 0}
