"""Connexion à la base métier (schéma rag_sys) : engine SQLAlchemy, session, modèles des tables
direction, _service, agent, _role, permission, role_permission, _user, journal_audit, conversation, message.

Les modèles document et chunk sont dans db/vecteur.py (même base, même schéma).
"""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Identity,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    func,
)
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from app.config import get_settings

SCHEMA = "rag_sys"


class Base(DeclarativeBase):
    metadata = MetaData(schema=SCHEMA)


engine = create_engine(
    get_settings().sqlalchemy_url,
    pool_pre_ping=True,
    # public reste dans le chemin pour résoudre le type « vector » de pgvector
    connect_args={"options": f"-c search_path={SCHEMA},public"},
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def _pk() -> Mapped[int]:
    return mapped_column(BigInteger, Identity(always=True), primary_key=True)


class Direction(Base):
    __tablename__ = "direction"

    id: Mapped[int] = _pk()
    code: Mapped[str] = mapped_column(String(30), unique=True)
    nom: Mapped[str] = mapped_column(String(180))
    actif: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    services: Mapped[list["Service"]] = relationship(back_populates="direction")


class Service(Base):
    __tablename__ = "_service"

    id: Mapped[int] = _pk()
    direction_id: Mapped[int] = mapped_column(ForeignKey("direction.id"))
    code: Mapped[str] = mapped_column(String(30), unique=True)
    nom: Mapped[str] = mapped_column(String(180))
    site: Mapped[str | None] = mapped_column(String(150))
    actif: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    direction: Mapped[Direction] = relationship(back_populates="services")


class Agent(Base):
    __tablename__ = "agent"

    id: Mapped[int] = _pk()
    matricule: Mapped[str] = mapped_column(String(50), unique=True)
    nom: Mapped[str] = mapped_column(String(100))
    prenom: Mapped[str] = mapped_column(String(100))
    fonction: Mapped[str | None] = mapped_column(String(150))
    email: Mapped[str | None] = mapped_column(String(180))
    service_id: Mapped[int | None] = mapped_column(ForeignKey("_service.id"))
    actif: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    service: Mapped[Service | None] = relationship()


role_permission = Table(
    "role_permission",
    Base.metadata,
    Column("role_id", BigInteger, ForeignKey("_role.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", BigInteger, ForeignKey("permission.id", ondelete="CASCADE"), primary_key=True),
)


class Permission(Base):
    __tablename__ = "permission"

    id: Mapped[int] = _pk()
    code: Mapped[str] = mapped_column(String(80), unique=True)
    libelle: Mapped[str] = mapped_column(String(180))


class Role(Base):
    __tablename__ = "_role"

    id: Mapped[int] = _pk()
    code: Mapped[str] = mapped_column(String(30), unique=True)
    libelle: Mapped[str] = mapped_column(String(100))

    permissions: Mapped[list[Permission]] = relationship(secondary=role_permission)


class User(Base):
    __tablename__ = "_user"

    id: Mapped[int] = _pk()
    agent_id: Mapped[int | None] = mapped_column(ForeignKey("agent.id"))
    nom_utilisateur: Mapped[str] = mapped_column(String(80), unique=True)
    mot_de_passe_hash: Mapped[str] = mapped_column(Text)
    role_id: Mapped[int] = mapped_column(ForeignKey("_role.id"))
    actif: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    derniere_connexion: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    role: Mapped[Role] = relationship()
    agent: Mapped[Agent | None] = relationship()


class JournalAudit(Base):
    __tablename__ = "journal_audit"

    id: Mapped[int] = _pk()
    user_id: Mapped[int | None] = mapped_column(ForeignKey("_user.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(60))
    entite: Mapped[str | None] = mapped_column(String(60))
    entite_id: Mapped[int | None] = mapped_column(BigInteger)
    detail: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    adresse_ip: Mapped[str | None] = mapped_column(INET)
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User | None] = relationship()


class Conversation(Base):
    __tablename__ = "conversation"

    id: Mapped[int] = _pk()
    user_id: Mapped[int] = mapped_column(ForeignKey("_user.id", ondelete="CASCADE"))
    titre: Mapped[str | None] = mapped_column(String(200))
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Message(Base):
    __tablename__ = "message"

    id: Mapped[int] = _pk()
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversation.id", ondelete="CASCADE"))
    emetteur: Mapped[str] = mapped_column(String(15))  # 'utilisateur' | 'assistant'
    contenu: Mapped[str] = mapped_column(Text)
    sources: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list, server_default="[]")
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
