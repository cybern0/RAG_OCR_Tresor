"""Schémas Pydantic des rôles de division."""

from pydantic import BaseModel, ConfigDict, Field


class RoleDivisionIn(BaseModel):
    code: str = Field(min_length=1, max_length=60)
    libelle: str = Field(min_length=1, max_length=180)


class RoleDivisionUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=60)
    libelle: str | None = Field(default=None, min_length=1, max_length=180)
    actif: bool | None = None


class RoleDivisionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    division_id: int
    code: str
    libelle: str
    actif: bool


class UserRoleAssignIn(BaseModel):
    role_ids: list[int] = Field(default_factory=list)
