# Plan : GED hiérarchique (Direction → Services → Divisions) dans RAG_OCR_Tresor

Ce document décrit **tout ce qui change** (base, API, interface, tests, jeux de données), avec le niveau d'impact de chaque fichier.
Il remplace l'ancien modèle « dossiers plats + rôles de dossier » (`dossier_membre`, `dossier_service`).

Légende : **[AJOUT]** nouveau · **[CONSIDÉRABLE]** réécriture / changement de modèle · **[MOYENNE]** adaptations importantes ·
**[MINEURE]** quelques lignes · **[SUPPRESSION]** retiré.

---

## 0. Point de départ constaté (audit du dépôt avant intégration)

| Constat | Conséquence dans ce plan |
|---|---|
| `core/permissions.py`, dossiers, documents, chat et recherche appliquent encore **l'ancien modèle** | Réécriture complète du contrôle d'accès (§ 4) |
| Les services/routes `demandes`, `securite`, `historique`, `roles_division`, `tableau_de_bord` sont des **squelettes** : `PUT /securite/secrets` accepte un hash fourni par le client, `deverrouiller` ne vérifie aucun mot de passe, `verification` renvoie toujours `ok`, le hash chaîné n'est jamais calculé, aucune portée par niveau | Réimplémentés (§ 4) |
| `database/01_schema.sql` fusionné a **perdu** : `vue_document_stats`, index HNSW / GIN, contrainte de normalisation des vecteurs, unicité d'un compte par agent, déclencheurs `modifie_le`, permissions `audit.consulter`, `classement.gerer`, `statistiques.globales` ; il garde `dossier_membre` / `dossier_service` ; aucun index d'unicité des chefs | Schéma réécrit (§ 3) |
| `Backend/app/cli.py creer-admin` crée un faux agent `CHEF_SERVICE` et un mot de passe **codé en dur** | Compte racine sans agent, mot de passe saisi (§ 4) |
| `MemoireChat.dossier_ids` (modèle) ≠ `document_ids` (SQL) | Aligné sur `document_ids` |
| Le frontend **ne compile pas** (`tsc` : `src/App.tsx`, `DemandesPage.tsx`) et ne contient aucune page du plan ; une quarantaine de fichiers sont orphelins | Nettoyage + nouvelles pages (§ 5) |
| `Document.cree_par_service_id` n'est jamais renseigné | Renseigné au dépôt (statistiques par service) |
| La recherche vectorielle n'exclut pas les fichiers en corbeille | Exclusion ajoutée |

---

## 1. Décisions validées

1. **Sous-dossier d'un dossier** : simple structure, **sans rôle**, visible de **tout agent de la division**. Ce sont les **fichiers** qu'il contient qui portent des rôles.
2. **Mots de passe de dossier** : réservés aux administrateurs **supérieurs** (super administrateur, chef de service). Le chef de division n'en a pas
   besoin, **non pas par dispense**, mais parce que sa division ne contient plus de dossier protégé par mot de passe.
3. **Titre = rôle d'administration** (une seule source de vérité). **Un seul chef de service par service et un seul chef de division par
   division**, garanti **en base** ; dans les formulaires la case « chef » se désactive d'elle-même si le poste est occupé.
4. **Un agent appartient à un seul service et à une seule division.**
5. **Classement des fichiers par rôle** : automatique selon l'utilisateur qui dépose. Si c'est un **administrateur**, il choisit le classement ;
   sans choix, le fichier est en **accès refusé par défaut** (métadonnée vide, « à classer »).

---

## 2. Modèle fonctionnel

### 2.1 Structure et identités

```
Direction (super administrateur, compte global ADMIN, sans agent)
 └── Service            (un chef de service : agent titré CHEF_SERVICE, sans division)
      └── Division      (un chef de division : agent titré CHEF_DIVISION)
           └── Dossiers et sous-dossiers libres (sans login) → fichiers (rôles de la division)
```

- Hiérarchie fixe, créée par le super administrateur. Agents créés par lui, avec un **titre** facultatif (`CHEF_SERVICE`, `CHEF_DIVISION`).
- **Niveau d'un compte** : `ROOT` (rôle global ADMIN), `SERVICE` (agent CHEF_SERVICE), `DIVISION` (agent CHEF_DIVISION), `AGENT`.
- Règles d'intégrité en base : un chef de service est rattaché à un service **sans division** ; un chef de division à une division ;
  l'agent et sa division sont toujours du même service ; un agent actif unique par poste (index uniques partiels).
