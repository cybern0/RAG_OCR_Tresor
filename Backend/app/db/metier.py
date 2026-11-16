"""Connexion à la base métier (schéma rag_sys) : engine SQLAlchemy, session, modèles des tables
direction, _service, agent, _role, permission, role_permission, _user, journal_audit, conversation, message,
dossier, dossier_membre, dossier_service, preference_utilisateur, memoire_chat.

Les modèles document, document_version et chunk sont dans db/vecteur.py (même base, même schéma).
"""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    ARRAY,
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
    divisions: Mapped[list["Division"]] = relationship(back_populates="service")


class Division(Base):
    __tablename__ = "division"

    id: Mapped[int] = _pk()
    service_id: Mapped[int] = mapped_column(ForeignKey("_service.id", ondelete="CASCADE"))
    code: Mapped[str | None] = mapped_column(String(30), unique=True, nullable=True)
    nom: Mapped[str] = mapped_column(String(180))
    actif: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    service: Mapped[Service] = relationship(back_populates="divisions")
    agents: Mapped[list["Agent"]] = relationship(back_populates="division")
    dossiers: Mapped[list["Dossier"]] = relationship(back_populates="division")
    roles: Mapped[list["RoleDivision"]] = relationship(back_populates="division")


class Agent(Base):
    __tablename__ = "agent"

    id: Mapped[int] = _pk()
    matricule: Mapped[str] = mapped_column(String(50), unique=True)
    nom: Mapped[str] = mapped_column(String(100))
    prenom: Mapped[str] = mapped_column(String(100))
    fonction: Mapped[str | None] = mapped_column(String(150))
    email: Mapped[str | None] = mapped_column(String(180))
    service_id: Mapped[int | None] = mapped_column(ForeignKey("_service.id"))
    division_id: Mapped[int | None] = mapped_column(ForeignKey("division.id", ondelete="SET NULL"))
    titre: Mapped[str | None] = mapped_column(String(30))
    actif: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    service: Mapped[Service | None] = relationship()
    division: Mapped[Division | None] = relationship(back_populates="agents")


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


# --- Dossiers partagés et rôles --------------------------------------------------------------------------------------

class Dossier(Base):
    """Dossier de travail : compatible avec l'ancien modèle plat, tout en prenant en charge la hiérarchie
    direction -> service -> division -> sous-dossiers libres."""

    __tablename__ = "dossier"

    id: Mapped[int] = _pk()
    division_id: Mapped[int | None] = mapped_column(ForeignKey("division.id", ondelete="SET NULL"))
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("dossier.id", ondelete="SET NULL"))
    nom: Mapped[str] = mapped_column(String(150))
    description: Mapped[str | None] = mapped_column(Text)
    archive: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    cree_par: Mapped[int | None] = mapped_column(ForeignKey("_user.id", ondelete="SET NULL"))
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    modifie_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    division: Mapped[Division | None] = relationship(back_populates="dossiers")
    parent: Mapped["Dossier | None"] = relationship(remote_side="Dossier.id", back_populates="enfants")
    enfants: Mapped[list["Dossier"]] = relationship(back_populates="parent")


