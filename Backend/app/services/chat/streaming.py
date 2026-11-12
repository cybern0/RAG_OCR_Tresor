"""Génération de la réponse en streaming (token par token) pour le chatbot de l'interface.

Format : Server-Sent Events. Événements, dans l'ordre :
  meta    {conversation_id}
  sources [{ref, document_id, titre, page, extrait}, ...]
  token   {t: "texte"}        (répété)
  done    {message_id}
  error   {detail}            (à la place de done si la génération échoue)
"""

import json
import logging
from collections.abc import Iterator

from app.db.metier import Message, SessionLocal
from app.services.chat.rag_chain import Prepared, stream_answer

logger = logging.getLogger(__name__)


def sse(event: str, data: object) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def event_stream(prepared: Prepared, conversation_id: int) -> Iterator[str]:
    sources = prepared.sources() if prepared.has_context else []
    yield sse("meta", {"conversation_id": conversation_id})
    yield sse("sources", sources)
    parts: list[str] = []
    try:
        for token in stream_answer(prepared):
            parts.append(token)
            yield sse("token", {"t": token})
    except Exception:  # noqa: BLE001 - on prévient le client plutôt que de couper le flux net
        logger.exception("Échec de la génération")
        yield sse("error", {"detail": "La génération a échoué : vérifier qu'Ollama est démarré."})
        return
    # session propre : celle de la requête est déjà fermée quand le flux se termine
    with SessionLocal() as db:
        message = Message(
            conversation_id=conversation_id, emetteur="assistant", contenu="".join(parts).strip(), sources=sources
        )
        db.add(message)
        db.commit()
        yield sse("done", {"message_id": message.id})
