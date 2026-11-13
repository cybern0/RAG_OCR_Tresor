# Plan d'implémentation : GED (classement, tableau de bord, partage) dans RAG_OCR_Tresor

Ce document décrit la feuille de route pour ajouter à `RAG_OCR_Tresor` une gestion documentaire complète : classement, tableau de bord avec graphiques groupés et croisés, partage de documents amélioré, collaboration et corbeille.

## 0. Principes et contraintes

- 100 % local : aucun service externe, aucun CDN, aucune télémétrie. Les graphiques sont embarqués par Vite. Les exports XLSX/CSV sont générés côté backend. Les notifications sont internes à l'application.
- Aucune nouvelle IA. Ollama, les embeddings et l'OCR restent tels quels et ne servent qu'au chatbot et à l'ingestion.
- Le classement automatique est déterministe et s'appuie sur des règles configurables.
- Le tableau de bord repose sur du SQL pur.
- Le modèle de sécurité existant est conservé et étendu, pas contourné : rôle de dossier recalculé à chaque requête, 404 si hors accès, 403 si rôle insuffisant, 409 si dossier archivé.
- Pas de nouvelle dépendance backend (SQLAlchemy, openpyxl et le worker existant suffisent).
- Côté frontend, une seule dépendance : une librairie de graphiques (Recharts).
- Les migrations suivent la convention de `database/05_*` : une transaction, répétable, avec un script de retour arrière et un script de vérification.

---

## 1. Ce qui existe et qu'on réutilise

| Existant | Réutilisé pour |
|---|---|
| `dossier`, `dossier_membre`, `dossier_service` + `roles_par_dossier()` | Socle du partage et filtre de sécurité obligatoire de toutes les statistiques |
| `document` / `document_version` | Mesures du tableau de bord |
| `journal_audit` | Historique de partage, activité |
| `chunk.contenu` + `contenu_tsv` | Règles de classement par mots-clés sans relire les fichiers |
| `ingestion_worker` et `pipeline.run_ingestion` | Point d'accroche du classement automatique |
| `apercu.preview_response` / `download_response` | Partage par lien |
| `message.sources` | Statistique « documents les plus cités par le chatbot » |
| `openpyxl` | Export XLSX |
| Limiteur d'échecs de connexion | Modèle pour limiter les accès aux liens de partage |

---

## 2. Vue d'ensemble des modifications

### Base de données

| Fichier | Niveau | Contenu |
|---|---|---|
| `database/06_classement_stats.sql` | [AJOUT] | Catégories, types, tags, règles, colonnes sur `document`, vue de statistiques, journal d'accès |
| `database/07_partage.sql` | [AJOUT] | Partage au niveau fichier, liens, demandes d'accès, expiration des accès de dossier |
| `database/08_collaboration.sql` | [AJOUT] | Commentaires, notifications, favoris, corbeille |
| `database/0x_retour_arriere.sql` et `0x_verification.sql` | [AJOUT] | Un couple par script, comme pour 05 |
| `database/04_seed_roles_permissions.sql` (via 06) | [MINEURE] | Nouvelles permissions : `classement.gerer`, `statistiques.globales` |

### Backend

