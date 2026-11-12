"""Tests de la chaîne RAG : réponse sourcée, cas « je ne sais pas »."""

from app.prompts.templates import NO_ANSWER, format_context
from app.services.chat import rag_chain
from app.services.chat.streaming import event_stream, sse
from app.services.retrieval.similarity_search import RetrievedChunk


def _chunk(i=1, page=3, text="Le délai de paiement est de 30 jours."):
    return RetrievedChunk(chunk_id=i, document_id=10 + i, titre="Contrat A", page=page, contenu=text, est_tableau=False)


def test_sans_contexte_le_llm_n_est_pas_appele(monkeypatch):
    def boom():
        raise AssertionError("le LLM ne doit pas être appelé sans contexte")

    monkeypatch.setattr(rag_chain, "get_llm", boom)
    out = "".join(rag_chain.stream_answer(rag_chain.Prepared("Quel est le délai ?", [])))
    assert out == NO_ANSWER and out.lower().startswith("je ne sais pas")


def test_sources_numerotees_et_extrait_court():
    prepared = rag_chain.Prepared("q", [_chunk(1, text="x " * 500), _chunk(2, page=None)])
    sources = prepared.sources()
    assert [s["ref"] for s in sources] == [1, 2]
    assert sources[0]["titre"] == "Contrat A" and sources[0]["page"] == 3
    assert len(sources[0]["extrait"]) <= rag_chain.EXTRACT_CHARS
    assert sources[1]["page"] is None


def test_contexte_du_prompt_contient_refs_et_pages():
    ctx = format_context([(1, "Contrat A", 3, "Texte un"), (2, "Note", None, "Texte deux")])
    assert "[1] (Contrat A, page 3)\nTexte un" in ctx and "[2] (Note)\nTexte deux" in ctx


def test_flux_sse_sans_contexte_ne_declenche_pas_d_erreur_et_garde_l_ordre(monkeypatch):
    saved = {}

    class FakeDb:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def add(self, m): saved["msg"] = m
        def commit(self): saved["msg"].id = 99

    monkeypatch.setattr("app.services.chat.streaming.SessionLocal", FakeDb)
    events = list(event_stream(rag_chain.Prepared("q", []), conversation_id=5))
    names = [e.split("\n")[0] for e in events]
    assert names == ["event: meta", "event: sources", "event: token", "event: done"]
    assert saved["msg"].contenu == NO_ANSWER and saved["msg"].sources == []


def test_sse_encode_les_retours_a_la_ligne():
    assert sse("token", {"t": "a\nb"}) == 'event: token\ndata: {"t": "a\\nb"}\n\n'
