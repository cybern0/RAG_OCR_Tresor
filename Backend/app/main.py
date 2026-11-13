"""Point d'entrée de l'API : création de l'app FastAPI, montage des routers (api/routes), CORS.
Lancement : uv run uvicorn app.main:app --reload --port 8000
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import audit, auth, chat, documents, dossiers, health, structure, users
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


app = FastAPI(title="RAG OCR Trésor", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

for module in (health, auth, users, structure, dossiers, documents, chat, audit):
    app.include_router(module.router)