| Fichier | Niveau | Pourquoi |
|---|---|---|
| `core/permissions.py` | [CONSIDÉRABLE] | Nouvelles actions, matrice étendue, expiration des accès, rôle effectif sur un fichier (partage individuel) |
| `services/documents/crud.py` + `api/routes/documents.py` | [CONSIDÉRABLE] | Filtres, tri, pagination côté serveur, classement manuel, suppression douce, accès par partage individuel |
| `services/retrieval/similarity_search.py` | [CONSIDÉRABLE] | Exclure la corbeille, filtrer par catégorie/tags, garder la règle « liste vide = aucun résultat » |
| `api/routes/dossiers.py` + `services/dossiers/crud.py` | [CONSIDÉRABLE] | Gestion des accès de gestionnaires, pas seulement admin |
| `db/vecteur.py` | [MOYENNE] | Colonnes catégorie, type, confidentialité, source du classement, corbeille |
| `db/metier.py` | [MOYENNE] | Modèles `Categorie`, `TypeDocument`, `Tag`, `RegleClassement`, partages, commentaires... |
| `services/ingestion/pipeline.py` | [MOYENNE] | Appel du moteur de règles après le parsing |
| `services/chat/history.py`, `memoire.py` | [MOYENNE] | Masquage des sources par accès au fichier et plus seulement au dossier |
| `schemas/document.py`, `schemas/dossier.py` | [MOYENNE] | Nouveaux champs et filtres |
| `services/dossiers/crud.py::_nb_fichiers`, `list_dossiers` | [MINEURE] | Ne pas compter la corbeille |
| `main.py` | [MINEURE] | Ajouter les nouveaux routers |
| `config.py`, `.env.example` | [MINEURE] | Nouvelles variables |
| `cli.py` | [MINEURE] | Commandes `reclasser` et `purger-corbeille` |
| `services/classement/`, `services/stats/`, `services/partage/`, `services/commentaires/`, `services/notifications/`, `services/recherche/` | [AJOUT] | Logique métier des nouvelles fonctions |
| `api/routes/classement.py`, `stats.py`, `partage.py`, `commentaires.py`, `notifications.py`, `recherche.py`, `annuaire.py` | [AJOUT] | Routes HTTP |
| `tests/test_classement.py`, `test_stats.py`, `test_partage.py` | [AJOUT] | Tests de sécurité et de non-régression |

### Frontend

| Fichier | Niveau | Pourquoi |
|---|---|---|
| `features/documents/DashboardDocuments.tsx` | [CONSIDÉRABLE] | Explorateur de fichiers et sélection multiple |
| `App.tsx` | [MOYENNE] | Nouvelles pages, drill-down, lecture du lien de partage, cloche de notifications |
| `AddDocumentForm.tsx`, `UpdateDocumentForm.tsx`, `NewVersionForm.tsx` | [MOYENNE] | Section « Classement » |
| `features/admin/AdminPage.tsx` | [MOYENNE] | Onglet « Classement » |
| `features/dossiers/AccesDossierModal.tsx`, `DossiersPanel.tsx` | [MOYENNE] | Gestionnaires et partage |
| `features/chat/Chatbot.tsx` | [MINEURE] | Filtre par catégorie |
| `types/*.ts`, `api/*.ts` | [MOYENNE] | Nouveaux types et appels |
| `index.css` | [MINEURE] | Palette des graphiques |
| `features/stats/*`, `features/classement/*`, `features/partage/*`, `features/commentaires/*`, `features/recherche/*`, `components/charts/*` | [AJOUT] | Nouveaux écrans et composants |

> Attention au nommage : `DashboardDocuments.tsx` est en réalité l’explorateur de dossiers et de fichiers, pas un tableau de bord. Pour éviter la confusion, le nouvel écran analytique s’appellera `features/stats/TableauDeBord.tsx`, et l’ancien peut être renommé `ExplorateurFichiers.tsx` (à noter dans `docs/renommages.md`).

---

## 3. Fonction A : classement des documents

### 3.1 Modèle

Deux axes indépendants (catégorie et type de document) plus des étiquettes libres : tags.

- Catégorie : thème (RH, Finance, Juridique...) avec hiérarchie sur 2 à 3 niveaux.
- Type de document : nature (courrier, facture, note de service, décret, rapport, tableau...).
- Tags : étiquettes libres, plusieurs par fichier.
- Confidentialité : `PUBLIC`, `INTERNE` (défaut), `CONFIDENTIEL`.

