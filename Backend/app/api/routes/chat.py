"""Route de chat : reçoit la question et renvoie la réponse en streaming (SSE), avec les sources citées.
La recherche est limitée aux documents du service de l'utilisateur (tous les services pour l'ADMIN)."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require
from app.core.permissions import CHAT_UTILISER, Principal
from app.db.metier import Conversation, Message
from app.schemas.chat import ChatIn, ConversationOut, MessageOut
from app.services.chat import rag_chain
from app.services.chat.streaming import event_stream

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])


def _own_conversation(db: Session, principal: Principal, conversation_id: int) -> Conversation:
    conv = db.get(Conversation, conversation_id)
    if conv is None or conv.user_id != principal.user.id:  # les conversations sont strictement personnelles
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation introuvable.")
    return conv


@router.post("")
def ask(data: ChatIn, principal: Principal = Depends(require(CHAT_UTILISER)), db: Session = Depends(get_db)):
    ids = principal.chat_service_ids()
    if ids is not None and not ids:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Votre compte n'est rattaché à aucun service.")

    if data.conversation_id is not None:
        conv = _own_conversation(db, principal, data.conversation_id)
    else:
        conv = Conversation(user_id=principal.user.id, titre=" ".join(data.question.split())[:80])
        db.add(conv)
        db.flush()
    db.add(Message(conversation_id=conv.id, emetteur="utilisateur", contenu=data.question, sources=[]))
    db.commit()

    try:
        prepared = rag_chain.prepare(db, principal, data.question)
    except Exception:  # noqa: BLE001
        logger.exception("Recherche impossible")
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "La recherche a échoué : vérifier qu'Ollama est démarré."
        ) from None

    return StreamingResponse(
        event_stream(prepared, conv.id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/conversations", response_model=list[ConversationOut])
def list_conversations(principal: Principal = Depends(require(CHAT_UTILISER)), db: Session = Depends(get_db)):
    return list(
        db.scalars(
            select(Conversation).where(Conversation.user_id == principal.user.id)
            .order_by(Conversation.cree_le.desc(), Conversation.id.desc()).limit(50)
        )
    )


@router.get("/conversations/{conversation_id}", response_model=list[MessageOut])
def get_messages(
    conversation_id: int, principal: Principal = Depends(require(CHAT_UTILISER)), db: Session = Depends(get_db)
):
    _own_conversation(db, principal, conversation_id)
    return list(
        db.scalars(
            select(Message).where(Message.conversation_id == conversation_id).order_by(Message.id)
        )
    )


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(
    conversation_id: int, principal: Principal = Depends(require(CHAT_UTILISER)), db: Session = Depends(get_db)
) -> Response:
    db.delete(_own_conversation(db, principal, conversation_id))
    db.commit()
    return Response(status_code=204)
