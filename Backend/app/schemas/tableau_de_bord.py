"""Schémas du tableau de bord : un contenu par niveau (super administrateur, chef de division, agent)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.schemas.user import RoleDivisionBrief
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
    division_nom: str
    depose_par: str | None
    depose_le: datetime


class AccesPonctuelBrief(BaseModel):
    document_id: int
    document_titre: str
    expire_le: datetime


class NomTotal(BaseModel):
    nom: str
    total: int


class ErreurIndexationBrief(BaseModel):
    """Une version en échec d'indexation : où (division, service), déposé par qui, pourquoi."""

    document_id: int
    titre: str
    version_numero: int
    nom_fichier: str
    message_erreur: str | None
    division_nom: str
    service_nom: str | None
    depose_par: str | None = None
    cree_le: datetime


class ErreursIndexation(BaseModel):
    """Traçage des erreurs d'indexation : total, répartition par service / division / auteur, et les cas à corriger."""

    total: int
    par_service: list[NomTotal] = []
    par_division: list[NomTotal] = []
    par_auteur: list[NomTotal] = []
    items: list[ErreurIndexationBrief] = []


class TableauDeBordOut(BaseModel):
    niveau: Literal["ROOT", "SERVICE", "DIVISION", "AGENT"]
    titre: str
    sous_titre: str | None = None
    indicateurs: list[Indicateur]
    repartition: Repartition | None = None
    alertes: list[str] = []
    a_affecter: list[FichierBrief] = []
    erreurs_indexation: ErreursIndexation | None = None
    derniers_changements: list[HistoriqueOut] = []
    mes_roles: list[RoleDivisionBrief] = []
    mes_fichiers: list[FichierBrief] = []
    acces_ponctuels: list[AccesPonctuelBrief] = []
