# RAG_OCR_Tresor

Assistant RAG 100 % local en français, sur CPU, organisé en **GED hiérarchique** :
Direction → Service → Division → agents. Chaque **division** reçoit des **fichiers versionnés** déposés
directement (plus de dossiers ni d'arborescence — OCR inclus, aperçu et téléchargement), des **rôles de
division** pour le classement et l'accès (un fichier peut porter plusieurs classes, un agent en porter
plusieurs), et un **assistant** qui ne répond qu'à partir des fichiers auxquels on a accès.

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

- [docs/refonte_fichiers.md](docs/refonte_fichiers.md) : **refonte 11/2026** — `/fichiers` remplace `/dossiers` (dépôt direct dans la division, sans arborescence), filtres par rôle et par division, droits étendus du chef de service (agents et chefs de division de son service) et traçage des erreurs d'indexation dans les tableaux de bord.
- [docs/retour_chef_service.md](docs/retour_chef_service.md) : **évolution 11/2026** — le chef de service est rétabli (même rôle que le chef de division, sur toutes les divisions de son service).
- [docs/refonte_super_admin.md](docs/refonte_super_admin.md) : **refonte 11/2026** — regroupement des responsabilités sur le super administrateur (partiellement remplacée par l'évolution ci-dessus : le chef de service est rétabli).
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

**Aucun script de migration** : les scripts `01`, `02`, `03` sont faits pour une **base vierge**. Une base d'une
version antérieure se **recrée** (sauvegarde, `DROP DATABASE`, `CREATE DATABASE`, puis la chaîne ci-dessus ; ordre
complet et précautions : `docs/ordre_execution_sql.md`). Le backend refuse de démarrer sur un schéma non conforme.


Pour contrôler que les embeddings sont bien normalisés : `psql -U postgres -d rag -f database/verif_vecteurs_normalises.sql` (attendu : 0 non normalisé).

## Serveur Linux ou Windows

Le backend peut être déployé sur l'un ou l'autre ; la conversion bureautique s'adapte automatiquement à l'OS
(`Backend/app/services/conversion_office.py`, détection au démarrage du process) :

- **Linux** : LibreOffice doit être installé (`soffice`) — il sert à l'aperçu des fichiers Word, PowerPoint,
  Excel et OpenDocument (conversion en PDF) et est appelé en interne par LiteParse pour l'indexation.
- **Windows** : Microsoft Office doit être installé sur le serveur — l'aperçu et l'ingestion convertissent les
  fichiers Office/OpenDocument en PDF via Office piloté en COM/PowerShell (Word, Excel, PowerPoint selon le type) ;
  LibreOffice (`soffice.exe`) sert de repli si Office est indisponible. PowerShell est présent par défaut sur
  Windows Server, rien à installer.

Sans aucune suite bureautique, l'aperçu de ces types répond par un message clair (501) et le téléchargement reste possible.

La démo et le développement peuvent tourner **entièrement sur Windows 11** (Python, PostgreSQL, OCR, API :
rien ne dépend du système), la **cible de production est Linux** — même code, mêmes commandes, LibreOffice
et systemd en exploitation. L'application ne s'intègre à aucun annuaire ni compte du système : voir
`docs/refonte_classes.md` pour la décision et le périmètre.

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

Authentification gérée **par l'application elle-même** : comptes créés par le super administrateur (ou au
CLI), mots de passe hachés (scrypt) dans la base — aucun compte du système d'exploitation, aucune
intégration PAM ni annuaire. Décision de refonte et modèle d'accès : `docs/refonte_classes.md`.

L'aperçu des fichiers Word, PowerPoint, Excel et OpenDocument demande une suite bureautique sur le serveur — Microsoft Office sous Windows, LibreOffice sous Linux (voir « Serveur Linux ou Windows ») ;
sans elle, l'aperçu de ces types répond par un message clair et le téléchargement reste possible.

Chaque formulaire de l'interface a un bouton « Remplir avec exemple » qui le remplit de fausses informations (champs vides tant qu'on ne clique pas).

