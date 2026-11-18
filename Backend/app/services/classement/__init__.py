"""Moteur de classement des documents.

Le package expose deux blocs de logique :
- le moteur purement fonctionnel `evaluer_regles` ;
- l’application des règles sur un document réel dans la base.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from app.db.metier import DocumentTag, RegleClassement, Tag
from app.services.classement.moteur import _eval_critere, evaluer_regles


def _criteres_rule(rule: Any) -> list[dict[str, Any]]:
    critere = getattr(rule, "critere", None)
    if critere is None:
        return []
    if isinstance(critere, list):
        return [c for c in critere if isinstance(c, dict)]
    if isinstance(critere, dict):
        valeurs: list[dict[str, Any]] = []
        for value in critere.values():
            if isinstance(value, list):
                valeurs.extend([item for item in value if isinstance(item, dict)])
            elif isinstance(value, dict):
                valeurs.append(value)
        return valeurs or [critere]
    return [{"champ": "texte", "op": "regex", "valeur": str(critere)}]


def _normaliser_tags(tags: Any) -> list[str]:
    out: list[str] = []
    for tag in tags or []:
        value = str(tag).strip().lower()
        if value and value not in out:
            out.append(value)
    return out


def _regle_gagnante(regles: list[dict[str, Any]], contexte: dict[str, Any]) -> tuple[int | None, dict[str, Any] | None]:
    if not regles:
        return None, None

    matches: list[tuple[int, dict[str, Any]]] = []
    for regle in regles:
        criteres = regle.get("criteres") or regle.get("critere") or regle.get("conditions") or []
        if not isinstance(criteres, list):
            criteres = [criteres]
        if not criteres:
            continue
        if all(_eval_critere(critere, contexte) for critere in criteres if isinstance(critere, dict)):
            matches.append((int(regle.get("priorite", 9999)), regle))

    if not matches:
        return None, None

    _, winning_rule = min(matches, key=lambda item: item[0])
    return int(winning_rule.get("_rule_id", 0) or 0), winning_rule


def definir_classement_manuel(
    db,
    doc,
    *,
    categorie_id: int | None = None,
    type_document_id: int | None = None,
    tags: list[str] | None = None,
    confidentialite: str | None = None,
) -> None:
    """Applique un classement manuel sans supprimer les tags automatiques déjà présents."""
    if categorie_id is not None:
        doc.categorie_id = categorie_id
    if type_document_id is not None:
        doc.type_document_id = type_document_id
    if confidentialite is not None:
        doc.confidentialite = confidentialite
    doc.classement_source = "manuel"
    doc.regle_id = None

    if tags is not None:
        db.query(DocumentTag).filter(DocumentTag.document_id == doc.id, DocumentTag.source == "manuel").delete()
        for tag_name in _normaliser_tags(tags):
            tag = db.query(Tag).filter(Tag.nom == tag_name).first()
            if tag is None:
                tag = Tag(nom=tag_name)
                db.add(tag)
                db.flush()
            if db.query(DocumentTag).filter(DocumentTag.document_id == doc.id, DocumentTag.tag_id == tag.id).first() is None:
                db.add(DocumentTag(document_id=doc.id, tag_id=tag.id, source="manuel"))


def appliquer(db, doc, version, texte: str) -> None:
    """Applique un classement automatique à un document, sans écraser un classement manuel.

    L’algorithme suit la stratégie du plan GED :
    - on récupère les règles actives triées par priorité ;
    - on évalue le contexte (nom, extension, texte, service, taille, pages, OCR) ;
    - on met à jour le document et ses tags auto ;
    - on laisse le flag `classement_source = 'manuel'` empêcher toute écriture automatique.
    """
    if getattr(doc, "classement_source", "aucun") == "manuel":
        return

    contexte = {
        "service_createur_id": getattr(doc, "cree_par_service_id", None),
        "extension": (Path(getattr(version, "nom_fichier", "")).suffix or "").lstrip("."),
        "nom_fichier": getattr(version, "nom_fichier", ""),
        "texte": texte,
        "taille_octets": getattr(version, "taille_octets", None),
        "nb_pages": getattr(version, "nb_pages", None),
        "ocr_utilise": getattr(version, "ocr_utilise", False),
    }

    regles_db = (
        db.query(RegleClassement)
        .filter(RegleClassement.actif.is_(True))
        .order_by(RegleClassement.priorite.asc(), RegleClassement.id.asc())
        .all()
    )
    regles = []
    for regle in regles_db:
        regles.append(
            {
                "_rule_id": regle.id,
                "nom": regle.nom,
                "priorite": regle.priorite,
                "categorie_id": regle.categorie_id,
                "type_document_id": regle.type_document_id,
                "tags": list(regle.tags or []),
                "confidentialite": regle.confidentialite,
                "criteres": _criteres_rule(regle),
            }
        )

    result = evaluer_regles(regles, contexte)
    if not any(
        value is not None
        for value in (result.get("categorie_id"), result.get("type_document_id"), result.get("confidentialite"))
    ) and not result.get("tags"):
        doc.classement_source = "aucun"
        doc.regle_id = None
        return

    win_id, _ = _regle_gagnante(regles, contexte)
    doc.categorie_id = result.get("categorie_id")
    doc.type_document_id = result.get("type_document_id")
    doc.confidentialite = result.get("confidentialite") or getattr(doc, "confidentialite", "INTERNE")
    doc.classement_source = "regle"
    doc.regle_id = win_id

    db.query(DocumentTag).filter(DocumentTag.document_id == doc.id, DocumentTag.source == "regle").delete()
    for tag_name in _normaliser_tags(result.get("tags") or []):
        tag = db.query(Tag).filter(Tag.nom == tag_name).first()
        if tag is None:
            tag = Tag(nom=tag_name)
            db.add(tag)
            db.flush()
        existing = db.query(DocumentTag).filter(DocumentTag.document_id == doc.id, DocumentTag.tag_id == tag.id).first()
        if existing is not None and existing.source == "manuel":
            continue
        if existing is None:
            db.add(DocumentTag(document_id=doc.id, tag_id=tag.id, source="regle"))
        else:
            existing.source = "regle"

    db.commit()


def reclasser_documents(db, document_ids: list[int]) -> tuple[int, list[int]]:
    """Relance le classement automatique sur une liste de documents et renvoie (succès, ids traités)."""
    from app.db.vecteur import Document

    traites: list[int] = []
    for document_id in document_ids:
        doc = db.get(Document, document_id)
        if doc is None or not doc.versions:
            continue
        latest = doc.versions[-1]
        chunks = db.query("Chunk").filter_by(document_version_id=latest.id).all() if False else []
        texte = "\n".join(chunk.contenu for chunk in chunks)[:20_000] if chunks else ""
        appliquer(db, doc, latest, texte)
        traites.append(document_id)
    return len(traites), traites


def charger_noms(db) -> dict[str, dict[int, dict[str, Any]]]:
    """Noms (et couleurs) des entités citées par les statistiques, pour que l'interface affiche des libellés et non des numéros."""
    from sqlalchemy import select

    from app.db.metier import Categorie, Direction, Service, TypeDocument

    def table(*columns):
        return {row[0]: {"nom": row[1], "couleur": row[2] if len(row) > 2 else None} for row in db.execute(select(*columns)).all()}

    return {
        "categorie": table(Categorie.id, Categorie.nom, Categorie.couleur),
        "type": table(TypeDocument.id, TypeDocument.nom),
        "service": table(Service.id, Service.nom),
        "direction": table(Direction.id, Direction.nom),
    }


