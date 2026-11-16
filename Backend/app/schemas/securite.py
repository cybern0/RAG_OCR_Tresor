"""Schémas Pydantic de la sécurité d'unité."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SecretUniteIn(BaseModel):
    service_id: int | None = None
    division_id: int | None = None
    secret_hash: str = Field(min_length=1)


class SecretUniteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    service_id: int | None = None
    division_id: int | None = None
    admin_user_id: int
    modifie_le: datetime


class DeverrouillerIn(BaseModel):
    secret_unite_id: int
    duree_minutes: int = Field(default=15, ge=1, le=240)


class DeverrouillageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    secret_unite_id: int
    user_id: int
    valide_jusqua: datetime
    actif: bool
