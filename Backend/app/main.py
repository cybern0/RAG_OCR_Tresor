"""Point d'entrée de l'API : création de l'app FastAPI, montage des routers (api/routes), CORS, interface web.

Toutes les routes métier vivent sous le préfixe API_PREFIX (« /api » par défaut) : les autres chemins appartiennent au
routage de l'application monopage (SPA). Si le build du frontend existe (frontend/dist), il est servi par l'API elle-même,
avec repli sur index.html pour les liens profonds (/dossiers/12, /admin/utilisateurs...).
Lancement : uv run uvicorn app.main:app --reload --port 8000
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import (
    audit,
    auth,
    chat,
    classement,
    commentaires,
    demandes,
    documents,
    dossiers,
    health,
    historique,
    notifications,
    roles_division,
    securite,
    structure,
    tableau_de_bord,
    users,
)
from app.config import get_settings
from app.workers import ingestion_worker

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s : %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    settings.check_secret()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    ingestion_worker.start()
    yield
    ingestion_worker.stop()


def _mount_spa(app: FastAPI, dist: Path, api_prefix: str) -> None:
    """Sert le build du frontend. Un chemin d'API inconnu reste un 404 JSON ; tout autre chemin rend index.html."""
    index = dist / "index.html"
    assets = dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{chemin:path}", include_in_schema=False)
    def spa(chemin: str) -> FileResponse:
        if chemin == api_prefix.strip("/") or chemin.startswith(api_prefix.strip("/") + "/"):
            raise HTTPException(404, "Route d'API introuvable.")
        candidate = (dist / chemin).resolve()
        if chemin and candidate.is_file() and dist.resolve() in candidate.parents:  # favicon.svg, icons.svg...
            return FileResponse(candidate)
        return FileResponse(index)


def create_app() -> FastAPI:
    settings = get_settings()
    api = FastAPI(title="RAG OCR Trésor", version="3.0.0", lifespan=lifespan)

    api.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    prefix = "/" + settings.api_prefix.strip("/") if settings.api_prefix.strip("/") else ""
    for module in (
        health,
        auth,
        users,
            structure,
        roles_division,
        dossiers,
        documents,
        classement,
        commentaires,
        chat,
        audit,
        securite,
        historique,
        notifications,
        demandes,
        tableau_de_bord,
    ):
        api.include_router(module.router, prefix=prefix)
    if prefix:
        api.include_router(health.router)  # /health reste disponible pour la supervision

    if (settings.frontend_dist / "index.html").is_file():
        _mount_spa(api, settings.frontend_dist, prefix or "/api")
    return api


app = create_app()
