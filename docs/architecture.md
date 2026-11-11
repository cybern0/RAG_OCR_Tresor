# Architecture

## Flux d'ingestion
1. Le frontend envoie le fichier (api/documents.ts) vers `POST /documents`.
2. Le backend enregistre le document avec le statut `pending` (services/documents/crud.py).
3. Le worker (workers/ingestion_worker.py) exécute services/ingestion/pipeline.py :
   parsing LiteParse (+ OCR si besoin), découpage, embeddings Ollama, écriture dans pgvector.
4. Le statut passe à `processing`, puis `ready` ou `error` ; le tableau de bord le suit.

## Flux de question
1. Le chatbot envoie la question (api/chat.ts).
2. services/retrieval/similarity_search.py renvoie les chunks les plus proches, filtrés selon les droits.
3. services/chat/rag_chain.py construit le prompt, le LLM répond, la réponse est streamée avec ses sources.

## Rôle des dossiers du backend
- `api/` : HTTP seulement, sans logique métier
- `services/` : logique métier par domaine
- `clients/` : accès à Ollama et au serveur OCR
- `db/` : connexions aux bases
- `core/` : sécurité et permissions
- `schemas/` : formats d'entrée et de sortie de l'API
- `workers/` : tâches lentes en arrière-plan

## Contrôle d'accès
- Deux rôles : ADMIN et UTILISATEUR. Les deux gèrent les documents de leur propre service ; seul ADMIN consulte le journal d'audit.
- Aucun rôle ne crée d'agent ni d'utilisateur dans l'application : les comptes sont créés hors application (backend/scripts/creer_compte.py).
- Le service est déduit côté serveur (utilisateur, agent, service), jamais fourni par le client.
- Le filtre par service s'applique à la recherche vectorielle avant tout appel au LLM.
- Détail et consignes d'implémentation : docs/PROMPT_SUITE_APP.md
