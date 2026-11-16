"""Mots de passe d'unité, déverrouillage et réinitialisation hiérarchique.
Le modèle est prêt pour le verrou applicatif Direction/Service/Division.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.db.metier import SecretUnite, Deverrouillage


class SecuriteService:
    def __init__(self, db: Session):
        self.db = db

    def set_secret(self, *, admin_user_id: int, service_id: int | None = None, division_id: int | None = None, secret_hash: str) -> SecretUnite:
        item = SecretUnite(
            service_id=service_id,
            division_id=division_id,
            admin_user_id=admin_user_id,
            secret_hash=secret_hash,
            modifie_le=datetime.utcnow(),
        )
        self.db.add(item)
        self.db.flush()
        return item

    def deverrouiller(self, *, secret_unite_id: int, user_id: int, duree_minutes: int = 15) -> Deverrouillage:
        item = Deverrouillage(
            secret_unite_id=secret_unite_id,
            user_id=user_id,
            valide_jusqua=datetime.utcnow() + timedelta(minutes=duree_minutes),
            actif=True,
        )
        self.db.add(item)
        self.db.flush()
        return item
