"""Schémas Pydantic du chat : question, conversations, messages, sources citées."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ChatIn(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    conversation_id: int | None = None


class SourceOut(BaseModel):
    ref: int
    document_id: int
    titre: str
    page: int | None
    extrait: str


class MessageOut(BaseModel):
    id: int
    emetteur: Literal["utilisateur", "assistant"]
    contenu: str
    sources: list[SourceOut]
    cree_le: datetime


class ConversationOut(BaseModel):
    id: int
    titre: str | None
    cree_le: datetime
