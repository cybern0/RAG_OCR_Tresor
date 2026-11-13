"""Aperçu et téléchargement du contenu d'une version de fichier.

Sécurité (le contenu est servi par l'API, jamais exécuté) :
- seuls des types sûrs sont servis « inline » : PDF, PNG/JPEG/WebP/BMP, texte brut (txt, md, csv servis en text/plain) ;
- le type MIME est DÉDUIT DE L'EXTENSION validée au dépôt, jamais du type envoyé par le client ;
- jamais de HTML ni de SVG rendus tels quels ; X-Content-Type-Options: nosniff ; CSP « sandbox » sur toute réponse ;
- Word, PowerPoint, Excel, ODF : convertis en PDF par LibreOffice (conversion mise en cache, une version ne changeant jamais) ;
- téléchargement : Content-Disposition: attachment avec le nom d'origine, en application/octet-stream.
"""

import shutil
import subprocess
import tempfile
import threading
from pathlib import Path
from urllib.parse import quote

from fastapi import HTTPException, status
from fastapi.responses import FileResponse

from app.config import get_settings
from app.db.vecteur import DocumentVersion

_IMAGES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".bmp": "image/bmp"}
_TEXTE = {".txt", ".md", ".csv"}
_CONVERTIS = {".docx", ".doc", ".pptx", ".ppt", ".odt", ".ods", ".odp", ".rtf", ".xls", ".xlsx"}

_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": "sandbox; default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline'",
    "Cache-Control": "private, no-store",
}
_convert_lock = threading.Lock()  # LibreOffice n'aime pas deux conversions simultanées sur le même profil
CONVERSION_TIMEOUT = 120


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
    path = Path(version.chemin_stockage)
    if not path.is_file():
        raise HTTPException(status.HTTP_410_GONE, "Le fichier de cette version est introuvable sur le serveur.")
    return path


def cache_path(version_id: int) -> Path:
    return get_settings().upload_dir / "_apercus" / f"{version_id}.pdf"


def remove_cache(version_id: int) -> None:
    try:
        cache_path(version_id).unlink(missing_ok=True)
    except OSError:
        pass


def _soffice() -> str:
    binary = shutil.which("soffice") or shutil.which("libreoffice")
    if binary is None:
        raise HTTPException(
            status.HTTP_501_NOT_IMPLEMENTED,
            "Aperçu impossible : LibreOffice n'est pas installé sur le serveur. Télécharger le fichier pour le lire.",
        )
    return binary


def convert_to_pdf(version: DocumentVersion) -> Path:
    """PDF de la version (cache ; conversion LibreOffice au premier appel)."""
    target = cache_path(version.id)
    if target.is_file():
        return target
    source = _stored(version)
    binary = _soffice()
    target.parent.mkdir(parents=True, exist_ok=True)
    with _convert_lock, tempfile.TemporaryDirectory(prefix="apercu_") as work:
        try:
            subprocess.run(
                [binary, f"-env:UserInstallation=file://{work}/profil", "--headless", "--norestore",
                 "--convert-to", "pdf", "--outdir", work, str(source)],
                check=True, capture_output=True, timeout=CONVERSION_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            raise HTTPException(status.HTTP_504_GATEWAY_TIMEOUT, "La conversion en PDF a pris trop de temps.") from None
        except subprocess.CalledProcessError:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Ce fichier n'a pas pu être converti en PDF.") from None
        produced = Path(work) / f"{source.stem}.pdf"
        if not produced.is_file():
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Ce fichier n'a pas pu être converti en PDF.")
        shutil.move(str(produced), target)
    return target


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
