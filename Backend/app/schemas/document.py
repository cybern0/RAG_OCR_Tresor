"""Schémas Pydantic des fichiers (documents) et de leurs versions : métadonnées, historique daté, statut d'ingestion.

Le contenu d'un fichier n'est jamais renvoyé par ces schémas : il passe par les routes d'aperçu et de téléchargement,
protégées par les rôles de classement du fichier.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Statut = Literal["pending", "processing", "ready", "error"]
# comment l'aperçu d'une version est produit : direct dans le navigateur, ou pas disponible
ApercuMode = Literal["pdf", "image", "texte", "csv", "pdf_converti", "aucun"]


class RoleBrief(BaseModel):
    id: int
    code: str
    libelle: str


class RoleFiltreOut(RoleBrief):
    """Rôle proposé dans le filtre de la liste des fichiers, avec sa division (un chef de service
    filtre parmi les rôles de plusieurs divisions)."""

    division_id: int
    division_nom: str | None


class FiltresOut(BaseModel):
    """Options des filtres de la liste des fichiers selon le périmètre du compte."""

    roles: list[RoleFiltreOut] = []
    divisions: list[dict] = []  # {id, nom}
    depot_divisions: list[int] = []


class RolesDocumentIn(BaseModel):
    role_ids: list[int] = Field(max_length=50)
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
    roles: list[RoleBrief] = []  # rôles de la division qui donnent accès au fichier
    a_classer: bool = False  # aucun rôle : accès refusé par défaut, seul le gérant (et l'auteur) le voit
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


class DocumentLienPartageIn(BaseModel):
    role: str = "LECTEUR"
    expire_le: datetime | None = None
    est_anonyme: bool = True
    token: str | None = None


class DocumentLienPartageOut(BaseModel):
    id: int
    document_id: int
    role: str
    est_anonyme: bool = True
    expire_le: datetime | None = None
    token_hash: str | None = None
    token: str | None = None
    cree_le: datetime


class PartageRequestIn(BaseModel):
    requested_role: str = "LECTEUR"
    message: str = ""


class AccessRequestDecisionIn(BaseModel):
    decision: str
    granted_role: str | None = None
    message: str | None = None


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