```sql
CREATE TABLE categorie (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  parent_id BIGINT REFERENCES categorie(id),
  nom VARCHAR(120) NOT NULL, couleur VARCHAR(9), ordre INT NOT NULL DEFAULT 0,
  actif BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE type_document (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  nom VARCHAR(120) UNIQUE NOT NULL,
  actif BOOLEAN DEFAULT TRUE
);

CREATE TABLE tag (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  nom VARCHAR(60) NOT NULL
);

CREATE UNIQUE INDEX uq_tag_nom ON tag (lower(nom));

CREATE TABLE document_tag (
  document_id BIGINT REFERENCES document(id) ON DELETE CASCADE,
  tag_id BIGINT REFERENCES tag(id) ON DELETE CASCADE,
  source VARCHAR(10) NOT NULL DEFAULT 'manuel' CHECK (source IN ('manuel','regle')),
  PRIMARY KEY (document_id, tag_id)
);

ALTER TABLE document
  ADD COLUMN categorie_id BIGINT REFERENCES categorie(id),
  ADD COLUMN type_document_id BIGINT REFERENCES type_document(id),
  ADD COLUMN confidentialite VARCHAR(15) NOT NULL DEFAULT 'INTERNE'
      CHECK (confidentialite IN ('PUBLIC','INTERNE','CONFIDENTIEL')),
  ADD COLUMN classement_source VARCHAR(10) NOT NULL DEFAULT 'aucun'
      CHECK (classement_source IN ('aucun','regle','manuel')),
  ADD COLUMN regle_id BIGINT,
  ADD COLUMN cree_par_service_id BIGINT REFERENCES _service(id),
  ADD COLUMN corbeille_le TIMESTAMPTZ;
```

Les documents existants restent `aucun` / `NULL` / `Non classé`.
`cree_par_service_id` est rempli par la migration à partir de l’agent du créateur pour stabiliser les statistiques par service.

### 3.2 Règles de classement automatique (sans IA)

Table `regle_classement` : `nom`, `priorite`, `actif`, `critere` (JSONB), et le résultat (`categorie_id`, `type_document_id`, tags, confidentialité éventuelle).

```json
{ "tous": [
    { "champ": "extension",  "op": "dans",            "valeur": ["pdf", "docx"] },
    { "champ": "texte",      "op": "contient_un_de",  "valeur": ["décret", "arrêté"] },
    { "champ": "nom_fichier","op": "regex",           "valeur": "^FAC-\\d{4}" },
    { "champ": "dossier_id", "op": "=",               "valeur": 3 }
] }
```

Champs possibles : `extension`, `nom_fichier`, `texte`, `dossier_id`, `service_createur_id`, `taille_octets`, `nb_pages`, `ocr_utilise`.

Le moteur `services/classement/moteur.py` expose une fonction pure : `evaluer(regles, contexte) -> Resultat`.

- Les règles sont évaluées par priorité croissante.
- Pour chaque axe (catégorie, type), la première règle qui répond gagne.
- Les tags s’accumulent.
- Suite à un changement manuel, `classement_source = 'manuel'` empêche l’écrasement par le moteur.
- Les tags générés automatiquement sont marqués `source = 'regle'` pour être supprimés et recalculés sans toucher aux tags manuels.

### 3.3 Accroche dans le flux d’ingestion

- Au dépôt (`create_document` / `add_version`) : classement par nom de fichier, extension, dossier.
- Après le parsing (`pipeline.run_ingestion`) :

```python
texte = "\n".join(d.page_content for d in parsed.documents)[:20_000]
classement.appliquer(db, doc, version, texte)  # no-op si classement_source == 'manuel'
```

Le texte analysé est plafonné à 20 000 caractères pour garder un coût constant.

- Reclassement en masse : tâche en arrière-plan, one-thread, avec lecture de `chunk.contenu` de la version courante.
- Commande CLI associée : `python -m app.cli reclasser`
- Simulation `POST /classement/simuler` : renvoie le nombre de correspondances et un échantillon sans écrire.

### 3.4 Droits

| Action | Qui |
|---|---|
| Créer, renommer, désactiver catégories, types, règles ; créer des tags | ADMIN (`classement.gerer`) |
| Classer à la main un fichier | CONTRIBUTEUR et plus du dossier |
| Changer la confidentialité | GESTIONNAIRE et plus |
| Voir les catégories, types, tags | Utilisateur connecté |

Une catégorie utilisée n’est jamais supprimée : elle est simplement désactivée.

### 3.5 API

