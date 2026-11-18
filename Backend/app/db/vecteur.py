"""Accès à la base vectorielle (pgvector) : tables document, document_version et chunk.

Choix : même base et même schéma que le métier, donc SQLAlchemy partout (type Vector du paquet pgvector),
ce qui permet de filtrer les chunks par division avec de simples jointures chunk -> document.

- document : le fichier « logique », déposé directement dans UNE division (titre, options tableaux/images) ;
- document_version : chaque dépôt du fichier, daté et numéroté, avec son statut d'ingestion ;
- chunk : un extrait d'une version, avec son embedding et son texte indexé pour la recherche plein texte.
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
from app.db.metier import Base, Categorie, Division, DocumentTag, TypeDocument, User

STATUTS = ("pending", "processing", "ready", "error")


class Document(Base):
    __tablename__ = "document"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    division_id: Mapped[int] = mapped_column(ForeignKey("division.id"))
    titre: Mapped[str] = mapped_column(String(250))
    categorie_id: Mapped[int | None] = mapped_column(ForeignKey("categorie.id", ondelete="SET NULL"))
    type_document_id: Mapped[int | None] = mapped_column(ForeignKey("type_document.id", ondelete="SET NULL"))
    confidentialite: Mapped[str] = mapped_column(String(15), default="INTERNE", server_default="INTERNE")
    classement_source: Mapped[str] = mapped_column(String(10), default="aucun", server_default="aucun")
    regle_id: Mapped[int | None] = mapped_column(BigInteger)
    cree_par_service_id: Mapped[int | None] = mapped_column(ForeignKey("_service.id", ondelete="SET NULL"))
    corbeille_le: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # options de lecture : tableaux (markdown, en-tête répété) et images (OCR en plus de l'extraction normale)
    has_tabular: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    has_image: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    cree_par: Mapped[int | None] = mapped_column(ForeignKey("_user.id", ondelete="SET NULL"))
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    modifie_par: Mapped[int | None] = mapped_column(ForeignKey("_user.id", ondelete="SET NULL"))
    modifie_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    division: Mapped[Division] = relationship()
    categorie: Mapped[Categorie | None] = relationship()
    type_document: Mapped[TypeDocument | None] = relationship()
    # lecture seule : les étiquettes s'écrivent via services/classement (requêtes directes sur DocumentTag)
    tag_liens: Mapped[list[DocumentTag]] = relationship(
        primaryjoin="Document.id == foreign(DocumentTag.document_id)", viewonly=True
    )
    createur: Mapped[User | None] = relationship(foreign_keys=[cree_par])
    versions: Mapped[list["DocumentVersion"]] = relationship(
        back_populates="document", order_by="DocumentVersion.numero", cascade="all, delete-orphan",
        passive_deletes=True,
    )


class DocumentVersion(Base):
    __tablename__ = "document_version"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("document.id", ondelete="CASCADE"))
    numero: Mapped[int] = mapped_column(Integer)
    nom_fichier: Mapped[str] = mapped_column(String(255))
    type_mime: Mapped[str | None] = mapped_column(String(120))
    taille_octets: Mapped[int | None] = mapped_column(BigInteger)
    hash_sha256: Mapped[str] = mapped_column(String(64))
    chemin_stockage: Mapped[str] = mapped_column(Text)
    nb_pages: Mapped[int | None] = mapped_column(Integer)
    ocr_utilise: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    statut: Mapped[str] = mapped_column(String(20), default="pending", server_default="pending")
    message_erreur: Mapped[str | None] = mapped_column(Text)
    cree_par: Mapped[int | None] = mapped_column(ForeignKey("_user.id", ondelete="SET NULL"))
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    document: Mapped[Document] = relationship(back_populates="versions")
    auteur: Mapped[User | None] = relationship(foreign_keys=[cree_par])


class Chunk(Base):
    __tablename__ = "chunk"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("document.id", ondelete="CASCADE"))
    document_version_id: Mapped[int] = mapped_column(ForeignKey("document_version.id", ondelete="CASCADE"))
    chunk_index: Mapped[int] = mapped_column(Integer)
    page: Mapped[int | None] = mapped_column(Integer)
    contenu: Mapped[str] = mapped_column(Text)
    est_tableau: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    # nombre de chunks de la version : sert à calculer le nombre de passages à renvoyer (top-k dynamique)
    taille_ref: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # nommé « meta » côté Python car « metadata » est réservé par SQLAlchemy
    meta: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict, server_default="{}")
    embedding: Mapped[list[float]] = mapped_column(Vector(get_settings().embedding_dim))
    # colonne générée par Postgres : jamais écrite, seulement utilisée pour la recherche plein texte
    contenu_tsv: Mapped[Any] = mapped_column(
        TSVECTOR, Computed("to_tsvector('french', contenu)", persisted=True), deferred=True
    )
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
