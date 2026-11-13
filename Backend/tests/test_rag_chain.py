"""Tests de la chaîne RAG : réponse sourcée avec version et date, cas « je ne sais pas », historique masqué par accès,
top-k dynamique."""

from datetime import datetime
from types import SimpleNamespace


from app.prompts.templates import NO_ANSWER, format_context
from app.services.chat import rag_chain
from app.services.chat.streaming import event_stream, sse
from app.services.chat.history import MASQUE, filter_visible
from app.services.retrieval.similarity_search import RetrievedChunk, dynamic_k


def _chunk(i=1, page=3, text="Le délai de paiement est de 30 jours."):
    return RetrievedChunk(
        chunk_id=i, document_id=10 + i, titre="Contrat A", page=page, contenu=text, est_tableau=False,
        dossier_id=7, version=2, date_version=datetime(2026, 11, 12, 9, 0), est_derniere=True, taille_ref=20,
    )


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
    assert sources[0]["dossier_id"] == 7 and sources[0]["version"] == 2 and sources[0]["date"].startswith("2026-11-12")


def test_contexte_du_prompt_contient_refs_et_pages():
    ctx = format_context([(1, "Contrat A", 3, "Texte un"), (2, "Note", None, "Texte deux")])
    assert "[1] (Contrat A, page 3)\nTexte un" in ctx and "[2] (Note)\nTexte deux" in ctx


def test_contexte_indique_version_et_date():
    d = datetime(2026, 11, 12)
    ctx = format_context([(1, "Contrat A", 3, "Texte", 2, d, True), (2, "Contrat A", None, "Ancien", 1, d, False)])
    assert "[1] (Contrat A, version 2 du 12/11/2026 (la plus récente), page 3)" in ctx
    assert "[2] (Contrat A, version 1 du 12/11/2026 (ancienne version))" in ctx


def test_top_k_dynamique_croit_avec_la_taille_des_fichiers_et_reste_borne():
    assert dynamic_k([], 3, 8) == 3
    assert dynamic_k([2, 4, 3], 3, 8) == 3          # petits fichiers : minimum
    assert dynamic_k([25, 25, 30], 3, 8) == 5
    assert dynamic_k([400, 900], 3, 8) == 8         # gros fichiers : maximum
    assert dynamic_k([4, 400, 900, 900, 900], 3, 8) == 8


def test_historique_masque_les_reponses_d_un_dossier_perdu():
    def msg(i, who, sources):
        return SimpleNamespace(id=i, emetteur=who, contenu=f"texte {i}", sources=sources)

    rows = [msg(1, "utilisateur", []), msg(2, "assistant", [{"document_id": 1, "dossier_id": 7}]),
            msg(3, "assistant", [{"document_id": 2, "dossier_id": 8}]), msg(4, "assistant", [])]
    out = filter_visible(None, rows, {7})
    assert [v.masque for v in out] == [False, False, True, False]
    assert out[2].contenu == MASQUE and out[2].sources == [] and out[1].contenu == "texte 2"
    assert all(v.masque for v in filter_visible(None, rows[1:3], set()) if v.message.sources)


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
