from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CategorieIn(BaseModel):
    nom: str = Field(min_length=1, max_length=120)
    parent_id: int | None = None
    couleur: str | None = Field(default=None, max_length=9)
    ordre: int = 0
    actif: bool = True


class CategorieUpdate(BaseModel):
    nom: str | None = Field(default=None, min_length=1, max_length=120)
    parent_id: int | None = None
    couleur: str | None = Field(default=None, max_length=9)
    ordre: int | None = None
    actif: bool | None = None


class CategorieOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    parent_id: int | None
    nom: str
    couleur: str | None
    ordre: int
    actif: bool


class TypeDocumentIn(BaseModel):
    nom: str = Field(min_length=1, max_length=120)
    actif: bool = True


class TypeDocumentUpdate(BaseModel):
    nom: str | None = Field(default=None, min_length=1, max_length=120)
    actif: bool | None = None


class TypeDocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nom: str
    actif: bool


class TagIn(BaseModel):
    nom: str = Field(min_length=1, max_length=60)


class TagUpdate(BaseModel):
    nom: str | None = Field(default=None, min_length=1, max_length=60)


class TagOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nom: str


class RegleClassementIn(BaseModel):
    nom: str = Field(min_length=1, max_length=120)
    priorite: int = 100
    actif: bool = True
    critere: dict[str, Any] = Field(default_factory=dict)
    categorie_id: int | None = None
    type_document_id: int | None = None
    tags: list[str] = Field(default_factory=list)
    confidentialite: str | None = Field(default=None, max_length=15)


class RegleClassementUpdate(BaseModel):
    nom: str | None = Field(default=None, min_length=1, max_length=120)
    priorite: int | None = None
    actif: bool | None = None
    critere: dict[str, Any] | None = None
    categorie_id: int | None = None
    type_document_id: int | None = None
    tags: list[str] | None = None
    confidentialite: str | None = Field(default=None, max_length=15)


class RegleClassementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nom: str
    priorite: int
    actif: bool
    critere: dict[str, Any] = Field(default_factory=dict)
    categorie_id: int | None
    type_document_id: int | None
    tags: list[str]
    confidentialite: str | None
    cree_le: datetime
    modifie_le: datetime


class ClassementResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    categorie_id: int | None = None
    type_document_id: int | None = None
    tags: list[str] = Field(default_factory=list)
    confidentialite: str | None = None


class SimulerClassementIn(BaseModel):
    nom_fichier: str | None = None
    extension: str | None = None
    service_createur_id: int | None = None
    texte: str | None = None
    taille_octets: int | None = None
    nb_pages: int | None = None
    ocr_utilise: bool = False
    classement_source: str = "regle"
