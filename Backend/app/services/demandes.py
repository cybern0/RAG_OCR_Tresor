"""Demandes d'accès.

- Demande de RÔLE : durable ; acceptée, le rôle s'ajoute aux rôles de l'agent (décision du gérant de la division).
- Demande d'accès PONCTUEL à un fichier : exception à expiration, sans modifier les rôles de l'agent.
Une demande en attente par cible et par demandeur (index unique en base). Création, décision, annulation : historisées et notifiées.
"""

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.acces import (
    divisions_deverrouillees,
    divisions_gerees,
    est_chef_nominal,
    est_membre,
    exiger_gestion_division,
    role_sur_document,
)
from app.core.permissions import Principal
from app.db.metier import AccesException, DemandeAcces, Division, RoleDivision, User, UserRoleDivision
from app.db.vecteur import Document
from app.schemas.demande import DemandeIn, DemandeOut, ExceptionOut
from app.services.audit import log_action
from app.services.historique import ecrire_historique
from app.services.notifications import destinataires_gestion, notifier

DUREE_PAR_DEFAUT_HEURES = 24


def _maintenant() -> datetime:
    return datetime.now(timezone.utc)


def _nom_user(db: Session, user_id: int | None) -> str | None:
    if user_id is None:
        return None
    u = db.get(User, user_id)
    if u is None:
        return None
    return f"{u.agent.prenom} {u.agent.nom}" if u.agent else u.nom_utilisateur


def _libelle_cible(db: Session, principal: Principal, d: DemandeAcces, *, voir_titre: bool) -> str:
    if d.type_demande == "role":
        role = db.get(RoleDivision, d.role_division_id)
        return role.libelle if role else "Rôle supprimé"
    doc = db.get(Document, d.document_id)
    if doc is None:
        return "Fichier supprimé"
    # le titre d'un fichier masqué n'est révélé qu'à ceux qui peuvent le lire (gérant, ou demandeur ayant désormais accès)
    return doc.titre if voir_titre or role_sur_document(db, principal, doc) is not None else f"Fichier n°{doc.id}"


def _out(db: Session, principal: Principal, d: DemandeAcces, gerees: set[int]) -> DemandeOut:
    division = db.get(Division, d.division_id)
    return DemandeOut(
        id=d.id, type_demande=d.type_demande, statut=d.statut, demandeur_user_id=d.demandeur_user_id,
        demandeur_nom=_nom_user(db, d.demandeur_user_id) or "?", division_id=d.division_id, division_nom=division.nom,
        cible_id=d.role_division_id or d.document_id, cible_libelle=_libelle_cible(db, principal, d, voir_titre=d.division_id in gerees),
        motif=d.motif, duree_heures=d.duree_heures, reponse=d.reponse, decisionnaire_nom=_nom_user(db, d.decisionnaire_user_id),
        date_creation=d.date_creation, date_decision=d.date_decision,
        peut_decider=d.statut == "en_attente" and d.division_id in gerees,
        peut_annuler=d.statut == "en_attente" and d.demandeur_user_id == principal.user.id,
    )


def _divisions_traitables(db: Session, principal: Principal) -> set[int]:
    """Divisions dont on peut traiter les demandes : gérant, et division déverrouillée si l'on n'en est pas le chef."""
    debloquees = divisions_deverrouillees(db, principal)
    return {d.id for d in divisions_gerees(db, principal) if est_chef_nominal(principal, d.id) or d.id in debloquees}


