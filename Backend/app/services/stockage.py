"""Stockage physique des fichiers déposés : UN SEUL emplacement, géré par l'application.

Refonte (docs/refonte_classes.md) : tous les fichiers vivent à plat dans upload_dir, sous un nom
généré (uuid4 + extension), jamais le nom fourni par le client. Plus d'arborescence par division ou
par dossier sur le disque : la division, le dossier, la classe et les rôles d'un fichier sont des
données de la base et l'application contrôle seule l'accès — aucun partage système ne dépend du
chemin. Les dépôts anciens (upload_dir/<division>/<dossier>/... ou déjà à plat) restent lisibles :
c'est le chemin enregistré en base (chemin_stockage de document_version) qui fait foi.
"""

import uuid
from pathlib import Path

from app.config import get_settings


def chemin(extension: str) -> Path:
    """Nouveau chemin d'un fichier déposé : à plat dans upload_dir, nom généré (uuid4 + extension)."""
    rep = get_settings().upload_dir
    rep.mkdir(parents=True, exist_ok=True)
    return rep / f"{uuid.uuid4().hex}{extension}"
