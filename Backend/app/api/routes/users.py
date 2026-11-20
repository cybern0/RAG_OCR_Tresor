"""Routes de gestion des comptes, limitées au périmètre du compte connecté (voir core/portee.py)."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import client_ip, get_db, require
from app.core.permissions import UTILISATEUR_CREER, UTILISATEUR_LISTER, UTILISATEUR_MODIFIER, Principal
from app.schemas.user import AgentBrief, UserCreate, UserOut, UserUpdate
from app.services.users import crud

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserOut])
def list_users(principal: Principal = Depends(require(UTILISATEUR_LISTER)), db: Session = Depends(get_db)):
    return crud.users_out(db, crud.list_users(db, principal))


@router.get("/agents-disponibles", response_model=list[AgentBrief])
def agents_disponibles(
    pour_user: int | None = None,
    principal: Principal = Depends(require(UTILISATEUR_CREER)), db: Session = Depends(get_db),
):
    """Agents sans compte que l'on peut doter d'un compte (+ l'agent actuel de `pour_user`, pour le changer)."""
    return crud.agents_disponibles(db, principal, pour_user)


@router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: int, principal: Principal = Depends(require(UTILISATEUR_LISTER)), db: Session = Depends(get_db)):
    return crud.user_out(db, crud.get_user_visible(db, principal, user_id))


@router.post("", response_model=UserOut, status_code=201)
def create_user(
    data: UserCreate, request: Request,
    actor: Principal = Depends(require(UTILISATEUR_CREER)), db: Session = Depends(get_db),
):
    return crud.user_out(db, crud.create_user(db, actor, data, client_ip(request)))


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int, data: UserUpdate, request: Request,
    actor: Principal = Depends(require(UTILISATEUR_MODIFIER)), db: Session = Depends(get_db),
):
    return crud.user_out(db, crud.update_user(db, actor, user_id, data, client_ip(request)))
