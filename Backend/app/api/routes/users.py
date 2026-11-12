"""Routes de gestion des utilisateurs (côté UI : features/users).
Réservées à l'ADMIN : seul lui possède les permissions utilisateur.* — un UTILISATEUR ne peut créer aucun compte."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import client_ip, get_db, require
from app.core.permissions import UTILISATEUR_CREER, UTILISATEUR_LISTER, UTILISATEUR_MODIFIER, Principal
from app.schemas.user import UserCreate, UserOut, UserUpdate
from app.services.users import crud

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserOut])
def list_users(_: Principal = Depends(require(UTILISATEUR_LISTER)), db: Session = Depends(get_db)):
    return [crud.to_user_out(u) for u in crud.list_users(db)]


@router.post("", response_model=UserOut, status_code=201)
def create_user(
    data: UserCreate, request: Request,
    actor: Principal = Depends(require(UTILISATEUR_CREER)), db: Session = Depends(get_db),
):
    return crud.to_user_out(crud.create_user(db, actor, data, client_ip(request)))


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int, data: UserUpdate, request: Request,
    actor: Principal = Depends(require(UTILISATEUR_MODIFIER)), db: Session = Depends(get_db),
):
    return crud.to_user_out(crud.update_user(db, actor, user_id, data, client_ip(request)))
