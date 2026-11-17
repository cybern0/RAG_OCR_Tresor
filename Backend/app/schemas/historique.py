"""Schémas Pydantic de l'historique de traçabilité."""

from datetime import datetime

from pydantic import BaseModel


class HistoriqueOut(BaseModel):
    id: int
    rang: int | None = None
    acteur_user_id: int | None = None
    acteur_nom: str | None = None
    concerne_user_id: int | None = None
    cible_type: str
    cible_id: int | None = None
    action: str
    avant: str | None = None
    apres: str | None = None
    motif: str | None = None
    service_id: int | None = None
    division_id: int | None = None
    date_action: datetime
    hash_courant: str | None = None


class HistoriquePageOut(BaseModel):
    total: int
    items: list[HistoriqueOut]


class VerificationHistoriqueOut(BaseModel):
    ok: bool
    total: int
    premier_rang_invalide: int | None = None
    message: str
