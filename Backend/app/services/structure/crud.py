"""Logique de la structure : directions, services, divisions, agents, titres et postes.

Suppression gardée (CRUD complet) : une direction encore pourvue de services, un service encore pourvu de
divisions ou d'agents, une division encore utilisée (agents, rôles, documents, demandes d'accès) sont refusés
avec un 409 qui dit quoi traiter d'abord. Supprimer un agent dissocie son compte utilisateur — le compte survit,
sans agent lié. Un titre vaut rôle d'administration : un seul chef de division actif par division et un seul chef
de service actif par service, garantis par des index uniques en base ; ici on donne seulement des messages clairs
et on trace dans l'historique. Le chef de service a le même rôle que le chef de division, étendu à toutes les
divisions de son service ; il gère les agents de SON service (création, affectation, postes de chef de division)
— le périmètre est vérifié ici.
"""

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.core.permissions import (
    NIVEAU_ROOT,
    NIVEAU_SERVICE,
    TITRE_CHEF_DIVISION,
    TITRE_CHEF_SERVICE,
    Principal,
)
from app.db.metier import (
    Agent,
    DemandeAcces,
    Direction,
    Division,
    RoleDivision,
    Service,
    User,
    UserRoleDivision,
)
from app.db.vecteur import Document  # gardes de suppression : documents classés dans la division
from app.schemas.structure import (
    AgentIn,
    AgentOut,
    AgentUpdate,
    ChefOut,
    DirectionIn,
    DirectionUpdate,
    DivisionIn,
    DivisionOut,
    DivisionUpdate,
    PosteDivisionOut,
    PosteServiceOut,
    PostesOut,
    ServiceArbreOut,
    ServiceIn,
    ServiceOut,
    ServiceUpdate,
    UniteArbreOut,
)
from app.services.audit import log_action
from app.services.historique import ecrire_historique
from app.services.notifications import notifier, super_admins_actifs, users_de_agent


def _commit_or_conflict(db: Session, message: str) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, message) from None


def _apply(obj, data: dict) -> dict:
    changes = {}
    for key, value in data.items():
        if getattr(obj, key) != value:
            setattr(obj, key, value)
            changes[key] = value
    return changes


def _nom(a: Agent) -> str:
    return f"{a.prenom} {a.nom}"


def _chef_out(a: Agent | None) -> ChefOut | None:
    return ChefOut(agent_id=a.id, nom_complet=_nom(a)) if a else None


def _service_perimetre(db: Session, principal: Principal, service_id: int) -> Service:
    """Un chef de service ne gère que SA structure : 404 hors périmètre (l'existence n'est pas révélée)."""
    service = db.get(Service, service_id)
    if service is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Service introuvable.")
    if principal.niveau != NIVEAU_ROOT and principal.service_id != service_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Service introuvable.")
    return service


# --- Directions ----------------------------------------------------------------------------------------------

def list_directions(db: Session) -> list[Direction]:
    return list(db.scalars(select(Direction).order_by(Direction.nom)))


def create_direction(db: Session, actor_id: int, data: DirectionIn, ip: str | None) -> Direction:
    obj = Direction(code=data.code.strip().upper(), nom=data.nom.strip())
    db.add(obj)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Ce code de direction existe déjà.") from None
    log_action(db, actor_id, "structure.direction.creer", "direction", obj.id, {"code": obj.code}, ip)
    db.commit()
    return obj


def update_direction(db: Session, actor_id: int, direction_id: int, data: DirectionUpdate, ip: str | None) -> Direction:
    obj = db.get(Direction, direction_id)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Direction introuvable.")
    changes = _apply(obj, data.model_dump(exclude_unset=True, exclude_none=True))
    if changes:
        log_action(db, actor_id, "structure.direction.modifier", "direction", obj.id, changes, ip)
        db.commit()
    return obj


# --- Services ------------------------------------------------------------------------------------------------

def to_service_out(s: Service) -> ServiceOut:
    return ServiceOut(
        id=s.id, code=s.code, nom=s.nom, site=s.site, actif=s.actif,
        direction_id=s.direction_id, direction_nom=s.direction.nom,
    )


