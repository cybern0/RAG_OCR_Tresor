"""Préférences du chat et mémoire ENTRE sessions (option par utilisateur, désactivée par défaut).

Mémoire : à la fin de chaque réponse sourcée (si l'option est active), un résumé du résultat est retenu avec la liste
des dossiers dont il vient. Aux sessions suivantes, ces résumés enrichissent le prompt, mais SEULEMENT si l'utilisateur
a encore accès à TOUS les dossiers d'origine : un retrait d'accès rend l'entrée muette. Le résumé est tronqué (pas
d'appel au LLM : il serait lent sur CPU).

Préférence « dernière version seulement » : la recherche du chat ne garde que la version la plus récente de chaque fichier.
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.metier import MemoireChat, PreferenceUtilisateur

QUESTION_CHARS = 150
REPONSE_CHARS = 350
_LOOKBACK = 40  # entrées récentes examinées avant filtrage par accès


def get_preferences(db: Session, user_id: int) -> PreferenceUtilisateur:
    """Préférences de l'utilisateur ; valeurs par défaut (non enregistrées) s'il n'en a jamais réglé."""
    pref = db.get(PreferenceUtilisateur, user_id)
    if pref is None:
        pref = PreferenceUtilisateur(user_id=user_id, memoire_inter_sessions=False, derniere_version_seulement=False)
    return pref


def set_preferences(
    db: Session, user_id: int, memoire_inter_sessions: bool | None, derniere_version_seulement: bool | None
) -> PreferenceUtilisateur:
    pref = db.get(PreferenceUtilisateur, user_id)
    if pref is None:
        pref = PreferenceUtilisateur(user_id=user_id, memoire_inter_sessions=False, derniere_version_seulement=False)
        db.add(pref)
    if memoire_inter_sessions is not None:
        pref.memoire_inter_sessions = memoire_inter_sessions
    if derniere_version_seulement is not None:
        pref.derniere_version_seulement = derniere_version_seulement
    db.commit()
    return pref


def record(
    db: Session, user_id: int, conversation_id: int | None, question: str, answer: str, dossier_ids: list[int]
) -> None:
    """Retient le résultat d'un échange. Sans dossier source, il n'y a rien à retenir."""
    if not dossier_ids:
        return
    resume = f"Question : {' '.join(question.split())[:QUESTION_CHARS]} | Résultat : {' '.join(answer.split())[:REPONSE_CHARS]}"
    db.add(
        MemoireChat(
            user_id=user_id, conversation_id=conversation_id, resume=resume, dossier_ids=sorted(set(dossier_ids))
        )
    )
    db.commit()


def load(db: Session, user_id: int, accessibles: set[int], current_conversation_id: int | None = None) -> list[str]:
    """Résumés réutilisables : récents, d'autres conversations que la courante, et dont TOUS les dossiers sont
    encore accessibles."""
    stmt = select(MemoireChat).where(MemoireChat.user_id == user_id)
    if current_conversation_id is not None:
        stmt = stmt.where(
            (MemoireChat.conversation_id.is_(None)) | (MemoireChat.conversation_id != current_conversation_id)
        )
    rows = db.scalars(stmt.order_by(MemoireChat.id.desc()).limit(_LOOKBACK))
    out: list[str] = []
    for row in rows:
        if row.dossier_ids and set(row.dossier_ids) <= accessibles:
            out.append(f"- {_date(row.cree_le)} : {row.resume}")
            if len(out) >= get_settings().memory_max_entries:
                break
    return out[::-1]


def _date(value: datetime) -> str:
    return value.strftime("%d/%m/%Y")
