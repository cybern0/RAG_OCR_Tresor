# RAG_OCR_Tresor

Assistant RAG 100 % local en français, sur CPU : dépôt de documents (OCR inclus) et questions via un chatbot.
Les utilisateurs ajoutent, modifient et suppriment des documents, sans en lire le contenu : seul le chat l'interroge.

## Arborescence

```
RAG_OCR_Tresor/
├── Backend/        API FastAPI (Python, uv)
├── frontend/       Interface React + TypeScript (Vite)
├── database/       Scripts SQL, à exécuter dans l'ordre 01 à 04
├── ocr_server/     Serveur PaddleOCR, séparé du backend
├── docs/           Architecture et historique des renommages
└── .env.example
```

## Services externes

- Ollama (natif, port 11434) : LLM et embeddings
- PostgreSQL + pgvector : base métier et base vectorielle
- ocr_server (port 8829) : OCR des images et des scans

## Initialiser la base

PostgreSQL avec l'extension pgvector doit être installé. Créer la base puis exécuter les scripts dans l'ordre :

```
psql -U postgres -c "CREATE DATABASE rag;"
psql -U postgres -d rag -f database/01_schema_metier.sql
psql -U postgres -d rag -f database/02_schema_documents_vecteurs.sql
psql -U postgres -d rag -f database/03_index.sql
psql -U postgres -d rag -f database/04_seed_roles_permissions.sql
```

Les scripts sont répétables. Pour contrôler que les embeddings sont bien normalisés : `psql -U postgres -d rag -f database/verif_vecteurs_normalises.sql` (attendu : 0 non normalisé). Le compte `admin` est créé verrouillé : voir l'en-tête de `04_seed_roles_permissions.sql`.

## Démarrer

1. Base : voir ci-dessus, puis `cp .env.example .env` et renseigner `SECRET_KEY`.
2. Ollama : `ollama pull qwen3:4b-instruct-2507-q4_K_M` et `ollama pull embeddinggemma:300m-qat-q4_0`.
3. OCR (optionnel tant qu'on ne dépose pas de scans ni d'images) : `cd ocr_server && uv run server.py`.
4. Backend : `cd Backend && uv sync && uv run python -m app.cli set-password admin && uv run uvicorn app.main:app --reload`.
5. Frontend : `cd frontend && npm install && npm run dev` puis http://localhost:5173 (le proxy `/api` vise le port 8000).

Connexion avec `admin` et le mot de passe choisi à l'étape 4. L'admin crée ensuite une direction, un service, des agents, puis les
comptes utilisateurs (chaque utilisateur est lié à un agent, donc à un service).

## Rôles

- **ADMIN** : tout (utilisateurs, agents, services, documents et chat de tous les services, audit).
- **UTILISATEUR** : ajoute, modifie, supprime les documents de son service et interroge le chatbot sur ce service ; ne crée ni agent ni utilisateur.

Détails dans `docs/architecture.md`.
