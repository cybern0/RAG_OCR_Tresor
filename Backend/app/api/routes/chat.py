"""Route de chat : reçoit la question et renvoie la réponse en streaming (SSE), avec les sources citées.

- La recherche est limitée aux fichiers que l'utilisateur peut lire (rôles de sa division, ses dépôts, accès ponctuels ;
  le super administrateur n'y entre pas : l'IA est pour les chefs et les agents) : core/acces.py.
- Mémoire dans une session : obligatoire. L'historique de la conversation est relu en base à chaque question, donc il
  se retrouve après une déconnexion/reconnexion.
- Deux options personnelles (GET/PUT /chat/preferences) : mémoire entre sessions, et « dernière version seulement ».
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require
from app.core.acces import condition_acces_fichiers
from app.core.permissions import CHAT_UTILISER, NIVEAU_ROOT, Principal
from app.db.metier import Conversation, Message
from app.schemas.chat import ChatIn, ConversationOut, MessageOut, PreferencesIn, PreferencesOut
from app.services.chat import memoire, rag_chain
from app.services.chat.history import ConversationHistory, filter_visible
from app.services.chat.streaming import event_stream

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])


def _own_conversation(db: Session, principal: Principal, conversation_id: int) -> Conversation:
    conv = db.get(Conversation, conversation_id)
    if conv is None or conv.user_id != principal.user.id:  # les conversations sont strictement personnelles
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation introuvable.")
    return conv


@router.post("")
def ask(
    data: ChatIn,
    principal: Principal = Depends(require(CHAT_UTILISER)), db: Session = Depends(get_db),
):
    from app.db.vecteur import Document

    if principal.niveau == NIVEAU_ROOT:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "L'IA n'est pas accessible au super administrateur : il administre, les chefs et les agents interrogent.",
        )
    if db.scalars(select(Document.id).where(condition_acces_fichiers(db, principal), Document.corbeille_le.is_(None)).limit(1)).first() is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Vous n'avez accès à aucun fichier.")
    prefs = memoire.get_preferences(db, principal.user.id)

    if data.conversation_id is not None:
        conv = _own_conversation(db, principal, data.conversation_id)
    else:
        conv = Conversation(user_id=principal.user.id, titre=" ".join(data.question.split())[:80])
        db.add(conv)
        db.flush()
    # historique AVANT d'ajouter la question courante ; masqué pour les fichiers dont l'accès a été retiré
    historique = ConversationHistory(db, conv.id, principal).messages
    souvenirs = (
        memoire.load(db, principal.user.id, principal, conv.id) if prefs.memoire_inter_sessions else []
    )
    db.add(Message(conversation_id=conv.id, emetteur="utilisateur", contenu=data.question, sources=[]))
    db.commit()

    try:
        prepared = rag_chain.prepare(
            db, principal, data.question, historique, souvenirs,
            derniere_version_seulement=prefs.derniere_version_seulement,
        )
    except Exception:  # noqa: BLE001
        logger.exception("Recherche impossible")
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "La recherche a échoué : vérifier qu'Ollama est démarré."
        ) from None

    user_id, conversation_id, question = principal.user.id, conv.id, data.question
    retenir = prefs.memoire_inter_sessions and prepared.has_context

    def after_answer(session: Session, answer: str, sources: list[dict]) -> None:
        if retenir:
            memoire.record(
                session, user_id, conversation_id, question, answer,
                [s["document_id"] for s in sources if s.get("document_id") is not None],
            )

    return StreamingResponse(
        event_stream(prepared, conv.id, after_answer),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/preferences", response_model=PreferencesOut)
def get_preferences(principal: Principal = Depends(require(CHAT_UTILISER)), db: Session = Depends(get_db)):
    return memoire.get_preferences(db, principal.user.id)


@router.put("/preferences", response_model=PreferencesOut)
def put_preferences(
    data: PreferencesIn, principal: Principal = Depends(require(CHAT_UTILISER)), db: Session = Depends(get_db)
):
    return memoire.set_preferences(db, principal.user.id, data.memoire_inter_sessions, data.derniere_version_seulement)


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
    rows = list(
        db.scalars(select(Message).where(Message.conversation_id == conversation_id).order_by(Message.id))
    )
    visibles = filter_visible(db, rows, principal)
    return [
        MessageOut(
            id=v.message.id, emetteur=v.message.emetteur, contenu=v.contenu, sources=v.sources, masque=v.masque,
            cree_le=v.message.cree_le,
        )
        for v in visibles
    ]


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(
    conversation_id: int, principal: Principal = Depends(require(CHAT_UTILISER)), db: Session = Depends(get_db)
) -> Response:
    db.delete(_own_conversation(db, principal, conversation_id))
    db.commit()
    return Response(status_code=204)
