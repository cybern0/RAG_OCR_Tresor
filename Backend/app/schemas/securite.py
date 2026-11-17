"""Schémas des mots de passe de dossier (unités) et du déverrouillage."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.core.security import PASSWORD_MIN_LENGTH

TypeUnite = Literal["service", "division"]


class DeverrouillerIn(BaseModel):
    type: TypeUnite
    unite_id: int
    mot_de_passe: str = Field(min_length=1, max_length=200)


class VerrouillerIn(BaseModel):
    type: TypeUnite
    unite_id: int


class SecretIn(BaseModel):
    """Définit ou change son mot de passe de dossier ; un supérieur peut réinitialiser celui d'un subordonné (utilisateur_cible_id)."""

    type: TypeUnite
    unite_id: int
    nouveau_mot_de_passe: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=200)
    ancien_mot_de_passe: str | None = Field(default=None, max_length=200)
    utilisateur_cible_id: int | None = None


class DeverrouillageOut(BaseModel):
    valide_jusqua: datetime
    minutes: int


class UniteSecretOut(BaseModel):
    type: TypeUnite
    id: int
    nom: str
    service_id: int
    service_nom: str
    secret_defini: bool
    deverrouille: bool
    valide_jusqua: datetime | None = None
    via_service: bool = False  # ouverte parce que son service est déverrouillé


class DelegationOut(BaseModel):
    """Pour un super administrateur : le mot de passe de dossier du chef de service sur une division de son service."""

    division_id: int
    division_nom: str
    service_nom: str
    titulaire_user_id: int | None
    titulaire_nom: str | None
    secret_defini: bool