def creer(db: Session, principal: Principal, data: DemandeIn, ip: str | None) -> DemandeOut:
    if data.type_demande == "role":
        role = db.get(RoleDivision, data.cible_id)
        if role is None or not est_membre(principal, role.division_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Rôle introuvable.")
        if not role.actif:
            raise HTTPException(status.HTTP_409_CONFLICT, "Ce rôle est désactivé : il ne peut plus être demandé.")
        if role.id in principal.role_ids:
            raise HTTPException(status.HTTP_409_CONFLICT, "Vous avez déjà ce rôle.")
        division_id, libelle = role.division_id, f"le rôle « {role.libelle} »"
        demande = DemandeAcces(demandeur_user_id=principal.user.id, division_id=division_id, type_demande="role", role_division_id=role.id, motif=data.motif.strip())
    else:
        doc = db.get(Document, data.cible_id)
        if doc is None or not est_membre(principal, doc.division_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Fichier introuvable.")
        if doc.corbeille_le is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, "Ce fichier est dans la corbeille.")
        if role_sur_document(db, principal, doc) is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, "Vous avez déjà accès à ce fichier.")
        division_id, libelle = doc.division_id, f"l'accès au fichier « {doc.titre} »"
        demande = DemandeAcces(
            demandeur_user_id=principal.user.id, division_id=division_id, type_demande="fichier", document_id=doc.id,
            motif=data.motif.strip(), duree_heures=data.duree_heures or DUREE_PAR_DEFAUT_HEURES,
        )
    division = db.get(Division, division_id)
    if not division.actif:
        raise HTTPException(status.HTTP_409_CONFLICT, "Cette division est désactivée.")
    db.add(demande)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Une demande identique est déjà en attente.") from None
    nom = _nom_user(db, principal.user.id)
    ecrire_historique(
        db, acteur=principal.user, cible_type="demande", cible_id=demande.id, action="demande_creee",
        apres={"type": data.type_demande, "cible": libelle}, motif=demande.motif,
        service_id=division.service_id, division_id=division.id, concerne_user_id=principal.user.id,
    )
    notifier(
        db, destinataires_gestion(db, division), "demande_acces", f"{nom} demande {libelle}.",
        reference_type="demande", reference_id=demande.id, sauf_user_id=principal.user.id,
    )
    db.commit()
    return _out(db, principal, demande, set())


def lister(db: Session, principal: Principal, vue: str = "mes", statut: str | None = None) -> list[DemandeOut]:
    gerees = _divisions_traitables(db, principal)
    stmt = select(DemandeAcces)
    if vue == "a_traiter":
        if not gerees:
            return []
        stmt = stmt.where(DemandeAcces.division_id.in_(gerees))
    else:
        stmt = stmt.where(DemandeAcces.demandeur_user_id == principal.user.id)
    if statut:
        stmt = stmt.where(DemandeAcces.statut == statut)
    rows = db.scalars(stmt.order_by(DemandeAcces.date_creation.desc(), DemandeAcces.id.desc()).limit(200)).all()
    return [_out(db, principal, d, gerees) for d in rows]


def decider(db: Session, principal: Principal, demande_id: int, accepter: bool, reponse: str | None, duree_heures: int | None, ip: str | None) -> DemandeOut:
    demande = db.get(DemandeAcces, demande_id)
    if demande is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Demande introuvable.")
    division = exiger_gestion_division(db, principal, demande.division_id)  # 404 / 403 / 423
    if demande.statut != "en_attente":
        raise HTTPException(status.HTTP_409_CONFLICT, "Cette demande a déjà été traitée.")
    demandeur = db.get(User, demande.demandeur_user_id)
    if accepter:
        if demandeur is None or not demandeur.actif or demandeur.agent is None or demandeur.agent.division_id != division.id:
            raise HTTPException(status.HTTP_409_CONFLICT, "Le demandeur n'est plus actif dans cette division : refusez la demande.")
        if demande.type_demande == "role":
            role = db.get(RoleDivision, demande.role_division_id)
            if role is None or not role.actif:
                raise HTTPException(status.HTTP_409_CONFLICT, "Ce rôle n'existe plus ou est désactivé.")
            db.merge(UserRoleDivision(user_id=demandeur.id, role_division_id=role.id))
            ecrire_historique(
                db, acteur=principal.user, cible_type="utilisateur", cible_id=demandeur.id, action="roles_attribues",
                apres=[role.libelle], motif=f"Demande n°{demande.id} acceptée", service_id=division.service_id,
                division_id=division.id, concerne_user_id=demandeur.id,
            )
            resume = f"le rôle « {role.libelle} »"
        else:
            doc = db.get(Document, demande.document_id)
            if doc is None or doc.corbeille_le is not None:
                raise HTTPException(status.HTTP_409_CONFLICT, "Ce fichier n'existe plus : refusez la demande.")
            heures = duree_heures or demande.duree_heures or DUREE_PAR_DEFAUT_HEURES
            exception = AccesException(
                user_id=demandeur.id, document_id=doc.id, demande_id=demande.id, accorde_par=principal.user.id,
                motif=demande.motif, expire_le=_maintenant() + timedelta(hours=heures),
            )
            db.add(exception)
            db.flush()
            ecrire_historique(
                db, acteur=principal.user, cible_type="document", cible_id=doc.id, action="exception_accordee",
                apres={"utilisateur": demandeur.nom_utilisateur, "heures": heures}, motif=f"Demande n°{demande.id} acceptée",
                service_id=division.service_id, division_id=division.id, concerne_user_id=demandeur.id,
            )
            resume = f"l'accès au fichier « {doc.titre} » pendant {heures} h"
    demande.statut = "acceptee" if accepter else "refusee"
    demande.decisionnaire_user_id = principal.user.id
    demande.reponse = reponse
    demande.date_decision = _maintenant()
    db.flush()
    ecrire_historique(
        db, acteur=principal.user, cible_type="demande", cible_id=demande.id,
        action="demande_acceptee" if accepter else "demande_refusee", motif=reponse,
        service_id=division.service_id, division_id=division.id, concerne_user_id=demande.demandeur_user_id,
    )
    log_action(db, principal.user.id, "demande.decider", "demande", demande.id, {"accepter": accepter}, ip)
    notifier(
        db, [demande.demandeur_user_id], "demande_decidee",
        f"Votre demande est acceptée : {resume}." if accepter else "Votre demande a été refusée" + (f" : {reponse}" if reponse else "."),
        reference_type="demande", reference_id=demande.id,
    )
    db.commit()
    return _out(db, principal, demande, {division.id})


