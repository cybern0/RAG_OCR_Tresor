"""Schémas des demandes d'accès : demande de rôle (durable) et demande d'accès ponctuel à un fichier (exception à expiration)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class DemandeIn(BaseModel):
    type_demande: Literal["role", "fichier"]
    cible_id: int  # identifiant du rôle de division ou du fichier
    motif: str = Field(min_length=3, max_length=1000)
    duree_heures: int | None = Field(default=None, ge=1, le=720)  # fichier : durée d'accès souhaitée


class DemandeDecisionIn(BaseModel):
    accepter: bool
    reponse: str | None = Field(default=None, max_length=1000)
    duree_heures: int | None = Field(default=None, ge=1, le=720)  # fichier : durée accordée (sinon celle demandée, sinon 24 h)


class DemandeOut(BaseModel):
    id: int
    type_demande: Literal["role", "fichier"]
    statut: Literal["en_attente", "acceptee", "refusee", "annulee"]
    demandeur_user_id: int
    demandeur_nom: str
    division_id: int
    division_nom: str
    cible_id: int | None
    cible_libelle: str
    motif: str
    duree_heures: int | None
    reponse: str | None
    decisionnaire_nom: str | None
    date_creation: datetime
    date_decision: datetime | None
    peut_decider: bool = False
    peut_annuler: bool = False


class ExceptionOut(BaseModel):
    id: int
    user_id: int
    utilisateur_nom: str
    document_id: int
    document_titre: str
    division_nom: str
    expire_le: datetime
    motif: str | None
    accorde_par_nom: str | None
