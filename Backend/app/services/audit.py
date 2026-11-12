"""Journal d'audit : qui a fait quoi (ajout, modification, suppression, connexion...)."""

from typing import Any

from sqlalchemy.orm import Session

from app.db.metier import JournalAudit


def log_action(
    db: Session,
    user_id: int | None,
    action: str,
    entite: str | None = None,
    entite_id: int | None = None,
    detail: dict[str, Any] | None = None,
    ip: str | None = None,
) -> None:
    """Ajoute une ligne au journal dans la transaction en cours (le commit est fait par l'appelant)."""
    db.add(
        JournalAudit(
            user_id=user_id, action=action, entite=entite, entite_id=entite_id, detail=detail or {}, adresse_ip=ip
        )
    )
