"""Orchestration de l'ingestion : parse, chunk, embeddings, écriture dans pgvector,
avec mise à jour du statut (pending, processing, ready, error)."""

import logging
from pathlib import Path

import httpx
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError

from app.db.metier import SessionLocal
from app.db.vecteur import Chunk, Document
from app.services.ingestion.chunking import chunk_documents
from app.services.ingestion.embedding import EmbeddingError, embed_documents
from app.services.ingestion.parser import IngestionError, parse_file

logger = logging.getLogger(__name__)


def _error_message(exc: Exception) -> str:
    if isinstance(exc, (IngestionError, EmbeddingError)):
        return str(exc)
    if isinstance(exc, (httpx.ConnectError, ConnectionError)):
        return "Ollama est injoignable : le démarrer, puis relancer l'indexation (modifier le document)."
    return f"{type(exc).__name__} : {str(exc)[:300]}"


def _mark_error(document_id: int, message: str) -> None:
    with SessionLocal() as db:
        doc = db.get(Document, document_id)
        if doc is not None:
            doc.statut = "error"
            doc.message_erreur = message
            db.commit()


def run_ingestion(document_id: int) -> None:
    """Indexe un document. Ne lève jamais : toute erreur est enregistrée dans le document."""
    try:
        with SessionLocal() as db:
            doc = db.get(Document, document_id)
            if doc is None:  # supprimé entre-temps
                return
            doc.statut = "processing"
            doc.message_erreur = None
            db.commit()

            # has_tabular contient ici l'indication donnée par l'utilisateur au dépôt
            parsed = parse_file(Path(doc.chemin_stockage), force_tabular=doc.has_tabular)
            chunks = chunk_documents(parsed.documents, doc.id, doc.nom_fichier)
            if not chunks:
                raise IngestionError("Aucun passage exploitable n'a été extrait de ce fichier.")
            vectors = embed_documents([c.page_content for c in chunks])

            db.execute(delete(Chunk).where(Chunk.document_id == doc.id))
            db.add_all(
                Chunk(
                    document_id=doc.id,
                    chunk_index=c.metadata["chunk_index"],
                    page=c.metadata.get("page"),
                    contenu=c.page_content,
                    est_tableau=bool(c.metadata.get("est_tableau")),
                    meta={k: v for k, v in c.metadata.items() if k not in ("chunk_index", "page", "est_tableau")},
                    embedding=vec,
                )
                for c, vec in zip(chunks, vectors, strict=True)
            )
            doc.nb_pages = parsed.nb_pages
            doc.ocr_utilise = parsed.ocr_utilise
            doc.has_tabular = parsed.has_tabular
            doc.statut = "ready"
            doc.message_erreur = None
            db.commit()
            logger.info("Document %s indexé : %s passages", document_id, len(chunks))
    except IntegrityError:
        logger.info("Document %s supprimé pendant son indexation", document_id)
    except Exception as exc:  # noqa: BLE001 - le worker ne doit jamais s'arrêter
        logger.exception("Échec de l'indexation du document %s", document_id)
        _mark_error(document_id, _error_message(exc))
