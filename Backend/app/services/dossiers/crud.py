"""Logique des dossiers : création, renommage, archivage, suppression (ADMIN seul) et attribution des rôles.

Règles :
- les dossiers sont plats (pas de sous-dossier) et sans lien avec les directions ; un service n'intervient que comme
  bénéficiaire d'un rôle (dossier_service) ;
- seul l'ADMIN (permission dossier.gerer) crée, renomme, archive, supprime un dossier et gère ses membres ;
- un dossier archivé est en lecture seule et n'est plus interrogé par le chat ;
- un dossier qui contient des fichiers ne se supprime pas : le vider d'abord (ses fichiers sont supprimés un par un,
  avec leurs versions, par un gestionnaire de contenu ou l'admin).
Chaque changement est inscrit au journal d'audit.
"""

from fastapi import HTTPException, status
from sqlalchemy import func, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.core.permissions import Principal, roles_par_dossier
from app.db.metier import Dossier, Service, User
from app.db.vecteur import Document
from app.schemas.dossier import (
    AccesDossierOut, DossierIn, DossierOut, DossierUpdate, MembreOut, ServiceAccesOut,
)
from app.services.audit import log_action


def _nb_fichiers(db: Session) -> dict[int, int]:
    return dict(db.execute(select(Document.dossier_id, func.count(Document.id)).group_by(Document.dossier_id)).all())


def to_out(d: Dossier, role: str, nb_fichiers: int) -> DossierOut:
    return DossierOut(
        id=d.id, nom=d.nom, description=d.description, archive=d.archive, nb_fichiers=nb_fichiers,
        mon_role=role, cree_le=d.cree_le, modifie_le=d.modifie_le,
    )


def list_dossiers(db: Session, principal: Principal) -> list[DossierOut]:
    """Les dossiers auxquels l'utilisateur a accès (tous pour l'ADMIN), avec son rôle effectif."""
    roles = roles_par_dossier(db, principal)
    if not roles:
        return []
    counts = _nb_fichiers(db)
    rows = db.scalars(select(Dossier).where(Dossier.id.in_(roles)).order_by(func.lower(Dossier.nom)))
    return [to_out(d, roles[d.id], counts.get(d.id, 0)) for d in rows]


def _get(db: Session, dossier_id: int) -> Dossier:
    d = db.get(Dossier, dossier_id)
    if d is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dossier introuvable.")
    return d


def _name_taken(db: Session, nom: str, ignore_id: int | None = None) -> bool:
    stmt = select(Dossier.id).where(func.lower(Dossier.nom) == nom.lower())
    if ignore_id is not None:
        stmt = stmt.where(Dossier.id != ignore_id)
    return db.scalar(stmt) is not None


def create_dossier(db: Session, actor: Principal, data: DossierIn, ip: str | None) -> Dossier:
    if _name_taken(db, data.nom):
        raise HTTPException(status.HTTP_409_CONFLICT, "Un dossier porte déjà ce nom.")
    d = Dossier(nom=data.nom, description=(data.description or "").strip() or None, cree_par=actor.user.id)
    db.add(d)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Un dossier porte déjà ce nom.") from None
    log_action(db, actor.user.id, "dossier.creer", "dossier", d.id, {"nom": d.nom}, ip)
    db.commit()
    return d


def update_dossier(db: Session, actor: Principal, dossier_id: int, data: DossierUpdate, ip: str | None) -> Dossier:
    d = _get(db, dossier_id)
    changes: dict = {}
    if data.nom is not None:
        nom = " ".join(data.nom.split())
        if not nom:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Le nom du dossier ne peut pas être vide.")
        if nom != d.nom:
            if _name_taken(db, nom, d.id):
                raise HTTPException(status.HTTP_409_CONFLICT, "Un dossier porte déjà ce nom.")
            d.nom = nom
            changes["nom"] = nom
    if data.description is not None and (data.description.strip() or None) != d.description:
        d.description = data.description.strip() or None
        changes["description"] = d.description
    if data.archive is not None and data.archive != d.archive:
        d.archive = data.archive
        changes["archive"] = data.archive
    if changes:
        log_action(db, actor.user.id, "dossier.modifier", "dossier", d.id, changes, ip)
        db.commit()
    return d


def delete_dossier(db: Session, actor: Principal, dossier_id: int, ip: str | None) -> None:
    d = _get(db, dossier_id)
    if db.scalar(select(func.count(Document.id)).where(Document.dossier_id == d.id)):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Ce dossier contient des fichiers : les supprimer d'abord (ou l'archiver)."
        )
    log_action(db, actor.user.id, "dossier.supprimer", "dossier", d.id, {"nom": d.nom}, ip)
    db.delete(d)  # membres et accès par service partent en cascade
    db.commit()


