"""Chaîne RAG : reformulation de la question de suivi, recherche des chunks, construction du prompt, appel du LLM.

Consigne : répondre en français, uniquement à partir du contexte, sinon dire « je ne sais pas ».
Droits : la recherche ne porte que sur les dossiers que l'utilisateur peut interroger (core/permissions.py) ; l'historique
et la mémoire fournis à la chaîne sont déjà filtrés par ses accès (services/chat/history.py et memoire.py).
Les passages portent leur numéro de version et sa date : le LLM peut ainsi citer l'historique des versions.
"""

import logging
from collections.abc import Iterator
from dataclasses import dataclass, field

from langchain_core.messages import BaseMessage
from langchain_core.output_parsers import StrOutputParser
from sqlalchemy.orm import Session

from app.clients.ollama import get_llm
from app.config import get_settings
from app.core.permissions import Principal, ids_dossiers_interrogeables
from app.prompts.templates import CONDENSE_PROMPT, NO_ANSWER, QA_PROMPT, format_context
from app.services.ingestion.embedding import embed_query
from app.services.retrieval.similarity_search import RetrievedChunk, search_chunks

logger = logging.getLogger(__name__)

EXTRACT_CHARS = 240
STANDALONE_MAX_CHARS = 500


@dataclass
class Prepared:
    question: str
    chunks: list[RetrievedChunk]
    historique: list[BaseMessage] = field(default_factory=list)
    memoire: list[str] = field(default_factory=list)
    question_autonome: str | None = None

    @property
    def has_context(self) -> bool:
        return bool(self.chunks)

    def sources(self) -> list[dict]:
        """Une entrée par passage cité : ref, fichier, dossier, version, date, page, court extrait."""
        return [
            {
                "ref": i,
                "document_id": c.document_id,
                "dossier_id": c.dossier_id,
                "titre": c.titre,
                "version": c.version,
                "date": c.date_version.isoformat() if c.date_version else None,
                "page": c.page,
                "extrait": " ".join(c.contenu.split())[:EXTRACT_CHARS],
            }
            for i, c in enumerate(self.chunks, start=1)
        ]


def condense_question(historique: list[BaseMessage], question: str) -> str:
    """Rend une question de suivi autonome (« et pour l'an dernier ? ») avant la recherche vectorielle.
    En cas d'échec du LLM, on garde la question telle quelle."""
    if not historique:
        return question
    try:
        out = (CONDENSE_PROMPT | get_llm() | StrOutputParser()).invoke({"historique": historique, "question": question})
    except Exception:  # noqa: BLE001
        logger.warning("Reformulation impossible, question gardée telle quelle", exc_info=True)
        return question
    out = " ".join(out.split())[:STANDALONE_MAX_CHARS]
    return out or question


def _within_budget(chunks: list[RetrievedChunk], max_chars: int) -> list[RetrievedChunk]:
    """Garde les meilleurs passages tant que le contexte tient dans la fenêtre du LLM (au moins un)."""
    kept, total = [], 0
    for c in chunks:
        if kept and total + len(c.contenu) > max_chars:
            break
        kept.append(c)
        total += len(c.contenu)
    return kept


def prepare(
    db: Session,
    principal: Principal,
    question: str,
    historique: list[BaseMessage] | None = None,
    memoire: list[str] | None = None,
    derniere_version_seulement: bool = False,
) -> Prepared:
    historique, memoire = historique or [], memoire or []
    dossier_ids = ids_dossiers_interrogeables(db, principal)
    if not dossier_ids:
        return Prepared(question, [], historique, memoire)
    standalone = condense_question(historique, question)
    chunks = search_chunks(
        db, embed_query(standalone), standalone, dossier_ids,
        derniere_version_seulement=derniere_version_seulement,
    )
    chunks = _within_budget(chunks, get_settings().context_max_chars)
    return Prepared(question, chunks, historique, memoire, question_autonome=standalone)


def build_inputs(prepared: Prepared) -> dict:
    passages = [
        (i, c.titre, c.page, c.contenu, c.version, c.date_version, c.est_derniere)
        for i, c in enumerate(prepared.chunks, start=1)
    ]
    return {
        "historique": prepared.historique,
        "memoire": "\n".join(prepared.memoire) or "(aucune)",
        "contexte": format_context(passages),
        "question": prepared.question,
    }


def stream_answer(prepared: Prepared) -> Iterator[str]:
    """Génère la réponse morceau par morceau. Sans contexte, le LLM n'est même pas appelé."""
    if not prepared.has_context:
        yield NO_ANSWER
        return
    chain = QA_PROMPT | get_llm() | StrOutputParser()
    yield from chain.stream(build_inputs(prepared))