```http
GET    /classement/categories | /types | /tags
POST/PATCH  /classement/categories | /types | /tags | /regles      (classement.gerer)
POST   /classement/simuler                                          (classement.gerer)
POST   /classement/reclasser                                        (classement.gerer, tâche de fond)
PATCH  /documents/{id}                  (ajout : categorie_id, type_document_id, tags, confidentialite)
POST   /documents/classer-lot           (ids[], categorie_id, type_document_id, ajouter_tags[]...)
```

Le classement par lot doit vérifier le droit pour chaque fichier, puis renvoyer un bilan par fichier (`ok / 403 / 404`).

---

## 4. Fonction B : recherche et filtres (prérequis du tableau de bord)

`GET /documents` doit accepter :

- `dossier_id`
- `q` (titre, nom de fichier)
- `categorie_id` (avec descendants)
- `type_id`
- `tag_id[]`
- `confidentialite`
- `statut`
- `extension`
- `du`, `au`
- `auteur_id`
- `tri`, `page`, `taille`
- `partages=true`

La réponse devient : `{ items, total, page, taille }`.

Recherche plein texte (sans LLM) : `GET /recherche?q=...` via `similarity_search.py`, avec filtrage par dossiers accessibles et `ts_headline` pour les extraits.

---

## 5. Fonction C : tableau de bord et graphiques croisés / groupés

### 5.1 Principe : vue SQL + registre de dimensions

Vue `vue_document_stats` : une ligne par fichier, avec ses caractéristiques de la version la plus récente.

```sql
CREATE OR REPLACE VIEW vue_document_stats AS
SELECT d.id AS document_id, d.dossier_id, d.categorie_id, d.type_document_id,
       d.confidentialite, d.corbeille_le, d.cree_le, d.cree_par,
       d.cree_par_service_id AS service_id, s.direction_id,
       v.numero AS version_courante, v.statut, v.taille_octets, v.nb_pages, v.ocr_utilise,
       lower(substring(v.nom_fichier from '\.([^.]+)$')) AS extension,
       (SELECT count(*) FROM document_version x WHERE x.document_id = d.id) AS nb_versions
FROM document d
JOIN LATERAL (SELECT * FROM document_version
              WHERE document_id = d.id ORDER BY numero DESC LIMIT 1) v ON TRUE
LEFT JOIN _service s ON s.id = d.cree_par_service_id;
```

Le registre de dimensions et mesures est décrit dans `services/stats/registre.py`.

#### Dimensions

- `dossier` → `dossier_id`
- `categorie` → `categorie_id`
- `type_document` → `type_document_id`
- `extension` → `extension`
- `statut` → `statut`
- `confidentialite` → `confidentialite`
- `mois`, `annee` → `date_trunc(... AT TIME ZONE :tz)`
- `ocr` → `ocr_utilise`
- `tag` → via `document_tag` (multi-valeur ; un fichier à 2 tags compte 2 fois)
- `service`, `direction`, `auteur` → réservées à `statistiques.globales`

#### Mesures

- `nb_documents` → `count(*)`
- `nb_versions` → `sum(nb_versions)`
- `taille` → `sum(taille_octets)`
- `nb_pages` → `sum(nb_pages)`
- `nb_passages` → `count` sur `chunk`
- `nb_acces` → `count` sur `acces_document`
- `nb_citations_chat` → via `jsonb_array_elements(message.sources)`

### 5.2 Règle de sécurité

Toute requête de statistiques est exécutée avec :

```python
dossiers = ids_dossiers_accessibles(db, principal)
if client_dossier_ids:
    dossiers = [i for i in dossiers if i in client_dossier_ids]
if not dossiers:
    return resultat_vide()
```

- Un utilisateur ne voit que ses dossiers.
- L’ADMIN voit tout.
- Les dimensions `service`, `direction`, `auteur` sont réservées aux admins.
- Les statistiques excluent la corbeille (`corbeille_le IS NULL`).
- Aucun cache partagé entre utilisateurs.

### 5.3 Graphiques groupés et croisés

- Groupé : une dimension en abscisse + une dimension en séries.
- Croisé : deux dimensions → matrice lignes × colonnes avec totaux en une seule requête grâce à `GROUPING SETS`.

