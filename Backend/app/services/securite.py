"""Mots de passe de dossier (unités) : définition, déverrouillage temporaire.

Un secret = un couple (unité, super administrateur). Une division et un service en ont un pour chaque super administrateur ;
le chef de division n'en a pas : sa division ne contient pas de dossier protégé. Il n'y a plus de chef de service :
plus de réinitialisation hiérarchique (aucun échelon supérieur au super administrateur), le mot de passe de dossier
est strictement personnel. C'est une ré-authentification (verrou applicatif), pas un chiffrement.
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


def _maintenant() -> datetime:
    return datetime.now(timezone.utc)


def _unite(db: Session, type_unite: str, unite_id: int) -> Service | Division:
    obj = db.get(Service if type_unite == "service" else Division, unite_id)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unité introuvable.")
    return obj


def _service_id(unite: Service | Division) -> int:
    return unite.id if isinstance(unite, Service) else unite.service_id


def _perimetre(unite: Service | Division) -> dict:
    if isinstance(unite, Service):
        return {"service_id": unite.id, "division_id": None}
    return {"service_id": unite.service_id, "division_id": unite.id}


def _eligible(db: Session, user: User, unite: Service | Division) -> bool:
    """Un compte a-t-il un mot de passe de dossier sur cette unité ? Seuls les super administrateurs en ont (sur toutes les unités)."""
    return user.role.code == "ADMIN"


def _secret(db: Session, type_unite: str, unite_id: int, user_id: int) -> SecretUnite | None:
    colonne = SecretUnite.service_id if type_unite == "service" else SecretUnite.division_id
    return db.scalars(select(SecretUnite).where(colonne == unite_id, SecretUnite.admin_user_id == user_id)).first()


def _fermer_deverrouillages(db: Session, secret_id: int) -> None:
    db.execute(update(Deverrouillage).where(Deverrouillage.secret_unite_id == secret_id, Deverrouillage.actif.is_(True)).values(actif=False))


def lister_unites(db: Session, principal: Principal) -> list[UniteSecretOut]:
    """Unités sur lesquelles le compte peut (ou doit) avoir un mot de passe de dossier : toutes, pour le super administrateur."""
    if principal.niveau != NIVEAU_ROOT:
        return []
    services = db.scalars(select(Service).order_by(Service.nom)).all()
    divisions = db.scalars(select(Division).order_by(Division.nom)).all()
    noms_service = {s.id: s.nom for s in db.scalars(select(Service))}
    secrets = {(s.service_id, s.division_id): s for s in db.scalars(select(SecretUnite).where(SecretUnite.admin_user_id == principal.user.id))}
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
    for s in services:
        sec = secrets.get((s.id, None))
        vj = ouverts.get(sec.id) if sec else None
        sortie.append(UniteSecretOut(type="service", id=s.id, nom=s.nom, service_id=s.id, service_nom=s.nom,
                                     secret_defini=sec is not None, deverrouille=vj is not None, valide_jusqua=vj))
    for d in divisions:
        sec = secrets.get((None, d.id))
        vj = ouverts.get(sec.id) if sec else None
        via = False
        if vj is None:  # ouverte par le déverrouillage de son service (super administrateur)
            sec_s = secrets.get((d.service_id, None))
            vj_s = ouverts.get(sec_s.id) if sec_s else None
            if vj_s is not None:
                vj, via = vj_s, True
        sortie.append(UniteSecretOut(type="division", id=d.id, nom=d.nom, service_id=d.service_id, service_nom=noms_service.get(d.service_id, ""),
                                     secret_defini=sec is not None, deverrouille=vj is not None, valide_jusqua=vj, via_service=via))
    return sortie


def definir_secret(db: Session, actor: Principal, data: SecretIn, ip: str | None) -> None:
    """Définit ou change SON mot de passe de dossier ; l'ancien est exigé pour changer, et l'opération ferme les déverrouillages."""
    unite = _unite(db, data.type, data.unite_id)
    cible = actor.user
    if not _eligible(db, cible, unite):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cette unité n'a pas de mot de passe de dossier pour ce compte.")
    existant = _secret(db, data.type, data.unite_id, cible.id)
    if existant is not None:
        cle = f"secret|{cible.id}|{data.type}{data.unite_id}"
        if login_throttle.is_blocked(cle):
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Trop de tentatives. Réessayer dans quelques minutes.")
        if not verify_password(data.ancien_mot_de_passe or "", existant.secret_hash):
            login_throttle.record_failure(cle)
            log_action(db, actor.user.id, "securite.secret_echec", data.type, data.unite_id, {}, ip)
            db.commit()
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "L'ancien mot de passe de dossier est incorrect.")
        login_throttle.reset(cle)
    nouveau_hash = hash_password(data.nouveau_mot_de_passe)
    if existant is None:
        existant = SecretUnite(
            service_id=unite.id if data.type == "service" else None, division_id=unite.id if data.type == "division" else None,
            admin_user_id=cible.id, secret_hash=nouveau_hash, modifie_par=actor.user.id,
        )
        db.add(existant)
        action = "secret_defini"
    else:
        existant.secret_hash, existant.modifie_par, existant.modifie_le = nouveau_hash, actor.user.id, _maintenant()
        action = "secret_modifie"
    db.flush()
    _fermer_deverrouillages(db, existant.id)
    ecrire_historique(
        db, acteur=actor.user, cible_type="unite", cible_id=unite.id, action=action,
        apres={"unite": data.type, "nom": unite.nom}, concerne_user_id=cible.id, **_perimetre(unite),
    )
    db.commit()


def deverrouiller(db: Session, actor: Principal, type_unite: str, unite_id: int, mot_de_passe: str, ip: str | None) -> DeverrouillageOut:
    unite = _unite(db, type_unite, unite_id)
    if isinstance(unite, Division) and (est_chef_nominal(actor, unite.id) or est_membre(actor, unite.id)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Aucun mot de passe de dossier : c'est votre division.")
    if not _eligible(db, actor.user, unite):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unité introuvable.")
    secret = _secret(db, type_unite, unite_id, actor.user.id)
    if secret is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={"code": "SECRET_NON_DEFINI", "message": "Aucun mot de passe de dossier défini pour cette unité : définissez-le d'abord."},
        )
    cle = f"unite|{actor.user.id}|{type_unite}{unite_id}"
    if login_throttle.is_blocked(cle):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Trop de tentatives. Réessayer dans quelques minutes.")
    if not verify_password(mot_de_passe, secret.secret_hash):
        login_throttle.record_failure(cle)
        log_action(db, actor.user.id, "securite.deverrouillage_echec", type_unite, unite_id, {"unite": unite.nom}, ip)
        db.commit()
        # 403 et non 401 : un 401 déconnecterait l'interface comme une session expirée
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Mot de passe de dossier incorrect.")
    login_throttle.reset(cle)
    _fermer_deverrouillages(db, secret.id)
    minutes = get_settings().deverrouillage_minutes
    fin = _maintenant() + timedelta(minutes=minutes)
    db.add(Deverrouillage(secret_unite_id=secret.id, user_id=actor.user.id, valide_jusqua=fin))
    log_action(db, actor.user.id, "securite.deverrouillage", type_unite, unite_id, {"unite": unite.nom}, ip)
    ecrire_historique(
        db, acteur=actor.user, cible_type="unite", cible_id=unite.id, action="deverrouillage",
        apres={"unite": type_unite, "nom": unite.nom, "minutes": minutes}, **_perimetre(unite),
    )
    db.commit()
    return DeverrouillageOut(valide_jusqua=fin, minutes=minutes)


def verrouiller(db: Session, actor: Principal, type_unite: str, unite_id: int) -> None:
    secret = _secret(db, type_unite, unite_id, actor.user.id)
    if secret is not None:
        _fermer_deverrouillages(db, secret.id)
        db.commit()