def list_services(db: Session, principal: Principal | None = None) -> list[Service]:
    """Tous les services (super administrateur) ; le chef de service ne voit que le sien."""
    stmt = select(Service).options(joinedload(Service.direction)).order_by(Service.nom)
    if principal is not None and principal.niveau == NIVEAU_SERVICE:
        stmt = stmt.where(Service.id == principal.service_id)
    return list(db.scalars(stmt))


def _get_service(db: Session, service_id: int) -> Service:
    obj = db.scalars(select(Service).options(joinedload(Service.direction)).where(Service.id == service_id)).one_or_none()
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Service introuvable.")
    return obj


def create_service(db: Session, actor_id: int, data: ServiceIn, ip: str | None) -> Service:
    if db.get(Direction, data.direction_id) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Direction introuvable.")
    obj = Service(direction_id=data.direction_id, code=data.code.strip().upper(), nom=data.nom.strip(), site=data.site)
    db.add(obj)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Ce code de service existe déjà.") from None
    log_action(db, actor_id, "structure.service.creer", "service", obj.id, {"code": obj.code}, ip)
    db.commit()
    return _get_service(db, obj.id)


def update_service(db: Session, actor_id: int, service_id: int, data: ServiceUpdate, ip: str | None) -> Service:
    obj = _get_service(db, service_id)
    values = data.model_dump(exclude_unset=True)
    if values.get("direction_id") is not None and db.get(Direction, values["direction_id"]) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Direction introuvable.")
    values = {k: v for k, v in values.items() if v is not None or k == "site"}
    changes = _apply(obj, values)
    if changes:
        log_action(db, actor_id, "structure.service.modifier", "service", obj.id, changes, ip)
        db.commit()
    return _get_service(db, obj.id)


# --- Divisions -----------------------------------------------------------------------------------------------

def to_division_out(d: Division) -> DivisionOut:
    return DivisionOut(
        id=d.id, service_id=d.service_id, service_nom=d.service.nom if d.service else None,
        code=d.code, nom=d.nom, actif=d.actif,
    )


def list_divisions(db: Session, principal: Principal | None = None) -> list[Division]:
    """Toutes les divisions (super administrateur) ; celles du service pour un chef de service."""
    stmt = select(Division).options(joinedload(Division.service)).order_by(Division.nom)
    if principal is not None and principal.niveau == NIVEAU_SERVICE:
        stmt = stmt.where(Division.service_id == principal.service_id)
    return list(db.scalars(stmt))


def _get_division(db: Session, division_id: int) -> Division:
    obj = db.scalars(select(Division).options(joinedload(Division.service)).where(Division.id == division_id)).one_or_none()
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Division introuvable.")
    return obj


def create_division(db: Session, actor_id: int, data: DivisionIn, ip: str | None) -> Division:
    service = db.get(Service, data.service_id)
    if service is None or not service.actif:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Service introuvable ou inactif.")
    obj = Division(service_id=data.service_id, nom=data.nom.strip(), code=(data.code or data.nom).strip()[:30])
    db.add(obj)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Cette division existe déjà (nom ou code).") from None
    log_action(db, actor_id, "structure.division.creer", "division", obj.id, {"nom": obj.nom}, ip)
    db.commit()
    return _get_division(db, obj.id)


def update_division(db: Session, actor_id: int, division_id: int, data: DivisionUpdate, ip: str | None) -> Division:
    obj = _get_division(db, division_id)
    changes = {}
    if data.nom is not None:
        value = data.nom.strip()
        if not value:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Le nom de la division ne peut pas être vide.")
        obj.nom = value
        changes["nom"] = value
    if data.code is not None:
        obj.code = data.code.strip()[:30] or None
        changes["code"] = obj.code
    if data.actif is not None and data.actif != obj.actif:
        obj.actif = data.actif
        changes["actif"] = data.actif
    if changes:
        log_action(db, actor_id, "structure.division.modifier", "division", obj.id, changes, ip)
        _commit_or_conflict(db, "Ce nom ou ce code de division existe déjà.")
    return _get_division(db, obj.id)


# --- Agents --------------------------------------------------------------------------------------------------

