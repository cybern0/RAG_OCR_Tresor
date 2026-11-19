# Refonte « /fichiers remplace /dossiers » — fichiers à plat, droits étendus du chef de service, erreurs d'indexation

**11/2026** — troisième refonte, après `docs/refonte_classes.md` (comptes applicatifs, stockage à plat,
super administrateur administrateur seul) et `docs/retour_chef_service.md` (rétablissement du chef de service).
Cette refonte suit quatre demandes :

1. **Supprimer `/dossiers` et remplacer par `/fichiers`** : plus d'arborescence, les fichiers sont ajoutés
   directement, avec un filtre par rôle — les fichiers déposés par les admins portent plusieurs rôles et un
   agent peut avoir plusieurs rôles.
2. **Admin division** : pareil — tous ses fichiers à plat avec filtres de classes ; dans `/roles`, retirer
   l'onglet descriptif « Classement par rôle ».
3. **Admin service** : comme l'admin division mais sur plusieurs divisions (filtres rôle **et** division),
   plus l'affectation des agents dans son service via `/admin/utilisateurs` et `/admin/agents`, le changement
   de leurs mots de passe et `/roles` — notamment **créer l'administrateur (chef) de chaque division et son
   mot de passe** si le super administrateur ne l'a pas fait (les agents s'adressent à l'un ou l'autre,
   en face à face).
4. **Super administrateur** : plus d'Accueil — `/admin` devient sa première page ; refonte du tableau de bord
   pour tracer les **erreurs d'indexation** (par service, division et rôle), le tout adapté à l'architecture
   actuelle ; l'Accueil des admins service/division (et de l'agent, très restreint) reprend cette traçabilité
   dans leur périmètre.

## Ce qui disparaît

- La table `dossier`, sa route (`/dossiers`), son service, son schéma Pydantic et les pages frontend
  `DossiersPage` / `DossierPage` ; plus aucun dépôt ne choisit un dossier.
- La configuration `DOSSIERS_DEFAUT` (le « modèle de dossiers » posé à la création des divisions).
- La colonne `document.dossier_id`, la clé composite `document → dossier` et `par_dossier` des statistiques ;
  la contrainte `uq_document_id_division` reste (elle sert de cible à la clé composite de `document_role`).
- Les actions `dossier_voir`, `dossier_creer`, `dossier_gerer` de `core/acces.py` et l'archivage de dossiers.
- Les dossiers dans les sources du chat (`dossier_id` dans les événements et l'historique des messages).

## Ce qui change

### Backend

- **Dépôt direct** : `POST /documents` prend `division_id` (plus de `dossier_id`) ; accès par
  `exiger_depot_division` (membre ou chef de la division, 404 hors périmètre, 409 division désactivée) ;
  dédoublonnage par hash **dans la division**.
- **Liste à plat** : `GET /documents` sans `dossier_id`, avec deux nouveaux filtres — `role_id`
  (fichiers portant ce rôle de classement) et `division_id` ; toujours bornée par
  `condition_acces_fichiers` (la même condition SQL que le chat : personne ne voit au-delà de ses droits).
- **`GET /documents/filtres`** : options des filtres selon le compte — ses rôles (agent) ou les rôles
  actifs de ses divisions (chefs), ses divisions, et `depot_divisions` (où il peut déposer).
- **Chef de service** (niveau SERVICE) :
  - `structure.gerer` ajouté à ses permissions, appliqué **à son service seulement** :
    listes (services, divisions, agents, postes) scopées, création/déplacement d'agents de son service,
    nomination des chefs de division de ses divisions ; directions, services, divisions et postes de
    chef de service restent réservés au super administrateur (`_super_admin` dans la route).
  - `core/portee.py::gere_agent` : il gère les comptes de son service **y compris les comptes des chefs
    de division** (création, mot de passe, rôles) — pas l'autre chef de service ; le chef de division
    gère les agents sans titre de sa division, inchangé.
- **Tableau de bord** (`/tableau-de-bord`, section `erreurs_indexation`) : total + regroupements
  **par service, par division et par rôle** + les cas à corriger (fichier, version, message du worker,
  classes). ROOT voit tout, SERVICE ses divisions, DIVISION sa division ; **AGENT : très restreint** —
  seulement ses propres fichiers en échec (titre + message, sans regroupement ni accès aux autres).
  Chaque niveau reçoit un indicateur « Erreurs d'indexation » qui pointe vers le filtre `statut=error`
  de `/fichiers`.

### Frontend

- **Page `/fichiers`** (nouvelle `features/fichiers/FichiersPage.tsx`) : liste à plat — recherche, filtre
  rôle (groupé par division pour un chef de service), filtre division (si plusieurs), statut, tri,
  pagination, onglets Fichiers / Corbeille / À classer, sélection multiple,
  dépôt direct (choix de la division si plusieurs). Les anciens liens `/dossiers/...` redirigent.
  (Les filtres catégorie / type / confidentialité présents à l'origine ont été retirés ensuite : ces champs
  restent des métadonnées de classement — badges, statistiques, règles automatiques.)
- `/admin` (StatsPage refondue) : indicateurs, alertes du tableau de bord, section **Erreurs
  d'indexation** (regroupements + tableau des cas), répartition par service (divisions, agents, fichiers),
  statut d'indexation, état du système ; les statistiques « par dossier » disparaissent.
- **Accueil** : le super administrateur est redirigé vers `/admin` (il n'a plus d'Accueil ni de nav
  correspondante) ; SERVICE, DIVISION et AGENT voient la section erreurs dans leur périmètre
  (pour l'agent : « Mes fichiers en échec »).
- `/roles` : un seul onglet — le dictionnaire de rôles ; la carte descriptive « Classement par rôle »
  est retirée ; `admin/classement` redirige vers `/roles`.
- Libellés : « accès par rôles » (plus « par dossiers ») ; le choix du rôle global ADMIN et du changement
  de rôle n'est proposé qu'au super administrateur.

## Base de données

- `database/01_schema.sql` : table `dossier` supprimée, `document.dossier_id` supprimé, vue
  `vue_document_stats` sans `dossier_id`, invariant « rôle de fichier hors de la division du fichier »
  remplace l'ancien contrôle dossier/document.
- **Base existante** : plus de script de migration (supprimé) ; la base se recrée vierge avec `01`, `02`, `03` (voir `docs/ordre_execution_sql.md`).

## Pourquoi (rappels)

- La division est la frontière hiérarchique réelle ; le dossier n'apportait qu'un niveau factice déjà
  uniforme (modèle imposé), jamais un droit : les rôles de classement décident déjà tout.
- Le filtre par rôle répond au cas d'usage annoncé : un agent multi-rôles cherche « tout ce qui est
  classé Paie » sans parcourir quoi que ce soit.
- Donner la gestion des chefs de division au chef de service évite les blocages quand le super
  administrateur n'est pas disponible ; le poste de chef de service et la structure globale restent
  sous le super administrateur seul.
- Les erreurs d'indexation étaient invisibles côté administration (seul le déposant voyait le statut
  sur sa fiche) ; le worker enregistre déjà `message_erreur` — le dashboard l'expose là où on agit.
