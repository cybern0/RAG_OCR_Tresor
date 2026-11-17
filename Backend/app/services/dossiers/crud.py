"""Dossiers et sous-dossiers d'une division.

Libres : tout agent de la division en crée, sans nouveau login ; ils héritent de la division. Un dossier n'a PAS de rôle : il est visible de
tous les agents de la division ; ce sont les fichiers qu'il contient qui portent des rôles (le nombre de fichiers masqués est indiqué).
Renommer, déplacer, archiver, supprimer : le créateur ou le chef de division. Un administrateur supérieur consulte (lecture seule).
"""

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.acces import (
    DOSSIER_CREER,
    DOSSIER_MODIFIER,
    DOSSIER_VOIR,
    est_chef_nominal,
    est_membre,
    exiger_acces_division,
    exiger_acces_dossier,
)
from app.core.permissions import Principal
from app.db.metier import Division, Dossier, User
from app.db.vecteur import Document
from app.schemas.dossier import CheminOut, DossierDetailOut, DossierIn, DossierOut, DossierUpdate
from app.services.audit import log_action
from app.services.documents.crud import compter_fichiers
from app.services.historique import ecrire_historique

PROFONDEUR_MAX = 10


def _chemin(db: Session, dossier: Dossier) -> list[Dossier]:
    chaine = [dossier]
    while chaine[0].parent_id is not None and len(chaine) <= PROFONDEUR_MAX + 2:
        parent = db.get(Dossier, chaine[0].parent_id)
        if parent is None:
            break
        chaine.insert(0, parent)
    return chaine


def _descendants(db: Session, dossier_id: int) -> list[Dossier]:
    trouves, a_voir = [], [dossier_id]
    while a_voir:
        enfants = list(db.scalars(select(Dossier).where(Dossier.parent_id.in_(a_voir))))
        trouves.extend(enfants)
        a_voir = [e.id for e in enfants]
    return trouves


def _perimetre(db: Session, dossier: Dossier) -> dict:
    division = db.get(Division, dossier.division_id)
    return {"service_id": division.service_id, "division_id": division.id}


def _sorties(db: Session, principal: Principal, dossiers: list[Dossier]) -> list[DossierOut]:
    if not dossiers:
        return []
    ids = [d.id for d in dossiers]
    divisions = {d.id: d for d in db.scalars(select(Division).where(Division.id.in_({x.division_id for x in dossiers})))}
    enfants = dict(db.execute(select(Dossier.parent_id, func.count()).where(Dossier.parent_id.in_(ids)).group_by(Dossier.parent_id)).all())
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
                id=d.id, division_id=d.division_id, division_nom=divisions[d.division_id].nom, parent_id=d.parent_id, nom=d.nom,
                description=d.description, archive=d.archive, cree_par_nom=createurs.get(d.cree_par), cree_le=d.cree_le,
                modifie_le=d.modifie_le, nb_sous_dossiers=enfants.get(d.id, 0), nb_fichiers=visibles, nb_fichiers_masques=masques,
                peut_modifier=peut_modifier and divisions[d.division_id].actif,
                peut_creer=membre and not d.archive and divisions[d.division_id].actif,
            )
        )
    return sortie


def lister(db: Session, principal: Principal, division_id: int | None, parent_id: int | None, inclure_archives: bool = True) -> list[DossierOut]:
    """Dossiers d'un niveau : racine d'une division (parent_id absent) ou sous-dossiers d'un dossier."""
    if parent_id is not None:
        parent = exiger_acces_dossier(db, principal, parent_id, DOSSIER_VOIR)
        division_id = parent.division_id
    else:
        division_id = division_id if division_id is not None else principal.division_id
        if division_id is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Choisissez une division.")
        exiger_acces_division(db, principal, division_id)
    stmt = select(Dossier).where(Dossier.division_id == division_id, Dossier.parent_id.is_(None) if parent_id is None else Dossier.parent_id == parent_id)
    if not inclure_archives:
        stmt = stmt.where(Dossier.archive.is_(False))
    return _sorties(db, principal, list(db.scalars(stmt.order_by(func.lower(Dossier.nom)))))


def detail(db: Session, principal: Principal, dossier_id: int) -> DossierDetailOut:
    dossier = exiger_acces_dossier(db, principal, dossier_id, DOSSIER_VOIR)
    base = _sorties(db, principal, [dossier])[0]
    enfants = lister(db, principal, None, dossier_id)
    return DossierDetailOut(**base.model_dump(), chemin=[CheminOut(id=c.id, nom=c.nom) for c in _chemin(db, dossier)], sous_dossiers=enfants)


