"""Configuration des tests.

- Tests unitaires (sécurité, parsing, chaîne RAG) : aucun service externe.
- Tests d'API (test_api.py) : demandent une base PostgreSQL + pgvector avec les scripts database/01 à 04 appliqués.
  Ils sont ignorés sans TEST_DATABASE_URL, par exemple :
    TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/rag_test uv run pytest
  Ollama est remplacé par de faux modèles : ni Ollama ni OCR ne sont nécessaires.
"""

import hashlib
import math
import os
import re
import tempfile

os.environ.setdefault("SECRET_KEY", "cle-de-test-" + "x" * 40)
if os.environ.get("TEST_DATABASE_URL"):
    os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
    os.environ["UPLOAD_DIR"] = tempfile.mkdtemp(prefix="rag_test_uploads_")


class FakeEmbeddings:
    """Embeddings déterministes par « sac de mots » hachés : deux textes proches donnent des vecteurs proches.
    Les vecteurs sont volontairement NON normalisés (norme 3,7) : c'est au backend de les normaliser."""

    dim = 768
    scale = 3.7

    def _vec(self, text: str) -> list[float]:
        v = [0.0] * self.dim
        for word in re.findall(r"\w+", text.lower()):
            v[int(hashlib.md5(word.encode()).hexdigest(), 16) % self.dim] += 1.0
        norm = math.sqrt(sum(x * x for x in v)) or 1.0
        return [self.scale * x / norm for x in v]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vec(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vec(text)
