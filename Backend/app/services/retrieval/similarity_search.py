"""Recherche des chunks les plus proches dans pgvector, avec filtres sur les métadonnées : document, service, droits.

Similarité : produit scalaire via l'opérateur <#> (qui renvoie le produit scalaire NÉGATIF, donc ORDER BY croissant),
servi par l'index HNSW vector_ip_ops. Les embeddings étant tous normalisés (norme 1), le produit scalaire donne
exactement le même classement que le cosinus. Le vecteur de la question est revérifié ici avant la requête.

Recherche hybride : les meilleurs chunks par similarité vectorielle et par plein texte français
(sigles, numéros, noms propres que les embeddings captent mal) sont fusionnés par Reciprocal Rank Fusion.
Seuls les documents « ready » des services autorisés sont interrogés.
"""

import re
from dataclasses import dataclass

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.db.vecteur import Chunk, Document
from app.services.ingestion.embedding import assert_unit

RRF_K = 60
_WORD = re.compile(r"[^\W_]{3,}", re.UNICODE)


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: int
    document_id: int
    titre: str
    page: int | None
    contenu: str
    est_tableau: bool


def _base(service_ids: list[int] | None):
    stmt = (
        select(Chunk.id, Chunk.document_id, Document.titre, Chunk.page, Chunk.contenu, Chunk.est_tableau)
        .join(Document, Document.id == Chunk.document_id)
        .where(Document.statut == "ready")
    )
    if service_ids is not None:
        stmt = stmt.where(Document.service_id.in_(service_ids))
    return stmt


def search_chunks(
    db: Session,
    query_embedding: list[float],
    query_text: str,
    service_ids: list[int] | None,
    k: int = 5,
    document_id: int | None = None,
) -> list[RetrievedChunk]:
    """service_ids=None : tous les services ; liste vide : aucun résultat."""
    if service_ids is not None and not service_ids:
        return []
    assert_unit(query_embedding, "embedding de la question")  # <#> ne vaut le cosinus que si la norme est 1
    pool = max(k * 4, 20)

    db.execute(text("SET LOCAL hnsw.ef_search = 100"))  # meilleur rappel quand le filtre par service est sélectif

    vec_stmt = _base(service_ids).order_by(Chunk.embedding.max_inner_product(query_embedding)).limit(pool)
    if document_id is not None:
        vec_stmt = vec_stmt.where(Chunk.document_id == document_id)
    vector_rows = db.execute(vec_stmt).all()

    words = list(dict.fromkeys(w.lower() for w in _WORD.findall(query_text)))[:12]
    text_rows = []
    if words:
        tsquery = func.to_tsquery("french", " | ".join(words))  # mots issus de [^\W_] : sans caractère spécial
        ft_stmt = (
            _base(service_ids)
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
    best = sorted(scores, key=scores.__getitem__, reverse=True)[:k]
    return [
        RetrievedChunk(r.id, r.document_id, r.titre, r.page, r.contenu, r.est_tableau)
        for r in (rows_by_id[i] for i in best)
    ]
