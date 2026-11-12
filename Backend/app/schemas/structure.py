"""Schémas Pydantic de la structure : directions, services, agents, journal d'audit."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class DirectionIn(BaseModel):
    code: str = Field(min_length=1, max_length=30)
    nom: str = Field(min_length=1, max_length=180)


class DirectionUpdate(BaseModel):
    nom: str | None = Field(default=None, min_length=1, max_length=180)
    actif: bool | None = None


class DirectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    nom: str
    actif: bool


class ServiceIn(BaseModel):
    direction_id: int
    code: str = Field(min_length=1, max_length=30)
    nom: str = Field(min_length=1, max_length=180)
    site: str | None = Field(default=None, max_length=150)


class ServiceUpdate(BaseModel):
    direction_id: int | None = None
    nom: str | None = Field(default=None, min_length=1, max_length=180)
    site: str | None = Field(default=None, max_length=150)
    actif: bool | None = None


class ServiceOut(BaseModel):
    id: int
    code: str
    nom: str
    site: str | None
    actif: bool
    direction_id: int
    direction_nom: str


class AgentIn(BaseModel):
    matricule: str = Field(min_length=1, max_length=50)
    nom: str = Field(min_length=1, max_length=100)
    prenom: str = Field(min_length=1, max_length=100)
    fonction: str | None = Field(default=None, max_length=150)
    email: EmailStr | None = None
    service_id: int


class AgentUpdate(BaseModel):
    nom: str | None = Field(default=None, min_length=1, max_length=100)
    prenom: str | None = Field(default=None, min_length=1, max_length=100)
    fonction: str | None = Field(default=None, max_length=150)
    email: EmailStr | None = None
    service_id: int | None = None
    actif: bool | None = None


class AgentOut(BaseModel):
    id: int
    matricule: str
    nom: str
    prenom: str
    fonction: str | None
    email: str | None
    service_id: int | None
    service_nom: str | None
    actif: bool
    nom_utilisateur: str | None  # compte lié, s'il existe


class AuditOut(BaseModel):
    id: int
    cree_le: datetime
    nom_utilisateur: str | None
    action: str
    entite: str | None
    entite_id: int | None
    detail: dict
    adresse_ip: str | None
