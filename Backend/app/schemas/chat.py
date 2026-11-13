"""Schémas Pydantic du chat : question, conversations, messages, sources citées, préférences."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ChatIn(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    conversation_id: int | None = None


class SourceOut(BaseModel):
    ref: int
    document_id: int
    dossier_id: int | None = None
    titre: str
    version: int | None = None
    date: datetime | None = None
    page: int | None
    extrait: str


class MessageOut(BaseModel):
    id: int
    emetteur: Literal["utilisateur", "assistant"]
    contenu: str
    sources: list[SourceOut]
    masque: bool = False  # réponse masquée : accès perdu à l'un des dossiers cités
    cree_le: datetime


class ConversationOut(BaseModel):
    id: int
    titre: str | None
    cree_le: datetime


class PreferencesOut(BaseModel):
    memoire_inter_sessions: bool
    derniere_version_seulement: bool


class PreferencesIn(BaseModel):
    memoire_inter_sessions: bool | None = None
    derniere_version_seulement: bool | None = None