```sql
WITH base AS (
  SELECT COALESCE(c.nom, 'Non classé') AS ligne, v.extension AS colonne, v.taille_octets
  FROM vue_document_stats v
  LEFT JOIN categorie c ON c.id = v.categorie_id
  WHERE v.dossier_id = ANY(:dossiers) AND v.corbeille_le IS NULL
)
SELECT ligne, colonne, count(*) AS nb, sum(taille_octets) AS taille,
       GROUPING(ligne) AS total_colonne,
       GROUPING(colonne) AS total_ligne
FROM base
GROUP BY GROUPING SETS ((ligne, colonne), (ligne), (colonne), ());
```

### 5.4 Endpoints

```http
GET /stats/dimensions
GET /stats/synthese
GET /stats/agreger         -> ?mesure&x&serie&filtres
GET /stats/croise          -> ?mesure&lignes&colonnes&filtres
GET /stats/serie           -> ?mesure&pas=mois|semaine|jour&serie
GET /stats/activite        -> documents les plus consultés, plus cités, dépôts par jour
GET /stats/export          -> format=xlsx|csv
```

Filtres communs : `dossier_ids`, `categorie_ids`, `type_ids`, `tag_ids`, `extensions`, `statuts`, `confidentialites`, `du`, `au`.

### 5.5 Journal d’accès

Les aperçus et téléchargements ne sont pas journalisés dans `journal_audit`; on ajoute `acces_document` avec les colonnes `document_id`, `version_numero`, `user_id`, `type`, `cree_le`.

### 5.6 Contenu de l’écran

- Bandeau de KPI : nombre de fichiers, volume, ajoutés sur la période, non classés, en erreur d’indexation, partagés.
- Graphiques : barres groupées/empilées, courbe temporelle, anneau, carte de chaleur catégorie × type, tableau croisé.
- Filtres globaux en haut : période, dossier, catégorie, type, statut.
- Sélecteurs « Abscisse / Séries / Mesure / Forme ».
- Drill-down : clic sur une barre ou une cellule → explorateur de fichiers pré-filtré.
- Bouton Exporter (XLSX/CSV).

### 5.6 bis Choix technique côté interface

- Recharts v3 pour les barres, courbes, anneaux.
- Carte de chaleur et tableau croisé écrits à la main (CSS).
- `App.tsx` reste simple (`useState`), pas d’App Router.

---

## 6. Fonction D : partage de documents

### 6.1 Étape 1 : déléguer la gestion des accès aux gestionnaires

- `api/routes/dossiers.py` et `services/dossiers/crud.py` : les routes `acces`, `membres`, `services` passent de `ADMIN` à `exiger_acces(..., PARTAGER)`.
- La création, le renommage, l’archivage et la suppression du dossier restent réservés à l’admin.
- Garde-fous : un gestionnaire ne peut pas donner un rôle supérieur au sien, il ne peut pas retirer le dernier gestionnaire, tout est audité dans `journal_audit`.
- Expiration des accès : `expire_le` sur `dossier_membre` et `dossier_service`, avec les conditions de `roles_par_dossier()`.

### 6.2 Étape 2 : partage d’un seul fichier

```sql
CREATE TABLE document_partage (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  document_id BIGINT NOT NULL REFERENCES document(id) ON DELETE CASCADE,
  user_id BIGINT REFERENCES _user(id) ON DELETE CASCADE,
  service_id BIGINT REFERENCES _service(id),
  role VARCHAR(15) NOT NULL CHECK (role IN ('LECTEUR','CONTRIBUTEUR')),
  expire_le TIMESTAMPTZ, cree_par BIGINT REFERENCES _user(id) ON DELETE SET NULL,
  cree_le TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CHECK ((user_id IS NULL) <> (service_id IS NULL))
);
```

- `core/permissions.py` : `role_effectif_document(db, principal, doc)` ; le plus haut entre rôle du dossier et rôle de partage individuel.
- `services/documents/crud.py::get_document` : essaie le partage individuel avant 404.
- `list_documents` : `WHERE dossier_id IN (...) OR id IN (partages)`.
- Vue virtuelle `GET /documents?partages=true`.
- Chatbot : v1 non interrogeable sur les fichiers partagés individuellement.

