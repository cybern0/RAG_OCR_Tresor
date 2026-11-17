"""Dictionnaire de rôles d'une division et rôles d'un utilisateur."""

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_principal
from app.core.permissions import Principal
from app.schemas.roles_division import RoleDivisionIn, RoleDivisionOut, RoleDivisionUpdate
from app.schemas.user import RoleDivisionBrief, RolesUtilisateurIn
from app.services import roles_division as svc
from app.services.users import crud as users_crud

router = APIRouter(tags=["roles"])


@router.get("/divisions/{division_id}/roles", response_model=list[RoleDivisionOut])
def lister(division_id: int, actifs_seulement: bool = False, principal: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    return svc.lister_roles(db, principal, division_id, inclure_inactifs=not actifs_seulement)


@router.post("/divisions/{division_id}/roles", response_model=RoleDivisionOut, status_code=201)
def creer(division_id: int, data: RoleDivisionIn, principal: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    return svc.creer_role(db, principal, division_id, data)


@router.patch("/divisions/{division_id}/roles/{role_id}", response_model=RoleDivisionOut)
def modifier(division_id: int, role_id: int, data: RoleDivisionUpdate, principal: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    return svc.modifier_role(db, principal, division_id, role_id, data)


@router.delete("/divisions/{division_id}/roles/{role_id}", status_code=204)
def supprimer(division_id: int, role_id: int, principal: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    svc.supprimer_role(db, principal, division_id, role_id)
    return Response(status_code=204)


@router.get("/users/{user_id}/roles", response_model=list[RoleDivisionBrief])
def roles_utilisateur(user_id: int, principal: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    user = users_crud.get_user_visible(db, principal, user_id)
    return [RoleDivisionBrief(id=r.id, code=r.code, libelle=r.libelle) for r in svc.roles_de_user(db, user.id)]


@router.put("/users/{user_id}/roles", response_model=list[RoleDivisionBrief])
def definir_roles(user_id: int, data: RolesUtilisateurIn, principal: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    user = users_crud.get_user_visible(db, principal, user_id)
    roles = svc.definir_roles_utilisateur(db, principal, user, data.role_ids, data.motif)
    return [RoleDivisionBrief(id=r.id, code=r.code, libelle=r.libelle) for r in roles]
