"""Journal d'audit (lecture seule), réservé à la permission audit.consulter (ADMIN)."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_db, require
from app.core.permissions import AUDIT_CONSULTER, Principal
from app.db.metier import JournalAudit
from app.schemas.structure import AuditOut

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=list[AuditOut])
def list_audit(
    limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0),
    _: Principal = Depends(require(AUDIT_CONSULTER)), db: Session = Depends(get_db),
):
    rows = db.scalars(
        select(JournalAudit).options(joinedload(JournalAudit.user))
        .order_by(JournalAudit.cree_le.desc(), JournalAudit.id.desc()).limit(limit).offset(offset)
    )
    return [
        AuditOut(
            id=r.id, cree_le=r.cree_le, nom_utilisateur=r.user.nom_utilisateur if r.user else None,
            action=r.action, entite=r.entite, entite_id=r.entite_id, detail=r.detail,
            adresse_ip=str(r.adresse_ip) if r.adresse_ip else None,
        )
        for r in rows
    ]
