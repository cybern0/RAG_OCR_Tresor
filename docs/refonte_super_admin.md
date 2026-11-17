# Refonte : suppression du chef de service, responsabilités regroupées sur le super administrateur

> Refonte appliquée en novembre 2026. Ce document décrit le concept retenu, la liste exacte des changements
> et la marche à suivre pour les bases existantes. Voir aussi `docs/paln.md` (plan historique de la GED
> hiérarchique, dont le § « chef de service » est désormais obsolète) et `docs/architecture.md`.

## 1. Pourquoi cette refonte

Le modèle hiérarchique comptait **trois échelons d'administration** empilés sur la structure
Direction → Service → Division :

| Échelon | Porteur | Périmètre |
|---|---|---|
| ROOT | rôle global ADMIN (« super administrateur ») | toute l'organisation |
| SERVICE | titre d'agent `CHEF_SERVICE` (sans division) | son service |
| DIVISION | titre d'agent `CHEF_DIVISION` (avec division) | sa division |

Le chef de service était un **administrateur intermédiaire** : gestion des comptes de son service,
intérim des divisions vacantes, supervision en lecture (après déverrouillage) et mots de passe de
dossier des divisions de son service. Or :

- ses pouvoirs **dupliquaient** ceux du super administrateur sur un périmètre plus petit ;
- la chaîne d'intérim (division sans chef → chef de service → super administrateur) alourdissait
  chaque règle d'accès et chaque notification ;
- il créait un **point de blocage** : une division de son service ne pouvait pas être gérée par le
  super administrateur tant qu'elle avait un chef, et le secret d'un chef de service exigeait une
  « réinitialisation hiérarchique » dédiée ;