def to_agent_out(a: Agent, username: str | None) -> AgentOut:
    return AgentOut(
        id=a.id, matricule=a.matricule, nom=a.nom, prenom=a.prenom, fonction=a.fonction, email=a.email,
        service_id=a.service_id, division_id=a.division_id, titre=a.titre,
        service_nom=a.service.nom if a.service else None, division_nom=a.division.nom if a.division else None,
        actif=a.actif, nom_utilisateur=username,
    )


def list_agents(db: Session, principal: Principal | None = None) -> list[AgentOut]:
    """Tous les agents (super administrateur) ; les agents du service pour un chef de service."""
    stmt = (
        select(Agent, User.nom_utilisateur)
        .options(joinedload(Agent.service), joinedload(Agent.division))
        .outerjoin(User, User.agent_id == Agent.id)
        .order_by(Agent.nom, Agent.prenom)
    )
    if principal is not None and principal.niveau == NIVEAU_SERVICE:
        stmt = stmt.where(Agent.service_id == principal.service_id)
    return [to_agent_out(a, username) for a, username in db.execute(stmt).unique()]


def _agent_out(db: Session, agent_id: int) -> AgentOut:
    row = db.execute(
        select(Agent, User.nom_utilisateur).options(joinedload(Agent.service), joinedload(Agent.division))
        .outerjoin(User, User.agent_id == Agent.id).where(Agent.id == agent_id)
    ).unique().one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Agent introuvable.")
    return to_agent_out(*row)


def _occupant(db: Session, titre: str, division_id: int, sauf_agent_id: int | None = None) -> Agent | None:
    stmt = select(Agent).where(Agent.titre == titre, Agent.actif.is_(True), Agent.division_id == division_id)
    if sauf_agent_id is not None:
        stmt = stmt.where(Agent.id != sauf_agent_id)
    return db.scalars(stmt).first()


def _exiger_poste_libre(db: Session, titre: str, division_id: int, sauf_agent_id: int | None = None) -> None:
    occupant = _occupant(db, titre, division_id, sauf_agent_id)
    if occupant is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Le poste de chef de division est déjà occupé par {_nom(occupant)} : utilisez le transfert de poste.",
        )


def _occupant_service(db: Session, service_id: int, sauf_agent_id: int | None = None) -> Agent | None:
    stmt = select(Agent).where(Agent.titre == TITRE_CHEF_SERVICE, Agent.actif.is_(True), Agent.service_id == service_id)
    if sauf_agent_id is not None:
        stmt = stmt.where(Agent.id != sauf_agent_id)
    return db.scalars(stmt).first()


def _exiger_poste_libre_service(db: Session, service_id: int, sauf_agent_id: int | None = None) -> None:
    occupant = _occupant_service(db, service_id, sauf_agent_id)
    if occupant is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Le poste de chef de service est déjà occupé par {_nom(occupant)} : utilisez le transfert de poste.",
        )


def _valider_etat(db: Session, service_id: int, division_id: int | None, titre: str | None, *, creation: bool) -> Division | None:
    service = db.get(Service, service_id)
    if service is None or not service.actif:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Service introuvable ou inactif.")
    division = None
    if division_id is not None:
        division = db.get(Division, division_id)
        if division is None or not division.actif:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Division introuvable ou inactive.")
        if division.service_id != service_id:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "La division n'appartient pas à ce service.")
    if titre == TITRE_CHEF_DIVISION and division_id is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Un chef de division doit appartenir à une division.")
    if titre == TITRE_CHEF_SERVICE and division_id is not None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Un chef de service n'appartient à aucune division : il couvre toutes les divisions de son service.",
        )
    if creation and titre is None and division_id is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Choisissez la division de l'agent.")
    return division


