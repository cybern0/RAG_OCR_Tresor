"""Calcul des embeddings via Ollama, avec les préfixes de tâche d'EmbeddingGemma
(identiques à l'indexation et à la recherche : c'est ce qui rend les vecteurs comparables).

NORMALISATION : tout vecteur (document comme question) est normalisé en norme L2 = 1 puis vérifié avant d'être
utilisé. La recherche emploie le produit scalaire (<#>, index vector_ip_ops), qui ne classe comme le cosinus
que si tous les vecteurs sont unitaires. Trois garde-fous :
  1. ici : normalisation + vérification (`normalize`, `assert_unit`), échec explicite sinon ;
  2. dans la recherche : `assert_unit` sur le vecteur de la question ;
  3. dans Postgres : contrainte ck_chunk_embedding_normalise (database/02).

Le titre du document n'entre pas dans le préfixe (« none ») : renommer un document ne demande donc pas
de réindexation.
"""

import math

from app.clients.ollama import get_embeddings
from app.config import get_settings

DOCUMENT_PREFIX = "title: none | text: "
QUERY_PREFIX = "task: search result | query: "
BATCH_SIZE = 16

# Tolérance après normalisation en float64 : bien plus stricte que celle de la base (0,1 %, float32).
UNIT_TOLERANCE = 1e-6


class EmbeddingError(RuntimeError):
    pass


def norm(vector: list[float]) -> float:
    return math.sqrt(math.fsum(x * x for x in vector))


def normalize(vector: list[float]) -> list[float]:
    """Divise le vecteur par sa norme L2. Refuse un vecteur nul ou contenant NaN/infini (non normalisable)."""
    n = norm(vector)
    if not math.isfinite(n) or n == 0.0:
        raise EmbeddingError("Le modèle d'embeddings a renvoyé un vecteur nul ou invalide : impossible de le normaliser.")
    return [x / n for x in vector]


def assert_unit(vector: list[float], label: str = "vecteur") -> None:
    """Lève une erreur si le vecteur n'est pas de norme 1 (à la tolérance près)."""
    n = norm(vector)
    if not math.isfinite(n) or abs(n - 1.0) > UNIT_TOLERANCE:
        raise EmbeddingError(f"{label} non normalisé (norme = {n}) : la recherche par produit scalaire serait faussée.")


def _check_dim(vectors: list[list[float]]) -> None:
    expected = get_settings().embedding_dim
    for v in vectors:
        if len(v) != expected:
            raise EmbeddingError(
                f"Le modèle d'embeddings renvoie {len(v)} dimensions, la base attend {expected} "
                "(vector(768) dans database/02). Adapter EMBEDDING_DIM et le schéma si le modèle change."
            )


def _prepare(vectors: list[list[float]], label: str) -> list[list[float]]:
    _check_dim(vectors)
    unit = [normalize(v) for v in vectors]
    for v in unit:
        assert_unit(v, label)  # aucun vecteur ne sort d'ici sans avoir été vérifié
    return unit


def embed_documents(texts: list[str]) -> list[list[float]]:
    model = get_embeddings()
    raw: list[list[float]] = []
    for i in range(0, len(texts), BATCH_SIZE):
        batch = [DOCUMENT_PREFIX + t for t in texts[i : i + BATCH_SIZE]]
        raw.extend(model.embed_documents(batch))
    if len(raw) != len(texts):
        raise EmbeddingError("Le modèle d'embeddings n'a pas renvoyé un vecteur par passage.")
    return _prepare(raw, "embedding de document")


def embed_query(question: str) -> list[float]:
    return _prepare([get_embeddings().embed_query(QUERY_PREFIX + question)], "embedding de la question")[0]