def build_dashboard_stats(rows: list[dict[str, Any]], noms: dict[str, dict[int, dict[str, Any]]] | None = None) -> dict[str, Any]:
    """Construit les métriques de tableau de bord à partir d'une liste de lignes de vue stats.

    `noms` (voir charger_noms) ajoute un libellé « nom » (et « couleur » pour les catégories) à chaque ligne groupée.
    """
    noms = noms or {}
    statut = {"pending": 0, "processing": 0, "ready": 0, "error": 0}
    groupes: dict[str, defaultdict[int, int]] = {k: defaultdict(int) for k in ("categorie", "type", "service", "direction")}
    par_confidentialite: defaultdict[str, int] = defaultdict(int)
    par_extension: defaultdict[str, int] = defaultdict(int)
    total_documents = actifs = corbeille = sans_classement = 0
    stockage = versions = 0

    for row in rows:
        total_documents += 1
        key = str(row.get("statut") or "pending").lower()
        statut[key] = statut.get(key, 0) + 1

        if row.get("corbeille_le") is None:
            actifs += 1
        else:
            corbeille += 1

        stockage += int(row.get("taille_octets") or 0)
        versions += int(row.get("nb_versions") or 1)

        for groupe, champ in (("categorie", "categorie_id"), ("type", "type_document_id"), ("service", "service_id"),
                              ("direction", "direction_id")):
            valeur = row.get(champ)
            if valeur is not None:
                groupes[groupe][int(valeur)] += 1
        if row.get("categorie_id") is None and row.get("type_document_id") is None:
            sans_classement += 1

        par_confidentialite[str(row.get("confidentialite") or "INCONNU")] += 1
        par_extension[str(row.get("extension") or "inconnu").lower()] += 1

    def lignes(groupe: str, champ: str) -> list[dict[str, Any]]:
        out = []
        for ident, total in sorted(groupes[groupe].items(), key=lambda item: (-item[1], item[0])):
            info = noms.get(groupe, {}).get(ident, {})
            ligne = {champ: ident, "total": total, "nom": info.get("nom")}
            if groupe == "categorie":
                ligne["couleur"] = info.get("couleur")
            out.append(ligne)
        return out

    return {
        "total_documents": total_documents,
        "actifs": actifs,
        "corbeille": corbeille,
        "sans_classement": sans_classement,
        "stockage_octets": stockage,
        "nb_versions": versions,
        "statut": dict(sorted(statut.items())),
        "par_categorie": lignes("categorie", "categorie_id"),
        "par_type": lignes("type", "type_document_id"),
        "par_confidentialite": dict(sorted(par_confidentialite.items())),
        "par_extension": dict(sorted(par_extension.items())),
        "par_service": lignes("service", "service_id"),
        "par_direction": lignes("direction", "direction_id"),
    }
