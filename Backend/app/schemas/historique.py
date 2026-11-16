"""Schémas Pydantic de l'historique de traçabilité."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class HistoriqueOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    acteur_user_id: int | None = None
    cible_type: str
    cible_id: int | None = None
    action: str
    avant: str | None = None
    apres: str | None = None
    motif: str | None = None
    service_id: int | None = None
    division_id: int | None = None
    date_action: datetime
    hash_precedent: str | None = None
    hash_courant: str | None = None


class VerificationHistoriqueOut(BaseModel):
    ok: bool
    total: int
    message: str
