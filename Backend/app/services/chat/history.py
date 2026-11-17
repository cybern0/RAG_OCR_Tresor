"""Historique d'une conversation pour le LLM (mémoire DANS une session, obligatoire).

L'historique vit dans la table message : il survit donc à une déconnexion/reconnexion, et se recharge à chaque question
à partir de conversation_id. ConversationHistory est un BaseChatMessageHistory de LangChain, lu à la demande.

Droits : une réponse de l'assistant est le fruit de passages de fichiers précis. Si l'utilisateur a perdu l'accès à l'un
de ces fichiers, la réponse est MASQUÉE (ni affichée, ni transmise au LLM, ni utilisée pour reformuler la question) :
le retrait d'un accès coupe tout, y compris l'historique. Les anciens messages ne sont pas purgés : si l'accès revient,
ils réapparaissent.
"""

from dataclasses import dataclass
from typing import Any

from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.acces import ids_documents_accessibles
from app.core.permissions import Principal
from app.db.metier import Message

MASQUE = "[Réponse masquée : vous n'avez plus accès à l'un des fichiers cités.]"


@dataclass(frozen=True)
class VisibleMessage:
    message: Message
    contenu: str
    sources: list[dict[str, Any]]
    masque: bool


def filter_visible(db: Session, messages: list[Message], principal: Principal) -> list[VisibleMessage]:
    """Masque les messages dont une source vient d'un fichier devenu inaccessible (ou supprimé : par prudence il est
    considéré comme inaccessible)."""
    ids = list({s["document_id"] for m in messages for s in m.sources if s.get("document_id") is not None})
    autorises = ids_documents_accessibles(db, principal, ids)
    out = []
    for m in messages:
        masque = any(s.get("document_id") is None or s["document_id"] not in autorises for s in m.sources)
        out.append(VisibleMessage(m, MASQUE if masque else m.contenu, [] if masque else list(m.sources), masque))
    return out


class ConversationHistory(BaseChatMessageHistory):
    """Derniers messages d'une conversation, filtrés selon les accès de l'utilisateur et tronqués pour tenir dans le
    contexte du LLM (petit modèle, fenêtre de 8192 tokens)."""

    def __init__(self, db: Session, conversation_id: int | None, principal: Principal):
        self.db = db
        self.conversation_id = conversation_id
        self.principal = principal

    @property
    def messages(self) -> list[BaseMessage]:  # type: ignore[override]
        if self.conversation_id is None:
            return []
        s = get_settings()
        rows = list(
            self.db.scalars(
                select(Message).where(Message.conversation_id == self.conversation_id)
                .order_by(Message.id.desc()).limit(s.history_max_messages)
            )
        )[::-1]
        out: list[BaseMessage] = []
        for v in filter_visible(self.db, rows, self.principal):
            text = " ".join(v.contenu.split())[: s.history_message_chars]
            out.append(HumanMessage(text) if v.message.emetteur == "utilisateur" else AIMessage(text))
        return out

    def add_messages(self, messages: list[BaseMessage]) -> None:
        """Enregistre des messages dans la conversation (sans sources). L'API enregistre elle-même les échanges, avec
        leurs sources ; cette méthode complète l'interface LangChain."""
        if self.conversation_id is None:
            raise ValueError("Pas de conversation.")
        for m in messages:
            self.db.add(
                Message(
                    conversation_id=self.conversation_id, sources=[], contenu=str(m.content),
                    emetteur="utilisateur" if isinstance(m, HumanMessage) else "assistant",
                )
            )
        self.db.flush()

    def clear(self) -> None:  # pragma: no cover - jamais utilisé : les conversations se suppriment par l'API
        raise NotImplementedError("Supprimer une conversation passe par DELETE /chat/conversations/{id}.")