- il fallait deux concepts pour deux pouvoirs (titre d'agent pour la division, rôle global pour la racine).

## 2. Le concept retenu

**Un seul échelon d'administration au-dessus de la division : le super administrateur.**
La hiérarchie de gestion devient :

```
ROOT       (rôle global ADMIN : le super administrateur)
  └─ DIVISION   (titre d'agent CHEF_DIVISION : le chef de division)
       └─ AGENT   (sans titre)
```

- Le **service** redevient un simple conteneur organisationnel (regroupement de divisions) :
  il n'a plus de chef, plus de tableau de bord propre, plus de périmètre de gestion.
- Le **super administrateur reprend toutes les responsabilités** de l'ancien chef de service :
  1. **Comptes** : il crée, modifie, désactive et réinitialise les comptes de toute
     l'organisation — y compris les chefs de division (ils ne se gèrent que par lui).
  2. **Intérim** : toute division dont le poste de chef est vacant passe sous sa gestion directe
     (avec déverrouillage), notification « poste vacant » comprise.
  3. **Supervision** : il est le seul « administrateur supérieur » : lecture seule de toute unité
     après saisie du mot de passe de dossier (423), agrégats du tableau de bord par service.
  4. **Mots de passe de dossier** : un secret par couple (unité, super administrateur), sur les
     divisions **et** les services. Le mot de passe de dossier devient **strictement personnel** :
     la réinitialisation hiérarchique disparaît (aucun échelon supérieur au super administrateur).
  5. **Notifications** : vacance d'un poste de chef, demandes d'accès et fichiers à classer d'une
     division sans chef lui sont notifiés directement.
- Le **chef de division** conserve exactement ses pouvoirs d'origine : gérant de sa division
  (rôles, classement, demandes, dossiers), création des comptes des agents de sa division,
  lecture des fichiers de sa division. Une seule nouveauté : il ne peut plus créer les comptes
  des divisions vacantes de son service (c'était un pouvoir d'intérim du chef de service).

**Ce qui ne change pas** : les rôles de division (`role_division`), le classement, les demandes
d'accès et exceptions ponctuelles, les dossiers et sous-dossiers, l'historique chaîné, l'OCR/RAG.

## 3. Changements par fichier

### Base de données (`database/`)
| Script | Changement |
|---|---|
| `01_schema.sql` | `agent.titre` limité à `CHEF_DIVISION` (contrainte + `ck_agent_titre_division`) ; index `uq_chef_service` supprimé ; commentaires mis à jour |
| `02_donnees_reference.sql` | commentaire : le niveau SERVICE n'existe plus |
| `03_verification.sql` | contrôles `chef_service_unique`, `chef_service_sans_division`, `services_actifs_sans_chef` retirés ; nouveau contrôle `agent_titre_inconnu` ; `secret_de_division_sans_droit` simplifié (ADMIN seulement) |
| `seed.sql` | les deux agents `CHEF_SERVICE` de démonstration retirés |
| `10_suppression_chef_service.sql` | script de migration **retiré** : fusionné dans les scripts de base, qui naissent directement conformes (aucun `ALTER` dans `database/`) ; une base existante est recréée depuis `01` → `02` — ordre complet : `docs/ordre_execution_sql.md` |

### Backend (`Backend/app/`)
| Fichier | Changement |
|---|---|
| `core/permissions.py` | `NIVEAU_SERVICE`, `TITRE_CHEF_SERVICE` supprimés ; niveaux = ROOT > DIVISION > AGENT ; `PERMISSIONS_DU_NIVEAU` sans SERVICE |
| `core/portee.py` | périmètre de comptes : ROOT (tout) ou DIVISION (les agents sans titre de sa division) ; les chefs de division ne se gèrent que par ROOT |
| `core/acces.py` | `chef_service_actif()` supprimé ; `est_superieur()` = ROOT seulement ; `peut_gerer_division()` : chef nominal, sinon super administrateur ; `divisions_gerees()` et `divisions_deverrouillees()` sans branche SERVICE |
| `services/structure/crud.py` | `_occupant`/`_exiger_poste_libre`/`_valider_etat` simplifiés (division seule) ; `transferer_chef()` signature `division_id=` ; `postes()` sans entrée services ; `arbre()` sans chef de service et filtré à sa division pour les non-ROOT ; `_notifier_vacance()` prévient les super administrateurs |
| `services/securite.py` | `_eligible()` = rôle ADMIN seulement ; `lister_unites()` = toutes les unités (ROOT) ; `lister_delegations()` et la réinitialisation hiérarchique supprimées ; le secret exige l'ancien mot de passe et ferme les déverrouillages |
| `services/users/crud.py` | `unites_protegees` = super administrateur ; commentaires |
| `services/notifications.py` | `destinataires_gestion()` : chef de division, sinon super administrateurs |
| `services/historique.py` | périmètre ROOT / DIVISION / agent (branche SERVICE retirée) |
| `services/tableau_de_bord.py` | tableau de bord SERVICE supprimé ; alerte « division vacante » = intérim du super administrateur ; comptage « agents sans division » simplifié |
| `schemas/structure.py` | `titre: Literal["CHEF_DIVISION"]` ; `PostesOut` sans `services` ; `ServiceArbreOut` sans `chef` |
| `schemas/user.py` | `niveau: Literal["ROOT", "DIVISION", "AGENT"]` ; `unites_protegees` = super administrateur |
| `schemas/securite.py` | `DelegationOut` et `SecretIn.utilisateur_cible_id` supprimés |
| `api/routes/structure.py` | route `PUT /services/{id}/chef` supprimée ; `PUT /divisions/{id}/chef` conservée |
| `api/routes/securite.py` | route `GET /delegations` supprimée ; toutes les routes réservées au super administrateur |
| `api/routes/historique.py` | l'agent retrouve la lecture de « ce qui le concerne » (correction, voir § 5) |
| `main.py` | le routeur `demandes` est maintenant monté (correction, voir § 5) |

### Frontend (`frontend/src/`)
| Fichier | Changement |
|---|---|
| `types/structure.ts`, `features/admin/types.ts` | `titre: 'CHEF_DIVISION' | null` |
| `features/auth/types.ts`, `features/accueil/api.ts` | `niveau: 'ROOT' | 'DIVISION' | 'AGENT'` |
| `app/nav.ts` | `isIntermediateAdmin` sans SERVICE |
| `features/roles/RolesPage.tsx`, `features/dossiers/DossiersPage.tsx` | choix de division réservé au ROOT |
| `features/admin/api.ts` | `transfererChef(unitId, agentId)` : divisions seulement |
| `features/admin/structure/AgentsPage.tsx` | badge et boutons « chef de division » uniquement |
| `src/App.tsx`, `features/admin/demandes/`, `features/admin/dossiers/AdminDossiersPage.tsx` | **supprimés** : code mort référencant la fonctionnalité de partage abandonnée ; ils empêchaient `npm run build` (`tsc -b`) |

### Tests (`Backend/tests/`)
- `test_api.py` : fixture `world` sans chef de service ; `unites_protegees` vérifié sur l'admin.
- `test_hierarchie.py` : intérim du **super administrateur** sur une division vacante ; secrets de
  dossier réservés au super administrateur (403 pour chef de division et agent) ; création des
  comptes d'une division vacante par le super administrateur ; arbre et tableaux de bord sans
  niveau SERVICE ; le titre `CHEF_SERVICE` est refusé (422).

## 4. Recréation d'une base existante (migration fusionnée, sans ALTER)

Le script de migration `10_suppression_chef_service.sql` a été **fusionné dans les scripts de base** :
`01_schema.sql`, `02_donnees_reference.sql` et `03_verification.sql` naissent directement conformes
(titre limité à `CHEF_DIVISION`, secrets réservés au rôle ADMIN, contrôles `agent_titre_inconnu` et
`secret_de_division_sans_droit`), et aucun fichier de `database/` ne contient d'`ALTER`. Une installation
existante est donc recréée : `DROP DATABASE`, puis la chaîne d'installation (ordre complet et précautions
dans `docs/ordre_execution_sql.md`), puis restauration des données. Dans une base recréée, les anciens
chefs de service redeviennent agents simples **sans division** — ils perdent l'accès aux fichiers jusqu'à
ce que le super administrateur les réaffecte à une division et, s'il le veut, nomme l'un d'eux chef de
division ; leurs comptes restent recréables. Une base neuve n'a besoin de rien de plus.

