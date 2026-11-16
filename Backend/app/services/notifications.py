"""Notifications internes de la GED hiérarchique.
Les événements sont stockés en base et consultés par l'interface via polling de 15 à 30 s.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.metier import Notification


def create_notification(db: Session, *, destinataire_user_id: int, type_evenement: str, message: str, reference_type: str | None = None, reference_id: int | None = None) -> Notification:
    notification = Notification(
        destinataire_user_id=destinataire_user_id,
        type_evenement=type_evenement,
        reference_type=reference_type,
        reference_id=reference_id,
        message=message,
        lu=False,
    )
    db.add(notification)
    db.flush()
    return notification


def list_notifications(db: Session, *, destinataire_user_id: int):
    return db.query(Notification).filter(Notification.destinataire_user_id == destinataire_user_id).order_by(Notification.cree_le.desc()).all()
