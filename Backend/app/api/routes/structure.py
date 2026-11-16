"""Routes de la structure : directions, services, agents. Réservées à l'ADMIN (permission structure.gerer).
Un UTILISATEUR ne peut donc créer ni agent, ni service, ni direction."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import client_ip, get_db, require
from app.core.permissions import STRUCTURE_GERER, Principal
from app.schemas.structure import (
    AgentIn, AgentOut, AgentUpdate, DirectionIn, DirectionOut, DirectionUpdate, DivisionIn, DivisionOut, DivisionUpdate,
    ServiceIn, ServiceOut, ServiceUpdate,
)
from app.services.structure import crud

router = APIRouter(prefix="/structure", tags=["structure"])
_admin = require(STRUCTURE_GERER)


@router.get("/directions", response_model=list[DirectionOut])
def list_directions(_: Principal = Depends(_admin), db: Session = Depends(get_db)):
    return crud.list_directions(db)


@router.post("/directions", response_model=DirectionOut, status_code=201)
def create_direction(data: DirectionIn, request: Request, actor: Principal = Depends(_admin), db: Session = Depends(get_db)):
    return crud.create_direction(db, actor.user.id, data, client_ip(request))


@router.patch("/directions/{direction_id}", response_model=DirectionOut)
def update_direction(
    direction_id: int, data: DirectionUpdate, request: Request,
    actor: Principal = Depends(_admin), db: Session = Depends(get_db),
):
    return crud.update_direction(db, actor.user.id, direction_id, data, client_ip(request))


@router.get("/services", response_model=list[ServiceOut])
def list_services(_: Principal = Depends(_admin), db: Session = Depends(get_db)):
    return [crud.to_service_out(s) for s in crud.list_services(db)]


@router.post("/services", response_model=ServiceOut, status_code=201)
def create_service(data: ServiceIn, request: Request, actor: Principal = Depends(_admin), db: Session = Depends(get_db)):
    return crud.to_service_out(crud.create_service(db, actor.user.id, data, client_ip(request)))


@router.patch("/services/{service_id}", response_model=ServiceOut)
def update_service(
    service_id: int, data: ServiceUpdate, request: Request,
    actor: Principal = Depends(_admin), db: Session = Depends(get_db),
):
    return crud.to_service_out(crud.update_service(db, actor.user.id, service_id, data, client_ip(request)))


@router.get("/divisions", response_model=list[DivisionOut])
def list_divisions(_: Principal = Depends(_admin), db: Session = Depends(get_db)):
    return [crud.to_division_out(d) for d in crud.list_divisions(db)]


@router.post("/divisions", response_model=DivisionOut, status_code=201)
def create_division(
    data: DivisionIn, request: Request, actor: Principal = Depends(_admin), db: Session = Depends(get_db),
):
    return crud.to_division_out(crud.create_division(db, actor.user.id, data, client_ip(request)))


@router.patch("/divisions/{division_id}", response_model=DivisionOut)
def update_division(
    division_id: int, data: DivisionUpdate, request: Request,
    actor: Principal = Depends(_admin), db: Session = Depends(get_db),
):
    return crud.to_division_out(crud.update_division(db, actor.user.id, division_id, data, client_ip(request)))


@router.get("/postes", response_model=dict)
def list_postes(_: Principal = Depends(_admin), db: Session = Depends(get_db)):
    return {"chefs_service": [], "chefs_division": []}


@router.get("/agents", response_model=list[AgentOut])
def list_agents(_: Principal = Depends(_admin), db: Session = Depends(get_db)):
    return crud.list_agents(db)


@router.post("/agents", response_model=AgentOut, status_code=201)
def create_agent(data: AgentIn, request: Request, actor: Principal = Depends(_admin), db: Session = Depends(get_db)):
    return crud.create_agent(db, actor.user.id, data, client_ip(request))


@router.patch("/agents/{agent_id}", response_model=AgentOut)
def update_agent(
    agent_id: int, data: AgentUpdate, request: Request,
    actor: Principal = Depends(_admin), db: Session = Depends(get_db),
):
    return crud.update_agent(db, actor.user.id, agent_id, data, client_ip(request))
