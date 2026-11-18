"""Moteur de règles de classement déterministe.

Le moteur est purement fonctionnel : il n'écrit ni ne lit la base, et il s'appuie sur
un contexte de document déjà connu (nom, extension, texte, etc.).
"""

from __future__ import annotations

import re
from typing import Any

MAX_REGEX_LEN = 256
MAX_TEXTE_ANALYSE = 20000


def _normaliser_tags(tags: Any) -> list[str]:
    if tags is None:
        return []
    values = [str(tag).strip().lower() for tag in tags if str(tag).strip()]
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out


def _valider_regex(pattern: str) -> str:
    if not isinstance(pattern, str):
        raise ValueError("Une expression régulière de classement doit être une chaîne de caractères.")
    if len(pattern) > MAX_REGEX_LEN:
        raise ValueError(f"Expression régulière trop longue ({len(pattern)} > {MAX_REGEX_LEN}).")
    try:
        re.compile(pattern)
    except re.error as exc:  # pragma: no cover - couvert par test direct
        raise ValueError(f"Expression régulière invalide : {exc}") from exc
    return pattern


def _champ(contexte: dict[str, Any], champ: str) -> Any:
    if champ == "texte":
        texte = str(contexte.get("texte") or "")
        return texte[:MAX_TEXTE_ANALYSE]
    if champ == "nom_fichier":
        return str(contexte.get("nom_fichier") or "")
    if champ == "extension":
        value = str(contexte.get("extension") or "")
        return value.lower().lstrip('.')
    return contexte.get(champ)


def _eval_critere(critere: dict[str, Any], contexte: dict[str, Any]) -> bool:
    if not isinstance(critere, dict):
        return False
    champ = critere.get("champ")
    op = critere.get("op")
    valeur = critere.get("valeur")
    if not champ or not op:
        return False

    left = _champ(contexte, champ)
    if op == "=":
        return left == valeur
    if op == "dans":
        if not isinstance(valeur, (list, tuple, set)):
            return False
        return left in {str(v).lower() for v in valeur}
    if op == "contient_un_de":
        if not isinstance(valeur, (list, tuple, set)):
            return False
        text = str(left).lower()
        return any(needle.lower() in text for needle in [str(v) for v in valeur])
    if op == "regex":
        pattern = _valider_regex(str(valeur))
        if left is None:
            return False
        return re.search(pattern, str(left), flags=re.IGNORECASE) is not None
    return False


def _as_rule_list(regles: list[dict[str, Any]] | dict[str, Any] | None) -> list[dict[str, Any]]:
    if regles is None:
        return []
    if isinstance(regles, dict):
        flat: list[dict[str, Any]] = []
        for group in regles.values():
            if isinstance(group, list):
                flat.extend(group)
        return flat
    if isinstance(regles, list):
        return regles
    raise TypeError("Les règles doivent être une liste ou un dictionnaire de groupes.")


def evaluer_regles(regles: list[dict[str, Any]] | dict[str, Any] | None, contexte: dict[str, Any]) -> dict[str, Any]:
    """Évalue les règles dans l'ordre de priorité croissante, la première règle qui correspond gagne.

    Retourne un dictionnaire de forme :
    {
        'categorie_id': ...,
        'type_document_id': ...,
        'tags': [...],
        'confidentialite': ...,
    }
    """
    if contexte.get("classement_source") == "manuel":
        return {"categorie_id": None, "type_document_id": None, "tags": [], "confidentialite": None}

    candidates = []
    for idx, regle in enumerate(_as_rule_list(regles)):
        criteres = regle.get("criteres") or regle.get("critere") or regle.get("conditions") or []
        if not isinstance(criteres, list):
            criteres = [criteres]
        if all(_eval_critere(c, contexte) for c in criteres):
            candidates.append(regle)

    if not candidates:
        return {"categorie_id": None, "type_document_id": None, "tags": [], "confidentialite": None}

    gagnante = min(candidates, key=lambda item: int(item.get("priorite", 9999)))
    tags = []
    for regle in candidates:
        tags.extend(_normaliser_tags(regle.get("tags") or []))

    result = {
        "categorie_id": gagnante.get("categorie_id"),
        "type_document_id": gagnante.get("type_document_id"),
        "tags": _normaliser_tags(tags),
        "confidentialite": gagnante.get("confidentialite"),
    }
    return result
