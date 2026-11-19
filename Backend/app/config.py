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
    # Conversion Office/OpenDocument -> PDF : délai calculé d'après la taille du fichier déposé
    # (base + secondes par Mo, plafonné) ; le moteur est interrompu au-delà.
    conversion_timeout_base_s: int = 60
    conversion_timeout_par_mo_s: int = 15
    conversion_timeout_max_s: int = 1800
    # Windows + Word : imprimante imposée à Word pendant la conversion (ex. « Microsoft Print to PDF »). Vide : celle de
    # Windows. Utile quand l'export Word se bloque à cause d'une imprimante réseau hors ligne.
    conversion_word_imprimante: str = ""
    # Windows + documents Word (WORD_EXT) : moteur utilisé quand Office ET LibreOffice sont installés.
    # « auto » (défaut) : Word d'abord avec un délai court (conversion_word_delai_office_s), puis LibreOffice si Word
    # n'a pas terminé — l'export PDF de Word piloté par COM peut se bloquer sur un serveur, pour tout document ;
    # « libreoffice » : LibreOffice directement ; « office » : Word seul, délai complet (comportement d'avant).
    conversion_moteur_word: str = "auto"
    # Délai court (secondes) accordé à Word en « auto » avant de basculer sur LibreOffice : un blocage de l'export
    # sous COM se voit dès les premières secondes, inutile d'attendre le délai complet calculé d'après la taille.
    conversion_word_delai_office_s: int = 35
    # Diagnostic uniquement (scripts/diagnostic_conversion.py) : Office visible sur le serveur ; méthode d'export Word
    # « export » (défaut) ou « saveas ».
    conversion_office_visible: bool = False
    conversion_word_methode: str = "export"

    # Sécurité
    secret_key: str = ""
    token_ttl_minutes: int = 480
    cors_origins: str = "http://localhost:5173"

    # Authentification : l'application gère elle-même ses comptes — mots de passe hachés (scrypt) dans _user,
    # créés par le super administrateur ou au CLI (`creer-admin`), jamais de comptes du système d'exploitation
    # (voir docs/refonte_classes.md pour la décision et le périmètre).

    # Interface web (SPA) : l'API vit sous ce préfixe, ce qui libère tous les autres chemins pour le routage côté navigateur.
    api_prefix: str = "/api"
    # Dossier du build du frontend (npm run build) : s'il existe, l'API le sert elle-même avec repli sur index.html.
    frontend_dist: Path = BASE_DIR.parent / "frontend" / "dist"

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
