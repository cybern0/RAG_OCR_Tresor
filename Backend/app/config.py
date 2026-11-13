"""Configuration centralisée (pydantic-settings), lue depuis le fichier .env.

Le .env est cherché à la racine du dépôt puis dans Backend/ ; les variables d'environnement l'emportent.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent  # dossier Backend/


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(BASE_DIR.parent / ".env", BASE_DIR / ".env"),
        extra="ignore",
    )

    # Base de données (Postgres + pgvector)
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/rag"

    # Ollama : génération et embeddings
    ollama_url: str = "http://localhost:11434"
    llm_model: str = "qwen3:4b-instruct-2507-q4_K_M"
    llm_num_ctx: int = 8192
    embedding_model: str = "embeddinggemma:300m-qat-q4_0"
    embedding_dim: int = 768  # doit correspondre à vector(768) dans database/02

    # OCR
    ocr_url: str = "http://localhost:8829"
    ocr_language: str = "fr"

    # Fichiers déposés
    upload_dir: Path = BASE_DIR / "storage" / "uploads"
    max_upload_mb: int = 50

    # Sécurité
    secret_key: str = ""
    token_ttl_minutes: int = 480
    cors_origins: str = "http://localhost:5173"

    # RAG
    chunk_size: int = 1000
    chunk_overlap: int = 150
    # nombre de passages renvoyés : calculé entre ces bornes d'après la taille des fichiers concernés (top-k dynamique)
    retrieval_k_min: int = 3
    retrieval_k_max: int = 8
    # contexte envoyé au LLM (≈ 8192 tokens de fenêtre) : caractères maximum pour les passages, l'historique et la mémoire
    context_max_chars: int = 9000
    history_max_messages: int = 6
    history_message_chars: int = 1200
    memory_max_entries: int = 5

    @property
    def sqlalchemy_url(self) -> str:
        """Force le pilote psycopg 3 (« postgresql:// » seul choisirait psycopg2)."""
        url = self.database_url
        for prefix in ("postgresql://", "postgres://"):
            if url.startswith(prefix):
                return "postgresql+psycopg://" + url[len(prefix):]
        return url

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def ocr_endpoint(self) -> str:
        return self.ocr_url.rstrip("/") + "/ocr"

    def check_secret(self) -> None:
        if len(self.secret_key) < 32:
            raise RuntimeError(
                "SECRET_KEY absente ou trop courte (32 caractères minimum). Générer une valeur avec : "
                "python -c \"import secrets; print(secrets.token_urlsafe(48))\" puis la mettre dans .env"
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()
