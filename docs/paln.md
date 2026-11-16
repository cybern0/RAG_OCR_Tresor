# Plan : GED hiérarchique (Direction → Services → Divisions) dans RAG_OCR_Tresor

Ce document liste **tout ce qui est modifié** dans l'application (base de données, API, interface, tests, scripts), avec le niveau
d'impact de chaque fichier. Il remplace l'ancien modèle « dossiers plats + rôles de dossier » (`dossier_membre`, `dossier_service`).
Les décisions ci-dessous sont celles validées pendant l'analyse ; les trois points restés ouverts ont une valeur par défaut (§ 3).

Légende : **[AJOUT]** nouveau fichier · **[CONSIDÉRABLE]** réécriture ou changement de modèle · **[MOYENNE]** adaptations
importantes · **[MINEURE]** quelques lignes · **[SUPPRESSION]** fichier retiré.

---

## 1. Modèle fonctionnel

### 1.1 Structure fixe

```
Direction (root, super administrateur)
 └── Service            (un chef de service)
      └── Division      (un chef de division)
           └── Dossiers et sous-dossiers libres (sans login), contenant des fichiers
```

- La hiérarchie Direction / Service / Division est **fixe** : créée par le super administrateur (compte `ADMIN`).
- Les **dossiers** d'une division, et leurs sous-dossiers à volonté, sont libres : tout agent de la division peut en créer, sans
  compte ni mot de passe propre (ils héritent de la division).
- Un agent appartient à **un seul service et une seule division**.

### 1.2 Agents, titres et comptes

- Les agents sont créés par le super administrateur, avec un **titre** facultatif : `CHEF_SERVICE`, `CHEF_DIVISION`, ou vide.
- Le **titre implique le rôle d'administration** (une seule source de vérité) : il n'existe pas de table d'affectation séparée.
- **Un seul chef de service par service, un seul chef de division par division**, garanti **en base** (index uniques partiels) et par
  l'API. Dans le formulaire, la case « chef » est désactivée automatiquement s'il y en a déjà un (`GET /structure/postes`).
  Pour remplacer un chef : opération de **transfert** atomique (`PUT /structure/services/{id}/chef`, `.../divisions/{id}/chef`).
- Un compte utilisateur est lié à un agent. Création : le chef de division crée les comptes des agents de sa division ; le chef de
  service crée ceux des chefs de division de son service ; le super administrateur crée tous les comptes (dont les chefs).

### 1.3 Métadonnées par division : dictionnaire de rôles

- Chaque chef de division définit le **dictionnaire de rôles** de sa division (`role_division`), référencés **par identifiant**
  (renommer un rôle ne casse aucun accès).
- Un **utilisateur** reçoit un ou plusieurs rôles du dictionnaire (`user_role_division`) à sa création, puis par modification, par
  le chef de division.
- Un **fichier** porte un ou plusieurs rôles de classement (`document_role`).

### 1.4 Règle d'accès à un fichier (évaluée à chaque requête, jamais en cache)

