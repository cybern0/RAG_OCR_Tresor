"""Tests de la normalisation des embeddings et de l'opérateur de recherche."""

import math

import pytest

from app.db.vecteur import Chunk
from app.services.ingestion import embedding
from app.services.ingestion.embedding import (
    EmbeddingError, assert_unit, embed_documents, embed_query, normalize, norm,
)
from app.services.retrieval.similarity_search import search_chunks

from .conftest import FakeEmbeddings


@pytest.fixture
def fake_model(monkeypatch):
    monkeypatch.setattr(embedding, "get_embeddings", lambda: FakeEmbeddings())


def test_normalize_donne_une_norme_de_1():
    v = normalize([3.0, 4.0])
    assert v == pytest.approx([0.6, 0.8]) and norm(v) == pytest.approx(1.0, abs=1e-12)
    assert normalize(normalize([5.0, 1.0, 2.0])) == pytest.approx(normalize([5.0, 1.0, 2.0]))  # idempotent


@pytest.mark.parametrize("bad", [[0.0, 0.0], [1.0, math.nan], [math.inf, 1.0]])
def test_normalize_refuse_un_vecteur_non_normalisable(bad):
    with pytest.raises(EmbeddingError):
        normalize(bad)


def test_assert_unit():
    assert_unit([0.6, 0.8])
    for bad in ([3.0, 4.0], [0.0, 0.0], [0.6, 0.81]):
        with pytest.raises(EmbeddingError):
            assert_unit(bad)


def test_le_modele_renvoie_du_non_normalise_le_backend_normalise(fake_model):
    assert norm(FakeEmbeddings().embed_query("test")) == pytest.approx(3.7)   # le modèle simulé n'est pas normalisé
    docs = embed_documents([f"passage numéro {i} du Trésor" for i in range(40)])  # 40 > BATCH_SIZE : plusieurs lots
    assert len(docs) == 40
    assert all(abs(norm(v) - 1.0) <= 1e-6 for v in docs)      # aucun vecteur n'échappe à la normalisation
    assert abs(norm(embed_query("quel est le délai ?")) - 1.0) <= 1e-6


def test_dimension_incorrecte_refusee(monkeypatch):
    class Short:
        def embed_documents(self, texts): return [[1.0, 2.0]] * len(texts)
        def embed_query(self, text): return [1.0, 2.0]

    monkeypatch.setattr(embedding, "get_embeddings", lambda: Short())
    with pytest.raises(EmbeddingError, match="dimensions"):
        embed_documents(["a"])


def test_vecteur_nul_refuse_a_l_indexation(monkeypatch):
    class Zero:
        def embed_documents(self, texts): return [[0.0] * 768] * len(texts)

    monkeypatch.setattr(embedding, "get_embeddings", lambda: Zero())
    with pytest.raises(EmbeddingError):
        embed_documents(["a"])


def test_la_recherche_refuse_une_question_non_normalisee():
    # le contrôle précède tout accès à la base : db=None suffit
    with pytest.raises(EmbeddingError, match="non normalisé"):
        search_chunks(None, [3.0] * 768, "question", dossier_ids=[1])


def test_la_requete_utilise_le_produit_scalaire():
    sql = str(Chunk.embedding.max_inner_product([0.1] * 768).compile(compile_kwargs={"literal_binds": False}))
    assert "<#>" in sql and "<=>" not in sql
