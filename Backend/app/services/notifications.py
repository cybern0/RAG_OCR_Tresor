"""Notifications en base (cloche de l'interface) et choix des destinataires."""

from collections.abc import Iterable

from sqlalchemy import and_, delete, or_, select, update
from sqlalchemy.orm import Session

from app.core.acces import chef_division_actif, chef_service_actif
from app.db.metier import DemandeAcces, Division, Notification, Role, User


def notifier(
    db: Session,
    user_ids: Iterable[int],
    type_evenement: str,
    message: str,
    *,
    reference_type: str | None = None,
    reference_id: int | None = None,
    sauf_user_id: int | None = None,
) -> None:
    for uid in dict.fromkeys(user_ids):  # sans doublon, ordre conservé
        if uid == sauf_user_id:
            continue
        db.add(
            Notification(
                destinataire_user_id=uid,
                type_evenement=type_evenement,
                message=message,
                reference_type=reference_type,
                reference_id=reference_id,
            )
        )
    db.flush()


def users_de_agent(db: Session, agent_id: int | None) -> list[int]:
    if agent_id is None:
        return []
    return list(db.scalars(select(User.id).where(User.agent_id == agent_id, User.actif.is_(True))))


def super_admins_actifs(db: Session) -> list[int]:
    return list(
        db.scalars(select(User.id).join(Role, Role.id == User.role_id).where(Role.code == "ADMIN", User.actif.is_(True)))
    )


def destinataires_gestion(db: Session, division: Division) -> list[int]:
    """Qui doit traiter une demande ou classer un fichier : le chef de division ; à défaut le chef de service ;
    sinon les super administrateurs (intérim)."""
    chef = chef_division_actif(db, division.id)
    if chef is not None and (ids := users_de_agent(db, chef.id)):
        return ids
    chef_service = chef_service_actif(db, division.service_id)
    if chef_service is not None and (ids := users_de_agent(db, chef_service.id)):
        return ids
    return super_admins_actifs(db)


def lister(db: Session, user_id: int, *, non_lues_seulement: bool = False, limit: int = 50) -> tuple[int, list[Notification]]:
    from sqlalchemy import func

    base = select(Notification).where(Notification.destinataire_user_id == user_id)
    non_lues = db.scalar(select(func.count()).select_from(base.where(Notification.lu.is_(False)).subquery())) or 0
    if non_lues_seulement:
        base = base.where(Notification.lu.is_(False))
    rows = db.scalars(base.order_by(Notification.cree_le.desc(), Notification.id.desc()).limit(limit)).all()
    return non_lues, list(rows)


def marquer_lue(db: Session, user_id: int, notification_id: int) -> bool:
    res = db.execute(
        update(Notification)
        .where(Notification.id == notification_id, Notification.destinataire_user_id == user_id)
        .values(lu=True)
    )
    return res.rowcount > 0


def marquer_toutes_lues(db: Session, user_id: int) -> int:
    res = db.execute(
        update(Notification).where(Notification.destinataire_user_id == user_id, Notification.lu.is_(False)).values(lu=True)
    )
    return res.rowcount


def purger_demande(db: Session, demande_id: int) -> None:
    """Une demande tranchée ou annulée n'est plus à traiter : ses notifications « demande_acces » disparaissent
    des boîtes des décideurs (la décision reste notifiée au demandeur et tracée dans l'historique)."""
    db.execute(
        delete(Notification).where(
            Notification.type_evenement == "demande_acces",
            Notification.reference_type == "demande",
            Notification.reference_id == demande_id,
        )
    )


def nettoyer(db: Session, user_id: int) -> int:
    """Supprime les notifications résolues du compte : les lues, et les « demande_acces » dont la demande
    a déjà été tranchée ou annulée (restées en attente d'un traitement qui n'existe plus)."""
    resolues = select(DemandeAcces.id).where(DemandeAcces.statut != "en_attente")
    res = db.execute(
        delete(Notification).where(
            Notification.destinataire_user_id == user_id,
            or_(
                Notification.lu.is_(True),
                and_(
                    Notification.type_evenement == "demande_acces",
                    Notification.reference_type == "demande",
                    Notification.reference_id.in_(resolues),
                ),
            ),
        )
    )
    return res.rowcount
