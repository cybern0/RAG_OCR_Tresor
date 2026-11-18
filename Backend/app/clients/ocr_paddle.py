"""Client HTTP du serveur OCR PaddleOCR (dossier ocr_server/) :
envoie une image, récupère le texte, les boîtes et la confiance (POST /ocr).

Les PDF scannés n'utilisent pas ce client : LiteParse appelle lui-même le serveur (ocr_server_url).
Ce client sert aux fichiers image déposés tels quels, et à la vérification de santé.
"""

from dataclasses import dataclass
from pathlib import Path

import httpx

from app.config import get_settings


class OcrError(RuntimeError):
    pass


@dataclass(frozen=True)
class OcrBox:
    text: str
    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float

    @property
    def cy(self) -> float:
        return (self.y1 + self.y2) / 2

    @property
    def height(self) -> float:
        return max(self.y2 - self.y1, 1.0)


def ocr_image(path: Path, language: str | None = None) -> list[OcrBox]:
    s = get_settings()
    try:
        with path.open("rb") as f:
            # l'OCR est lent sur CPU : délai large
            response = httpx.post(
                s.ocr_endpoint,
                files={"file": (path.name, f, "application/octet-stream")},
                data={"language": language or s.ocr_language},
                timeout=httpx.Timeout(600, connect=5),
            )
        response.raise_for_status()
        raw = response.json().get("results", [])
    except (httpx.HTTPError, ValueError) as e:
        raise OcrError(f"Serveur OCR indisponible ou en erreur ({s.ocr_endpoint}) : {e}") from e

    boxes = []
    for item in raw:
        text = str(item.get("text", "")).strip()
        bbox = item.get("bbox") or [0, 0, 0, 0]
        if text and len(bbox) == 4:
            boxes.append(OcrBox(text, *map(float, bbox), float(item.get("confidence", 0.0))))
    return boxes


def ping_ocr() -> bool:
    """Le serveur OCR est-il joignable ? Toute réponse HTTP suffit : une installation locale
    personnalisée (autre server.py) n'expose pas forcément /health — un 404 sur /health prouve
    quand même que l'hôte répond, et l'indexation via POST /ocr fonctionne. False uniquement
    si le host est injoignable (refus de connexion, délai dépassé, DNS)."""
    try:
        httpx.get(get_settings().ocr_url.rstrip("/") + "/health", timeout=3)
        return True
    except httpx.HTTPError:
        return False
