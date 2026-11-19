"""Aperçu et téléchargement du contenu d'une version de fichier.

Sécurité (le contenu est servi par l'API, jamais exécuté) :
- seuls des types sûrs sont servis « inline » : PDF, PNG/JPEG/WebP/BMP, texte brut (txt, md, csv servis en text/plain) ;
- le type MIME est DÉDUIT DE L'EXTENSION validée au dépôt, jamais du type envoyé par le client ;
- jamais de HTML ni de SVG rendus tels quels ; X-Content-Type-Options: nosniff ; CSP « sandbox » sur toute réponse ;
- Word, PowerPoint, Excel, ODF : convertis en PDF avant affichage (Microsoft Office sous Windows,
  LibreOffice sinon ; voir services/conversion_office.py ; conversion mise en cache, une version ne changeant jamais) ;
- téléchargement : Content-Disposition: attachment avec le nom d'origine, en application/octet-stream.
"""

import logging
import shutil
import tempfile
import threading
from pathlib import Path
from urllib.parse import quote

from fastapi import HTTPException, status
from fastapi.responses import FileResponse

from app.config import get_settings
from app.db.vecteur import DocumentVersion
from app.services import stockage
from app.services.conversion_office import (
    ConversionImpossibleError, ConversionTropLongueError, OfficeIndisponibleError, convertir_vers_pdf,
)

logger = logging.getLogger(__name__)

_IMAGES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".bmp": "image/bmp"}
_TEXTE = {".txt", ".md", ".csv"}
_CONVERTIS = {".docx", ".doc", ".pptx", ".ppt", ".odt", ".ods", ".odp", ".rtf", ".xls", ".xlsx"}

_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": "sandbox; default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline'",
    "Cache-Control": "private, no-store",
}
_convert_lock = threading.Lock()  # LibreOffice n'aime pas deux conversions simultanées sur le même profil


def apercu_mode(nom_fichier: str) -> str:
    ext = Path(nom_fichier).suffix.lower()
    if ext == ".pdf":
        return "pdf"
    if ext in _IMAGES:
        return "image"
    if ext == ".csv":
        return "csv"
    if ext in _TEXTE:
        return "texte"
    if ext in _CONVERTIS:
        return "pdf_converti"
    return "aucun"  # .tif/.tiff : les navigateurs ne les affichent pas


def _content_disposition(kind: str, name: str) -> str:
    ascii_name = name.encode("ascii", "ignore").decode() or "fichier"
    ascii_name = ascii_name.replace('"', "").replace("\\", "")
    return f"{kind}; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(name)}"


def _stored(version: DocumentVersion) -> Path:
    trouve = stockage.trouver(version.chemin_stockage)
    if trouve is None:
        raise HTTPException(status.HTTP_410_GONE, "Le fichier de cette version est introuvable sur le serveur.")
    return trouve


def cache_path(version_id: int) -> Path:
    return get_settings().upload_dir / "_apercus" / f"{version_id}.pdf"


def remove_cache(version_id: int) -> None:
    try:
        cache_path(version_id).unlink(missing_ok=True)
    except OSError:
        pass


def convert_to_pdf(version: DocumentVersion) -> Path:
    """PDF de la version (cache ; conversion au premier appel : Microsoft Office sous Windows, LibreOffice sinon).
    Le plus souvent le PDF existe déjà : il est préparé à l'indexation (preparer_apercu). Le délai de conversion
    dépend de la taille du fichier (conversion_office.timeout_pour)."""
    target = cache_path(version.id)
    if target.is_file():
        return target
    source = _stored(version)
    target.parent.mkdir(parents=True, exist_ok=True)
    with _convert_lock:
        if target.is_file():  # un autre fil (l'indexation) l'a produit pendant l'attente du verrou
            return target
        logger.info("Aperçu PDF de la version %s absent du cache : conversion à l'ouverture", version.id)
        with tempfile.TemporaryDirectory(prefix="apercu_") as work:
            try:
                convertir_vers_pdf(source, Path(work))  # délai calculé d'après la taille du fichier
            except OfficeIndisponibleError as e:
                raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, str(e)) from None
            except ConversionTropLongueError:
                raise HTTPException(status.HTTP_504_GATEWAY_TIMEOUT, "La conversion en PDF a pris trop de temps.") from None
            except ConversionImpossibleError:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Ce fichier n'a pas pu être converti en PDF.") from None
            produced = Path(work) / f"{source.stem}.pdf"
            shutil.move(str(produced), target)
    return target


def preparer_apercu(version: DocumentVersion, source: Path) -> tuple[Path | None, str | None]:
    """Convertit en PDF, dès l'indexation (donc dès le dépôt), un fichier Office/OpenDocument et met le PDF en cache :
    l'aperçu s'ouvre ensuite instantanément. Ne lève jamais : renvoie (chemin du PDF, None) ou (None, message d'erreur).
    Le même PDF sert à l'indexation, ce qui évite une seconde conversion."""
    if Path(version.nom_fichier).suffix.lower() not in _CONVERTIS:
        return None, None
    target = cache_path(version.id)
    try:
        with _convert_lock:
            if target.is_file():
                return target, None
            logger.info("Aperçu PDF de la version %s : conversion au dépôt (indexation)", version.id)
            target.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix="apercu_") as work:
                convertir_vers_pdf(source, Path(work))  # délai calculé d'après la taille du fichier
                shutil.move(str(Path(work) / f"{source.stem}.pdf"), target)
        return target, None
    except (OfficeIndisponibleError, ConversionImpossibleError, ConversionTropLongueError) as e:
        return None, str(e)
    except OSError as e:
        return None, f"Aperçu PDF non enregistré : {e}"


def preview_response(version: DocumentVersion) -> FileResponse:
    mode = apercu_mode(version.nom_fichier)
    ext = Path(version.nom_fichier).suffix.lower()
    if mode == "aucun":
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Pas d'aperçu pour ce type : télécharger le fichier.")
    if mode == "pdf":
        path, media = _stored(version), "application/pdf"
    elif mode == "image":
        path, media = _stored(version), _IMAGES[ext]
    elif mode in ("texte", "csv"):
        path, media = _stored(version), "text/plain; charset=utf-8"
    else:
        path, media = convert_to_pdf(version), "application/pdf"
    return FileResponse(
        path, media_type=media, headers={**_SECURITY_HEADERS, "Content-Disposition": _content_disposition("inline", "apercu" + Path(path).suffix)},
    )


def download_response(version: DocumentVersion) -> FileResponse:
    return FileResponse(
        _stored(version), media_type="application/octet-stream",
        headers={**_SECURITY_HEADERS, "Content-Disposition": _content_disposition("attachment", version.nom_fichier)},
    )
