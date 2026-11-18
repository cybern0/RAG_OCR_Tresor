"""Dossiers d'une division (un seul niveau, sans sous-dossiers).

Jamais créés à la main : à la création d'une division, le backend pose automatiquement le jeu de dossiers
par défaut issu du modèle configuré (services/structure/crud.py) — le même pour toutes les divisions.
Sans login ni rôle : les dossiers héritent de la division et sont visibles de tous ses agents. Un dossier n'a
PAS de rôle : ce sont les fichiers qu'il contient qui portent des rôles (le nombre de fichiers masqués est
indiqué). Renommer, archiver, supprimer : le super administrateur ; les agents déposent des fichiers dedans.
"""

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.acces import (
    DOSSIER_GERER,
    DOSSIER_VOIR,
    est_chef_nominal,
    est_membre,
    exiger_acces_division,
    exiger_acces_dossier,
)
from app.core.permissions import Principal
from app.db.metier import Division, Dossier, User
from app.db.vecteur import Document
from app.schemas.dossier import DossierOut, DossierUpdate
from app.services.audit import log_action
from app.services.documents.crud import compter_fichiers
from app.services.historique import ecrire_historique


def _perimetre(db: Session, dossier: Dossier) -> dict:
    division = db.get(Division, dossier.division_id)
    return {"service_id": division.service_id, "division_id": division.id}


def _sorties(db: Session, principal: Principal, dossiers: list[Dossier]) -> list[DossierOut]:
    if not dossiers:
        return []
    ids = [d.id for d in dossiers]
    divisions = {d.id: d for d in db.scalars(select(Division).where(Division.id.in_({x.division_id for x in dossiers})))}
    fichiers = compter_fichiers(db, principal, ids)
    createurs = {u.id: u.nom_utilisateur for u in db.scalars(select(User).where(User.id.in_({d.cree_par for d in dossiers if d.cree_par})))}
    sortie = []
    for d in dossiers:
        gerant = est_chef_nominal(db, principal, d.division_id)
        membre = est_membre(principal, d.division_id) or gerant
        peut_modifier = membre and (gerant or d.cree_par == principal.user.id)
        visibles, masques = fichiers.get(d.id, (0, 0))
        sortie.append(
            DossierOut(
                id=d.id, division_id=d.division_id, division_nom=divisions[d.division_id].nom, nom=d.nom,
                description=d.description, archive=d.archive, cree_par_nom=createurs.get(d.cree_par), cree_le=d.cree_le,
                modifie_le=d.modifie_le, nb_fichiers=visibles, nb_fichiers_masques=masques,
                peut_modifier=peut_modifier and divisions[d.division_id].actif,
                peut_creer=membre and not d.archive and divisions[d.division_id].actif,
            )
        )
    return sortie


def lister(db: Session, principal: Principal, division_id: int | None, inclure_archives: bool = True) -> list[DossierOut]:
    """Dossiers d'une division (un seul niveau : pas de sous-dossiers)."""
    division_id = division_id if division_id is not None else principal.division_id
    if division_id is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Choisissez une division.")
    exiger_acces_division(db, principal, division_id)
    stmt = select(Dossier).where(Dossier.division_id == division_id)
    if not inclure_archives:
        stmt = stmt.where(Dossier.archive.is_(False))
    return _sorties(db, principal, list(db.scalars(stmt.order_by(func.lower(Dossier.nom)))))


def detail(db: Session, principal: Principal, dossier_id: int) -> DossierOut:
    dossier = exiger_acces_dossier(db, principal, dossier_id, DOSSIER_VOIR)
    return _sorties(db, principal, [dossier])[0]


def modifier(db: Session, principal: Principal, dossier_id: int, data: DossierUpdate, ip: str | None) -> DossierOut:
    dossier = exiger_acces_dossier(db, principal, dossier_id, DOSSIER_GERER)
    champs = data.model_fields_set
    seulement_desarchivage = champs == {"archive"} and data.archive is False
    if dossier.archive and not seulement_desarchivage:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ce dossier est archivé : le rouvrir avant de le modifier.")
    avant, apres = {}, {}
    if data.nom is not None and data.nom.strip() != dossier.nom:
        avant["nom"], apres["nom"] = dossier.nom, data.nom.strip()
        dossier.nom = apres["nom"]
    if "description" in champs and data.description != dossier.description:
        avant["description"], apres["description"] = dossier.description, data.description
        dossier.description = data.description
    if data.archive is not None and data.archive != dossier.archive:
        avant["archive"], apres["archive"] = dossier.archive, data.archive
        dossier.archive = data.archive
    if apres:
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            raise HTTPException(status.HTTP_409_CONFLICT, "Un dossier de ce nom existe déjà dans cette division.") from None
        log_action(db, principal.user.id, "dossier.modifier", "dossier", dossier.id, apres, ip)
        ecrire_historique(db, acteur=principal.user, cible_type="dossier", cible_id=dossier.id, action="dossier_modifie", avant=avant, apres=apres, **_perimetre(db, dossier))
        db.commit()
    return _sorties(db, principal, [dossier])[0]


def supprimer(db: Session, principal: Principal, dossier_id: int, ip: str | None) -> None:
    dossier = exiger_acces_dossier(db, principal, dossier_id, DOSSIER_GERER)
    if db.scalar(select(func.count()).select_from(Document).where(Document.dossier_id == dossier.id)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Ce dossier contient des fichiers (corbeille comprise) : les supprimer d'abord.")
    division_id, identifiant = dossier.division_id, dossier.id  # capturés avant la suppression de la ligne
    perimetre = _perimetre(db, dossier)
    log_action(db, principal.user.id, "dossier.supprimer", "dossier", dossier.id, {"nom": dossier.nom}, ip)
    ecrire_historique(db, acteur=principal.user, cible_type="dossier", cible_id=dossier.id, action="dossier_supprime", avant=dossier.nom, **perimetre)
    db.delete(dossier)
    db.commit()
    # stockage à plat (services/stockage.py) : plus de répertoire physique par dossier à retirer
