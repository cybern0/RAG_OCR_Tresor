"""Orchestration de l'ingestion d'UNE VERSION de fichier : parse, chunk, embeddings, écriture dans pgvector,
avec mise à jour du statut de la version (pending, processing, ready, error).

Les chunks d'une version ne touchent jamais ceux des autres versions : déposer une nouvelle version ajoute des chunks,
n'en supprime aucun.
"""

import logging

import httpx
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError

from app.db.metier import SessionLocal
from app.db.vecteur import Chunk, DocumentVersion
from app.services import stockage
from app.services.classement import appliquer
from app.services.ingestion.chunking import chunk_documents
from app.services.ingestion.embedding import EmbeddingError, embed_documents
from app.services.ingestion.parser import IngestionError, parse_file

logger = logging.getLogger(__name__)


def _error_message(exc: Exception) -> str:
    if isinstance(exc, (IngestionError, EmbeddingError)):
        return str(exc)
    if isinstance(exc, (httpx.ConnectError, ConnectionError)):
        return "Ollama est injoignable : le démarrer, puis redéposer le fichier comme nouvelle version."
    return f"{type(exc).__name__} : {str(exc)[:300]}"


def _mark_error(version_id: int, message: str) -> None:
    with SessionLocal() as db:
        version = db.get(DocumentVersion, version_id)
        if version is not None:
            version.statut = "error"
            version.message_erreur = message
            db.commit()


def run_ingestion(version_id: int) -> None:
    """Indexe une version. Ne lève jamais : toute erreur est enregistrée dans la version."""
    try:
        with SessionLocal() as db:
            version = db.get(DocumentVersion, version_id)
            if version is None:  # supprimée entre-temps
                return
            doc = version.document
            version.statut = "processing"
            version.message_erreur = None
            db.commit()

            chemin = stockage.trouver(version.chemin_stockage)
            if chemin is None:
                raise IngestionError(
                    f"Le fichier « {version.nom_fichier} » est introuvable sur le serveur (supprimé ou déplacé). "
                    "Le redéposer comme nouvelle version."
                )
            # has_tabular / has_image sont les cases du fichier : cochées par l'utilisateur ou imposées par le type
            parsed = parse_file(chemin, force_tabular=doc.has_tabular, force_images=doc.has_image)
            chunks = chunk_documents(parsed.documents, doc.id, version.nom_fichier)
            if not chunks:
                raise IngestionError("Aucun passage exploitable n'a été extrait de ce fichier.")
            vectors = embed_documents([c.page_content for c in chunks])

            db.execute(delete(Chunk).where(Chunk.document_version_id == version.id))
            db.add_all(
                Chunk(
                    document_id=doc.id,
                    document_version_id=version.id,
                    chunk_index=c.metadata["chunk_index"],
                    page=c.metadata.get("page"),
                    contenu=c.page_content,
                    est_tableau=bool(c.metadata.get("est_tableau")),
                    taille_ref=len(chunks),  # nombre de chunks de la version : base du top-k dynamique
                    meta={k: v for k, v in c.metadata.items() if k not in ("chunk_index", "page", "est_tableau")},
                    embedding=vec,
                )
                for c, vec in zip(chunks, vectors, strict=True)
            )
            texte = "\n".join(c.page_content for c in chunks)[:20_000]
            appliquer(db, doc, version, texte)
            version.nb_pages = parsed.nb_pages
            version.ocr_utilise = parsed.ocr_utilise
            if parsed.has_tabular and not doc.has_tabular:
                doc.has_tabular = True  # tableaux détectés : la case est cochée
            version.statut = "ready"
            version.message_erreur = None
            db.commit()
            logger.info("Version %s (document %s) indexée : %s passages", version_id, doc.id, len(chunks))
    except IntegrityError:
        logger.info("Version %s supprimée pendant son indexation", version_id)
    except (IngestionError, EmbeddingError) as exc:  # cause attendue et déjà expliquée : pas de trace complète
        logger.warning("Indexation impossible pour la version %s : %s", version_id, exc)
        _mark_error(version_id, str(exc))
    except Exception as exc:  # noqa: BLE001 - le worker ne doit jamais s'arrêter
        logger.exception("Échec de l'indexation de la version %s", version_id)
        _mark_error(version_id, _error_message(exc))