def create_agent(db: Session, actor: Principal, data: AgentIn, ip: str | None) -> AgentOut:
    # un chef de service crée des agents dans SON service seulement (et ne nomme pas de chef de service)
    _service_perimetre(db, actor, data.service_id)
    if data.titre == TITRE_CHEF_SERVICE and actor.niveau != NIVEAU_ROOT:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Seul le super administrateur nomme un chef de service.")
    titre = data.titre
    _valider_etat(db, data.service_id, data.division_id, titre, creation=True)
    if titre == TITRE_CHEF_SERVICE:
        _exiger_poste_libre_service(db, data.service_id)
    elif titre:
        _exiger_poste_libre(db, titre, data.division_id)
    obj = Agent(
        matricule=data.matricule.strip(), nom=data.nom.strip(), prenom=data.prenom.strip(),
        fonction=data.fonction, email=data.email, service_id=data.service_id,
        division_id=data.division_id, titre=titre,
    )
    db.add(obj)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Ce matricule existe déjà.") from None
    log_action(db, actor.user.id, "structure.agent.creer", "agent", obj.id, {"matricule": obj.matricule}, ip)
    ecrire_historique(
        db, acteur=actor.user, cible_type="agent", cible_id=obj.id, action="agent_cree",
        apres={"nom": _nom(obj), "titre": titre}, service_id=obj.service_id, division_id=obj.division_id,
    )
    if titre:
        ecrire_historique(
            db, acteur=actor.user, cible_type="agent", cible_id=obj.id, action="chef_nomme", apres=titre,
            service_id=obj.service_id, division_id=obj.division_id,
        )
    db.commit()
    return _agent_out(db, obj.id)


def _retirer_roles_hors_division(db: Session, actor: User, agent: Agent) -> None:
    """Un agent qui change de division perd les rôles de l'ancienne (ils n'ont plus de sens ailleurs)."""
    user = db.scalars(select(User).where(User.agent_id == agent.id)).first()
    if user is None:
        return
    rows = db.execute(
        select(UserRoleDivision.role_division_id, RoleDivision.libelle, RoleDivision.division_id)
        .join(RoleDivision, RoleDivision.id == UserRoleDivision.role_division_id)
        .where(UserRoleDivision.user_id == user.id, RoleDivision.division_id.is_distinct_from(agent.division_id))
    ).all()
    if not rows:
        return
    ids = [r[0] for r in rows]
    db.execute(delete(UserRoleDivision).where(UserRoleDivision.user_id == user.id, UserRoleDivision.role_division_id.in_(ids)))
    ecrire_historique(
        db, acteur=actor, cible_type="utilisateur", cible_id=user.id, action="roles_retires",
        avant=[r[1] for r in rows], motif="Changement de division", service_id=agent.service_id,
        division_id=rows[0][2], concerne_user_id=user.id,
    )
    notifier(db, [user.id], "roles_modifies", "Vous avez changé de division : vos rôles de l'ancienne division sont retirés.",
             reference_type="utilisateur", reference_id=user.id)


def _notifier_vacance(db: Session, agent: Agent) -> None:
    """Un poste de chef devient vacant : on prévient les super administrateurs et, pour une division,
    le chef de service (il en est le gérant en attendant la nomination d'un chef)."""
    if agent.titre == TITRE_CHEF_SERVICE:
        notifier(
            db, super_admins_actifs(db), "poste_vacant",
            "Poste de chef de service vacant : le super administrateur assure l'intérim.",
            reference_type="agent", reference_id=agent.id,
        )
        return
    destinataires = list(super_admins_actifs(db))
    if agent.service_id is not None:
        chef_service = _occupant_service(db, agent.service_id)
        if chef_service is not None:
            destinataires += users_de_agent(db, chef_service.id)
    notifier(
        db, list(dict.fromkeys(destinataires)), "poste_vacant",
        "Poste de chef de division vacant : le super administrateur et le chef de service assurent l'intérim de la gestion de cette division.",
        reference_type="agent", reference_id=agent.id,
    )