### 6.3 Étape 3 : liens de partage

```sql
CREATE TABLE lien_partage (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  token_hash CHAR(64) UNIQUE NOT NULL,
  dossier_id BIGINT REFERENCES dossier(id) ON DELETE CASCADE,
  document_id BIGINT REFERENCES document(id) ON DELETE CASCADE,
  version_numero INT,
  mode VARCHAR(10) NOT NULL DEFAULT 'interne' CHECK (mode IN ('interne','anonyme')),
  expire_le TIMESTAMPTZ NOT NULL,
  max_usages INT, usages INT NOT NULL DEFAULT 0,
  mot_de_passe_hash TEXT,
  revoque_le TIMESTAMPTZ, cree_par BIGINT REFERENCES _user(id) ON DELETE SET NULL,
  cree_le TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CHECK ((dossier_id IS NULL) <> (document_id IS NULL))
);
```

Modes :

- `interne` : pointeur vers un fichier, personne doit être connectée et avoir accès.
- `anonyme` : lecture seule, désactivé par défaut, réservé aux non-confidentiels, durée maximale configurable, limiter les tentatives, toujours journaliser dans `acces_document` et `journal_audit`.

Jeton = `secrets.token_urlsafe(32)`, hashé puis stocké ; le token ne doit jamais réapparaître en clair.
URL : `PUBLIC_BASE_URL` + `?partage=<jeton>`.

### 6.4 Demandes d’accès

`demande_acces` : dossier ou document, user, message, rôle demandé, statut, traités par un gestionnaire.

### 6.5 Niveau de confidentialité face au partage

- `CONFIDENTIEL` : aucun lien anonyme possible.
- Un badge visible sur le fichier et dans la fenêtre de partage.

---

## 7. Fonction E : collaboration (Workspace amélioré)

| Fonction | Tables | Remarques |
|---|---|---|
| Commentaires | `commentaire` | Droit `COMMENTER`; édition/suppression par l’auteur ou gestionnaire |
| Mentions `@utilisateur` | `notification` | On notifie uniquement les personnes ayant accès |
| Notifications internes | `notification` | Cloche + polling toutes les 30–60 s |
| Favoris | `favori` | Vue « Favoris » |
| Activité récente | `journal_audit` + `acces_document` | Filtrée par dossiers accessibles |
| Corbeille | `document.corbeille_le`, `corbeille_par` | Voir §7.1 |
| Verrouillage d’édition | `document.verrou_par`, `verrou_expire_le` | Optionnel |

### 7.1 Corbeille (suppression douce)

- « Supprimer » → `corbeille_le = now()`.
- « Restaurer » → `corbeille_le = NULL`.
- « Supprimer définitivement » uniquement depuis la corbeille, avec purge automatique après `CORBEILLE_RETENTION_JOURS`.
- Exclusions : `similarity_search._base`, `dossiers/crud._nb_fichiers`, `list_documents`, `vue_document_stats`, contrôle de doublon.

---

## 8. Ce qui ne change pas

- Pipeline OCR/parsing, découpage en chunks, embeddings et normalisation.
- Index HNSW `vector_ip_ops`, top-k dynamique.
- Streaming SSE du chat.
- Authentification (scrypt, jetons HMAC).
- Règle « un fichier = des versions numérotées, la courante est la plus récente `ready` ».
- Le classement n’a aucune influence sur les chunks et n’exige pas de réindexation.

---

## 9. Impacts sur le chatbot (RAG)

- Corbeille : exclusion dans `similarity_search._base`.
- Filtre par catégorie/tags : paramètres `categorie_ids` et `tag_ids` dans `search_chunks`.
- Sources : ajouter catégorie et type dans les sources renvoyées.
- Fichiers partagés individuellement : recommandation v1 = non interrogeables.
- Expiration d’accès : rien de spécial côté chat; `ids_dossiers_interrogeables()` passe par `roles_par_dossier()` recalculé à chaque requête.

---

## 10. Sécurité et tests

À écrire avant les phases 3 et 5.