## Rôles et niveaux

Quatre niveaux de gestion (voir `docs/retour_chef_service.md` et `docs/refonte_classes.md`) :

- **ADMIN — super administrateur (niveau ROOT)** : gère la structure, **tous les comptes** (y compris les
  chefs), assure **l'intérim de la gestion des divisions vacantes**, consulte l'audit et l'historique complet,
  voit le tableau de bord par service. **Il ne fait qu'administrer** : ni consultation des fichiers,
  ni interrogation IA. Il ne peut pas être membre d'une division.
- **Chef de service (titre d'agent `CHEF_SERVICE`, niveau SERVICE)** : le **même rôle que le chef de division**,
  étendu à **toutes les divisions de son service** — gérant des fichiers, **classement des fichiers**,
  demandes —, y compris l'intérim local des divisions vacantes. Il **gère les comptes de son service,
  y compris les chefs de division** : création de compte et affectation d'agent, réinitialisation du mot
  de passe, rôles — il peut donc créer le compte de l'admin de chaque division si le super administrateur
  ne l'a pas fait. **Mêmes menus que le chef de division** (Rôles et classement, Utilisateurs) : la gestion
  des agents et de la structure reste au super administrateur. Il appartient à son service **sans division
  propre**. L'IA lui répond depuis tous les fichiers d'une division ou de toutes les divisions de son service.
- **Chef de division (titre d'agent `CHEF_DIVISION`, niveau DIVISION)** : gérant de sa division — définit
  le dictionnaire des rôles, **assigne les classes des fichiers**, traite les demandes
  d'accès et les exceptions ponctuelles, crée les comptes des agents de sa division. Lecture et écriture
  de tous les fichiers de sa division ; l'IA couvre sa division entière.
- **Agent (niveau AGENT)** : dépose des fichiers **directement dans sa division** (il en devient AUTEUR,
  classés automatiquement à ses rôles), voit **uniquement les fichiers de sa division classés selon ses
  rôles**, commente, demande un accès ponctuel
  (`demande_acces`). Hors de sa division : 404 ; rôle insuffisant : 403 ; division désactivée : écritures refusées (409).

Rôles effectifs sur un fichier (recalculés à chaque requête, matrice `MATRICE` de `core/acces.py`) :

| | LECTEUR | AUTEUR | GERANT (chef de division) | SUPERIEUR (super admin, déverrouillé) |
|---|---|---|---|---|
| Voir, aperçu, téléchargement, chat, commenter | oui | oui | oui | oui |
| Ajouter un fichier / une version, modifier titre et cases | non | oui | oui | non |
| Corbeille, restauration (suppression) | non | **non** | oui (chef de division / chef de service) | non |
| Purge définitive, rôles du fichier | non | non | oui | non |

**Plus de dossiers** (refonte `/fichiers`, `docs/refonte_fichiers.md`) : la page **Fichiers** liste à plat
tous les fichiers accessibles, avec recherche, filtres de classe (catégorie, type, confidentialité), **filtre
par rôle** (les fichiers des admins portent plusieurs rôles, un agent peut en porter plusieurs) et, pour le
chef de service, **filtre par division** ; dépôt direct dans la division (choix de la division s'il en gère
plusieurs). **Stockage à plat** (`docs/refonte_classes.md`) : tous les fichiers vivent dans le seul
`storage/uploads/` sous un nom généré — l'accès est entièrement contrôlé par l'application. Les dépôts
anciens (`<division>/<dossier>/…` ou déjà à plat) restent lisibles : c'est le chemin enregistré en base
qui fait foi. Le **tableau de bord du super administrateur (`/admin`, sa première page — il n'a pas d'Accueil)**
trace les **erreurs d'indexation** par service, par division et par rôle ; les Accueils du chef de service,
du chef de division et de l'agent reprennent la même traçabilité dans leur périmètre (l'agent : ses fichiers
seulement). La traçabilité complète est dans `historique_modification`
(en ajout seul, chaîné par hash, vérifiable via `/api/historique/verification`).
