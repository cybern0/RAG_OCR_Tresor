# Refonte « classes de fichiers » — décision après complications (11/2026)

Ce document acte la décision prise avec l'encadreur après les complications rencontrées avec les comptes
système, et décrit le système qui en résulte. Il remplace `docs/authentification_os.md` et
`docs/demo_windows11.md` (supprimés : l'authentification déléguée au système est abandonnée).

## La décision

1. **Plus de comptes du système d'exploitation** : ni PAM, ni pywin32/LogonUser, ni utilisateurs système.
   L'application gère elle-même l'authentification — comptes créés par le super administrateur (interface)
   ou au CLI (`python -m app.cli creer-admin` / `set-password`), mots de passe hachés (scrypt) dans `_user`.
   Tout le travail précédemment fait pour l'authentification OS (mode `AUTH_MODE=pam`, service
   `/etc/pam.d`, `LogonUser` sous Windows) est **retiré** du code.
2. **Déploiement sur un nouveau serveur**, à l'acquisition : l'application s'installe seule, sans intégration
   au système d'identité existant. **Le partage de fichiers actuel reste sur les anciens serveurs** : la
   GED n'y touche pas et ne migre rien automatiquement.
3. **Un seul emplacement de stockage** : tous les fichiers déposés vivent à plat dans
   `storage/uploads/` du serveur applicatif, sous un nom généré (`uuid4` + extension). Plus de
   répertoires par division ou par dossier sur le disque : la division, le dossier, la classe et les
   rôles d'un fichier sont des données de la base, et **l'application contrôle seule l'accès**. Les
   dépôts anciens restent lisibles (le chemin en base fait foi).
4. **Fonctionnalités liées aux « dossiers système » supprimées** : le verrouillage de division/service par
   « mot de passe de dossier » (déjà mort : tables et endpoints absents), les modules `securite` et
   `partage` (cassés, jamais montés), et toute idée de droits posés sur le système de fichiers.

## La hiérarchie reste la même

| Niveau | Ce qu'il peut faire |
|---|---|
| **Super administrateur** (ROOT) | Crée agents et divisions, gère comptes, dictionnaires de rôles, dossiers (renommer/archiver/supprimer), audit et historique. **Il ne fait qu'administrer** : ni consultation des fichiers, ni IA (permissions `document.lister` et `chat.utiliser` retirées à son niveau ; les fichiers lui répondent 404, l'IA 403). Il assure l'intérim de la GESTION d'une division sans chef, jamais de son contenu. |
| **Chef de service** (admin service) | Plusieurs divisions : gérant de tous les fichiers de son service ; **pose les classes des fichiers**, gère les comptes des agents de son service, **utilise l'IA sur tous les fichiers d'une division ou de toutes les divisions de son service**. |
| **Chef de division** (admin division) | La GED se fait au niveau division : gérant des fichiers de sa division, **pose les classes des fichiers**, utilise l'IA sur tous les fichiers de sa division. |
| **Agent** | Voit uniquement les fichiers de sa division **et seulement ceux classés selon ses rôles** (les siens, qu'il dépose automatiquement classés à ses rôles). L'IA répond depuis ce même périmètre ; hors classe : « Demander l'accès » (demande de rôle ou accès ponctuel au chef). |

## Les classes de fichiers

La « classe » d'un fichier est **un ou plusieurs rôles du dictionnaire de sa division** (`RoleDivision` /
`DocumentRole`) — le mécanisme existant devient la règle centrale :

- à l'ingestion, un fichier déposé par un agent reçoit automatiquement ses rôles (il ne peut qu'en
  retirer, jamais en ajouter) ; un chef peut choisir les classes au dépôt ;
- **l'admin service et l'admin division assignent les classes après coup** : `PUT /api/documents/{id}/roles`
  et `POST /api/documents/classer-lot` (interface : modale « Classer », onglet « Classement des fichiers ») ;
- un fichier sans classe est « à classer » : visible du chef (gérant) seul, signalé au tableau de bord ;
- la visibilité (listes, téléchargement, **interrogation IA**) filtre par division puis par classe —
  une seule condition SQL : `app/core/acces.py` (`condition_acces_fichiers`).

## Ce qui a été retiré ou ajusté dans le code

- **Auth** : `services/auth_os.py`, branche PAM du login, `provisionner_compte_os`, colonne
  `source_compte` (base et schémas), `auth_mode`/`auth_os_service`/`auth_os_domain`/`auth_os_auto_creer`
  (config), `python-pam` et `pywin32` (dépendances), `tests/test_auth_os.py`.
- **Code mort** : `services/securite.py` + `api/routes/securite.py` + `schemas/securite.py`
  (verrouillage), `services/partage.py` + `api/routes/partage.py` (partages/liens, imports cassés),
  `api/routes/me.py` (doublon), `tests/test_partage_collaboration.py`.
- **Stockage** : `stockage.py` réécrit (un seul `chemin()` à plat), plus de création/retrait de
  répertoires par dossier.
- **Super admin** : `condition_acces_fichiers` sans la clause ROOT (ne lit rien), `role_sur_document`
  sans le rôle SUPERIEUR, `load_permissions` retire `document.lister`/`chat.utiliser` au niveau ROOT,
  le chat refuse explicitement le super administrateur.
- **UI** : arbre legacy et écrans orphelins supprimés (ancien App.tsx, api/, hooks/, types/,
  composants ui, panneaux AdminPage/AuditPanel/Chatbot/DossiersPanel/panels structure & users, écran
  « Mots de passe »), FAB chat conditionné à `chat.utiliser`, routes /dossiers et /chat déjà gardées
  par permission (le super administrateur est automatiquement renvoyé à l'accueil), textes du chat
  actualisés.

## Migration d'une base existante

Les scripts `database/01→03` recréent le schéma sans `source_compte`. Sur une base existante, soit la
recréer (`docs/ordre_execution_sql.md`), soit exécuter :

```sql
ALTER TABLE rag_sys._user DROP COLUMN IF EXISTS source_compte;
ALTER TABLE rag_sys._user ALTER COLUMN mot_de_passe_hash SET NOT NULL;  -- après avoir fixé les hash NULL
```
