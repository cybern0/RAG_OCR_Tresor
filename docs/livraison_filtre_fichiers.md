# Livraison : filtre de fichiers simplifié (catégorie, types, confidentialité retirés)

> Demande du 19/11/2026 : « Modifier filtre de fichiers : supprimer catégorie, types, et à vérifier
> confidentialité si inutile enlever aussi. »

## La barre de filtres de la page Fichiers maintenant

**Recherche · Rôle (classe) · Division (chef de service) · Statut · Tri** — plus les onglets Fichiers /
Corbeille / À classer. Ont été retirés : **Catégorie**, **Type**, **Confidentialité**.

## Pourquoi la confidentialité aussi (vérification demandée)

Trois raisons de la juger inutile en l'état, donc de l'enlever :
1. **Elle ne distingue rien** : « INTERNE » est la valeur par défaut de tout fichier non classé
   (`crud.py` : `doc.confidentialite or "INTERNE"`) — filtrer « Interne » renvoie de fait tout le périmètre,
   et impossible de séparer « non classé » de « explicitement interne ».
2. **Ce n'est pas un critère d'accès** : la visibilité est déjà gouvernée par division + rôles côté serveur
   (condition d'accès SQL unique, la même pour la liste, la recherche et le chat). La confidentialité est
   descriptive, pas un contrôle.
3. **Les découpes utiles existent déjà** : À classer, rôle, division, statut, recherche.

Le **champ** confidentialité n'est PAS supprimé : il reste posé par le classement (ClassifyModal), affiché en
badge, regroupé dans les statistiques (« Par confidentialité ») et posable par les règles automatiques d'administration.

## Changements

- **Frontend** : `features/fichiers/FichiersPage.tsx` (les 3 menus déroulants retirés, filtres URL et
  « Effacer les filtres » alignés), `features/documents/types.ts` (`DocumentFilters` sans ces 3 champs).
  Les métadonnées de `DocumentMeta` (badges) sont inchangées.
- **Backend** : paramètres `categorie_id`, `type_id`, `confidentialite` retirés de `GET /documents`
  (`routes/documents.py`) et des fonctions `list_documents` / `apply_document_filters` (`services/documents/crud.py`).
  Aucun autre appelant (vérifié). Le filtre par tags est conservé (API), même sans UI aujourd'hui.
- **Tests** : `tests/test_document_filters.py` — le test du filtre par classement devient un test du filtre par
  tags (le filtre catégorie/type/confidentialite n'existe plus).

## Ancien frontend mort supprimé (le build était cassé)

En appliquant la demande, découverte : **`npm run build` échouait déjà sur le dépôt** — l'ancienne
architecture, dont la suppression était pourtant décidée et documentée à la refonte « classes »
(« Suppression de 50 fichiers inatteignables »), était restée en place et ne compile plus depuis
(reférences à `createDossier`, `setServiceAcces`, `dossier_id`... disparus).

Atteignabilité calculée depuis `main.tsx` (script d'imports en cascade) : **68 fichiers vivants, 55 morts**.
Les 55 ont été supprimés : `src/App.tsx` (racine), `src/api/*` (8), `src/components/ui/*` (6), `src/hooks/*` (3),
`src/lib/*` (2), `src/types/*` (4), `features/dossiers/` (9, dont l'ancienne page qui dupliquait ces mêmes
filtres), `features/admin/{AdminPage, GedDashboardPanel}`, `features/admin/{audit, classement, demandes,
dossiers}`, `features/{audit, demandes, securite, structure, users}`, et les vieux formulaires de
`features/documents/` (7) — la page Fichiers utilise les nouveaux composants `components/`.
Tout le code vivant (routeur, `shared/`, pages montées, référentiel de classement via
`features/documents/api.ts`) est conservé.

## Vérifications exécutées

- `npm run build` (tsc + vite) : **OK** (échec avant changement).
- `uv run pytest` : **93 réussis, 3 ignorés** (API sans `TEST_DATABASE_URL`), dont le test de filtres réécrit.
- `MODIFICATIONS.md` : entrée en tête ; README (`refonte /fichiers`) et `docs/refonte_fichiers.md` alignés.
