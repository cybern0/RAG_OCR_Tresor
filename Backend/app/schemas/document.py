"""Schémas Pydantic des fichiers (documents) et de leurs versions : métadonnées, historique daté, statut d'ingestion.

Le contenu d'un fichier n'est jamais renvoyé par ces schémas : il passe par les routes d'aperçu et de téléchargement,
protégées par les affectations du fichier (l'accès se demande au chef).
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Statut = Literal["pending", "processing", "ready", "error"]
# comment l'aperçu d'une version est produit : direct dans le navigateur, ou pas disponible
ApercuMode = Literal["pdf", "image", "texte", "csv", "pdf_converti", "aucun"]


class AffectationBrief(BaseModel):
    """Agent affecté manuellement à un fichier (c'est lui, pas son rôle, qui décide de l'accès en lecture)."""

    id: int  # id de l'agent
    nom: str
    prenom: str
    matricule: str | None = None


class AgentFiltreOut(BaseModel):
    """Agent proposé dans le filtre « affecté à » de la liste des fichiers, avec sa division
    (un chef de service filtre parmi les agents de plusieurs divisions)."""

    id: int
    nom: str
    prenom: str
    division_id: int
    division_nom: str | None


class FiltresOut(BaseModel):
    """Options des filtres de la liste des fichiers selon le périmètre du compte."""

    agents: list[AgentFiltreOut] = []
    divisions: list[dict] = []  # {id, nom}
    depot_divisions: list[int] = []


class AffectationsDocumentIn(BaseModel):
    agent_ids: list[int] = Field(max_length=200)
    motif: str | None = Field(default=None, max_length=500)


class VersionOut(BaseModel):
    numero: int
    nom_fichier: str
    type_mime: str | None
    taille_octets: int | None
    nb_pages: int | None
    ocr_utilise: bool
    statut: Statut
    message_erreur: str | None
    cree_par_nom: str | None
    cree_le: datetime  # la date de la version
    est_courante: bool  # version prête la plus récente : celle qui fait foi
    apercu: ApercuMode
    # paramètres de la dernière indexation réussie (None : inconnu) : l'interface en déduit si réindexer a un sens
    tableaux_indexes: bool | None = None
    images_indexes: bool | None = None


class DocumentOut(BaseModel):
    id: int
    titre: str
    division_id: int
    division_nom: str
    has_tabular: bool
    has_image: bool
    # cases imposées par le type de la version la plus récente (cochées et non modifiables dans l'interface)
    tableaux_imposes: bool
    images_imposees: bool
    nb_versions: int
    version: VersionOut  # la version la plus récente (tous statuts), pour suivre l'indexation
    mon_role: str  # GERANT | AUTEUR | LECTEUR
    droits: list[str] = []  # actions permises par ce rôle (voir core/acces.py)
    affectations: list[AffectationBrief] = []  # agents affectés manuellement : eux (et l'auteur) lisent le fichier
    a_affecter: bool = False  # aucune affectation : accès refusé par défaut, le chef (et l'auteur) le voit
    cree_par_nom: str | None
    cree_le: datetime
    modifie_le: datetime
    # classement documentaire
    categorie_id: int | None = None
    categorie_nom: str | None = None
    type_document_id: int | None = None
    type_nom: str | None = None
    confidentialite: str = "INTERNE"
    tags: list[str] = []
    classement_source: str = "aucun"
    corbeille_le: datetime | None = None


class DocumentPageOut(BaseModel):
    items: list[DocumentOut]
    total: int
    page: int
    taille: int


class CommentaireIn(BaseModel):
    contenu: str
    parent_id: int | None = None


class FavoriIn(BaseModel):
    entity_type: str = "document"


Confidentialite = Literal["PUBLIC", "INTERNE", "CONFIDENTIEL"]


class ClasserLotIn(BaseModel):
    """Classement manuel d'un ou plusieurs fichiers : seuls les champs fournis sont modifiés."""

    ids: list[int] = Field(min_length=1, max_length=200)
    categorie_id: int | None = None
    type_document_id: int | None = None
    tags: list[str] | None = None
    confidentialite: Confidentialite | None = None


class ClasserLotOut(BaseModel):
    ok: list[int]
    not_found: list[int]
    forbidden: list[int]
