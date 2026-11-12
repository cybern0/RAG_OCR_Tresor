"""Accès à la base vectorielle (pgvector) : tables document et chunk.

Choix : même base et même schéma que le métier, donc SQLAlchemy partout (type Vector du paquet pgvector),
ce qui permet de filtrer les chunks par service avec une simple jointure sur document.
"""

from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    Computed,
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config import get_settings
from app.db.metier import Base, Service, User

STATUTS = ("pending", "processing", "ready", "error")


class Document(Base):
    __tablename__ = "document"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("_service.id"))
    titre: Mapped[str] = mapped_column(String(250))
    nom_fichier: Mapped[str] = mapped_column(String(255))
    type_mime: Mapped[str | None] = mapped_column(String(120))
    taille_octets: Mapped[int | None] = mapped_column(BigInteger)
    hash_sha256: Mapped[str] = mapped_column(String(64))
    chemin_stockage: Mapped[str] = mapped_column(Text)
    nb_pages: Mapped[int | None] = mapped_column(Integer)
    ocr_utilise: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    has_tabular: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    statut: Mapped[str] = mapped_column(String(20), default="pending", server_default="pending")
    message_erreur: Mapped[str | None] = mapped_column(Text)
    cree_par: Mapped[int | None] = mapped_column(ForeignKey("_user.id", ondelete="SET NULL"))
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    modifie_par: Mapped[int | None] = mapped_column(ForeignKey("_user.id", ondelete="SET NULL"))
    modifie_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    service: Mapped[Service] = relationship()
    createur: Mapped[User | None] = relationship(foreign_keys=[cree_par])


class Chunk(Base):
    __tablename__ = "chunk"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("document.id", ondelete="CASCADE"))
    chunk_index: Mapped[int] = mapped_column(Integer)
    page: Mapped[int | None] = mapped_column(Integer)
    contenu: Mapped[str] = mapped_column(Text)
    est_tableau: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    # nommé « meta » côté Python car « metadata » est réservé par SQLAlchemy
    meta: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict, server_default="{}")
    embedding: Mapped[list[float]] = mapped_column(Vector(get_settings().embedding_dim))
    # colonne générée par Postgres : jamais écrite, seulement utilisée pour la recherche plein texte
    contenu_tsv: Mapped[Any] = mapped_column(
        TSVECTOR, Computed("to_tsvector('french', contenu)", persisted=True), deferred=True
    )
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