def creer(db: Session, principal: Principal, data: DossierIn, ip: str | None) -> DossierOut:
    if data.parent_id is not None:
        parent = exiger_acces_dossier(db, principal, data.parent_id, DOSSIER_CREER)
        division_id = parent.division_id
        if len(_chemin(db, parent)) >= PROFONDEUR_MAX:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Profondeur maximale atteinte ({PROFONDEUR_MAX} niveaux).")
    else:
        division_id = data.division_id if data.division_id is not None else principal.division_id
        if division_id is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Vous n'appartenez à aucune division.")
        exiger_acces_division(db, principal, division_id, ecriture=True)
    dossier = Dossier(division_id=division_id, parent_id=data.parent_id, nom=data.nom.strip(), description=data.description, cree_par=principal.user.id)
    db.add(dossier)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Un dossier de ce nom existe déjà à cet endroit.") from None
    log_action(db, principal.user.id, "dossier.creer", "dossier", dossier.id, {"nom": dossier.nom, "parent_id": data.parent_id}, ip)
    ecrire_historique(db, acteur=principal.user, cible_type="dossier", cible_id=dossier.id, action="dossier_cree", apres=dossier.nom, **_perimetre(db, dossier))
    db.commit()
    return _sorties(db, principal, [dossier])[0]


def modifier(db: Session, principal: Principal, dossier_id: int, data: DossierUpdate, ip: str | None) -> DossierOut:
    dossier = exiger_acces_dossier(db, principal, dossier_id, DOSSIER_MODIFIER)
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
    if "parent_id" in champs and data.parent_id != dossier.parent_id:
        if data.parent_id is not None:
            cible = exiger_acces_dossier(db, principal, data.parent_id, DOSSIER_CREER)
            if cible.division_id != dossier.division_id:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Un dossier ne quitte pas sa division.")
            if cible.id == dossier.id or cible.id in {d.id for d in _descendants(db, dossier.id)}:
                raise HTTPException(status.HTTP_409_CONFLICT, "Impossible de déplacer un dossier dans lui-même ou dans l'un de ses sous-dossiers.")
            if len(_chemin(db, cible)) >= PROFONDEUR_MAX:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Profondeur maximale atteinte ({PROFONDEUR_MAX} niveaux).")
        avant["parent_id"], apres["parent_id"] = dossier.parent_id, data.parent_id
        dossier.parent_id = data.parent_id
    if data.archive is not None and data.archive != dossier.archive:
        avant["archive"], apres["archive"] = dossier.archive, data.archive
        for d in [dossier, *_descendants(db, dossier.id)]:  # l'archivage s'applique aux sous-dossiers
            d.archive = data.archive
    if apres:
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            raise HTTPException(status.HTTP_409_CONFLICT, "Un dossier de ce nom existe déjà à cet endroit.") from None
        log_action(db, principal.user.id, "dossier.modifier", "dossier", dossier.id, apres, ip)
        ecrire_historique(db, acteur=principal.user, cible_type="dossier", cible_id=dossier.id, action="dossier_modifie", avant=avant, apres=apres, **_perimetre(db, dossier))
        db.commit()
    return _sorties(db, principal, [dossier])[0]


def supprimer(db: Session, principal: Principal, dossier_id: int, ip: str | None) -> None:
    dossier = exiger_acces_dossier(db, principal, dossier_id, DOSSIER_MODIFIER)
    if db.scalar(select(func.count()).select_from(Dossier).where(Dossier.parent_id == dossier.id)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Ce dossier contient des sous-dossiers : les supprimer ou les déplacer d'abord.")
    if db.scalar(select(func.count()).select_from(Document).where(Document.dossier_id == dossier.id)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Ce dossier contient des fichiers (corbeille comprise) : les supprimer d'abord.")
    perimetre = _perimetre(db, dossier)
    log_action(db, principal.user.id, "dossier.supprimer", "dossier", dossier.id, {"nom": dossier.nom}, ip)
    ecrire_historique(db, acteur=principal.user, cible_type="dossier", cible_id=dossier.id, action="dossier_supprime", avant=dossier.nom, **perimetre)
    db.delete(dossier)
    db.commit()