def update_agent(db: Session, actor: Principal, agent_id: int, data: AgentUpdate, ip: str | None) -> AgentOut:
    obj = db.get(Agent, agent_id)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Agent introuvable.")
    # périmètre : un chef de service ne gère que les agents de son service, sans toucher au poste de chef de service
    _service_perimetre(db, actor, obj.service_id)
    fixes = data.model_fields_set
    values = data.model_dump(exclude_unset=True)
    titre_avant, service_avant, division_avant, actif_avant = obj.titre, obj.service_id, obj.division_id, obj.actif

    titre_final = values["titre"] if "titre" in fixes else obj.titre
    service_final = values.get("service_id") or obj.service_id
    division_final = values["division_id"] if "division_id" in fixes else obj.division_id
    _service_perimetre(db, actor, service_final)  # pas de déplacement hors du service du compte
    if actor.niveau != NIVEAU_ROOT and (
        TITRE_CHEF_SERVICE in (titre_final, titre_avant) or service_final != service_avant
    ):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Le poste de chef de service et les déplacements entre services restent réservés au super administrateur.",
        )
    deplace = service_final != service_avant or division_final != division_avant
    if deplace and titre_avant is not None and titre_final == titre_avant:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Cet agent a un titre : retirez-le ou transférez le poste avant de le changer de service ou de division."
        )
    if deplace or titre_final != titre_avant:
        _valider_etat(db, service_final, division_final, titre_final, creation=False)
    actif_final = values["actif"] if values.get("actif") is not None else obj.actif
    if titre_final and actif_final and (titre_final != titre_avant or not actif_avant or deplace):
        if titre_final == TITRE_CHEF_SERVICE:
            _exiger_poste_libre_service(db, service_final, sauf_agent_id=obj.id)
        else:
            _exiger_poste_libre(db, titre_final, division_final, sauf_agent_id=obj.id)

    changes = {}
    for key in ("nom", "prenom"):
        if values.get(key) is not None:
            changes.update(_apply(obj, {key: values[key].strip()}))
    for key in ("fonction", "email"):
        if key in fixes:
            changes.update(_apply(obj, {key: values[key]}))
    if values.get("actif") is not None:
        changes.update(_apply(obj, {"actif": values["actif"]}))
    obj.service_id, obj.division_id, obj.titre = service_final, division_final, titre_final
    if service_final != service_avant:
        changes["service_id"] = service_final
    if division_final != division_avant:
        changes["division_id"] = division_final
    if titre_final != titre_avant:
        changes["titre"] = titre_final

    if changes:
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            raise HTTPException(status.HTTP_409_CONFLICT, "Modification impossible : conflit de poste ou de données.") from None
        log_action(db, actor.user.id, "structure.agent.modifier", "agent", obj.id, changes, ip)
        ecrire_historique(
            db, acteur=actor.user, cible_type="agent", cible_id=obj.id, action="agent_modifie", apres=changes,
            service_id=obj.service_id, division_id=obj.division_id or division_avant,
        )
        if titre_final != titre_avant:
            if titre_final:
                ecrire_historique(db, acteur=actor.user, cible_type="agent", cible_id=obj.id, action="chef_nomme", apres=titre_final,
                                  service_id=obj.service_id, division_id=obj.division_id)
                notifier(db, users_de_agent(db, obj.id), "chef_nomme", "Vous êtes nommé(e) à un poste de chef.", reference_type="agent", reference_id=obj.id)
            else:
                ecrire_historique(db, acteur=actor.user, cible_type="agent", cible_id=obj.id, action="chef_retire", avant=titre_avant,
                                  service_id=obj.service_id, division_id=division_avant)
                notifier(db, users_de_agent(db, obj.id), "chef_retire", "Votre titre de chef vous a été retiré.", reference_type="agent", reference_id=obj.id)
                _notifier_vacance(db, Agent(id=obj.id, titre=titre_avant, service_id=obj.service_id, division_id=division_avant))
        elif "actif" in changes and titre_avant and not obj.actif:
            ecrire_historique(db, acteur=actor.user, cible_type="agent", cible_id=obj.id, action="poste_vacant", avant=titre_avant,
                              service_id=obj.service_id, division_id=division_avant)
            _notifier_vacance(db, obj)
        if division_final != division_avant:
            _retirer_roles_hors_division(db, actor.user, obj)
        db.commit()
    return _agent_out(db, obj.id)


# --- Postes : transfert, vacance, arbre ---------------------------------------------------------------------------

