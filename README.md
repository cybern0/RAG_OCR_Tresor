# RAG_OCR_Tresor

Assistant RAG 100 % local en français, sur CPU, organisé comme un espace de partage de fichiers :
des **dossiers** (créés par l'admin, avec des rôles par utilisateur ou par service), des **fichiers versionnés** (OCR inclus,
aperçu et téléchargement) et un **chatbot** qui ne répond qu'à partir des dossiers auxquels on a accès.

## Arborescence

```
RAG_OCR_Tresor/
├── Backend/        API FastAPI (Python, uv)
├── frontend/       Interface React + TypeScript (Vite)
├── database/       Scripts SQL, à exécuter dans l'ordre 01 à 05 (+ retour arrière et vérification de 05)
├── ocr_server/     Serveur PaddleOCR, séparé du backend
├── docs/           Architecture, historique des renommages et plans d'implémentation
└── .env.example
```

### Documentation complémentaire

- [docs/architecture.md](docs/architecture.md) : architecture applicative et règles de sécurité.
- [docs/renommages.md](docs/renommages.md) : historique des renommages de fichiers et modules.
- [docs/plan_ged_implementation.md](docs/plan_ged_implementation.md) : plan détaillé de la GED (classement, statistiques, partage, collaboration, corbeille).

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
psql -U postgres -d rag -v ON_ERROR_STOP=1 -f database/05_dossiers_versions.sql
psql -U postgres -d rag -f database/05_verification.sql
```

Le script `05` sert aussi bien à une installation neuve qu'à la **migration d'une base déjà remplie** (un dossier est créé pour chaque
service et ouvert à ce service ; les documents existants deviennent la version 1). Il tourne en une seule transaction, est répétable,
et a son retour arrière `database/05_retour_arriere.sql`. Pas à pas : `docs/migration_05.md`.

Pour contrôler que les embeddings sont bien normalisés : `psql -U postgres -d rag -f database/verif_vecteurs_normalises.sql` (attendu : 0 non normalisé).
Le compte `admin` est créé verrouillé : voir l'en-tête de `04_seed_roles_permissions.sql`.

## Démarrer

1. Base : voir ci-dessus, puis `cp .env.example .env` et renseigner `SECRET_KEY`.
2. Ollama : `ollama pull qwen3:4b-instruct-2507-q4_K_M` et `ollama pull embeddinggemma:300m-qat-q4_0`.
3. OCR (optionnel tant qu'on ne dépose pas de scans ni d'images) : `cd ocr_server && uv run server.py`.
4. Backend : `cd Backend && uv sync && uv run python -m app.cli set-password admin && uv run uvicorn app.main:app --reload`.
5. Frontend : `cd frontend && npm install && npm run dev` puis http://localhost:5173 (le proxy `/api` vise le port 8000 ; `VITE_PROXY_TARGET` pour un autre).
   Toute l'API vit sous le préfixe `/api` (ex. `/api/auth/login`, `/api/health`) ; `/health` reste disponible pour la supervision.
   En production : `npm run build`, puis le backend sert `frontend/dist` lui-même (une seule adresse, liens profonds compris).

Connexion avec `admin` et le mot de passe choisi à l'étape 4. L'admin crée ensuite une direction, un service, des agents, puis les
comptes utilisateurs (chaque utilisateur est lié à un agent, donc à un service), puis des **dossiers** (onglet « Dossiers et accès »)
et leur donne des rôles : à des utilisateurs, ou à des services entiers.

L'aperçu des fichiers Word, PowerPoint, Excel et OpenDocument demande LibreOffice sur la machine du backend (conversion en PDF) ;
sans lui, l'aperçu de ces types répond par un message clair et le téléchargement reste possible.

Chaque formulaire de l'interface a un bouton « Remplir avec exemple » qui le remplit de fausses informations (champs vides tant qu'on ne clique pas).

## Rôles

- **ADMIN** : crée les dossiers et attribue les rôles ; gère utilisateurs, agents, services ; consulte l'audit ; peut tout faire dans tous les dossiers (aperçu, téléchargement, chat compris).
- **UTILISATEUR** : n'a aucun droit propre sur les fichiers ; tout dépend de ses rôles de dossier.

Rôles de dossier (donnés à un utilisateur ou à un service entier ; le plus élevé s'applique) :

| | LECTEUR | CONTRIBUTEUR | GESTIONNAIRE_DE_CONTENU |
|---|---|---|---|
| Voir la liste, l'historique des versions | oui | oui | oui |
| Aperçu, téléchargement (toute version) | oui | oui | oui |
| Interroger le chatbot sur le dossier | oui | oui | oui |
| Ajouter un fichier, une nouvelle version | non | oui | oui |
| Modifier le titre et les cases tableaux/images | non | oui | oui |
| Supprimer un fichier ou une version | non | non | oui |

Hors de ses dossiers : 404 ; rôle insuffisant : 403. Détails dans `docs/architecture.md`.
