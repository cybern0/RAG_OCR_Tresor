"""Routes de la structure : directions, services, divisions, agents.

Le super administrateur gère tout (permission structure.gérer + niveau ROOT). Le chef de service gère SON
service : listes, création et modification d'agents de son service, postes de chef de division de ses
divisions — le périmètre est vérifié dans services/structure (404 hors périmètre).
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.deps import client_ip, get_db, get_principal, require
from app.core.permissions import STRUCTURE_GERER, Principal
from app.schemas.structure import (
    AgentIn, AgentOut, AgentUpdate, DirectionIn, PostesOut, ServiceArbreOut, TransfertChefIn, DirectionOut, DirectionUpdate, DivisionIn, DivisionOut, DivisionUpdate,
    ServiceIn, ServiceOut, ServiceUpdate,
)
from app.services.structure import crud

router = APIRouter(prefix="/structure", tags=["structure"])
_admin = require(STRUCTURE_GERER)


def _super_admin(principal: Principal = Depends(_admin)) -> Principal:
    """Créations et modifications de la structure (directions, services, divisions) : super administrateur."""
    if not principal.is_admin:
        raise HTTPException(403, "Seul le super administrateur gère les directions, les services et les divisions.")
    return principal


@router.get("/directions", response_model=list[DirectionOut])
def list_directions(_: Principal = Depends(_super_admin), db: Session = Depends(get_db)):
    return crud.list_directions(db)


@router.post("/directions", response_model=DirectionOut, status_code=201)
def create_direction(data: DirectionIn, request: Request, actor: Principal = Depends(_super_admin), db: Session = Depends(get_db)):
    return crud.create_direction(db, actor.user.id, data, client_ip(request))


@router.patch("/directions/{direction_id}", response_model=DirectionOut)
def update_direction(
    direction_id: int, data: DirectionUpdate, request: Request,
    actor: Principal = Depends(_super_admin), db: Session = Depends(get_db),
):
    return crud.update_direction(db, actor.user.id, direction_id, data, client_ip(request))


@router.get("/services", response_model=list[ServiceOut])
def list_services(principal: Principal = Depends(_admin), db: Session = Depends(get_db)):
    return [crud.to_service_out(s) for s in crud.list_services(db, principal)]


@router.post("/services", response_model=ServiceOut, status_code=201)
def create_service(data: ServiceIn, request: Request, actor: Principal = Depends(_super_admin), db: Session = Depends(get_db)):
    return crud.to_service_out(crud.create_service(db, actor.user.id, data, client_ip(request)))


@router.patch("/services/{service_id}", response_model=ServiceOut)
def update_service(
    service_id: int, data: ServiceUpdate, request: Request,
    actor: Principal = Depends(_super_admin), db: Session = Depends(get_db),
):
    return crud.to_service_out(crud.update_service(db, actor.user.id, service_id, data, client_ip(request)))


@router.get("/divisions", response_model=list[DivisionOut])
def list_divisions(principal: Principal = Depends(_admin), db: Session = Depends(get_db)):
    return [crud.to_division_out(d) for d in crud.list_divisions(db, principal)]


@router.post("/divisions", response_model=DivisionOut, status_code=201)
def create_division(
    data: DivisionIn, request: Request, actor: Principal = Depends(_super_admin), db: Session = Depends(get_db),
):
    return crud.to_division_out(crud.create_division(db, actor.user.id, data, client_ip(request)))


@router.patch("/divisions/{division_id}", response_model=DivisionOut)
def update_division(
    division_id: int, data: DivisionUpdate, request: Request,
    actor: Principal = Depends(_super_admin), db: Session = Depends(get_db),
):
    return crud.to_division_out(crud.update_division(db, actor.user.id, division_id, data, client_ip(request)))


@router.get("/postes", response_model=PostesOut)
def list_postes(principal: Principal = Depends(_admin), db: Session = Depends(get_db)):
    """Qui occupe quel poste : l'interface désactive la case « chef » d'une division déjà pourvue."""
    return crud.postes(db, principal)


@router.get("/arbre", response_model=list[ServiceArbreOut])
def arbre(principal: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    """Organisation visible par le compte connecté (ses divisions et leurs chefs)."""
    return crud.arbre(db, principal)


@router.put("/divisions/{division_id}/chef", response_model=PostesOut)
def transferer_chef_division(
    division_id: int, data: TransfertChefIn, request: Request, actor: Principal = Depends(_admin), db: Session = Depends(get_db),
):
    return crud.transferer_chef(db, actor, division_id=division_id, agent_id=data.agent_id, motif=data.motif, ip=client_ip(request))


@router.put("/services/{service_id}/chef", response_model=PostesOut)
def transferer_chef_service(
    service_id: int, data: TransfertChefIn, request: Request, actor: Principal = Depends(_super_admin), db: Session = Depends(get_db),
):
    return crud.transferer_chef_service(db, actor.user, service_id=service_id, agent_id=data.agent_id, motif=data.motif, ip=client_ip(request))


@router.get("/agents", response_model=list[AgentOut])
def list_agents(principal: Principal = Depends(_admin), db: Session = Depends(get_db)):
    return crud.list_agents(db, principal)


@router.post("/agents", response_model=AgentOut, status_code=201)
def create_agent(data: AgentIn, request: Request, actor: Principal = Depends(_admin), db: Session = Depends(get_db)):
    return crud.create_agent(db, actor, data, client_ip(request))


@router.patch("/agents/{agent_id}", response_model=AgentOut)
def update_agent(
    agent_id: int, data: AgentUpdate, request: Request,
    actor: Principal = Depends(_admin), db: Session = Depends(get_db),
):
    return crud.update_agent(db, actor, agent_id, data, client_ip(request))
