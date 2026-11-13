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
