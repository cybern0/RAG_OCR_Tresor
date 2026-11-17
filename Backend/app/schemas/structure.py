"""Schémas Pydantic de la structure : directions, services, agents, journal d'audit."""

from datetime import datetime
from typing import Literal

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


class DivisionIn(BaseModel):
    service_id: int
    nom: str = Field(min_length=1, max_length=180)
    code: str | None = Field(default=None, min_length=1, max_length=30)


class DivisionUpdate(BaseModel):
    nom: str | None = Field(default=None, min_length=1, max_length=180)
    code: str | None = Field(default=None, min_length=1, max_length=30)
    actif: bool | None = None


class DivisionOut(BaseModel):
    id: int
    service_id: int
    code: str | None
    nom: str
    actif: bool
    service_nom: str | None = None


class AgentIn(BaseModel):
    matricule: str = Field(min_length=1, max_length=50)
    nom: str = Field(min_length=1, max_length=100)
    prenom: str = Field(min_length=1, max_length=100)
    fonction: str | None = Field(default=None, max_length=150)
    email: EmailStr | None = None
    service_id: int
    division_id: int | None = None
    titre: Literal["CHEF_SERVICE", "CHEF_DIVISION"] | None = None


class AgentUpdate(BaseModel):
    nom: str | None = Field(default=None, min_length=1, max_length=100)
    prenom: str | None = Field(default=None, min_length=1, max_length=100)
    fonction: str | None = Field(default=None, max_length=150)
    email: EmailStr | None = None
    service_id: int | None = None
    division_id: int | None = None
    titre: Literal["CHEF_SERVICE", "CHEF_DIVISION"] | None = None  # null explicite = retirer le titre
    actif: bool | None = None


class AgentOut(BaseModel):
    id: int
    matricule: str
    nom: str
    prenom: str
    fonction: str | None
    email: str | None
    service_id: int | None
    division_id: int | None
    titre: str | None
    service_nom: str | None
    division_nom: str | None = None
    actif: bool
    nom_utilisateur: str | None  # compte lié, s'il existe


class ChefOut(BaseModel):
    agent_id: int
    nom_complet: str


class PosteServiceOut(BaseModel):
    service_id: int
    service_nom: str
    chef: ChefOut | None


class PosteDivisionOut(BaseModel):
    division_id: int
    division_nom: str
    service_id: int
    chef: ChefOut | None


class PostesOut(BaseModel):
    services: list[PosteServiceOut]
    divisions: list[PosteDivisionOut]


class TransfertChefIn(BaseModel):
    agent_id: int | None = None  # null = retrait : le poste devient vacant
    motif: str | None = Field(default=None, max_length=500)


class UniteArbreOut(BaseModel):
    id: int
    code: str | None
    nom: str
    actif: bool
    chef: ChefOut | None
    nb_agents: int
    acces: Literal["membre", "superieur"]
    deverrouillee: bool = False  # pertinent pour acces = superieur
    secret_defini: bool = False


class ServiceArbreOut(BaseModel):
    id: int
    code: str
    nom: str
    actif: bool
    chef: ChefOut | None
    divisions: list[UniteArbreOut]


class AuditOut(BaseModel):
    id: int
    cree_le: datetime
    nom_utilisateur: str | None
    action: str
    entite: str | None
    entite_id: int | None
    detail: dict
    adresse_ip: str | None
