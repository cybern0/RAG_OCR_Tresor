"""Écriture de l'historique de traçabilité et de sécurité.
Le module est compatible avec le modèle hiérarchique Direction / Service / Division.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.db.metier import HistoriqueModification


def ecrire_historique(
    db: Session,
    *,
    acteur_user_id: int | None,
    cible_type: str,
    cible_id: int | None,
    action: str,
    avant: Any | None = None,
    apres: Any | None = None,
    motif: str | None = None,
    service_id: int | None = None,
    division_id: int | None = None,
    hash_precedent: str | None = None,
) -> HistoriqueModification:
    entry = HistoriqueModification(
        acteur_user_id=acteur_user_id,
        cible_type=cible_type,
        cible_id=cible_id,
        action=action,
        avant=str(avant) if avant is not None else None,
        apres=str(apres) if apres is not None else None,
        motif=motif,
        service_id=service_id,
        division_id=division_id,
        hash_precedent=hash_precedent,
        hash_courant=None,
        date_action=datetime.utcnow(),
    )
    db.add(entry)
    db.flush()
    return entry