# --- Membres et rôles -------------------------------------------------------------------------------------------------

def _legacy_table_exists(db: Session, table_name: str) -> bool:
    return table_name in inspect(db.get_bind()).get_table_names()


def list_acces(db: Session, dossier_id: int) -> AccesDossierOut:
    _get(db, dossier_id)

    membres = []
    services = []

    if _legacy_table_exists(db, "dossier_membre"):
        from app.db.metier import DossierMembre

        membres = db.scalars(
            select(DossierMembre).options(joinedload(DossierMembre.user).joinedload(User.agent))
            .where(DossierMembre.dossier_id == dossier_id)
        ).unique()

    if _legacy_table_exists(db, "dossier_service"):
        from app.db.metier import DossierService

        services = db.scalars(
            select(DossierService).options(joinedload(DossierService.service)).where(DossierService.dossier_id == dossier_id)
        )

    return AccesDossierOut(
        membres=sorted(
            (
                MembreOut(
                    user_id=m.user_id, nom_utilisateur=m.user.nom_utilisateur, role=m.role,
                    nom_complet=f"{m.user.agent.prenom} {m.user.agent.nom}" if m.user.agent else None,
                )
                for m in membres
            ),
            key=lambda m: m.nom_utilisateur,
        ),
        services=sorted(
            (
                ServiceAccesOut(service_id=s.service_id, service_code=s.service.code, service_nom=s.service.nom, role=s.role)
                for s in services
            ),
            key=lambda s: s.service_nom.lower(),
        ),
    )


def set_membre(db: Session, actor: Principal, dossier_id: int, user_id: int, role: str, ip: str | None) -> None:
    if not _legacy_table_exists(db, "dossier_membre"):
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "Le modèle de dossier plat n'est plus utilisé dans cette base.")

    from app.db.metier import DossierMembre

    d = _get(db, dossier_id)
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Utilisateur introuvable.")
    if not user.actif:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Ce compte est désactivé.")
    if user.role.code == "ADMIN":
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "Un administrateur a déjà tous les droits dans tous les dossiers."
        )
    existing = db.get(DossierMembre, (dossier_id, user_id))
    if existing is None:
        db.add(DossierMembre(dossier_id=dossier_id, user_id=user_id, role=role))
    elif existing.role == role:
        return
    else:
        existing.role = role
    log_action(db, actor.user.id, "dossier.membre_definir", "dossier", d.id,
               {"user_id": user_id, "nom_utilisateur": user.nom_utilisateur, "role": role}, ip)
    db.commit()


def remove_membre(db: Session, actor: Principal, dossier_id: int, user_id: int, ip: str | None) -> None:
    if not _legacy_table_exists(db, "dossier_membre"):
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "Le modèle de dossier plat n'est plus utilisé dans cette base.")

    from app.db.metier import DossierMembre

    d = _get(db, dossier_id)
    existing = db.get(DossierMembre, (dossier_id, user_id))
    if existing is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cet utilisateur n'est pas membre de ce dossier.")
    db.delete(existing)
    log_action(db, actor.user.id, "dossier.membre_retirer", "dossier", d.id, {"user_id": user_id}, ip)
    db.commit()


def set_service(db: Session, actor: Principal, dossier_id: int, service_id: int, role: str, ip: str | None) -> None:
    if not _legacy_table_exists(db, "dossier_service"):
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "Le modèle de dossier plat n'est plus utilisé dans cette base.")

    from app.db.metier import DossierService

    d = _get(db, dossier_id)
    service = db.get(Service, service_id)
    if service is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Service introuvable.")
    if not service.actif:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Ce service est inactif.")
    existing = db.get(DossierService, (dossier_id, service_id))
    if existing is None:
        db.add(DossierService(dossier_id=dossier_id, service_id=service_id, role=role))
    elif existing.role == role:
        return
    else:
        existing.role = role
    log_action(db, actor.user.id, "dossier.service_definir", "dossier", d.id,
               {"service_id": service_id, "service": service.code, "role": role}, ip)
    db.commit()


def remove_service(db: Session, actor: Principal, dossier_id: int, service_id: int, ip: str | None) -> None:
    if not _legacy_table_exists(db, "dossier_service"):
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "Le modèle de dossier plat n'est plus utilisé dans cette base.")

    from app.db.metier import DossierService

    d = _get(db, dossier_id)
    existing = db.get(DossierService, (dossier_id, service_id))
    if existing is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ce service n'a pas accès à ce dossier.")
    db.delete(existing)
    log_action(db, actor.user.id, "dossier.service_retirer", "dossier", d.id, {"service_id": service_id}, ip)
    db.commit()
