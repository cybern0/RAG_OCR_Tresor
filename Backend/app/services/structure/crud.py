"""Logique de la structure : directions, services, agents.
Pas de suppression physique (les documents et comptes en dépendent) : on désactive avec `actif = false`."""

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.db.metier import Agent, Direction, Service, User
from app.schemas.structure import (
    AgentIn, AgentOut, AgentUpdate, DirectionIn, DirectionUpdate, ServiceIn, ServiceOut, ServiceUpdate,
)
from app.services.audit import log_action


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


def list_services(db: Session) -> list[Service]:
    return list(db.scalars(select(Service).options(joinedload(Service.direction)).order_by(Service.nom)))


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


# --- Agents --------------------------------------------------------------------------------------------------

def to_agent_out(a: Agent, username: str | None) -> AgentOut:
    return AgentOut(
        id=a.id, matricule=a.matricule, nom=a.nom, prenom=a.prenom, fonction=a.fonction, email=a.email,
        service_id=a.service_id, service_nom=a.service.nom if a.service else None, actif=a.actif,
        nom_utilisateur=username,
    )


def list_agents(db: Session) -> list[AgentOut]:
    rows = db.execute(
        select(Agent, User.nom_utilisateur)
        .options(joinedload(Agent.service))
        .outerjoin(User, User.agent_id == Agent.id)
        .order_by(Agent.nom, Agent.prenom)
    ).unique()
    return [to_agent_out(a, username) for a, username in rows]


def _agent_out(db: Session, agent_id: int) -> AgentOut:
    row = db.execute(
        select(Agent, User.nom_utilisateur).options(joinedload(Agent.service))
        .outerjoin(User, User.agent_id == Agent.id).where(Agent.id == agent_id)
    ).unique().one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Agent introuvable.")
    return to_agent_out(*row)


def create_agent(db: Session, actor_id: int, data: AgentIn, ip: str | None) -> AgentOut:
    service = db.get(Service, data.service_id)
    if service is None or not service.actif:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Service introuvable ou inactif.")
    obj = Agent(
        matricule=data.matricule.strip(), nom=data.nom.strip(), prenom=data.prenom.strip(),
        fonction=data.fonction, email=data.email, service_id=data.service_id,
    )
    db.add(obj)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Ce matricule existe déjà.") from None
    log_action(db, actor_id, "structure.agent.creer", "agent", obj.id, {"matricule": obj.matricule}, ip)
    db.commit()
    return _agent_out(db, obj.id)


def update_agent(db: Session, actor_id: int, agent_id: int, data: AgentUpdate, ip: str | None) -> AgentOut:
    obj = db.get(Agent, agent_id)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Agent introuvable.")
    values = data.model_dump(exclude_unset=True)
    if values.get("service_id") is not None:
        service = db.get(Service, values["service_id"])
        if service is None or not service.actif:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Service introuvable ou inactif.")
    # nom, prénom, service et actif ne peuvent pas être vidés ; fonction et email, si
    values = {k: v for k, v in values.items() if v is not None or k in ("fonction", "email")}
    changes = _apply(obj, values)
    if changes:
        log_action(db, actor_id, "structure.agent.modifier", "agent", obj.id, changes, ip)
        _commit_or_conflict(db, "Modification impossible.")
    return _agent_out(db, obj.id)
