"""Schémas Pydantic des dossiers, de leurs membres et des rôles de dossier."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

RoleDossier = Literal["LECTEUR", "CONTRIBUTEUR", "GESTIONNAIRE_DE_CONTENU"]


class DossierIn(BaseModel):
    nom: str = Field(min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("nom")
    @classmethod
    def _nom(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("Le nom du dossier ne peut pas être vide.")
        return v


class DossierUpdate(BaseModel):
    nom: str | None = Field(default=None, max_length=150)
    description: str | None = Field(default=None, max_length=2000)
    archive: bool | None = None


class DossierOut(BaseModel):
    id: int
    nom: str
    description: str | None
    archive: bool
    nb_fichiers: int
    mon_role: RoleDossier  # rôle effectif de l'utilisateur connecté dans ce dossier
    cree_le: datetime
    modifie_le: datetime


class RoleIn(BaseModel):
    role: RoleDossier


class MembreOut(BaseModel):
    user_id: int
    nom_utilisateur: str
    nom_complet: str | None
    role: RoleDossier


class ServiceAccesOut(BaseModel):
    service_id: int
    service_code: str
    service_nom: str
    role: RoleDossier


class AccesDossierOut(BaseModel):
    membres: list[MembreOut]
    services: list[ServiceAccesOut]