def transferer_chef(db: Session, actor: Principal, *, division_id: int, agent_id: int | None, motif: str | None, ip: str | None) -> PostesOut:
    """Retire le chef actuel et nomme le nouveau dans UNE transaction (agent_id = null : le poste devient vacant).
    Un chef de service nomme les chefs de division de SON service ; le super administrateur partout."""
    unite = _get_division(db, division_id)
    _service_perimetre(db, actor, unite.service_id)
    ancien = _occupant(db, TITRE_CHEF_DIVISION, division_id)
    nouveau = None
    if agent_id is not None:
        nouveau = db.get(Agent, agent_id)
        if nouveau is None or not nouveau.actif:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Agent introuvable ou inactif.")
        if nouveau.service_id != unite.service_id or nouveau.division_id != division_id:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "L'agent doit appartenir à cette division.")
        if nouveau.titre is not None and nouveau.titre != TITRE_CHEF_DIVISION:
            raise HTTPException(status.HTTP_409_CONFLICT, "Cet agent a déjà un autre titre : retirez-le d'abord.")
    if ancien is not None and nouveau is not None and ancien.id == nouveau.id:
        return postes(db)
    if ancien is None and nouveau is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ce poste est déjà vacant.")

    perimetre = {"service_id": unite.service_id, "division_id": division_id}
    if ancien is not None:
        ancien.titre = None
        db.flush()  # libère l'index unique avant de nommer le successeur
        ecrire_historique(db, acteur=actor.user, cible_type="agent", cible_id=ancien.id, action="chef_retire", avant=TITRE_CHEF_DIVISION, motif=motif, **perimetre)
        notifier(db, users_de_agent(db, ancien.id), "chef_retire", "Votre titre de chef vous a été retiré.", reference_type="agent", reference_id=ancien.id)
    if nouveau is not None:
        nouveau.titre = TITRE_CHEF_DIVISION
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            raise HTTPException(status.HTTP_409_CONFLICT, "Conflit de poste : réessayez.") from None
        ecrire_historique(db, acteur=actor.user, cible_type="agent", cible_id=nouveau.id, action="chef_nomme", apres=TITRE_CHEF_DIVISION, motif=motif, **perimetre)
        notifier(db, users_de_agent(db, nouveau.id), "chef_nomme", "Vous êtes nommé(e) à un poste de chef.", reference_type="agent", reference_id=nouveau.id)
    else:
        _notifier_vacance(db, Agent(id=ancien.id, titre=TITRE_CHEF_DIVISION, service_id=unite.service_id, division_id=division_id))
    log_action(db, actor.user.id, "structure.chef.transferer", "division", division_id, {"ancien": ancien.id if ancien else None, "nouveau": agent_id}, ip)
    db.commit()
    return postes(db)


def transferer_chef_service(db: Session, actor: User, *, service_id: int, agent_id: int | None, motif: str | None, ip: str | None) -> PostesOut:
    """Retire le chef de service actuel et nomme le nouveau dans UNE transaction (agent_id = null : le poste devient vacant).
    Le chef de service a le même rôle que le chef de division, étendu à toutes les divisions de son service ;
    il appartient au service, sans division. Réservé au super administrateur (garde de la route)."""
    unite = _get_service(db, service_id)
    ancien = _occupant_service(db, service_id)
    nouveau = None
    if agent_id is not None:
        nouveau = db.get(Agent, agent_id)
        if nouveau is None or not nouveau.actif:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Agent introuvable ou inactif.")
        if nouveau.service_id != unite.id or nouveau.division_id is not None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "Le chef de service appartient à ce service, sans division : retirez d'abord sa division.",
            )
        if nouveau.titre is not None and nouveau.titre != TITRE_CHEF_SERVICE:
            raise HTTPException(status.HTTP_409_CONFLICT, "Cet agent a déjà un autre titre : retirez-le d'abord.")
    if ancien is not None and nouveau is not None and ancien.id == nouveau.id:
        return postes(db)
    if ancien is None and nouveau is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ce poste est déjà vacant.")

    perimetre = {"service_id": unite.id, "division_id": None}
    if ancien is not None:
        ancien.titre = None
        db.flush()  # libère l'index unique avant de nommer le successeur
        ecrire_historique(db, acteur=actor, cible_type="agent", cible_id=ancien.id, action="chef_retire", avant=TITRE_CHEF_SERVICE, motif=motif, **perimetre)
        notifier(db, users_de_agent(db, ancien.id), "chef_retire", "Votre titre de chef vous a été retiré.", reference_type="agent", reference_id=ancien.id)
    if nouveau is not None:
        nouveau.titre = TITRE_CHEF_SERVICE
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            raise HTTPException(status.HTTP_409_CONFLICT, "Conflit de poste : réessayez.") from None
        ecrire_historique(db, acteur=actor, cible_type="agent", cible_id=nouveau.id, action="chef_nomme", apres=TITRE_CHEF_SERVICE, motif=motif, **perimetre)
        notifier(db, users_de_agent(db, nouveau.id), "chef_nomme", "Vous êtes nommé(e) chef de service : vous gérez toutes les divisions de votre service.", reference_type="agent", reference_id=nouveau.id)
    else:
        _notifier_vacance(db, Agent(id=ancien.id, titre=TITRE_CHEF_SERVICE, service_id=unite.id, division_id=None))
    log_action(db, actor.id, "structure.chef_service.transferer", "service", service_id, {"ancien": ancien.id if ancien else None, "nouveau": agent_id}, ip)
    db.commit()
    return postes(db)


