"""Schémas Pydantic des documents : liste de métadonnées et statut d'ingestion.

Jamais de contenu : le contenu d'un document n'est consultable qu'à travers le chat.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

Statut = Literal["pending", "processing", "ready", "error"]


class DocumentOut(BaseModel):
    id: int
    titre: str
    nom_fichier: str
    type_mime: str | None
    taille_octets: int | None
    nb_pages: int | None
    ocr_utilise: bool
    has_tabular: bool
    statut: Statut
    message_erreur: str | None
    service_id: int
    service_nom: str
    cree_par_nom: str | None
    cree_le: datetime
    modifie_le: datetime
