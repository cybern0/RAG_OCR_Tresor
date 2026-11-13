"""Schémas Pydantic des fichiers (documents) et de leurs versions : métadonnées, historique daté, statut d'ingestion.

Le contenu d'un fichier n'est jamais renvoyé par ces schémas : il passe par les routes d'aperçu et de téléchargement,
protégées par le rôle de dossier.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

Statut = Literal["pending", "processing", "ready", "error"]
# comment l'aperçu d'une version est produit : direct dans le navigateur, ou pas disponible
ApercuMode = Literal["pdf", "image", "texte", "csv", "pdf_converti", "aucun"]


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
    dossier_id: int
    dossier_nom: str
    has_tabular: bool
    has_image: bool
    # cases imposées par le type de la version la plus récente (cochées et non modifiables dans l'interface)
    tableaux_imposes: bool
    images_imposees: bool
    nb_versions: int
    version: VersionOut  # la version la plus récente (tous statuts), pour suivre l'indexation
    mon_role: str
    cree_par_nom: str | None
    cree_le: datetime
    modifie_le: datetime


class DocumentPageOut(BaseModel):
    items: list[DocumentOut]
    total: int
    page: int
    taille: int


class DocumentPartageIn(BaseModel):
    role: str
    user_id: int | None = None
    service_id: int | None = None
    expire_le: datetime | None = None
    is_anonymous: bool = True
    token: str | None = None


class DocumentPartageOut(BaseModel):
    id: int
    document_id: int
    user_id: int | None = None
    service_id: int | None = None
    role: str
    expire_le: datetime | None = None
    is_anonymous: bool = True
    token_hash: str | None = None
    token: str | None = None
    cree_le: datetime


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
