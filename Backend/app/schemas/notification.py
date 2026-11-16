"""Schémas Pydantic des notifications internes."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    destinataire_user_id: int
    type_evenement: str
    reference_type: str | None = None
    reference_id: int | None = None
    message: str | None = None
    lu: bool = False
    cree_le: datetime