1. Compte et agent actifs, sinon refus.
2. Fichier de **sa division** :
   - le **chef de division** (ou l'intérimaire, § 3) voit tout, quelles que soient les métadonnées ;
   - un agent voit le fichier si **l'un de ses rôles figure dans les rôles du fichier**, ou s'il a une **exception ponctuelle valide**
     (non expirée) ;
   - sinon : **refus par défaut** (403 avec possibilité de « Demander l'accès »).
3. Fichier d'une **autre division** : seul un administrateur supérieur y accède (chef de service pour les divisions de son service,
   super administrateur pour toutes) **et** seulement si l'unité est **déverrouillée** par son mot de passe (§ 1.6). Accès en lecture.
4. Les **dossiers et sous-dossiers** sont visibles de tout agent de la division ; seuls leurs **fichiers** sont filtrés par rôle.
   Un dossier affiche le nombre de fichiers masqués.
5. Rôle effectif sur un fichier : `GERANT` (chef/intérimaire/super admin gérant), `AUTEUR` (celui qui l'a déposé),
   `LECTEUR` (rôle ou exception), `SUPERIEUR` (administrateur supérieur déverrouillé, lecture seule).

### 1.5 Classement des fichiers par rôle

- **Dépôt par un agent** : le fichier reçoit automatiquement les rôles de l'agent ; il peut en retirer avant de valider. Sans aucun
  rôle, le fichier est « à classer » : seul le chef de division le voit, et il est notifié.
- **Dépôt par un administrateur** (chef de division ou supérieur) : il choisit les rôles dans le dictionnaire de la division ; sans
  choix, le fichier est en **accès refusé par défaut** (« à classer »).
- Le classement n'est **jamais recalculé rétroactivement** : modifier les rôles d'un utilisateur ne change aucun fichier.
- Seul le chef de division change les rôles d'un fichier existant. Chaque changement est tracé.

### 1.6 Mots de passe de dossier (administrateurs hiérarchiques)

- Chaque **unité** (service, division) a un mot de passe **par administrateur supérieur** (`secret_unite`) :
  - une **division** a un secret pour le chef de son service et pour chaque super administrateur ;
  - un **service** a un secret pour chaque super administrateur ;
  - le **chef de division n'en a pas** : sa division ne contient plus de dossier protégé.
- Le mot de passe sert de **ré-authentification** : le déverrouiller ouvre l'unité pour une durée courte (15 min, configurable),
  stockée en base et révocable (`deverrouillage`). Hash scrypt, limitation des tentatives, échecs journalisés.
- Modifiable par **l'administrateur concerné** (il fournit l'ancien mot de passe) ou, **facilement, par son supérieur
  hiérarchique** (réinitialisation sans ancien mot de passe). Un changement ferme les déverrouillages en cours et notifie le titulaire.
- Ce mot de passe est un verrou applicatif contre l'accès accidentel ou abusif : le supérieur peut toujours le réinitialiser, mais
  il laisse une trace.

### 1.7 Demandes d'accès

- **Demande de rôle** (accès durable) : l'agent choisit un rôle du dictionnaire de sa division, avec un motif ; le chef de division
  accepte (le rôle est ajouté à l'agent) ou refuse.
- **Demande d'accès ponctuelle à un fichier** : motif et durée demandée ; si acceptée, une **exception** avec expiration est créée,
  sans modifier les rôles de l'agent.
- Une demande est traitée par le chef de division (ou l'intérimaire). Tout est notifié et tracé.

### 1.8 Notifications (sans serveur externe)

Table `notification` lue par l'interface (cloche, interrogation toutes les 30 s). Événements : nouvelle demande, décision,
fichier à classer, rôles modifiés, nomination ou retrait de chef, mot de passe de dossier réinitialisé.

### 1.9 Historique de traçabilité

- Table **`historique_modification`**, distincte de `journal_audit` : uniquement les **modifications et affectations** (comptes,
  rôles, fichiers, titres, demandes, exceptions, mots de passe de dossier). Les connexions et échecs restent dans `journal_audit`.
- Chaque ligne : acteur, cible, action, **avant / après**, motif, périmètre (service, division), date, **hash chaîné**.
- Table **en ajout seul** : un déclencheur refuse toute modification ou suppression ; le hash est calculé par la base
  (SHA-256, verrou consultatif) ; `GET /historique/verification` recalcule la chaîne.
- Consultation limitée au périmètre : super admin (tout), chef de service (son service), chef de division (sa division), agent (ce qui le
  concerne). Historique d'un fichier : `GET /documents/{id}/historique`.

### 1.10 Tableaux de bord (un par niveau)

`GET /tableau-de-bord` renvoie le tableau adapté : super admin (global, par service), chef de service (par division), chef de division
(par rôle, fichiers à classer, demandes en attente, derniers changements), agent (ses fichiers, ses rôles, ses demandes). Les
agrégats sont calculés côté serveur dans le périmètre du demandeur.

---

## 2. Base de données

Les anciens scripts `01` à `10` sont **fusionnés** (aucune donnée de démonstration, aucune migration : la base est recréée).

| Fichier | Niveau | Contenu |
|---|---|---|
| `database/01_schema.sql` | [AJOUT] | Schéma complet : organisation (`direction`, `_service`, `division`, `agent`), comptes, journal d'audit, chat, dossiers hiérarchiques, documents, versions, chunks vectoriels, classement (catégories, types, tags, règles), commentaires, rôles par division, demandes, exceptions, mots de passe de dossier, déverrouillages, historique chaîné, notifications, vue de statistiques, index, déclencheurs |
| `database/02_donnees_reference.sql` | [AJOUT] | Seulement les données **indispensables au fonctionnement** : rôles globaux `ADMIN` / `UTILISATEUR` et permissions. Ni compte, ni organisation, ni démo |
| `database/03_verification.sql` | [AJOUT] | Contrôles d'invariants (chefs uniques, cohérence service/division, chaîne d'historique, vecteurs normalisés) |
| `database/verif_vecteurs_normalises.sql` | conservé | Inchangé |
| `01_schema_metier`, `02_schema_documents_vecteurs`, `03_index`, `04_seed_roles_permissions`, `05_*`, `06_*`, `08_commentaires`, `09_nettoyage_partage`, `10_seed` | [SUPPRESSION] | Fusionnés dans `01` et `02` |

Changements de modèle principaux :

- `division` (nouvelle) ; `agent` gagne `division_id` et `titre` ; contraintes : un chef par unité, division cohérente avec le service.
- `dossier` gagne `division_id` et `parent_id` (sous-dossiers) ; **`dossier_membre` et `dossier_service` disparaissent**.
- `document` gagne `division_id` (dénormalisé, cohérent avec le dossier).
- `memoire_chat.dossier_ids` devient `document_ids` (l'accès se juge par fichier).
- Nouvelles tables : `role_division`, `user_role_division`, `document_role`, `demande_acces`, `acces_exception`, `secret_unite`,
  `deverrouillage`, `historique_modification`, `notification`.
- Compte initial : plus de compte `admin` verrouillé dans le SQL ; il est créé par `python -m app.cli creer-admin`.

---

## 3. Décisions par défaut (points restés ouverts)

| Question | Choix retenu |
|---|---|
| Plusieurs rôles à l'agent déposant | Tous ses rôles sont préselectionnés ; il peut en retirer avant de valider. Aucun rôle conservé = « à classer » |
| Rôles d'un utilisateur modifiés | Aucun reclassement rétroactif des fichiers ; l'accès suit les rôles actuels de l'agent |
| Suppression d'un rôle du dictionnaire | Refusée (409) tant qu'il est utilisé par un fichier ou un agent ; le renommer reste possible |
| Chef de division absent | Le **chef de service intérimaire** reçoit les pouvoirs de gestion de cette division (il doit toujours déverrouiller l'unité) ; sans chef de service non plus, le super administrateur gère |
| Compte super admin | Au moins deux recommandés ; on ne peut pas retirer le dernier |
| Départ ou mutation d'un agent | Changer la division d'un agent retire ses rôles de l'ancienne division ; désactiver un agent coupe ses accès immédiatement |

---

## 4. Backend

| Fichier | Niveau | Changement |
|---|---|---|
| `app/db/metier.py` | [CONSIDÉRABLE] | Modèles `Division`, rôles, demandes, exceptions, secrets, historique, notifications ; `Agent` (division, titre) ; `Dossier` (division, parent) ; suppression de `DossierMembre` / `DossierService` |
| `app/db/vecteur.py` | [MOYENNE] | `Document.division_id`, relation aux rôles |
| `app/core/permissions.py` | [CONSIDÉRABLE] | Niveau du compte (racine, service, division, agent), contexte d'accès, condition SQL d'accès aux fichiers, rôle effectif, pouvoirs de gestion (intérim compris), déverrouillage |
| `app/core/portee.py` | [AJOUT] | Périmètre d'un administrateur (divisions, services, comptes gérables) |
| `app/api/deps.py` | [MINEURE] | Rien d'autre que les nouveaux imports |
| `app/services/historique.py` | [AJOUT] | Écriture de l'historique de traçabilité |
| `app/services/notifications.py` | [AJOUT] | Création et lecture des notifications |
| `app/services/roles_division.py` | [AJOUT] | Dictionnaire de rôles, affectation aux agents et aux fichiers |
| `app/services/demandes.py` | [AJOUT] | Demandes de rôle et d'accès ponctuel, exceptions |
| `app/services/securite.py` | [AJOUT] | Mots de passe d'unité, déverrouillage, réinitialisation par le supérieur |
| `app/services/tableau_de_bord.py` | [AJOUT] | Tableaux de bord par niveau |
| `app/services/structure/crud.py` | [CONSIDÉRABLE] | Divisions, titres, transfert de chef, postes vacants, mutation d'agent |
| `app/services/users/crud.py` | [CONSIDÉRABLE] | Comptes par périmètre, rôles de division, garde-fous (dernier super admin, auto-désactivation) |
| `app/services/dossiers/crud.py` | [CONSIDÉRABLE] | Dossiers et sous-dossiers par division, déplacement, archivage, suppression |
| `app/services/documents/crud.py` | [CONSIDÉRABLE] | Classement par rôle au dépôt, filtre d'accès par fichier, droits auteur / gérant, historique |
| `app/services/retrieval/similarity_search.py` | [MOYENNE] | Filtre par condition d'accès fichier au lieu de la liste de dossiers |
| `app/services/chat/history.py`, `memoire.py`, `rag_chain.py`, `api/routes/chat.py` | [MOYENNE] | Masquage et mémoire par fichier |
| `app/services/ingestion/pipeline.py` | [MINEURE] | Aucun changement de logique (le classement par rôle se fait au dépôt) |
| `app/schemas/*.py` | [MOYENNE] | `structure`, `user`, `dossier`, `document` ; nouveaux `securite`, `demande`, `role_division`, `historique`, `notification`, `tableau_de_bord` |
| `app/api/routes/structure.py`, `users.py`, `dossiers.py`, `documents.py`, `me.py`, `audit.py` | [CONSIDÉRABLE / MOYENNE] | Nouveaux périmètres et droits |
| `app/api/routes/roles_division.py`, `demandes.py`, `securite.py`, `historique.py`, `notifications.py`, `tableau_de_bord.py` | [AJOUT] | Nouvelles routes |
| `app/api/routes/partage.py`, `app/services/partage.py` | [SUPPRESSION] | Code mort du partage abandonné (il n'importait plus rien de valide) |
| `app/main.py`, `app/config.py` | [MINEURE] | Nouveaux routers, durée de déverrouillage |
| `app/cli.py` | [MOYENNE] | `creer-admin` (direction + compte racine), `set-password` conservé |
| `.env.example` | [MINEURE] | `DEVERROUILLAGE_MINUTES` |

### API ajoutée

```http
GET    /tableau-de-bord
GET    /structure/arbre                       GET /structure/postes
POST/PATCH /structure/divisions               PUT /structure/services/{id}/chef   PUT /structure/divisions/{id}/chef
GET    /divisions/{id}/roles                  POST/PATCH/DELETE /divisions/{id}/roles[/{role_id}]
PUT    /users/{id}/roles                      (affectation des rôles de division)
POST   /dossiers (division_id, parent_id)     PATCH /dossiers/{id} (nom, parent, archive)
POST   /documents  (+ role_ids[])             PUT /documents/{id}/roles   GET /documents/{id}/historique
GET/POST /demandes                            POST /demandes/{id}/decision
GET    /securite/unites                       POST /securite/deverrouiller   POST /securite/verrouiller
PUT    /securite/secrets
GET    /historique                            GET /historique/verification
GET    /notifications                         POST /notifications/{id}/lue   POST /notifications/lues
```

Codes d'erreur : **404** hors périmètre (l'existence n'est pas révélée) ; **403** rôle insuffisant (dans sa division : le
fichier existe, la demande d'accès est proposée) ; **423** unité à déverrouiller ; **409** conflit (chef déjà présent, rôle utilisé, dossier archivé).

---

## 5. Interface (React + TypeScript)

| Fichier | Niveau | Changement |
|---|---|---|
| `src/features/auth/types.ts`, `session.ts` | [MOYENNE] | Niveau, division, titre, rôles de l'utilisateur |
| `src/app/nav.ts`, `router.tsx`, `layouts/AppLayout.tsx` | [MOYENNE] | Nouvelles pages, cloche de notifications, libellé du niveau |
| `src/features/tableau-de-bord/*` | [AJOUT] | Page d'accueil : un tableau de bord par niveau |
| `src/features/dossiers/*` | [CONSIDÉRABLE] | Navigation par division, fil d'Ariane, sous-dossiers, déverrouillage (423) |
| `src/features/documents/*` | [CONSIDÉRABLE] | Choix des rôles au dépôt, rôles du fichier, historique du fichier, bouton « Demander l'accès » |
| `src/features/roles/*` | [AJOUT] | Dictionnaire de rôles de la division |
| `src/features/demandes/*` | [AJOUT] | Mes demandes, demandes à traiter |
| `src/features/securite/*` | [AJOUT] | Mots de passe de dossier, déverrouillage |
| `src/features/historique/*` | [AJOUT] | Historique de traçabilité et vérification de la chaîne |
| `src/features/notifications/*` | [AJOUT] | Cloche et liste |
| `src/features/admin/users/*`, `structure/*` | [CONSIDÉRABLE] | Comptes avec rôles de division ; divisions, titres, transfert de chef |
| `src/features/admin/dossiers/AdminDossiersPage.tsx`, `dossiers/AccesDossierModal.tsx` | [SUPPRESSION] | L'accès par membres et par service disparaît |

---

## 6. Tests

| Fichier | Niveau | Contenu |
|---|---|---|
| `tests/test_hierarchie.py` | [AJOUT] | Chefs uniques, intérim, règle d'accès par rôle, déverrouillage et expiration, classement au dépôt, demandes, exceptions, historique chaîné et inaltérable, notifications, tableaux de bord |
| `tests/test_api.py` | [CONSIDÉRABLE] | Adapté au nouveau modèle (versions, aperçu, chat, comptes) ; les tests liés aux anciens rôles de dossier sont remplacés |
| `tests/test_partage_collaboration.py` | [SUPPRESSION] | Testait du code déjà retiré |
| autres tests | [MINEURE] | Adaptés si leurs appels changent |

---

## 7. Mise en place (après récupération du code)

```
psql -U postgres -c "DROP DATABASE IF EXISTS rag;" -c "CREATE DATABASE rag;"
psql -U postgres -d rag -v ON_ERROR_STOP=1 -f database/01_schema.sql
psql -U postgres -d rag -v ON_ERROR_STOP=1 -f database/02_donnees_reference.sql
psql -U postgres -d rag -f database/03_verification.sql
cd Backend && uv sync && uv run python -m app.cli creer-admin
cd ../frontend && npm install && npm run dev
```

Ensuite, dans l'interface (super administrateur) : direction → services → divisions → agents (avec titres) → comptes ; chaque chef de
division définit ses rôles et affecte les rôles à ses agents ; les administrateurs supérieurs définissent leurs mots de passe de dossier.