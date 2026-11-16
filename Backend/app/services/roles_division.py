"""Gestion du dictionnaire de rôles par division.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.metier import RoleDivision, UserRoleDivision


class RolesDivisionService:
    def __init__(self, db: Session):
        self.db = db

    def list_roles(self, division_id: int):
        return self.db.query(RoleDivision).filter(RoleDivision.division_id == division_id).order_by(RoleDivision.libelle.asc()).all()

    def create_role(self, division_id: int, code: str, libelle: str) -> RoleDivision:
        role = RoleDivision(division_id=division_id, code=code, libelle=libelle)
        self.db.add(role)
        self.db.flush()
        return role

    def assign_to_user(self, user_id: int, role_division_id: int) -> UserRoleDivision:
        row = UserRoleDivision(user_id=user_id, role_division_id=role_division_id)
        self.db.add(row)
        self.db.flush()
        return row
