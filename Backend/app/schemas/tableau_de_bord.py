"""Schémas du tableau de bord : un contenu par niveau (super administrateur, chef de service, chef de division, agent)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.schemas.document import RoleBrief
from app.schemas.historique import HistoriqueOut


class Indicateur(BaseModel):
    cle: str
    libelle: str
    valeur: int
    ton: Literal["neutre", "attention", "alerte"] = "neutre"
    lien: str | None = None  # page où agir


class ColonneRepartition(BaseModel):
    cle: str
    libelle: str


class LigneRepartition(BaseModel):
    id: int | None = None
    libelle: str
    sous_titre: str | None = None
    valeurs: dict[str, int]
    alerte: bool = False


class Repartition(BaseModel):
    titre: str
    colonnes: list[ColonneRepartition]
    lignes: list[LigneRepartition]


class FichierBrief(BaseModel):
    id: int
    titre: str
    dossier_id: int
    dossier_nom: str
    depose_par: str | None
    depose_le: datetime


class AccesPonctuelBrief(BaseModel):
    document_id: int
    document_titre: str
    expire_le: datetime


class TableauDeBordOut(BaseModel):
    niveau: Literal["ROOT", "SERVICE", "DIVISION", "AGENT"]
    titre: str
    sous_titre: str | None = None
    indicateurs: list[Indicateur]
    repartition: Repartition | None = None
    alertes: list[str] = []
    a_classer: list[FichierBrief] = []
    derniers_changements: list[HistoriqueOut] = []
    mes_roles: list[RoleBrief] = []
    mes_fichiers: list[FichierBrief] = []
    acces_ponctuels: list[AccesPonctuelBrief] = []
