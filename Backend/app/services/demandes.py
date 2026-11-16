"""Demandes d'accès, rôles et exceptions ponctuelles.
Cette couche est volontairement compatible avec le modèle actuel et prépare le modèle hiérarchique.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.db.metier import AccesException, DemandeAcces


class DemandesService:
    def __init__(self, db: Session):
        self.db = db

    def create_demande(self, *, demandeur_user_id: int, type_demande: str, cible_type: str, cible_id: int, motif: str) -> DemandeAcces:
        item = DemandeAcces(
            demandeur_user_id=demandeur_user_id,
            type_demande=type_demande,
            cible_type=cible_type,
            cible_id=cible_id,
            motif=motif,
            statut="en_attente",
        )
        self.db.add(item)
        self.db.flush()
        return item

    def create_exception(self, *, user_id: int, document_id: int, motif: str, duree_minutes: int = 60) -> AccesException:
        exception = AccesException(
            user_id=user_id,
            document_id=document_id,
            motif=motif,
            expire_le=datetime.utcnow() + timedelta(minutes=duree_minutes),
            active=True,
        )
        self.db.add(exception)
        self.db.flush()
        return exception
