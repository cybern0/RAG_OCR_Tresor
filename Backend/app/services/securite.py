"""Mots de passe de dossier (divisions) : définition, déverrouillage temporaire.

Les dossiers protégés existent au niveau des DIVISIONS seulement — aucun dossier ni mot de passe de service.
Un secret = un couple (division, super administrateur) : chaque division a SON mot de passe, individuel,
géré par le seul super administrateur. Les chefs (division ou service) n'en ont pas, et il n'existe plus de
réinitialisation hiérarchique (aucun échelon supérieur au super administrateur). C'est une ré-authentification
(verrou applicatif), pas un chiffrement.
"""

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.acces import est_chef_nominal, est_membre
from app.core.permissions import NIVEAU_ROOT, Principal
from app.core.security import hash_password, login_throttle, verify_password
from app.db.metier import Deverrouillage, Division, SecretUnite, Service, User
from app.schemas.securite import DeverrouillageOut, SecretIn, UniteSecretOut
from app.services.audit import log_action
from app.services.historique import ecrire_historique

_PAS_DE_SERVICE = "Les dossiers de service n'existent plus : chaque division a son propre mot de passe de dossier."


def _maintenant() -> datetime:
    return datetime.now(timezone.utc)


def _exiger_division(type_unite: str) -> None:
    if type_unite == "service":
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, _PAS_DE_SERVICE)


def _unite(db: Session, unite_id: int) -> Division:
    division = db.get(Division, unite_id)
    if division is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Division introuvable.")
    return division


def _eligible(db: Session, user: User, division: Division) -> bool:
    """Un compte a-t-il un mot de passe de dossier sur cette division ? Seuls les super administrateurs en ont (sur toutes)."""
    return user.role.code == "ADMIN"


def _secret(db: Session, division_id: int, user_id: int) -> SecretUnite | None:
    return db.scalars(
        select(SecretUnite).where(SecretUnite.division_id == division_id, SecretUnite.admin_user_id == user_id)
    ).first()


def _fermer_deverrouillages(db: Session, secret_id: int) -> None:
    db.execute(update(Deverrouillage).where(Deverrouillage.secret_unite_id == secret_id, Deverrouillage.actif.is_(True)).values(actif=False))


def lister_unites(db: Session, principal: Principal) -> list[UniteSecretOut]:
    """Divisions sur lesquelles le compte peut (ou doit) avoir un mot de passe de dossier : toutes, pour le super administrateur."""
    if principal.niveau != NIVEAU_ROOT:
        return []
    divisions = db.scalars(select(Division).order_by(Division.nom)).all()
    noms_service = {s.id: s.nom for s in db.scalars(select(Service))}
    secrets = {s.division_id: s for s in db.scalars(select(SecretUnite).where(SecretUnite.admin_user_id == principal.user.id))}
    now = _maintenant()
    ouverts = {
        sid: vj
        for sid, vj in db.execute(
            select(Deverrouillage.secret_unite_id, Deverrouillage.valide_jusqua).where(
                Deverrouillage.user_id == principal.user.id, Deverrouillage.actif.is_(True), Deverrouillage.valide_jusqua > now
            )
        )
    }
    sortie: list[UniteSecretOut] = []
    for d in divisions:
        sec = secrets.get(d.id)
        vj = ouverts.get(sec.id) if sec else None
        sortie.append(UniteSecretOut(type="division", id=d.id, nom=d.nom, service_id=d.service_id,
                                     service_nom=noms_service.get(d.service_id, ""),
                                     secret_defini=sec is not None, deverrouille=vj is not None, valide_jusqua=vj))
    return sortie