def postes(db: Session, principal: Principal | None = None) -> PostesOut:
    """Qui occupe quel poste : tout (super administrateur) ; les postes du service du chef de service."""
    chefs = db.scalars(select(Agent).where(Agent.titre == TITRE_CHEF_DIVISION, Agent.actif.is_(True))).all()
    cd = {a.division_id: a for a in chefs}
    chefs_service = db.scalars(select(Agent).where(Agent.titre == TITRE_CHEF_SERVICE, Agent.actif.is_(True))).all()
    cs = {a.service_id: a for a in chefs_service}
    stmt_div = select(Division).order_by(Division.nom)
    stmt_svc = select(Service).order_by(Service.nom)
    if principal is not None and principal.niveau == NIVEAU_SERVICE:
        stmt_div = stmt_div.where(Division.service_id == principal.service_id)
        stmt_svc = stmt_svc.where(Service.id == principal.service_id)
    divisions = db.scalars(stmt_div).all()
    services = db.scalars(stmt_svc).all()
    return PostesOut(
        divisions=[
            PosteDivisionOut(division_id=d.id, division_nom=d.nom, service_id=d.service_id, chef=_chef_out(cd.get(d.id)))
            for d in divisions
        ],
        services=[
            PosteServiceOut(service_id=s.id, service_nom=s.nom, chef=_chef_out(cs.get(s.id)))
            for s in services
        ],
    )


def arbre(db: Session, principal: Principal) -> list[ServiceArbreOut]:
    """Organisation visible par le compte : tout (ROOT), son service et toutes ses divisions (chef de service),
    sa division (chef de division et agents)."""
    chefs = db.scalars(select(Agent).where(Agent.titre == TITRE_CHEF_DIVISION, Agent.actif.is_(True))).all()
    cd = {a.division_id: a for a in chefs}
    from sqlalchemy import func

    effectifs = dict(db.execute(select(Agent.division_id, func.count()).where(Agent.actif.is_(True)).group_by(Agent.division_id)).all())
    if principal.niveau == NIVEAU_ROOT:
        services = db.scalars(select(Service).order_by(Service.nom)).all()
    elif principal.service_id is not None:
        services = db.scalars(select(Service).where(Service.id == principal.service_id)).all()
    else:
        services = []
    resultat = []
    for s in services:
        unites = []
        for d in db.scalars(select(Division).where(Division.service_id == s.id).order_by(Division.nom)):
            membre = principal.division_id == d.id
            if principal.niveau == NIVEAU_ROOT:
                acces = "superieur"
            elif principal.niveau == NIVEAU_SERVICE:
                acces = "gerant"  # le chef de service voit et gère toutes les divisions de son service
            elif membre:
                acces = "membre"
            else:
                continue
            unites.append(
                UniteArbreOut(
                    id=d.id, code=d.code, nom=d.nom, actif=d.actif, chef=_chef_out(cd.get(d.id)),
                    nb_agents=effectifs.get(d.id, 0), acces=acces,
                )
            )
        if unites:
            resultat.append(ServiceArbreOut(id=s.id, code=s.code, nom=s.nom, actif=s.actif, divisions=unites))
    return resultat