class DossierMembre(Base):
    """Rôle direct d'un utilisateur dans un dossier."""

    __tablename__ = "dossier_membre"

    dossier_id: Mapped[int] = mapped_column(ForeignKey("dossier.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("_user.id", ondelete="CASCADE"), primary_key=True)
    role: Mapped[str] = mapped_column(String(30))
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship()


class DossierService(Base):
    """Rôle donné à un service entier dans un dossier."""

    __tablename__ = "dossier_service"

    dossier_id: Mapped[int] = mapped_column(ForeignKey("dossier.id", ondelete="CASCADE"), primary_key=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("_service.id"), primary_key=True)
    role: Mapped[str] = mapped_column(String(30))
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    service: Mapped[Service] = relationship()


class RoleDivision(Base):
    __tablename__ = "role_division"

    id: Mapped[int] = _pk()
    division_id: Mapped[int] = mapped_column(ForeignKey("division.id", ondelete="CASCADE"))
    code: Mapped[str] = mapped_column(String(60))
    libelle: Mapped[str] = mapped_column(String(180))
    actif: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    division: Mapped[Division] = relationship(back_populates="roles")


class UserRoleDivision(Base):
    __tablename__ = "user_role_division"

    id: Mapped[int] = _pk()
    user_id: Mapped[int] = mapped_column(ForeignKey("_user.id", ondelete="CASCADE"))
    role_division_id: Mapped[int] = mapped_column(ForeignKey("role_division.id", ondelete="CASCADE"))
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DocumentRole(Base):
    __tablename__ = "document_role"

    id: Mapped[int] = _pk()
    document_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    role_division_id: Mapped[int] = mapped_column(ForeignKey("role_division.id", ondelete="CASCADE"))
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DemandeAcces(Base):
    __tablename__ = "demande_acces"

    id: Mapped[int] = _pk()
    demandeur_user_id: Mapped[int] = mapped_column(ForeignKey("_user.id", ondelete="CASCADE"))
    type_demande: Mapped[str] = mapped_column(String(30), default="role")
    cible_type: Mapped[str | None] = mapped_column(String(30))
    cible_id: Mapped[int | None] = mapped_column(BigInteger)
    motif: Mapped[str | None] = mapped_column(Text)
    statut: Mapped[str] = mapped_column(String(20), default="en_attente", server_default="en_attente")
    decisionnaire_user_id: Mapped[int | None] = mapped_column(ForeignKey("_user.id", ondelete="SET NULL"))
    reponse: Mapped[str | None] = mapped_column(Text)
    date_creation: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    date_decision: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expiration: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AccesException(Base):
    __tablename__ = "acces_exception"

    id: Mapped[int] = _pk()
    user_id: Mapped[int] = mapped_column(ForeignKey("_user.id", ondelete="CASCADE"))
    document_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    motif: Mapped[str | None] = mapped_column(Text)
    expire_le: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SecretUnite(Base):
    __tablename__ = "secret_unite"

    id: Mapped[int] = _pk()
    service_id: Mapped[int | None] = mapped_column(ForeignKey("_service.id", ondelete="CASCADE"))
    division_id: Mapped[int | None] = mapped_column(ForeignKey("division.id", ondelete="CASCADE"))
    admin_user_id: Mapped[int] = mapped_column(ForeignKey("_user.id", ondelete="CASCADE"))
    secret_hash: Mapped[str] = mapped_column(Text)
    modifie_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Deverrouillage(Base):
    __tablename__ = "deverrouillage"

    id: Mapped[int] = _pk()
    secret_unite_id: Mapped[int] = mapped_column(ForeignKey("secret_unite.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("_user.id", ondelete="CASCADE"))
    valide_jusqua: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actif: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class HistoriqueModification(Base):
    __tablename__ = "historique_modification"

    id: Mapped[int] = _pk()
    acteur_user_id: Mapped[int | None] = mapped_column(ForeignKey("_user.id", ondelete="SET NULL"))
    cible_type: Mapped[str] = mapped_column(String(40))
    cible_id: Mapped[int | None] = mapped_column(BigInteger)
    action: Mapped[str] = mapped_column(String(60))
    avant: Mapped[str | None] = mapped_column(Text)
    apres: Mapped[str | None] = mapped_column(Text)
    motif: Mapped[str | None] = mapped_column(Text)
    service_id: Mapped[int | None] = mapped_column(ForeignKey("_service.id", ondelete="SET NULL"))
    division_id: Mapped[int | None] = mapped_column(ForeignKey("division.id", ondelete="SET NULL"))
    date_action: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    hash_precedent: Mapped[str | None] = mapped_column(String(128))
    hash_courant: Mapped[str | None] = mapped_column(String(128))


class Notification(Base):
    __tablename__ = "notification"

    id: Mapped[int] = _pk()
    destinataire_user_id: Mapped[int] = mapped_column(ForeignKey("_user.id", ondelete="CASCADE"))
    type_evenement: Mapped[str] = mapped_column(String(60))
    reference_type: Mapped[str | None] = mapped_column(String(30))
    reference_id: Mapped[int | None] = mapped_column(BigInteger)
    message: Mapped[str | None] = mapped_column(Text)
    lu: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Commentaire(Base):
    """Commentaire sur un fichier (visible des contributeurs et plus)."""

    __tablename__ = "commentaire"

    id: Mapped[int] = _pk()
    sujet_type: Mapped[str] = mapped_column(String(20))
    sujet_id: Mapped[int] = mapped_column(BigInteger)
    auteur_id: Mapped[int] = mapped_column(ForeignKey("_user.id", ondelete="CASCADE"))
    contenu: Mapped[str] = mapped_column(Text)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("commentaire.id", ondelete="CASCADE"))
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    auteur: Mapped[User] = relationship()


class PreferenceUtilisateur(Base):
    __tablename__ = "preference_utilisateur"

    user_id: Mapped[int] = mapped_column(ForeignKey("_user.id", ondelete="CASCADE"), primary_key=True)
    memoire_inter_sessions: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    derniere_version_seulement: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")


class MemoireChat(Base):
    """Résultat retenu d'une session pour enrichir les suivantes ; dossier_ids sert au filtre d'accès."""

    __tablename__ = "memoire_chat"

    id: Mapped[int] = _pk()
    user_id: Mapped[int] = mapped_column(ForeignKey("_user.id", ondelete="CASCADE"))
    conversation_id: Mapped[int | None] = mapped_column(ForeignKey("conversation.id", ondelete="CASCADE"))
    resume: Mapped[str] = mapped_column(Text)
    dossier_ids: Mapped[list[int]] = mapped_column(ARRAY(BigInteger), default=list, server_default="{}")
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Categorie(Base):
    __tablename__ = "categorie"

    id: Mapped[int] = _pk()
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("categorie.id", ondelete="SET NULL"))
    nom: Mapped[str] = mapped_column(String(120))
    couleur: Mapped[str | None] = mapped_column(String(9))
    ordre: Mapped[int] = mapped_column(default=0, server_default="0")
    actif: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class TypeDocument(Base):
    __tablename__ = "type_document"

    id: Mapped[int] = _pk()
    nom: Mapped[str] = mapped_column(String(120), unique=True)
    actif: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class Tag(Base):
    __tablename__ = "tag"

    id: Mapped[int] = _pk()
    nom: Mapped[str] = mapped_column(String(60))


class DocumentTag(Base):
    __tablename__ = "document_tag"

    document_id: Mapped[int] = mapped_column(ForeignKey("document.id", ondelete="CASCADE"), primary_key=True)
    tag_id: Mapped[int] = mapped_column(ForeignKey("tag.id", ondelete="CASCADE"), primary_key=True)
    source: Mapped[str] = mapped_column(String(10), default="manuel", server_default="manuel")

    tag: Mapped["Tag"] = relationship(lazy="joined")


class RegleClassement(Base):
    __tablename__ = "regle_classement"

    id: Mapped[int] = _pk()
    nom: Mapped[str] = mapped_column(String(120))
    priorite: Mapped[int] = mapped_column(default=100, server_default="100")
    actif: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    critere: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    categorie_id: Mapped[int | None] = mapped_column(ForeignKey("categorie.id", ondelete="SET NULL"))
    type_document_id: Mapped[int | None] = mapped_column(ForeignKey("type_document.id", ondelete="SET NULL"))
    tags: Mapped[list[str]] = mapped_column(ARRAY(String(60)), default=list, server_default="{}")
    confidentialite: Mapped[str | None] = mapped_column(String(15))
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    modifie_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