def definir_secret(db: Session, actor: Principal, data: SecretIn, ip: str | None) -> None:
    """Définit ou change SON mot de passe de dossier ; l'ancien est exigé pour changer, et l'opération ferme les déverrouillages."""
    _exiger_division(data.type)
    division = _unite(db, data.unite_id)
    cible = actor.user
    if not _eligible(db, cible, division):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cette division n'a pas de mot de passe de dossier pour ce compte.")
    existant = _secret(db, division.id, cible.id)
    if existant is not None:
        cle = f"secret|{cible.id}|{division.id}"
        if login_throttle.is_blocked(cle):
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Trop de tentatives. Réessayer dans quelques minutes.")
        if not verify_password(data.ancien_mot_de_passe or "", existant.secret_hash):
            login_throttle.record_failure(cle)
            log_action(db, actor.user.id, "securite.secret_echec", data.type, division.id, {}, ip)
            db.commit()
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "L'ancien mot de passe de dossier est incorrect.")
        login_throttle.reset(cle)
    nouveau_hash = hash_password(data.nouveau_mot_de_passe)
    if existant is None:
        existant = SecretUnite(
            division_id=division.id, admin_user_id=cible.id, secret_hash=nouveau_hash, modifie_par=actor.user.id,
        )
        db.add(existant)
        action = "secret_defini"
    else:
        existant.secret_hash, existant.modifie_par, existant.modifie_le = nouveau_hash, actor.user.id, _maintenant()
        action = "secret_modifie"
    db.flush()
    _fermer_deverrouillages(db, existant.id)
    ecrire_historique(
        db, acteur=actor.user, cible_type="unite", cible_id=division.id, action=action,
        apres={"unite": "division", "nom": division.nom},
        service_id=division.service_id, division_id=division.id, concerne_user_id=cible.id,
    )
    db.commit()


def deverrouiller(db: Session, actor: Principal, type_unite: str, unite_id: int, mot_de_passe: str, ip: str | None) -> DeverrouillageOut:
    _exiger_division(type_unite)
    division = _unite(db, unite_id)
    if est_chef_nominal(db, actor, division.id) or est_membre(actor, division.id):
        raise HTTPException(status.HTTP_409_CONFLICT, "Aucun mot de passe de dossier : c'est votre division.")
    if not _eligible(db, actor.user, division):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Division introuvable.")
    secret = _secret(db, division.id, actor.user.id)
    if secret is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={"code": "SECRET_NON_DEFINI", "message": "Aucun mot de passe de dossier défini pour cette division : définissez-le d'abord."},
        )
    cle = f"unite|{actor.user.id}|division{unite_id}"
    if login_throttle.is_blocked(cle):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Trop de tentatives. Réessayer dans quelques minutes.")
    if not verify_password(mot_de_passe, secret.secret_hash):
        login_throttle.record_failure(cle)
        log_action(db, actor.user.id, "securite.deverrouillage_echec", type_unite, unite_id, {"unite": division.nom}, ip)
        db.commit()
        # 403 et non 401 : un 401 déconnecterait l'interface comme une session expirée
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Mot de passe de dossier incorrect.")
    login_throttle.reset(cle)
    _fermer_deverrouillages(db, secret.id)
    minutes = get_settings().deverrouillage_minutes
    fin = _maintenant() + timedelta(minutes=minutes)
    db.add(Deverrouillage(secret_unite_id=secret.id, user_id=actor.user.id, valide_jusqua=fin))
    log_action(db, actor.user.id, "securite.deverrouillage", type_unite, unite_id, {"unite": division.nom}, ip)
    ecrire_historique(
        db, acteur=actor.user, cible_type="unite", cible_id=division.id, action="deverrouillage",
        apres={"unite": "division", "nom": division.nom, "minutes": minutes},
        service_id=division.service_id, division_id=division.id,
    )
    db.commit()
    return DeverrouillageOut(valide_jusqua=fin, minutes=minutes)


def verrouiller(db: Session, actor: Principal, type_unite: str, unite_id: int) -> None:
    _exiger_division(type_unite)
    secret = _secret(db, unite_id, actor.user.id)
    if secret is not None:
        _fermer_deverrouillages(db, secret.id)
        db.commit()