# --- Suppressions (CRUD complet) : refus 409 tant que des éléments dépendent encore de l'objet ---------------

def delete_direction(db: Session, actor_id: int, direction_id: int, ip: str | None) -> None:
    """Supprime une direction ; refusée tant qu'elle contient des services (les déplacer ou les supprimer d'abord)."""
    obj = db.get(Direction, direction_id)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Direction introuvable.")
    nb = db.scalar(select(func.count()).select_from(Service).where(Service.direction_id == direction_id))
    if nb:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"La direction « {obj.nom} » contient {nb} service(s) : supprimez-les ou déplacez-les d'abord.",
        )
    db.delete(obj)
    log_action(db, actor_id, "structure.direction.supprimer", "direction", direction_id, {"code": obj.code, "nom": obj.nom}, ip)
    db.commit()


def delete_service(db: Session, actor_id: int, service_id: int, ip: str | None) -> None:
    """Supprime un service sans divisions ni agents (les documents ne bloquent pas : cree_par_service_id en SET NULL)."""
    obj = db.get(Service, service_id)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Service introuvable.")
    nb_div = db.scalar(select(func.count()).select_from(Division).where(Division.service_id == service_id))
    nb_agents = db.scalar(select(func.count()).select_from(Agent).where(Agent.service_id == service_id))
    if nb_div or nb_agents:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Le service « {obj.nom} » est encore utilisé ({nb_div} division(s), {nb_agents} agent(s)) : traitez-les d'abord.",
        )
    db.delete(obj)
    log_action(db, actor_id, "structure.service.supprimer", "service", service_id, {"code": obj.code, "nom": obj.nom}, ip)
    db.commit()


def delete_division(db: Session, actor_id: int, division_id: int, ip: str | None) -> None:
    """Supprime une division inutilisée ; le message liste ce qui la bloque : agents, rôles, documents, demandes."""
    obj = db.get(Division, division_id)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Division introuvable.")
    blocages = []
    nb_agents = db.scalar(select(func.count()).select_from(Agent).where(Agent.division_id == division_id))
    if nb_agents:
        blocages.append(f"{nb_agents} agent(s)")
    nb_roles = db.scalar(select(func.count()).select_from(RoleDivision).where(RoleDivision.division_id == division_id))
    if nb_roles:
        blocages.append(f"{nb_roles} rôle(s) de division")
    nb_docs = db.scalar(select(func.count()).select_from(Document).where(Document.division_id == division_id))
    if nb_docs:
        blocages.append(f"{nb_docs} document(s)")
    nb_demandes = db.scalar(select(func.count()).select_from(DemandeAcces).where(DemandeAcces.division_id == division_id))
    if nb_demandes:
        blocages.append(f"{nb_demandes} demande(s) d'accès")
    if blocages:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"La division « {obj.nom} » est encore utilisée : {', '.join(blocages)}. Traitez-les d'abord.",
        )
    db.delete(obj)
    log_action(db, actor_id, "structure.division.supprimer", "division", division_id, {"code": obj.code, "nom": obj.nom}, ip)
    db.commit()


def delete_agent(db: Session, actor: Principal, agent_id: int, ip: str | None) -> None:
    """Supprime un agent. Son compte utilisateur, s'il en a un, est dissocié (le compte survit, sans agent lié) ;
    l'historique conserve la fiche supprimée, titre compris — le poste redevient vacant (index unique libéré)."""
    obj = db.get(Agent, agent_id)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Agent introuvable.")
    compte = db.scalar(select(User).where(User.agent_id == agent_id))
    compte_nom = None
    if compte is not None:
        compte_nom = compte.nom_utilisateur
        compte.agent_id = None
    ecrire_historique(
        db, acteur=actor.user, cible_type="agent", cible_id=obj.id, action="agent_supprime",
        avant={"matricule": obj.matricule, "nom": obj.nom, "prenom": obj.prenom, "titre": obj.titre, "compte": compte_nom},
        service_id=obj.service_id, division_id=obj.division_id,
    )
    db.delete(obj)
    db.commit()
