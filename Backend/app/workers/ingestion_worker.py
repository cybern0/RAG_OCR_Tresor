"""Worker d'ingestion en arrière-plan : l'OCR et les embeddings sont lents sur CPU,
ils ne doivent pas bloquer les requêtes de l'API.

Un seul thread : les documents sont indexés l'un après l'autre (le CPU est le goulot, pas la file).
Au démarrage, les documents restés « pending » ou « processing » (arrêt brutal) sont remis en file.
"""

import logging
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import select, update

from app.db.metier import SessionLocal
from app.db.vecteur import Document
from app.services.ingestion.pipeline import run_ingestion

logger = logging.getLogger(__name__)

_executor: ThreadPoolExecutor | None = None


def start() -> None:
    global _executor
    _executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ingestion")
    with SessionLocal() as db:
        db.execute(update(Document).where(Document.statut == "processing").values(statut="pending"))
        db.commit()
        ids = list(db.scalars(select(Document.id).where(Document.statut == "pending").order_by(Document.id)))
    for document_id in ids:
        enqueue(document_id)
    if ids:
        logger.info("%s document(s) remis en file d'indexation", len(ids))


def enqueue(document_id: int) -> None:
    if _executor is None:
        raise RuntimeError("Worker d'ingestion non démarré.")
    _executor.submit(run_ingestion, document_id)


def stop() -> None:
    if _executor is not None:
        _executor.shutdown(wait=False, cancel_futures=True)
