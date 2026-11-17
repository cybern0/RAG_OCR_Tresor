# Ordre d'exécution des scripts SQL (`database/`)

La base naît **directement conforme** à la refonte (poste « chef de service » supprimé) : tous les
changements autrefois portés par le script de migration `10_suppression_chef_service.sql` sont
fusionnés dans les scripts de base. **Aucun fichier de `database/` ne contient d'`ALTER`** et aucun
script de migration n'est nécessaire — une base existante est simplement recréée (voir « Base
existante » plus bas). Six scripts subsistent :

| # | Script | Rôle | Transaction | Répétition |
|---|---|---|---|---|
| 1 | `01_schema.sql` | Schéma complet : organisation, comptes, audit, chat, dossiers hiérarchiques, documents, versions, chunks vectoriels, classement, demandes d'accès, mots de passe de dossier, historique chaîné, notifications, vue des statistiques | Oui (tout ou rien) | Non — base NEUVE uniquement |
| 2 | `02_donnees_reference.sql` | Rôles globaux `ADMIN` / `UTILISATEUR` et permissions (aucun compte, aucune organisation) | Non (insertions `ON CONFLICT`) | Oui (idempotent) |
| 3 | `03_verification.sql` | Contrôle des invariants : vue `verification_invariants` (chaque ligne attendue à 0) + avertissements | Non (lecture seule) | Oui, à tout moment |
| 4 | `seed.sql` | Données de DÉMONSTRATION `DEMO` / `demo_*` (organisation, agents, comptes, rôles, dossiers ; pas de fichiers) | Oui | Après `delete_seed.sql` seulement |
| 5 | `delete_seed.sql` | Supprime exactement la démonstration (préfixe `DEMO` / `demo_`) ; `historique_modification` non touché | Oui | Oui (répétable) |
| 6 | `verif_vecteurs_normalises.sql` | Contrôle facultatif : norme L2 des embeddings (attendu : `non_normalises = 0`) | Non (lecture seule) | Oui, à tout moment |

## Installation d'une base neuve (ordre imposé)

```
psql -U postgres -c "CREATE DATABASE rag;"
psql -U postgres -d rag -v ON_ERROR_STOP=1 -f database/01_schema.sql
psql -U postgres -d rag -v ON_ERROR_STOP=1 -f database/02_donnees_reference.sql
psql -U postgres -d rag -f database/03_verification.sql
psql -U postgres -d rag -v ON_ERROR_STOP=1 -f database/seed.sql        # facultatif : démonstration DEMO
```

1. **`01_schema.sql`** crée tout le schéma en une seule transaction ; à la moindre erreur rien n'est
   créé. Il exige une base **vide** (le relancer sur une base déjà installée échoue, par conception).
2. **`02_donnees_reference.sql`** insère les rôles globaux et les permissions indispensables au
   fonctionnement de l'API.
3. **`03_verification.sql`** affiche `verification_invariants` : **chaque ligne doit valoir 0**
   (`historique_chaine_alteree` compris). Les avertissements (`moins_de_2_super_admins_actifs`,
   `divisions_actives_sans_chef`, `fichiers_a_classer`) sont des recommandations, pas des erreurs.
4. **`seed.sql`** (facultatif) crée la démonstration ; mot de passe des comptes `demo_*` :
   `Demo@2026` — jamais en production. Les fichiers se déposent ensuite par l'API ou
   `scripts/seed_fichiers.py`.

## Réinitialisation de la démonstration (sans toucher aux données réelles)

```
psql -U postgres -d rag -v ON_ERROR_STOP=1 -f database/delete_seed.sql
psql -U postgres -d rag -v ON_ERROR_STOP=1 -f database/seed.sql
```

`delete_seed.sql` retire uniquement ce qui porte le préfixe `DEMO` / `demo_` et tout ce que la
démonstration y a ajouté (documents, demandes, secrets de dossier des comptes démo) ; l'historique
immuable et les données réelles ne sont pas touchés.

## Contrôles périodiques

- `03_verification.sql` : après un import de données ou à tout moment (les invariants doivent rester à 0).
- `verif_vecteurs_normalises.sql` : après une restauration ou un import de fichiers vectorisés.
- `SELECT * FROM verifier_historique();` : intégrité de la chaîne de traçabilité (ok = `t`).

## Base existante (installée avant la refonte)

Il n'y a **plus de migration ALTER** : la refonte « suppression du chef de service » est fusionnée dans
les scripts de base. Recréer la base (avec l'API arrêtée, après sauvegarde) :

```
psql -U postgres -c "DROP DATABASE rag;"
psql -U postgres -c "CREATE DATABASE rag;"
# puis la chaîne « Installation d'une base neuve » ci-dessus, et restaurer les données
# (organisation, agents, comptes, rôles métier, dossiers, fichiers) depuis la sauvegarde.
```

Dans la base recréée, les anciens agents titrés `CHEF_SERVICE` n'existent plus : le super
administrateur recrée leurs comptes, les réaffecte à une division et, s'il le veut, nomme l'un d'eux
chef de division. Détails de la refonte : `docs/refonte_super_admin.md`.
