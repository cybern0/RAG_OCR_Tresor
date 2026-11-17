"""Recherche des chunks les plus proches dans pgvector, filtrée par les FICHIERS que le compte peut lire.

Isolation : un seul index partagé ; chaque requête est limitée par la condition SQL core.acces.condition_acces_fichiers (rôles
de la division, auteur, exceptions valides ; le super administrateur lit tout), recalculée à chaque requête. C'est le point de sécurité
principal du RAG : sans condition, aucun résultat. Les fichiers en corbeille et les dossiers archivés ne sont jamais interrogés.

Similarité : produit scalaire via l'opérateur <#> (qui renvoie le produit scalaire NÉGATIF, donc ORDER BY croissant),
servi par l'index HNSW vector_ip_ops. Les embeddings étant tous normalisés (norme 1), le produit scalaire donne
exactement le même classement que le cosinus. Le vecteur de la question est revérifié ici avant la requête.

Recherche hybride : les meilleurs chunks par similarité vectorielle et par plein texte français
(sigles, numéros, noms propres que les embeddings captent mal) sont fusionnés par Reciprocal Rank Fusion.

Versions : toutes les versions « ready » sont interrogeables ; derniere_version_seulement ne garde que la version
la plus récente prête de chaque fichier.

Top-k dynamique : sans k explicite, le nombre de passages renvoyés dépend de la taille des fichiers des meilleurs
candidats (chunk.taille_ref = nombre de chunks de la version), entre retrieval_k_min et retrieval_k_max.
"""

import math
import re
import statistics
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import ColumnElement, func, select, text
from sqlalchemy.orm import Session, aliased

from app.config import get_settings
from app.db.metier import Dossier
from app.db.vecteur import Chunk, Document, DocumentVersion
from app.services.ingestion.embedding import assert_unit

RRF_K = 60
TOP_POUR_TAILLE = 5  # nombre de meilleurs candidats dont la taille de fichier décide du k
_WORD = re.compile(r"[^\W_]{3,}", re.UNICODE)


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: int
    document_id: int
    titre: str
    page: int | None
    contenu: str
    est_tableau: bool
    dossier_id: int | None = None
    version: int | None = None
    date_version: datetime | None = None
    est_derniere: bool = True
    taille_ref: int = 0


def dynamic_k(tailles: list[int], k_min: int, k_max: int) -> int:
    """Plus les fichiers concernés sont gros, plus on remonte de passages : racine carrée du nombre de chunks
    (médiane des meilleurs candidats), bornée. Exemples avec 3 à 8 : 4 chunks -> 3 ; 25 -> 5 ; 64 et plus -> 8."""
    tailles = [t for t in tailles if t > 0]
    if not tailles:
        return k_min
    k = math.ceil(math.sqrt(statistics.median(tailles)))
    return max(k_min, min(k_max, k))


def _base(acces: ColumnElement[bool], derniere_version_seulement: bool):
    latest = aliased(DocumentVersion)
    # numéro de la version prête la plus récente du fichier
    last_ready = (
        select(func.max(latest.numero))
        .where(latest.document_id == DocumentVersion.document_id, latest.statut == "ready")
        .correlate(DocumentVersion)
        .scalar_subquery()
    )
    stmt = (
        select(
            Chunk.id, Chunk.document_id, Document.titre, Chunk.page, Chunk.contenu, Chunk.est_tableau,
            Document.dossier_id, DocumentVersion.numero, DocumentVersion.cree_le,
            (DocumentVersion.numero == last_ready).label("est_derniere"), Chunk.taille_ref,
        )
        .join(Document, Document.id == Chunk.document_id)
        .join(DocumentVersion, DocumentVersion.id == Chunk.document_version_id)
        .join(Dossier, Dossier.id == Document.dossier_id)
        .where(
            DocumentVersion.statut == "ready", acces, Document.corbeille_le.is_(None), Dossier.archive.is_(False),
        )
    )
    if derniere_version_seulement:
        stmt = stmt.where(DocumentVersion.numero == last_ready)
    return stmt


def search_chunks(
    db: Session,
    query_embedding: list[float],
    query_text: str,
    acces: ColumnElement[bool] | None,
    k: int | None = None,
    document_id: int | None = None,
    derniere_version_seulement: bool = False,
) -> list[RetrievedChunk]:
    """acces : condition SQL des fichiers autorisés (core.acces.condition_acces_fichiers) ; None : aucun résultat. k=None : top-k dynamique."""
    if acces is None:
        return []
    assert_unit(query_embedding, "embedding de la question")  # <#> ne vaut le cosinus que si la norme est 1
    settings = get_settings()
    k_max = k if k is not None else settings.retrieval_k_max
    pool = max(k_max * 4, 20)

    db.execute(text("SET LOCAL hnsw.ef_search = 100"))  # meilleur rappel quand le filtre par dossier est sélectif

    vec_stmt = _base(acces, derniere_version_seulement).order_by(
        Chunk.embedding.max_inner_product(query_embedding)
    ).limit(pool)
    if document_id is not None:
        vec_stmt = vec_stmt.where(Chunk.document_id == document_id)
    vector_rows = db.execute(vec_stmt).all()

    words = list(dict.fromkeys(w.lower() for w in _WORD.findall(query_text)))[:12]
    text_rows = []
    if words:
        tsquery = func.to_tsquery("french", " | ".join(words))  # mots issus de [^\W_] : sans caractère spécial
        ft_stmt = (
            _base(acces, derniere_version_seulement)
            .where(Chunk.contenu_tsv.op("@@")(tsquery))
            .order_by(func.ts_rank_cd(Chunk.contenu_tsv, tsquery).desc())
            .limit(pool)
        )
        if document_id is not None:
            ft_stmt = ft_stmt.where(Chunk.document_id == document_id)
        text_rows = db.execute(ft_stmt).all()

    scores: dict[int, float] = {}
    rows_by_id = {}
    for rows in (vector_rows, text_rows):
        for rank, row in enumerate(rows):
            scores[row.id] = scores.get(row.id, 0.0) + 1.0 / (RRF_K + rank + 1)
            rows_by_id[row.id] = row
    ranked = sorted(scores, key=scores.__getitem__, reverse=True)
    if k is None:
        # seuls les fichiers des meilleurs candidats (donc accessibles) décident de k
        k = dynamic_k(
            [rows_by_id[i].taille_ref for i in ranked[:TOP_POUR_TAILLE]],
            settings.retrieval_k_min, settings.retrieval_k_max,
        )
    return [
        RetrievedChunk(
            r.id, r.document_id, r.titre, r.page, r.contenu, r.est_tableau,
            dossier_id=r.dossier_id, version=r.numero, date_version=r.cree_le,
            est_derniere=bool(r.est_derniere), taille_ref=r.taille_ref,
        )
        for r in (rows_by_id[i] for i in ranked[:k])
    ]
