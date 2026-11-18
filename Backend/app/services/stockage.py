"""Stockage physique des fichiers déposés : UN SEUL emplacement, géré par l'application.

Refonte (docs/refonte_classes.md) : tous les fichiers vivent à plat dans upload_dir, sous un nom
généré (uuid4 + extension), jamais le nom fourni par le client. Plus d'arborescence par division ou
à plat sur le disque : la division, la classe et les rôles d'un fichier sont des
données de la base et l'application contrôle seule l'accès — aucun partage système ne dépend du
chemin. Les dépôts anciens (upload_dir/<division>/<dossier>/...) restent lisibles :
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


def trouver(chemin_enregistre: str | Path) -> Path | None:
    """Retrouve sur le disque le fichier dont le chemin est enregistré en base, ou None s'il est introuvable.

    Un chemin relatif est cherché sous upload_dir. En dernier recours, le NOM du fichier est cherché à plat dans
    upload_dir : cela couvre une base importée d'une autre machine ou un projet déplacé (chemin absolu périmé).
    Le résultat reste toujours sous upload_dir : aucun chemin extérieur n'est jamais renvoyé.
    """
    brut = Path(chemin_enregistre)
    racine = get_settings().upload_dir.resolve()
    candidats: list[Path] = [brut] if brut.is_absolute() else [
        racine / brut, Path.cwd() / brut, racine.parent / brut,
    ]
    nom = str(chemin_enregistre).replace("\\", "/").rsplit("/", 1)[-1]
    if nom:
        candidats.append(racine / nom)
    for candidat in candidats:
        try:
            resolu = candidat.resolve(strict=False)
            resolu.relative_to(racine)
        except (OSError, ValueError):
            continue
        if resolu.is_file():
            return resolu
    return None