def annuler(db: Session, principal: Principal, demande_id: int) -> DemandeOut:
    demande = db.get(DemandeAcces, demande_id)
    if demande is None or demande.demandeur_user_id != principal.user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Demande introuvable.")
    if demande.statut != "en_attente":
        raise HTTPException(status.HTTP_409_CONFLICT, "Cette demande a déjà été traitée.")
    division = db.get(Division, demande.division_id)
    demande.statut, demande.date_decision = "annulee", _maintenant()
    ecrire_historique(
        db, acteur=principal.user, cible_type="demande", cible_id=demande.id, action="demande_annulee",
        service_id=division.service_id, division_id=division.id, concerne_user_id=principal.user.id,
    )
    db.commit()
    return _out(db, principal, demande, set())


# --- Exceptions ponctuelles -----------------------------------------------------------------------------------------

def lister_exceptions(db: Session, principal: Principal) -> list[ExceptionOut]:
    gerees = _divisions_traitables(db, principal)
    if not gerees:
        return []
    rows = db.execute(
        select(AccesException, Document)
        .join(Document, Document.id == AccesException.document_id)
        .where(Document.division_id.in_(gerees), AccesException.active.is_(True), AccesException.expire_le > _maintenant())
        .order_by(AccesException.expire_le)
    ).all()
    divisions = {d.id: d.nom for d in db.scalars(select(Division).where(Division.id.in_(gerees)))}
    return [
        ExceptionOut(
            id=e.id, user_id=e.user_id, utilisateur_nom=_nom_user(db, e.user_id) or "?", document_id=doc.id, document_titre=doc.titre,
            division_nom=divisions.get(doc.division_id, ""), expire_le=e.expire_le, motif=e.motif, accorde_par_nom=_nom_user(db, e.accorde_par),
        )
        for e, doc in rows
    ]


def revoquer_exception(db: Session, principal: Principal, exception_id: int) -> None:
    exception = db.get(AccesException, exception_id)
    doc = db.get(Document, exception.document_id) if exception else None
    if exception is None or doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Accès ponctuel introuvable.")
    division = exiger_gestion_division(db, principal, doc.division_id)
    if not exception.active:
        raise HTTPException(status.HTTP_409_CONFLICT, "Cet accès est déjà révoqué.")
    exception.active = False
    ecrire_historique(
        db, acteur=principal.user, cible_type="document", cible_id=doc.id, action="exception_revoquee",
        service_id=division.service_id, division_id=division.id, concerne_user_id=exception.user_id,
    )
    notifier(db, [exception.user_id], "exception_revoquee", f"Votre accès ponctuel au fichier « {doc.titre} » a été retiré.",
             reference_type="document", reference_id=doc.id)
    db.commit()
