# RAG_OCR_Tresor

Assistant RAG 100 % local en français, sur CPU, organisé en **GED hiérarchique** :
Direction → Service → Division → agents. Des **divisions** possèdent des **dossiers et sous-dossiers**,
des **fichiers versionnés** (OCR inclus, aperçu et téléchargement), des **rôles de division** pour le
classement et l'accès, et un **chatbot** qui ne répond qu'à partir des fichiers auxquels on a accès.

## Arborescence

```
RAG_OCR_Tresor/
├── Backend/        API FastAPI (Python, uv)
├── frontend/       Interface React + TypeScript (Vite)
├── database/       Scripts SQL, à exécuter dans l'ordre 01, 02 (+ contrôles et démonstration facultatifs)
├── ocr_server/     Serveur PaddleOCR, séparé du backend
├── docs/           Architecture, refontes, plans d'implémentation et historique des renommages
└── .env.example
```

### Documentation complémentaire

- [docs/refonte_super_admin.md](docs/refonte_super_admin.md) : **refonte 11/2026** — suppression du chef de service, responsabilités regroupées sur le super administrateur.
- [docs/architecture.md](docs/architecture.md) : architecture applicative et règles de sécurité.
- [docs/paln.md](docs/paln.md) : plan de la GED hiérarchique (le poste « chef de service » décrit dans ce plan est supprimé par la refonte).
- [docs/renommages.md](docs/renommages.md) : historique des renommages de fichiers et modules.
- [docs/plan_ged_implementation.md](docs/plan_ged_implementation.md) : plan historique de la GED (classement, statistiques, corbeille ; les fonctions de partage y sont abandonnées).

## Services externes

- Ollama (natif, port 11434) : LLM et embeddings
- PostgreSQL + pgvector : base métier et base vectorielle
- ocr_server (port 8829) : OCR des images et des scans

## Initialiser la base

PostgreSQL avec l'extension pgvector doit être installé. Créer la base puis exécuter les scripts dans l'ordre :

```
psql -U postgres -c "CREATE DATABASE rag;"
psql -U postgres -d rag -v ON_ERROR_STOP=1 -f database/01_schema.sql
psql -U postgres -d rag -v ON_ERROR_STOP=1 -f database/02_donnees_reference.sql
psql -U postgres -d rag -f database/03_verification.sql
psql -U postgres -d rag -v ON_ERROR_STOP=1 -f database/seed.sql   # facultatif : données de démonstration DEMO
```

`01` crée tout le schéma en une seule transaction (base NEUVE uniquement) ; `02` insère les rôles globaux
et les permissions ; `03` contrôle les invariants (`verification_invariants`, chaque ligne attendue à 0).

**Base existante antérieure à la refonte** (installation avec des chefs de service) : exécuter une fois
`database/10_suppression_chef_service.sql` — les agents titrés `CHEF_SERVICE` redeviennent agents simples,
leurs secrets et déverrouillages sont retirés, les contraintes et index obsolètes sont nettoyés. Puis le
super administrateur réaffecte ces agents à une division. Détails : `docs/refonte_super_admin.md`.

Pour contrôler que les embeddings sont bien normalisés : `psql -U postgres -d rag -f database/verif_vecteurs_normalises.sql` (attendu : 0 non normalisé).

## Démarrer

1. Base : voir ci-dessus, puis `cp .env.example .env` et renseigner `SECRET_KEY`.
2. Ollama : `ollama pull qwen3:4b-instruct-2507-q4_K_M` et `ollama pull embeddinggemma:300m-qat-q4_0`.
3. OCR (optionnel tant qu'on ne dépose pas de scans ni d'images) : `cd ocr_server && uv run server.py`.
4. Backend : `cd Backend && uv sync && uv run python -m app.cli set-password admin && uv run uvicorn app.main:app --reload`.
5. Frontend : `cd frontend && npm install && npm run dev` puis http://localhost:5173 (le proxy `/api` vise le port 8000 ; `VITE_PROXY_TARGET` pour un autre).
   Toute l'API vit sous le préfixe `/api` (ex. `/api/auth/login`, `/api/health`) ; `/health` reste disponible pour la supervision.
   En production : `npm run build`, puis le backend sert `frontend/dist` lui-même (une seule adresse, liens profonds compris).

Connexion avec `admin` et le mot de passe choisi à l'étape 4. Le super administrateur crée ensuite la
structure (direction, services, divisions, agents), les **comptes** (chaque compte est lié à un agent,
donc à une division) et nomme des **chefs de division** (transfert de poste dans l'onglet Agents).

L'aperçu des fichiers Word, PowerPoint, Excel et OpenDocument demande LibreOffice sur la machine du backend (conversion en PDF) ;
sans lui, l'aperçu de ces types répond par un message clair et le téléchargement reste possible.

Chaque formulaire de l'interface a un bouton « Remplir avec exemple » qui le remplit de fausses informations (champs vides tant qu'on ne clique pas).

## Rôles et niveaux

Trois niveaux de gestion, **sans chef de service** (tout échelon au-dessus de la division est le super
administrateur — voir `docs/refonte_super_admin.md`) :

- **ADMIN — super administrateur (niveau ROOT)** : gère la structure, **tous les comptes** (y compris les
  chefs de division), assure **l'intérim des divisions vacantes**, consulte l'audit et l'historique complet,
  voit le tableau de bord par service. Il est le seul à détenir des **mots de passe de dossier** :
  après déverrouillage (423 → saisie du secret), il consulte en lecture seule toute unité, et il gère
  directement les divisions sans chef. Il ne peut pas être membre d'une division.
- **Chef de division (titre d'agent `CHEF_DIVISION`, niveau DIVISION)** : gérant de sa division — crée ses
  dossiers et sous-dossiers, définit le dictionnaire des rôles, classe les fichiers, traite les demandes
  d'accès et les exceptions ponctuelles, crée les comptes des agents de sa division. Lecture et écriture
  de tous les fichiers de sa division.
- **Agent (niveau AGENT)** : dépose des fichiers dans les dossiers de sa division (il en devient AUTEUR),
  voit les fichiers qui partagent un **rôle de division** avec lui, commente, demande un accès ponctuel
  (`demande_acces`). Hors de sa division : 404 ; rôle insuffisant : 403 ; unité verrouillée : 423.

Rôles effectifs sur un fichier (recalculés à chaque requête, matrice `MATRICE` de `core/acces.py`) :

| | LECTEUR | AUTEUR | GERANT (chef de division) | SUPERIEUR (super admin, déverrouillé) |
|---|---|---|---|---|
| Voir, aperçu, téléchargement, chat, commenter | oui | oui | oui | oui |
| Ajouter un fichier / une version, modifier titre et cases | non | oui | oui | non |
| Corbeille, restauration | non | oui | oui | non |
| Purge définitive, rôles du fichier | non | non | oui | non |

Dossiers et sous-dossiers : visibles de tous les agents de la division (ils n'ont pas de rôle) ;
renommer/déplacer : créateur ou gérant. La traçabilité complète est dans `historique_modification`
(en ajout seul, chaîné par hash, vérifiable via `/api/historique/verification`).
