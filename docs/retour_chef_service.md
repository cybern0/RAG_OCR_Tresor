# Retour du chef de service et dossiers protégés par division (17/11/2026)

Cette évolution met en œuvre trois consignes : les dossiers protégés n'existent qu'au niveau des
divisions (plus rien au niveau des services), les mots de passe de dossier sont gérés par le seul
super administrateur — chaque division gardant son mot de passe individuel — et le poste de
**chef de service** est rétabli avec exactement le même rôle que le chef de division, étendu à
toutes les divisions de son service. Ce document remplace, sur ces points, la description faite
dans `docs/refonte_super_admin.md` (le reste de cette refonte reste valable).

## 1. Hiérarchie et niveaux

La hiérarchie de gestion redevient **ROOT > SERVICE > DIVISION > AGENT**. Le niveau se déduit du
titre de l'agent, seule source de vérité : `CHEF_DIVISION` → DIVISION, `CHEF_SERVICE` → SERVICE.
Le chef de service est un agent de son service **sans division propre** (contrainte de base
`ck_agent_titre_division`, branche « CHEF_SERVICE ») et un seul chef de service actif par service
est garanti par l'index unique `uq_chef_service`. En code, un prédicat unique — « chef nominal
d'une division » (`est_chef_nominal`) — réunit le chef de division (sa division) et le chef de
service (toutes les divisions de son service) : tous les droits de gérance s'y raccordent.

Le chef de service reçoit donc, sur **chaque division de son service** : le rôle GERANT sur tous
les fichiers (contenu, versions, classement, corbeille, purges), la gestion des dossiers et
sous-dossiers, le classement manuel (rôles au dépôt et reclassement tracé), le dictionnaire de
rôles, les décisions de demandes d'accès, et la gestion des comptes des agents **sans titre** de
ces divisions. Sur une division **sans chef**, il assure l'intérim localement, **sans
déverrouillage** — le super administrateur conserve son intérim global (avec déverrouillage).

Ses limites sont symétriques : rien hors de son service (404, l'existence n'est pas révélée), pas
de gestion des chefs de division ni des super administrateurs (403), pas de mot de passe de
dossier (403) — les mots de passe appartiennent au seul super administrateur.

## 2. Dossiers protégés : divisions uniquement

La table `secret_unite` ne référence plus les services : **un secret = un couple (division, super
administrateur)**, et l'index `uq_secret_division` garantit son unicité. Le déverrouillage par
service disparaît : ouvrir une division n'ouvre jamais les autres, et chaque division se
verrouille individuellement. Toute requête `/securite/*` portant `type: "service"` reçoit une
erreur 422 explicite (« Les dossiers de service n'existent plus : chaque division a son propre
mot de passe de dossier »). L'interface (page Mots de passe de dossier) ne liste que les
divisions, et le menu n'apparaît que pour le super administrateur (`unites_protegees`).

## 3. Changements par composant

| Fichier | Changement |
|---|---|
| `database/01_schema.sql` | `titre` CHECK ('CHEF_DIVISION', 'CHEF_SERVICE') ; `ck_agent_titre_division` à trois branches ; index `uq_chef_service` ; `secret_unite` sans `service_id` |
| `database/03_verification.sql` | Contrôles `chef_service_unique` et `chef_service_avec_division` ajoutés ; `agent_titre_inconnu` élargi ; contrôle `secret_de_service` retiré |
| `database/seed.sql` | Chef de service de démonstration (DEMO-010, compte `demo_chefsrv`) |
| `Backend/app/core/permissions.py` | `NIVEAU_SERVICE`, `TITRE_CHEF_SERVICE` ; niveaux ROOT > SERVICE > DIVISION > AGENT |
| `Backend/app/core/acces.py` | `est_chef_nominal(db, principal, division_id)` étendu au chef de service ; `chef_service_actif()` ; `divisions_gerees()` inclut les divisions du service ; `divisions_deverrouillees()` simplifié (divisions seules) ; accès dossiers/fichiers : le chef de service est gérant sans déverrouillage |
| `Backend/app/core/portee.py` | Périmètre de comptes SERVICE : les agents des divisions de son service (sans titre) |
| `Backend/app/services/securite.py` | Divisions uniquement : plus de branche service, 422 explicite, `via_service` supprimé |
| `Backend/app/services/structure/crud.py` | `transferer_chef_service()` (transfert atomique) ; postes de service dans `postes()` ; `arbre()` avec `acces: "gerant"` ; vacance notifiée au chef de service |
| `Backend/app/services/tableau_de_bord.py` | Tableau de bord niveau SERVICE (répartition par division, alertes de vacance) |
| `Backend/app/services/historique.py` | Périmètre historique du chef de service : les entrées de son service |
| `Backend/app/api/routes/structure.py` | `PUT /structure/services/{service_id}/chef` |
| `Backend/app/cli.py` | `reinitialiser-secret` par division (plus de `--type`) |
| `frontend/src/features/auth/types.ts` | Niveau SERVICE + `unites_protegees` |
| `frontend/src/features/admin/*` | Titre CHEF_SERVICE, `transfererChefService`, formulaire d'agent avec champ Poste, badges et boutons Nommer/Retirer pour les deux postes |
| `frontend/src/app/nav.ts`, `AppLayout.tsx` | Chef de service = administrateur intermédiaire ; menu Mots de passe réservé au super administrateur |
| `frontend/src/features/securite/*` | Divisions seulement, plus de « via le service » |

La migration est **fusionnée dans les scripts de base** (aucun ALTER dans `database/`) : une base
existante est recréée depuis la chaîne 01 → 02 → 03 — voir `docs/ordre_execution_sql.md`.

## 4. Vérifications

- `uv run pytest` : **98/98** (base PostgreSQL + pgvector neuve depuis les scripts fusionnés) ;
  nouveau test `test_le_chef_de_service_meme_role_sur_toutes_les_divisions` (pouvoirs ET limites).
- Vue `verification_invariants` : zéro anomalie sur base vide et base seedée.
- Chaîne SQL : 01 → 02 → 03 → seed → contrôles → `delete_seed` → re-seed, tout au vert.
- Frontend : `tsc -b && vite build` sans erreur.
