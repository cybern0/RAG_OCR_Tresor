"""Chaîne RAG : recherche des chunks, construction du prompt, appel du LLM.
Consigne : répondre en français, uniquement à partir du contexte, sinon dire « je ne sais pas ».
Les droits sont appliqués à la recherche : un utilisateur ne peut obtenir que des passages de son service
(l'ADMIN, de tous les services)."""

from collections.abc import Iterator
from dataclasses import dataclass

from langchain_core.output_parsers import StrOutputParser
from sqlalchemy.orm import Session

from app.clients.ollama import get_llm
from app.config import get_settings
from app.core.permissions import Principal
from app.prompts.templates import NO_ANSWER, QA_PROMPT, format_context
from app.services.ingestion.embedding import embed_query
from app.services.retrieval.similarity_search import RetrievedChunk, search_chunks

EXTRACT_CHARS = 240


@dataclass
class Prepared:
    question: str
    chunks: list[RetrievedChunk]

    @property
    def has_context(self) -> bool:
        return bool(self.chunks)

    def sources(self) -> list[dict]:
        """Une entrée par passage cité : ref, document, page, court extrait."""
        return [
            {
                "ref": i,
                "document_id": c.document_id,
                "titre": c.titre,
                "page": c.page,
                "extrait": " ".join(c.contenu.split())[:EXTRACT_CHARS],
            }
            for i, c in enumerate(self.chunks, start=1)
        ]


def prepare(db: Session, principal: Principal, question: str) -> Prepared:
    service_ids = principal.chat_service_ids()
    if service_ids is not None and not service_ids:
        return Prepared(question, [])
    chunks = search_chunks(db, embed_query(question), question, service_ids, k=get_settings().retrieval_k)
    return Prepared(question, chunks)


def build_inputs(prepared: Prepared) -> dict:
    passages = [(i, c.titre, c.page, c.contenu) for i, c in enumerate(prepared.chunks, start=1)]
    return {"contexte": format_context(passages), "question": prepared.question}


def stream_answer(prepared: Prepared) -> Iterator[str]:
    """Génère la réponse morceau par morceau. Sans contexte, le LLM n'est même pas appelé."""
    if not prepared.has_context:
        yield NO_ANSWER
        return
    chain = QA_PROMPT | get_llm() | StrOutputParser()
    yield from chain.stream(build_inputs(prepared))
