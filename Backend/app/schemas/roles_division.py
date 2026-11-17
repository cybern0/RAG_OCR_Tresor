"""Schémas des rôles de division."""

from pydantic import BaseModel, Field, field_validator


def _libelle_non_vide(v: str | None) -> str | None:
    if v is None:
        return v
    v = v.strip()
    if len(v) < 2:
        raise ValueError("Le libellé doit contenir au moins 2 caractères.")
    return v


class RoleDivisionIn(BaseModel):
    libelle: str = Field(min_length=2, max_length=180)
    code: str | None = Field(default=None, min_length=2, max_length=60, pattern=r"^[A-Za-z0-9_\-]+$")

    _libelle = field_validator("libelle")(_libelle_non_vide)


class RoleDivisionUpdate(BaseModel):
    libelle: str | None = Field(default=None, min_length=2, max_length=180)
    code: str | None = Field(default=None, min_length=2, max_length=60, pattern=r"^[A-Za-z0-9_\-]+$")
    actif: bool | None = None

    _libelle = field_validator("libelle")(_libelle_non_vide)


class RoleDivisionOut(BaseModel):
    id: int
    division_id: int
    code: str
    libelle: str
    actif: bool
    nb_agents: int = 0
    nb_fichiers: int = 0