- `tests/test_classement.py` : priorité des règles, tags accumulés, `manuel` jamais écrasé, regex invalide / trop longue refusée.
- `tests/test_stats.py` : sécurité, intersection des dossiers, dimensions protégées, corbeille exclue.
- `tests/test_partage.py` : accès expiré, partage individuel, dernier gestionnaire, lien révoqué/expiré, jeton non visible, chat sans corbeille ni fichiers partagés individuellement.

Non-régression : la matrice de droits existante doit rester verte.

---

## 11. Nouveaux paramètres (`config.py` / `.env.example`)

```env
TIMEZONE=Indian/Antananarivo
PUBLIC_BASE_URL=http://localhost:5173
PARTAGE_ANONYME_ACTIF=false
PARTAGE_DUREE_MAX_JOURS=30
CORBEILLE_RETENTION_JOURS=30
CLASSEMENT_TEXTE_MAX_CARS=20000
STATS_PERIODE_DEFAUT_JOURS=365
```

---

## 12. Ordre de réalisation

| Phase | Contenu | Taille | Dépend de |
|---|---|---|---|
| 0 | Filtres, tri, pagination de `GET /documents`; recherche plein texte; renommage `ExplorateurFichiers`; tests de non-régression | M | — |
| 1 | Classement (script 06, moteur, tests, hook dans le pipeline, onglet admin et modifs de formulaires) | L | 0 |
| 2 | Tableau de bord (vue SQL, accès, registre de dimensions, `/stats/*`, composants, export) | L | 1 |
| 3a | Partage : délégation aux gestionnaires | M | 0 |
| 3b | Partage : fichier | L | 3a |
| 3c | Partage : liens et demandes d’accès | M | 3b |
| 4 | Collaboration (commentaires, notifications, favoris, activité) | M | 3a |
| 5 | Corbeille (suppression douce, restauration, purge) | M | 0 |
| Option | Sous-dossiers | XL | — |

### Sous-dossiers

À éviter en v1 : un dossier peut rester plat. Ajouter `parent_id` obligerait de gérer héritage des rôles, récursion dans `roles_par_dossier`, déplacement et droits, ce qui sort du périmètre de la première version.

---

## 13. Décisions à trancher

| Question | Recommandation |
|---|---|
| Fichiers partagés individuellement interrogeables par chatbot ? | Non en v1 |
| Contributeurs peuvent-ils créer des tags ? | Oui, avec normalisation |
| Liens anonymes ? | Désactivés par défaut |
| Confidentialité restreint-elle aussi les droits ? | Étiquette + garde-fou sur les liens en v1 |
| « Documents » dans les stats = fichiers logiques ou versions ? | Fichiers logiques avec dernières versions ; nombre de versions comme mesure |
| Stats par service : service du créateur à l’instant T ou actuel ? | Instantané (`cree_par_service_id`) |

---

## 14. Remarques d’implémentation opérationnelle

1. Les scripts SQL doivent suivre la convention de migration déjà adoptée dans le dépôt : transaction unique, script de retour arrière, script de vérification, exécution dans l’ordre numérique.
2. Les changements de permissions et de sécurité doivent être validés avec des tests de non-régression sur les droits existants.
3. Le moteur de classement doit rester purement déterministe et sans IA ; les règles doivent être simples, testables et auditables.
4. Le tableau de bord doit être calculé à partir des données métier accessibles et non de données de cache utilisateur global.
5. Les fichiers partagés par lien doivent rester entièrement alignés sur le modèle de sécurité actuel : aucun mode “anonyme” sans garde-fou.
6. Le nom `DashboardDocuments.tsx` est trompeur et doit être renommé pour éviter toute confusion entre explorateur et tableau de bord analytique.

---

## 15. Résumé exécutif

La GED à livrer en v1 est une évolution du système existant, pas une refonte complète : elle ajoute un classement métier, des statistiques SQL de niveau entreprise, un partage par fichier et par lien, et une collaboration légère autour des documents, tout en gardant la logique de sécurité actuelle. Le point clé est de rester compatible avec le modèle « dossiers + rôles calculés à chaque requête », afin de ne pas introduire de fuite de données ni de dépendance externe.
