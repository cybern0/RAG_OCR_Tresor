"""GET /health : état de l'API, de Postgres, d'Ollama et du serveur OCR."""

from fastapi import APIRouter
from sqlalchemy import text

from app.clients.ocr_paddle import ping_ocr
from app.clients.ollama import ping_ollama
from app.db.metier import engine

router = APIRouter(tags=["health"])


def _ping_postgres() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001
        return False


@router.get("/health")
def health() -> dict:
    services = {"postgres": _ping_postgres(), "ollama": ping_ollama(), "ocr": ping_ocr()}
    return {"status": "ok" if all(services.values()) else "degraded", "api": True, **services}
