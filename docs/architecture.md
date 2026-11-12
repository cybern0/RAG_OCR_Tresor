# Architecture

## Rôles et droits
Deux rôles seulement (tables `_role`, `permission`, `role_permission`, remplies par `database/04`) :

- **ADMIN** : toutes les permissions. Crée les directions, services, agents et utilisateurs ; gère les documents et interroge le chatbot sur tous les services ; consulte le journal d'audit.
- **UTILISATEUR** : `document.lister|creer|modifier|supprimer` et `chat.utiliser`. Il fait le CRUD des documents de **son propre service** et interroge le chatbot sur ce service. Il ne peut créer ni agent, ni utilisateur, ni service.

Le service d'un compte est celui de son agent (`_user.agent_id -> agent.service_id`). Règles appliquées par le backend :
un UTILISATEUR doit être lié à un agent actif ayant un service ; un agent n'a qu'un compte ; on ne peut ni se rétrograder, ni se désactiver, ni retirer le dernier admin actif.
Un document d'un autre service renvoie 404 (son existence n'est pas révélée).

## Authentification
Connexion `POST /auth/login` -> jeton signé (HMAC-SHA256) envoyé en `Authorization: Bearer`. Mots de passe hachés avec scrypt.
Le jeton devient invalide si le mot de passe change ou si le compte est désactivé. Un hash commençant par `!` verrouille le compte
(l'admin du seed). Cinq échecs en cinq minutes bloquent temporairement la connexion (par IP + nom).

## Flux d'ingestion
1. Le frontend envoie le fichier (api/documents.ts) vers `POST /documents`.
2. Le backend enregistre le document avec le statut `pending` (services/documents/crud.py), sous un nom de fichier généré.
3. Le worker (workers/ingestion_worker.py, un seul thread) exécute services/ingestion/pipeline.py :
   parsing LiteParse (OCR seulement si une page n'a pas de texte natif), découpage, embeddings Ollama, écriture dans pgvector.
4. Le statut passe à `processing`, puis `ready` ou `error` (avec `message_erreur`) ; le tableau de bord le suit.
Au redémarrage de l'API, les documents restés `pending` ou `processing` sont remis en file.

## Flux de question
1. Le chatbot envoie la question (api/chat.ts) vers `POST /chat`.
2. services/retrieval/similarity_search.py renvoie les chunks les plus proches (vecteurs + plein texte français, fusionnés),
   limités aux documents `ready` des services autorisés (voir « Vecteurs » ci-dessous).
3. services/chat/rag_chain.py construit le prompt ; sans passage trouvé, le LLM n'est pas appelé et la réponse est « Je ne sais pas ».
   La réponse est streamée en Server-Sent Events (meta, sources, token, done) avec les sources citées.

## Vecteurs : normalisation et produit scalaire
- Tous les embeddings (passages **et** questions) sont normalisés en norme L2 = 1 par `services/ingestion/embedding.py`, puis vérifiés
  (tolérance 1e-6) avant tout usage : un vecteur nul, non fini ou mal normalisé provoque une erreur explicite.
- La recherche classe par produit scalaire : opérateur `<#>` (qui renvoie le produit scalaire négatif, d'où `ORDER BY` croissant),
  servi par l'index HNSW `vector_ip_ops`. Sur des vecteurs unitaires, le classement est identique à celui du cosinus.
- Trois garde-fous : normalisation dans le backend, contrôle du vecteur de la question avant la requête, et contrainte SQL
  `ck_chunk_embedding_normalise` (`vector_norm(embedding)` entre 0,999 et 1,001) qui refuse tout vecteur non normalisé.
- Changer de modèle d'embeddings : adapter `EMBEDDING_DIM` et `vector(768)` dans `database/02` ; la normalisation reste valable.
- Ne pas mélanger les opérateurs : `<=>` ou `<->` ne seraient plus servis par l'index `vector_ip_ops`.
- `database/verif_vecteurs_normalises.sql` (facultatif) compte les vecteurs non normalisés ; le résultat attendu est 0.

## Rôle des dossiers du backend
- `api/` : HTTP seulement, sans logique métier
- `services/` : logique métier par domaine (documents, ingestion, retrieval, chat, users, structure, audit)
- `clients/` : accès à Ollama et au serveur OCR
- `db/` : connexion et modèles (métier et vecteurs)
- `core/` : sécurité et permissions
- `schemas/` : formats d'entrée et de sortie de l'API
- `workers/` : tâches lentes en arrière-plan
- `cli.py` : définition du mot de passe d'un compte (`python -m app.cli set-password`)

## Interface
Thème : fonds vert végétal, texte blanc cassé, composants (boutons, bordures, badges, éléments actifs) jaune doré ;
définis une seule fois dans `frontend/src/index.css`.
