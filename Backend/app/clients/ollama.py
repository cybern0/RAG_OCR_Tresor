"""Clients Ollama (LLM + embeddings), créés une fois et réutilisés.
L'URL vient de config.py (par défaut http://localhost:11434).

Modèles utilisés (ollama list) :
  qwen3:4b-instruct-2507-q4_K_M   2.5 GB   génération
  embeddinggemma:300m-qat-q4_0    238 MB   embeddings (768 dimensions)
"""

from functools import lru_cache

import httpx
from langchain_ollama import ChatOllama, OllamaEmbeddings

from app.config import get_settings


@lru_cache
def get_llm() -> ChatOllama:
    s = get_settings()
    return ChatOllama(model=s.llm_model, base_url=s.ollama_url, temperature=0.1, num_ctx=s.llm_num_ctx)


@lru_cache
def get_embeddings() -> OllamaEmbeddings:
    s = get_settings()
    return OllamaEmbeddings(model=s.embedding_model, base_url=s.ollama_url)


def ping_ollama() -> bool:
    try:
        return httpx.get(get_settings().ollama_url.rstrip("/") + "/api/tags", timeout=3).is_success
    except httpx.HTTPError:
        return False
