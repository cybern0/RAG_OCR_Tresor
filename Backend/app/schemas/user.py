"""Schémas Pydantic des utilisateurs et de la connexion."""

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.security import PASSWORD_MIN_LENGTH

RoleCode = Literal["ADMIN", "UTILISATEUR"]
_USERNAME_RE = re.compile(r"^[a-z0-9._-]{3,80}$")


class LoginIn(BaseModel):
    nom_utilisateur: str = Field(min_length=1, max_length=80)
    mot_de_passe: str = Field(min_length=1, max_length=200)


class AgentBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    matricule: str
    nom: str
    prenom: str
    service_id: int | None
    service_nom: str | None = None
    division_id: int | None = None
    division_nom: str | None = None
    titre: str | None = None


class RoleDivisionBrief(BaseModel):
    id: int
    code: str
    libelle: str


class UserOut(BaseModel):
    id: int
    nom_utilisateur: str
    role: RoleCode
    niveau: Literal["ROOT", "DIVISION", "AGENT"] = "AGENT"
    actif: bool
    derniere_connexion: datetime | None
    cree_le: datetime
    agent: AgentBrief | None
    roles_division: list[RoleDivisionBrief] = []


class DivisionBrief(BaseModel):
    id: int
    nom: str


class MeOut(UserOut):
    permissions: list[str]
    service_id: int | None
    service_nom: str | None
    division_id: int | None = None
    division_nom: str | None = None
    titre: str | None = None
    divisions_gerees: list[DivisionBrief] = []  # divisions dont il est gérant (la sienne, ou intérim)
    unites_protegees: bool = False  # a des mots de passe de dossier à gérer (super administrateur)


class TokenOut(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: MeOut


def _check_password(value: str) -> str:
    if len(value) < PASSWORD_MIN_LENGTH:
        raise ValueError(f"Le mot de passe doit contenir au moins {PASSWORD_MIN_LENGTH} caractères.")
    return value


class UserCreate(BaseModel):
    nom_utilisateur: str
    mot_de_passe: str = Field(max_length=200)
    role: RoleCode = "UTILISATEUR"
    agent_id: int | None = None
    role_ids: list[int] = Field(default_factory=list, max_length=50)  # rôles de division attribués dès la création

    @field_validator("nom_utilisateur")
    @classmethod
    def _username(cls, v: str) -> str:
        v = v.strip().lower()
        if not _USERNAME_RE.match(v):
            raise ValueError("3 à 80 caractères : lettres minuscules, chiffres, point, tiret, tiret bas.")
        return v

    _pwd = field_validator("mot_de_passe")(_check_password)


class UserUpdate(BaseModel):
    role: RoleCode | None = None
    agent_id: int | None = None
    retirer_agent: bool = False
    actif: bool | None = None
    mot_de_passe: str | None = Field(default=None, max_length=200)

    @field_validator("mot_de_passe")
    @classmethod
    def _pwd(cls, v: str | None) -> str | None:
        return _check_password(v) if v is not None else v


class ProfileUpdate(BaseModel):
    """Modification de son propre profil : nom d'utilisateur et/ou mot de passe (l'ancien est alors exigé)."""

    nom_utilisateur: str | None = None
    ancien_mot_de_passe: str | None = Field(default=None, max_length=200)
    nouveau_mot_de_passe: str | None = Field(default=None, max_length=200)
    confirmation_mot_de_passe: str | None = Field(default=None, max_length=200)

    @field_validator("nom_utilisateur")
    @classmethod
    def _username(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip().lower()
        if not _USERNAME_RE.match(v):
            raise ValueError("3 à 80 caractères : lettres minuscules, chiffres, point, tiret, tiret bas.")
        return v

    @field_validator("nouveau_mot_de_passe")
    @classmethod
    def _pwd(cls, v: str | None) -> str | None:
        return _check_password(v) if v is not None else v

    @model_validator(mode="after")
    def _coherence(self) -> "ProfileUpdate":
        if self.nouveau_mot_de_passe is not None:
            if not self.ancien_mot_de_passe:
                raise ValueError("Saisir le mot de passe actuel pour en définir un nouveau.")
            if self.confirmation_mot_de_passe != self.nouveau_mot_de_passe:
                raise ValueError("La confirmation ne correspond pas au nouveau mot de passe.")
        if self.nom_utilisateur is None and self.nouveau_mot_de_passe is None:
            raise ValueError("Rien à modifier.")
        return self


class RolesUtilisateurIn(BaseModel):
    role_ids: list[int] = Field(max_length=50)
    motif: str | None = Field(default=None, max_length=500)
