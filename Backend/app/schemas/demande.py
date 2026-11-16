"""Schémas Pydantic des demandes d'accès et de rôle."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DemandeAccesIn(BaseModel):
    type_demande: str = Field(default="role")
    cible_type: str | None = None
    cible_id: int | None = None
    motif: str | None = None
    duree_minutes: int | None = None


class DemandeDecisionIn(BaseModel):
    statut: str = Field(default="accepte")
    reponse: str | None = None


class DemandeAccesOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    demandeur_user_id: int
    type_demande: str
    cible_type: str | None = None
    cible_id: int | None = None
    motif: str | None = None
    statut: str
    decisionnaire_user_id: int | None = None
    reponse: str | None = None
    date_creation: datetime
    date_decision: datetime | None = None
    expiration: datetime | None = None