## 5. Corrections de défauts préexistants (hors périmètre, incluses dans la refonte)

Trois tests échouaient déjà avant la refonte (sur la base d'origine : 92 tests passés, 3 échecs) :

1. **Le routeur `demandes` n'était pas monté** dans `main.py` : l'API des demandes d'accès répondait
   404 et la page « Demandes » ne pouvait pas fonctionner. Corrigé.
2. **`GET /historique` interdisait le niveau AGENT** alors que le service métier implémente son
   périmètre (« ce qui me concerne ») et que la documentation de la route l'annonce. Corrigé.
3. La fin du test `test_mots_de_passe_de_dossier` n'était jamais atteinte (échec plus haut dans le
   test) ; son verrouillage final omettait de verrouiller la division v1 après le test du
   déverrouillage par division. Corrigé dans le test.

Après refonte et corrections : **95 tests passés, 0 échec** (base de test vierge).

## 6. Garanties conservées après la refonte (privilèges, dossiers de division, classement)

La refonte ne retire **aucun privilège** aux rôles conservés : la matrice d'accès (AUTEUR, LECTEUR,
GERANT, SUPERIEUR), les codes 404 / 403 / 423 et les périmètres de gestion des chefs de division et
des agents sont inchangés — seuls les pouvoirs de l'ancien chef de service migrent vers le super
administrateur. Les dossiers restent **propres à chaque division** : rattachés à leur division dans
le stockage (clé étrangère composite, aucun déplacement ni suppression lors de la migration) et dans
l'interface (liste des dossiers filtrée par division, arbre de structure). Chaque division conserve
**son mot de passe de dossier individuel** : un secret par couple (division, super administrateur),
déverrouillage et verrouillage indépendants d'une division à l'autre (l'ouverture d'un service entier
restant possible pour le super administrateur, sans effacer les secrets individuels).

Deux modes de classement des fichiers restent pris en charge :

1. **Classement automatique** : un agent qui dépose un fichier sans préciser les rôles reçoit
   automatiquement tous ses rôles de division (`_roles_au_depot`, branche agent) — le fichier est
   classé selon l'organisation prévue et devient visible des détenteurs de ces rôles ;
   il peut retirer des rôles, jamais en ajouter qu'il ne détient pas.
2. **Attribution manuelle par le chef de division** : le chef choisit explicitement les rôles dans
   le dictionnaire de sa division — à l'achat du dépôt, ou après coup sur un fichier « à classer »
   (`PUT /documents/{id}/roles`, tracé et réservé au gérant) — ce qui attribue le fichier à un ou
   plusieurs agents de la division (ceux qui détiennent ces rôles) ; sans choix, le fichier est
   « à classer », l'accès étant refusé par défaut et le chef notifié.

Ces garanties sont couvertes par deux tests dédiés (`test_privileges_inchanges_et_dossiers_conerves_par_division`,
`test_deux_modes_de_classement`) ; la suite complète passe : **97 tests, 0 échec**.

## 7. Vérifications effectuées

- `uv run pytest` : **97/97** (base PostgreSQL + pgvector neuve, pgserver embarqué ; `test_partage_collaboration.py` exclu : module mort cassé à l'identique avant et après la refonte).
- `npm run build` (tsc -b + vite) : **succès**, `tsc --noEmit` : **0 erreur** (22 erreurs préexistantes éliminées avec le code mort).
- `python -c "import app.main"` : succès ; aucun résidu `CHEF_SERVICE` / `NIVEAU_SERVICE` dans le code.
- Scripts SQL appliqués sur une base neuve : `01`, `02`, `03` sans erreur, `verification_invariants` à 0 anomalie.
