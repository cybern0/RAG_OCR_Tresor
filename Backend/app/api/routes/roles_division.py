"""Routes de gestion des rôles de division."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import client_ip, get_db, require
from app.core.permissions import Principal, STRUCTURE_GERER
from app.db.metier import RoleDivision, UserRoleDivision
from app.schemas.role_division import RoleDivisionIn, RoleDivisionOut, RoleDivisionUpdate, UserRoleAssignIn

router = APIRouter(prefix="/divisions", tags=["roles_division"])
_admin = require(STRUCTURE_GERER)


@router.get("/{division_id}/roles", response_model=list[RoleDivisionOut])
def list_roles(division_id: int, _: Principal = Depends(_admin), db: Session = Depends(get_db)):
    return db.query(RoleDivision).filter(RoleDivision.division_id == division_id).order_by(RoleDivision.libelle.asc()).all()


@router.post("/{division_id}/roles", response_model=RoleDivisionOut, status_code=201)
def create_role(
    division_id: int,
    data: RoleDivisionIn,
    request: Request,
    actor: Principal = Depends(_admin),
    db: Session = Depends(get_db),
):
    role = RoleDivision(division_id=division_id, code=data.code.strip(), libelle=data.libelle.strip())
    db.add(role)
    db.commit()
    db.refresh(role)
    return role


@router.patch("/{division_id}/roles/{role_id}", response_model=RoleDivisionOut)
def patch_role(
    division_id: int,
    role_id: int,
    data: RoleDivisionUpdate,
    request: Request,
    actor: Principal = Depends(_admin),
    db: Session = Depends(get_db),
):
    role = db.get(RoleDivision, role_id)
    if role is None or role.division_id != division_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Rôle introuvable.")
    if data.code is not None:
        role.code = data.code.strip()
    if data.libelle is not None:
        role.libelle = data.libelle.strip()
    if data.actif is not None:
        role.actif = data.actif
    db.commit()
    db.refresh(role)
    return role


@router.delete("/{division_id}/roles/{role_id}", status_code=204)
def delete_role(
    division_id: int,
    role_id: int,
    actor: Principal = Depends(_admin),
    db: Session = Depends(get_db),
):
    role = db.get(RoleDivision, role_id)
    if role is None or role.division_id != division_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Rôle introuvable.")
    db.delete(role)
    db.commit()


@router.put("/users/{user_id}/roles")
def assign_roles_to_user(
    user_id: int,
    data: UserRoleAssignIn,
    actor: Principal = Depends(_admin),
    db: Session = Depends(get_db),
):
    db.query(UserRoleDivision).filter(UserRoleDivision.user_id == user_id).delete()
    for role_id in data.role_ids:
        db.add(UserRoleDivision(user_id=user_id, role_division_id=role_id))
    db.commit()
    return {"user_id": user_id, "role_ids": data.role_ids}
