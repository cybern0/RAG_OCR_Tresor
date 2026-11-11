# RAG_OCR_Tresor

Assistant RAG 100 % local en français, sur CPU : dépôt de documents (OCR inclus) et questions via un chatbot.
Les utilisateurs ajoutent, modifient et suppriment des documents, sans en lire le contenu : seul le chat l'interroge.

## Arborescence

```
RAG_OCR_Tresor/
├── backend/        API FastAPI (Python, uv)
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

Les scripts sont répétables. Le compte `admin` est créé verrouillé : voir l'en-tête de `04_seed_roles_permissions.sql`.

## État

Structure en place : les fichiers ne contiennent que des commentaires décrivant leur rôle, hors contenu d'origine conservé tel quel.
