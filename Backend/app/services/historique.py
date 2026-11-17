"""Historique de traçabilité : modifications et affectations (comptes, titres, rôles, fichiers, demandes, exceptions, secrets).

Le rang et le hash chaîné sont posés par la BASE (déclencheur) ; la table est en ajout seul. Ce module ne fait qu'écrire et lire.
Distinct de journal_audit (technique : connexions, échecs).
"""

import json
from typing import Any

from sqlalchemy import ColumnElement, or_, select, text
from sqlalchemy.orm import Session

from app.core.permissions import NIVEAU_DIVISION, NIVEAU_ROOT, NIVEAU_SERVICE, Principal
from app.db.metier import HistoriqueModification, User


def _texte(valeur: Any) -> str | None:
    if valeur is None or isinstance(valeur, str):
        return valeur
    return json.dumps(valeur, ensure_ascii=False, sort_keys=True, default=str)


def ecrire_historique(
    db: Session,
    *,
    acteur: User | None,
    cible_type: str,
    cible_id: int | None,
    action: str,
    avant: Any = None,
    apres: Any = None,
    motif: str | None = None,
    service_id: int | None = None,
    division_id: int | None = None,
    concerne_user_id: int | None = None,
) -> None:
    db.add(
        HistoriqueModification(
            acteur_user_id=acteur.id if acteur else None,
            acteur_nom=acteur.nom_utilisateur if acteur else None,
            concerne_user_id=concerne_user_id,
            cible_type=cible_type,
            cible_id=cible_id,
            action=action,
            avant=_texte(avant),
            apres=_texte(apres),
            motif=motif,
            service_id=service_id,
            division_id=division_id,
        )
    )
    db.flush()  # l'ordre des appels est l'ordre de la chaîne


def filtre_perimetre(principal: Principal) -> ColumnElement[bool] | None:
    """None = tout (super administrateur)."""
    if principal.niveau == NIVEAU_ROOT:
        return None
    if principal.niveau == NIVEAU_SERVICE:
        return HistoriqueModification.service_id == principal.service_id
    if principal.niveau == NIVEAU_DIVISION:
        return HistoriqueModification.division_id == principal.division_id
    moi = principal.user.id
    return or_(HistoriqueModification.acteur_user_id == moi, HistoriqueModification.concerne_user_id == moi)


def lister_historique(
    db: Session,
    principal: Principal,
    *,
    cible_type: str | None = None,
    action: str | None = None,
    division_id: int | None = None,
    service_id: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[int, list[HistoriqueModification]]:
    from sqlalchemy import func

    stmt = select(HistoriqueModification)
    perimetre = filtre_perimetre(principal)
    if perimetre is not None:
        stmt = stmt.where(perimetre)
    if cible_type:
        stmt = stmt.where(HistoriqueModification.cible_type == cible_type)
    if action:
        stmt = stmt.where(HistoriqueModification.action == action)
    if division_id is not None:
        stmt = stmt.where(HistoriqueModification.division_id == division_id)
    if service_id is not None:
        stmt = stmt.where(HistoriqueModification.service_id == service_id)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(HistoriqueModification.rang.desc()).limit(limit).offset(offset)).all()
    return total, list(rows)


def historique_cible(db: Session, cible_type: str, cible_id: int, limit: int = 100) -> list[HistoriqueModification]:
    return list(
        db.scalars(
            select(HistoriqueModification)
            .where(HistoriqueModification.cible_type == cible_type, HistoriqueModification.cible_id == cible_id)
            .order_by(HistoriqueModification.rang.desc())
            .limit(limit)
        )
    )


def verifier_chaine(db: Session) -> dict[str, Any]:
    ok, total, premier = db.execute(text("SELECT ok, total, premier_rang_invalide FROM verifier_historique()")).one()
    return {"ok": bool(ok), "total": int(total), "premier_rang_invalide": premier}


def to_out(h: HistoriqueModification):
    from app.schemas.historique import HistoriqueOut

    return HistoriqueOut(
        id=h.id, rang=h.rang, acteur_user_id=h.acteur_user_id, acteur_nom=h.acteur_nom, concerne_user_id=h.concerne_user_id,
        cible_type=h.cible_type, cible_id=h.cible_id, action=h.action, avant=h.avant, apres=h.apres, motif=h.motif,
        service_id=h.service_id, division_id=h.division_id, date_action=h.date_action, hash_courant=h.hash_courant,
    )
