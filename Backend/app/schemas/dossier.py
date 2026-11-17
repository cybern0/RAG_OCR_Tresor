"""Schémas des dossiers et sous-dossiers d'une division (visibles de tous les agents de la division, sans rôle propre)."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


def _nom_non_vide(v: str | None) -> str | None:
    if v is None:
        return v
    v = v.strip()
    if not v:
        raise ValueError("Le nom ne peut pas être vide.")
    return v


class DossierIn(BaseModel):
    nom: str = Field(min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=2000)
    parent_id: int | None = None  # sous-dossier : la division est celle du parent
    division_id: int | None = None  # dossier racine : par défaut la division du compte

    _nom = field_validator("nom")(_nom_non_vide)


class DossierUpdate(BaseModel):
    nom: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=2000)
    archive: bool | None = None
    parent_id: int | None = None  # déplacement ; null explicite = à la racine de la division

    _nom = field_validator("nom")(_nom_non_vide)


class CheminOut(BaseModel):
    id: int
    nom: str


class DossierOut(BaseModel):
    id: int
    division_id: int
    division_nom: str
    parent_id: int | None
    nom: str
    description: str | None
    archive: bool
    cree_par_nom: str | None
    cree_le: datetime
    modifie_le: datetime
    nb_sous_dossiers: int = 0
    nb_fichiers: int = 0  # fichiers que JE peux voir
    nb_fichiers_masques: int = 0  # fichiers du dossier auxquels je n'ai pas accès (leur nombre seulement)
    peut_modifier: bool = False
    peut_creer: bool = False


class DossierDetailOut(DossierOut):
    chemin: list[CheminOut] = []  # fil d'Ariane, du plus haut au dossier courant
    sous_dossiers: list[DossierOut] = []