- **Transfert de poste** atomique (retire l'ancien, nomme le nouveau, même transaction, tracé, notifié). Poste vacant = aucun chef **actif**.
- **Création des comptes** : le super administrateur crée tous les comptes ; le chef de service ceux des chefs de division de son service ;
  le chef de division (ou son intérimaire) ceux des agents de sa division.

### 2.2 Dictionnaire de rôles par division

- Défini par le chef de division (`role_division`), référencé **par identifiant** (renommer ne casse rien). Unicité du code par division.
- Un utilisateur reçoit **un ou plusieurs rôles** à sa création puis par modification (`user_role_division`).
- Un fichier porte **un ou plusieurs rôles** (`document_role`, cohérence de division garantie par clés étrangères composites).
- Rôle **inactif** : n'est plus attribuable ni demandable, les attributions existantes restent valables. Suppression refusée (409) tant qu'il est utilisé.

### 2.3 Règle d'accès (évaluée à chaque requête, jamais en cache)

1. Compte **et** agent actifs, sinon refus (401).
2. Fichier de **sa division** :
   - **GERANT** (chef de division, ou intérimaire §9) : voit et gère tout ;
   - **AUTEUR** (celui qui a déposé) : voit, modifie, ajoute des versions, met à la corbeille ses propres fichiers ;
   - **LECTEUR** : l'un de ses rôles ∈ rôles du fichier, ou **exception ponctuelle** valide ;
   - sinon **403** (le fichier existe, « Demander l'accès » est proposé).
3. Fichier d'une **autre division** : seul un administrateur supérieur (chef de service pour son service, super administrateur partout), **en lecture**,
   et seulement si l'unité est **déverrouillée** (**423** sinon). Rôle effectif : **SUPERIEUR**. Hors périmètre : **404**.
4. **Dossiers et sous-dossiers** : visibles de tout agent de la division ; le nombre de fichiers **masqués** est affiché.
5. Matrice (une seule source de vérité : `core/acces.py`) :

| Action | GERANT | AUTEUR | LECTEUR | SUPERIEUR |
|---|---|---|---|---|
| voir, aperçu, télécharger, interroger (chat) | oui | oui | oui | oui (unité déverrouillée) |
| commenter | oui | oui | oui | non |
| ajouter un fichier (dans sa division) | oui (membre) | — | — | non |
| ajouter une version, modifier titre/cases | oui | oui | non | non |
| mettre à la corbeille / restaurer | oui | oui | non | non |
| supprimer définitivement, changer les rôles du fichier | oui | non | non | non |

### 2.4 Classement par rôle au dépôt

- **Agent** : le fichier reçoit tous ses rôles (préselectionnés) ; il peut en retirer, jamais en ajouter un qu'il n'a pas. Aucun rôle = « à classer » :
  visible du gérant (notifié) et de l'auteur.
- **Administrateur** : choisit dans le dictionnaire de la division ; sans choix = **accès refusé par défaut** (« à classer »).
- **Jamais de reclassement rétroactif** : modifier les rôles d'un utilisateur ne change aucun fichier.
- Seul le gérant change les rôles d'un fichier existant ; tout est historisé.

### 2.5 Mots de passe de dossier (unités)

- Un secret par couple **(unité, administrateur supérieur)** : une **division** a un secret pour le chef de son service et pour chaque super
  administrateur ; un **service** en a un pour chaque super administrateur. Déverrouiller un service ouvre toutes ses divisions.
- **Ré-authentification** : le déverrouillage dure 15 min (`DEVERROUILLAGE_MINUTES`), stocké en base, révocable. Hash scrypt, 5 échecs / 5 min,
  échecs journalisés. Réponse **403** (jamais 401 : l'interface ne doit pas se déconnecter).
- Un administrateur définit/modifie son secret (ancien mot de passe exigé s'il existe). Son **supérieur** peut le **réinitialiser sans ancien mot
  de passe** (super administrateur → secrets du chef de service) : ferme ses déverrouillages, le notifie, tracé. Verrou applicatif contre
  l'accès accidentel : le supérieur garde la main, mais laisse une trace.
- Gérer une division depuis l'extérieur (intérim) exige aussi le déverrouillage.

### 2.6 Demandes d'accès

- **Demande de rôle** (durable) : décidée par le gérant ; si acceptée, le rôle est ajouté à l'agent.
- **Demande d'accès ponctuel à un fichier** : motif + durée demandée ; si acceptée, **exception à expiration**, rôles inchangés. Révocable.
- Une demande en attente par cible et par demandeur. Tout est notifié et historisé.

### 2.7 Notifications, historique, tableaux de bord

- **Notifications** (table `notification`, cloche, interrogation toutes les 30 s) : nouvelle demande, décision, fichier à classer, rôles modifiés,
  nomination/retrait de chef, poste vacant, mot de passe de dossier réinitialisé.
- **Historique de traçabilité** (`historique_modification`, distinct de `journal_audit`) : comptes, rôles, fichiers, titres, demandes, exceptions,
  secrets, déverrouillages. Ligne : acteur, cible, action, avant/après, motif, périmètre, **rang et hash chaîné calculés par la base**
  (SHA-256, verrou consultatif), table **en ajout seul** (déclencheurs), sans clé étrangère (registre immuable). `GET /historique/verification`
  recalcule la chaîne. Consultation par périmètre : super admin (tout), chef de service (son service), chef de division (sa division), agent
  (ce qui le concerne).
- **Tableau de bord** par niveau, agrégats calculés côté serveur dans le périmètre : super admin (par service, alertes : < 2 super admins,
  postes vacants), chef de service (par division), chef de division (par rôle, fichiers à classer, demandes), agent (ses fichiers, rôles, demandes).

---

## 3. Base de données

Scripts fusionnés ; **aucune migration** (base recréée).

| Fichier | Niveau | Contenu |
|---|---|---|
| `database/01_schema.sql` | [CONSIDÉRABLE] | Schéma complet et contraintes : organisation, comptes, audit, chat, dossiers hiérarchiques, documents, versions, chunks (HNSW, GIN, normalisation), classement documentaire, commentaires, rôles par division, demandes, exceptions, secrets, déverrouillages, historique chaîné + déclencheurs, notifications, vue `vue_document_stats`, déclencheurs `modifie_le` |
| `database/02_donnees_reference.sql` | [CONSIDÉRABLE] | Rôles globaux `ADMIN` / `UTILISATEUR` et permissions. Ni compte, ni organisation |
| `database/03_verification.sql` | [CONSIDÉRABLE] | Vue `verification_invariants` (toutes les valeurs attendues : 0) et fonction `verifier_historique()` |
| `database/seed.sql` | [AJOUT] | Jeu de démonstration (préfixe `DEMO`) : 1 direction, 2 services, 4 divisions, 14 agents, comptes, rôles, dossiers, fichiers, demandes, secrets |
| `database/delete_seed.sql` | [AJOUT] | Retire exactement ce que `seed.sql` a créé (et ce que la démo y a ajouté), sans toucher aux données réelles |
| `database/verif_vecteurs_normalises.sql` | [AJOUT] | Rétabli (supprimé à tort lors de la fusion) |

Changements de modèle : `division` ; `agent` gagne `division_id`, `titre` ; `dossier` gagne `division_id`, `parent_id` ; `document` gagne
`division_id` ; **`dossier_membre` et `dossier_service` disparaissent** ; `memoire_chat.document_ids` ; nouvelles tables `role_division`,
`user_role_division`, `document_role`, `demande_acces`, `acces_exception`, `secret_unite`, `deverrouillage`, `historique_modification`, `notification`.

---

## 4. Backend

| Fichier | Niveau | Changement |
|---|---|---|
| `app/db/metier.py`, `db/vecteur.py` | [CONSIDÉRABLE] | Modèles alignés sur le schéma ; suppression de `DossierMembre` / `DossierService` ; `MemoireChat.document_ids` |
| `app/core/permissions.py` | [CONSIDÉRABLE] | `Principal` (niveau, agent, division, rôles), permissions globales + permissions par niveau |
| `app/core/acces.py` | [AJOUT] | Règle d'accès hiérarchique : gérant, intérim, déverrouillage, rôle effectif sur dossier/fichier, **condition SQL** d'accès aux fichiers (liste, recherche, chat) |
| `app/core/portee.py` | [CONSIDÉRABLE] | Portée d'un administrateur (comptes, divisions, services gérables) |
| `app/api/deps.py` | [MINEURE] | Refus des agents inactifs |
| `app/services/historique.py`, `notifications.py` | [CONSIDÉRABLE] | Écriture tracée (hash par la base), vérification ; destinataires de gestion |
| `app/services/roles_division.py`, `demandes.py`, `securite.py`, `tableau_de_bord.py` | [CONSIDÉRABLE] | Logique métier réelle |
| `app/services/structure/crud.py` | [CONSIDÉRABLE] | Divisions, titres, transfert de chef, postes, arbre, mutation d'agent |
| `app/services/users/crud.py` | [CONSIDÉRABLE] | Comptes par périmètre, rôles de division, garde-fous |
| `app/services/dossiers/crud.py` | [CONSIDÉRABLE] | Dossiers et sous-dossiers par division, déplacement (sans cycle), archivage, suppression |
| `app/services/documents/crud.py` | [CONSIDÉRABLE] | Classement par rôle au dépôt, filtre SQL d'accès, historique |
| `app/services/retrieval/similarity_search.py`, `chat/*`, `api/routes/chat.py` | [MOYENNE] | Filtre par condition d'accès fichier ; masquage et mémoire par fichier |
| `app/api/routes/*` (structure, users, dossiers, documents, commentaires, chat, auth) | [CONSIDÉRABLE / MOYENNE] | Périmètres et codes d'erreur |
| `app/api/routes/roles_division.py`, `demandes.py`, `securite.py`, `historique.py`, `notifications.py`, `tableau_de_bord.py` | [CONSIDÉRABLE] | Réécrites |
| `app/api/routes/me.py`, `partage.py`, `services/partage.py` | [SUPPRESSION] | Doublon de `/auth/me` ; code mort du partage abandonné |
| `app/cli.py` | [MOYENNE] | `creer-admin` (direction + compte racine, mot de passe saisi), `set-password`, `reinitialiser-secret` |
| `scripts/seed_fichiers.py` | [AJOUT] | Écrit sur disque les fichiers texte des documents de `seed.sql` |
| `app/config.py`, `.env.example` | [MINEURE] | `DEVERROUILLAGE_MINUTES` |

Codes d'erreur : **404** hors périmètre (l'existence n'est pas révélée) ; **403** rôle insuffisant (dans sa division, « Demander l'accès ») ;
**423** unité à déverrouiller ; **409** conflit (chef déjà présent, rôle utilisé, dossier archivé, doublon).

### API

```http
GET    /auth/me                                         (niveau, division, titre, rôles de division)
GET    /tableau-de-bord
GET    /structure/arbre            GET /structure/postes
POST|PATCH /structure/directions|services|divisions|agents          (super administrateur)
PUT    /structure/services/{id}/chef      PUT /structure/divisions/{id}/chef
GET|POST /divisions/{id}/roles     PATCH|DELETE /divisions/{id}/roles/{role_id}
GET|PUT /users/{id}/roles          GET /users/agents-disponibles
GET|POST /users    GET|PATCH /users/{id}
GET    /dossiers?division_id&parent_id    POST /dossiers    GET|PATCH|DELETE /dossiers/{id}
GET|POST /documents (+ role_ids[])        PUT /documents/{id}/roles    GET /documents/{id}/historique
GET|POST /demandes?vue=mes|a_traiter      POST /demandes/{id}/decision
GET    /demandes/exceptions               DELETE /demandes/exceptions/{id}
GET    /securite/unites     POST /securite/deverrouiller   POST /securite/verrouiller   PUT /securite/secrets
GET    /historique          GET /historique/verification
GET    /notifications       POST /notifications/{id}/lue   POST /notifications/lues
```

---

## 5. Interface (React + TypeScript)

| Fichier | Niveau | Changement |
|---|---|---|
| `features/auth/types.ts`, `session.ts` | [MOYENNE] | Niveau, division, titre, rôles de division |
| `app/nav.ts`, `router.tsx`, `layouts/AppLayout.tsx` | [MOYENNE] | Nouvelles pages ; cloche de notifications ; libellé du niveau ; accueil = tableau de bord |
| `features/tableau-de-bord/*` | [AJOUT] | Un tableau de bord par niveau |
| `features/dossiers/*` | [CONSIDÉRABLE] | Navigation par division, fil d'Ariane, sous-dossiers, fichiers masqués, déverrouillage (423) |
| `features/documents/*` | [CONSIDÉRABLE] | Rôles au dépôt, rôles du fichier, historique du fichier, « Demander l'accès » (403) |
| `features/roles/*`, `demandes/*`, `securite/*`, `historique/*`, `notifications/*` | [AJOUT] | Nouvelles pages |
| `features/admin/users/*`, `admin/structure/*` | [CONSIDÉRABLE] | Comptes par périmètre avec rôles ; divisions, titres, transfert de chef |
| `features/admin/dossiers/AdminDossiersPage.tsx`, `dossiers/AccesDossierModal.tsx` | [SUPPRESSION] | L'accès par membres et par service disparaît |
| `src/App.tsx`, `src/api`, `src/components`, `src/hooks`, `src/lib`, `src/types`, anciens panneaux | [SUPPRESSION] | Fichiers orphelins qui empêchent `tsc` de passer |

Vérification de l'interface : build (`tsc` + `vite build`), puis parcours automatisé (Playwright) de chaque niveau sur la base de démonstration,
avec captures d'écran, et corrections.

---

## 6. Tests

| Fichier | Niveau | Contenu |
|---|---|---|
| `tests/test_hierarchie.py` | [AJOUT] | Chefs uniques, transfert, intérim, règle d'accès (404/403/423), déverrouillage et expiration, classement au dépôt, demandes, exceptions, historique chaîné et inaltérable, notifications, tableaux de bord, comptes par périmètre |
| `tests/test_api.py` | [CONSIDÉRABLE] | Fixtures hiérarchiques ; versions, aperçu, chat, mémoire, cases tableaux/images |
| `tests/test_partage_collaboration.py`, `test_security.py` (matrice) | [SUPPRESSION / MOYENNE] | Code retiré ; matrice remplacée |

---

## 7. Jeux de données

- `database/seed.sql` : mot de passe des comptes `demo_*` : **`Demo-GED-2026!`** ; mots de passe de dossier : **`Dossier-2026!`**.
  Compte super administrateur de démonstration `demo_root`. Les fichiers de démonstration pointent vers `Backend/storage/uploads/seed/` : lancer
  `uv run python scripts/seed_fichiers.py` pour les écrire (aperçu et téléchargement).
- `database/delete_seed.sql` : supprime les données `DEMO` et tout ce que la démonstration y a ajouté ; **l'historique est immuable** et n'est pas
  touché (un bloc optionnel, commenté, le réinitialise pour le propriétaire de la base).

## 8. Mise en place

```
psql -U postgres -c "DROP DATABASE IF EXISTS rag;" -c "CREATE DATABASE rag;"
psql -U postgres -d rag -v ON_ERROR_STOP=1 -f database/01_schema.sql
psql -U postgres -d rag -v ON_ERROR_STOP=1 -f database/02_donnees_reference.sql
psql -U postgres -d rag -f database/03_verification.sql
psql -U postgres -d rag -v ON_ERROR_STOP=1 -f database/seed.sql          # facultatif (démonstration)
cd Backend && uv sync && uv run python -m app.cli creer-admin             # sans démonstration
cd ../frontend && npm install && npm run dev
```

## 9. Décisions par défaut

| Question | Choix retenu |
|---|---|
| Plusieurs rôles à l'agent déposant | Tous préselectionnés ; il peut en retirer. Aucun conservé = « à classer » |
| Rôles d'un utilisateur modifiés | Aucun reclassement rétroactif |
| Suppression d'un rôle du dictionnaire | 409 tant qu'il est utilisé ; désactivation possible |
| Chef de division absent | Le **chef de service** reçoit les pouvoirs de gestion (avec déverrouillage) ; sans lui non plus, le super administrateur |
| Super administrateurs | Au moins deux recommandés (alerte) ; on ne retire jamais le dernier |
| Mutation d'un agent | Changer de division retire ses rôles de l'ancienne ; un agent titré ne se mute pas (transférer d'abord) ; désactiver coupe l'accès immédiatement |
| Division désactivée | Lecture conservée, écritures refusées (409) |
| Superviseurs et dépôt | Un administrateur supérieur est en lecture seule sur une autre division |
| Nom d'un sous-dossier | Visible de toute la division ; ne pas y mettre de nom confidentiel |

---

## 10. Suivi d'intégration

### État global

- [x] Schéma et règles de périmètre alignés sur le nouveau modèle hiérarchique.
- [x] Permissions, accès fichiers et validation des rôles d'unité mises en cohérence.
- [x] Formulaires de création de compte et rôles de division adaptés au modèle actuel.
- [x] Script de préparation des fichiers de démonstration ajouté pour l'aperçu et le téléchargement.
- [x] Résolution sécurisée des chemins relatifs pour les aperçus de versions.
- [x] Documentation de plan de migration mise à jour avec le suivi d'intégration.

### Vérifications à garder en place

1. `cd Backend && uv run pytest tests/test_api.py -k "apercu or validation_des_depots"`
2. `cd Backend && uv run pytest tests/test_hierarchie.py`
3. `cd frontend && npm run build`
4. Contrôle manuel de la création de compte, des rôles de division et du parcours de démonstration.

### Points de vigilance

- Les chemins de fichiers stockés doivent rester confinés dans le dossier d'upload.
- Les comptes créés sans agent doivent rester interdits pour les utilisateurs standards.
- Les rôles de division doivent être attribués au moment de la création et conservés séparément du rôle global.
