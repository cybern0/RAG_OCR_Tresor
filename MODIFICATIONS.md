# Dossiers à un seul niveau, créés automatiquement depuis un modèle

Refonte en deux étapes :

1. **Suppression des sous-dossiers** : chaque division ne contient plus qu'**un seul niveau de
   dossiers** (plus de sous-dossiers, plus de bouton de création de sous-dossier, plus de déplacement).
2. **Suppression de la création manuelle** : même le super administrateur ne crée plus de dossier à la
   main. À la **création d'une division**, le backend pose automatiquement le jeu de dossiers du
   **modèle configuré** — le même pour toutes les divisions.
3. **Existence physique** : un dossier n'est pas qu'une ligne en base — chaque dossier est un vrai
   répertoire de stockage `storage/uploads/<division_id>/<dossier_id>/`, créé avec lui, dans lequel les
   fichiers déposés sont écrits, et retiré quand le dossier est supprimé (il est alors vide).

Les dossiers n'ont ni login ni rôle : ils héritent de la division et sont visibles de tous ses agents ;
ce sont les fichiers qu'ils contiennent qui portent des rôles. La division regroupe déjà agents et
fichiers au niveau logique ; le dossier apporte l'organisation physique sur le disque (sauvegardes,
purges, navigation d'exploitation sans passer par l'API).

## Le modèle de dossiers

La liste est fixée dans `Backend/app/config.py` (`dossiers_defaut`) et surchargeable via `.env` :

```
DOSSIERS_DEFAUT=["Courrier entrant","Courrier sortant","Notes de service","Rapports","Archives"]
```

Chaque nouvelle division reçoit exactement ce jeu (noms vides et doublons du modèle ignorés) ; les
créations sont tracées dans le journal d'audit (`dossier.creer`, détail `auto: true`) et dans
l'historique chaîné (`dossier_cree`). Aucun endpoint de création n'existe : `POST /dossiers` répond 405.

## Règles d'accès après refonte

| Action | Qui |
|---|---|
| Voir un dossier (et les dossiers de sa division) | membres de la division, chefs, super admin (lecture seule hors division) |
| Déposer / versionner / classer des fichiers dans un dossier | membres de la division (inchangé) |
| **Créer un dossier** | **personne à la main : automatique à la création de la division** |
| Renommer, archiver, supprimer un dossier | super administrateur seulement (niveau ROOT) |

Côté serveur, la gestion du dossier lui-même passe par l'action `DOSSIER_GERER` (`core/acces.py`) ;
`DOSSIER_CREER` ne concerne que le dépôt de fichiers dans un dossier existant.

## Fichiers modifiés

**Backend**
- `app/db/metier.py` : colonne `parent_id` retirée du modèle `Dossier`.
- `app/schemas/dossier.py` : `DossierIn`, `parent_id`, `nb_sous_dossiers`, `CheminOut`, `DossierDetailOut` supprimés.
- `app/core/acces.py` : `DOSSIER_MODIFIER` remplacé par `DOSSIER_GERER` (super admin) ; plus de création d'API.
- `app/config.py` : **nouveau** `dossiers_defaut` (le modèle des dossiers, surchargeable par `DOSSIERS_DEFAUT`).
- `app/services/stockage.py` : **nouveau** — répertoire physique de chaque dossier
  (`uploads/<division>/<dossier>/`, créé au besoin) et retrait quand le dossier est supprimé.
- `app/services/structure/crud.py` : **`_dossiers_defaut`** — à la création d'une division, pose le jeu de
  dossiers du modèle (répertoire physique créé + audit + historique chaîné, dans la même transaction).
- `app/services/documents/crud.py` : `_save_upload` écrit dans le répertoire physique du dossier
  (création de document et ajout de version) ; les dépôts anciens à plat restent lisibles via leur chemin
  enregistré en base.
- `app/services/dossiers/crud.py` : plus de chemin / descendants / déplacement / création ;
  renommage, archivage et suppression réservés au super administrateur ; suppression refusée tant que
  le dossier contient des fichiers (corbeille comprise) ; à la suppression, retrait du répertoire physique.
- `app/api/routes/dossiers.py` : `POST /dossiers` supprimé ; paramètre `parent_id` retiré du listage.

**Frontend**
- `src/features/dossiers/SousDossiers.tsx` : **supprimé** (liste + bouton de création de sous-dossier).
- `src/features/dossiers/DossiersPage.tsx` : plus aucun bouton de création ; note pour le super admin
  (« dossiers créés automatiquement selon le modèle fixe ») ; filtre `parent_id` retiré.
- `src/features/dossiers/api.ts`, `types.ts` : `createDossier` et champs de sous-dossiers retirés.
- `src/features/dossiers/DossierPage.tsx` : section sous-dossiers et fil d'Ariane retirés.

**Base de données**
- `database/01_schema.sql` : table `dossier` sans `parent_id` ; unicité des noms par division (`lower(nom)`).
- `database/seed.sql` : chaque division de démonstration reçoit le jeu de dossiers du modèle (le backend
  le pose automatiquement pour les divisions créées via l'API ; le seed le reproduit pour ses divisions
  créées par SQL) + ses dossiers de démo ; `03_verification.sql`, `delete_seed.sql` : alignés.
- Scripts `database/migration_*.sql` **supprimés** : avec la recréation de la base, les migrations
  incrémentales (`migration_suppression_sous_dossiers.sql`, `migration_dossiers_defaut.sql`) n'ont plus
  d'objet — leurs effets sont portés par les scripts de base ci-dessus. Une base existante est recréée
  (ordre complet : `docs/ordre_execution_sql.md`).

**Tests / docs**
- `tests/test_hierarchie.py` : nouveau test `test_dossiers_automatiques_sans_role_et_fichiers_avec_roles`
  (POST 405, modèle complet présent, même jeu pour une division neuve, **répertoires physiques créés**,
  fichier déposé dans le répertoire du dossier, répertoire retiré à la suppression, gestion super admin,
  rôles des fichiers, archivage) ; le test du chef de service utilise le dossier automatique de v2.
- `tests/test_api.py` : `dossier_par_defaut` remplace `mk_dossier` ; le monde de test s'appuie sur les
  dossiers automatiques des divisions v1 et v3.
- `README.md`, `docs/ordre_execution_sql.md`, `.env.example` : mentions mises à jour.

## Recréation de la base (les migrations n'existent plus)

1. Sauvegarder la base, arrêter l'API.
2. `DROP DATABASE` puis la chaîne d'installation neuve : `01_schema.sql` → `02_donnees_reference.sql` →
   `03_verification.sql` → `seed.sql` (facultatif) — ordre détaillé : `docs/ordre_execution_sql.md`.
3. Restaurer les données depuis la sauvegarde (les lignes `dossier` reviennent avec le dump) ; pour toute
   division créée ensuite via l'API, le backend pose automatiquement le jeu du modèle.
4. Déployer le backend et le front reconstruit (`npm run build`).

Aucun script de stockage à exécuter : les répertoires `<division>/<dossier>` sont créés à la volée
(à la création des dossiers et, par précaution, à chaque dépôt) ; les fichiers déjà présents, stockés
à plat, restent téléchargeables — leur chemin est enregistré en base.

Les tests d'API demandent une base de test recréée avec le nouveau `01_schema.sql`
(`TEST_DATABASE_URL=postgresql://... uv run pytest`).

---

# Authentification déléguée au système (PAM) — phase 1 de l'orientation système et réseau

> **ABANDONNÉ (11/2026, refonte « classes de fichiers »)** : cette orientation est retirée du code —
> plus de comptes système, ni PAM ni pywin32 ; l'application gère elle-même ses comptes. Voir la section
> suivante et `docs/refonte_classes.md`. Le texte ci-dessous est conservé pour l'historique.

L'application devient un **intermédiaire** : les comptes et leurs mots de passe appartiennent au système
d'exploitation (créés et réinitialisés par l'administrateur OS), la vérification passe par PAM, et
l'application ne stocke ni ne journalise jamais le mot de passe. Le mode historique (`AUTH_MODE=local`,
hash scrypt en base) reste disponible par défaut — développement, secours, comptes de démarrage.

## Fonctionnement

- `AUTH_MODE=pam` (config : `auth_mode`, `AUTH_OS_SERVICE` pour le service PAM, `AUTH_OS_AUTO_CREER`).
- Connexion : compte `source_compte = 'os'` ou inconnu → vérification PAM (`services/auth_os.py`, import
  paresseux de `python-pam`, message d'erreur générique, 503 si PAM indisponible) ; compte `local` →
  vérification scrypt comme avant (démarrage et secours toujours possibles).
- Premier accès OS : **provisionnement automatique** d'un profil minimal (rôle `UTILISATEUR`, sans agent,
  sans mot de passe local) ; le super administrateur rattache ensuite l'agent (division, rôles métier)
  via l'interface. Désactivable (`AUTH_OS_AUTO_CREER=false` : mapping exigé avant toute connexion).
- Jetons : nouvelle `empreinte_session` — liés au hash local ou, pour un compte OS, à une empreinte du
  nom OS (le mot de passe du système n'est jamais visible de l'application) ; TTL borné (8 h par défaut).
- Garde-fous : ni le compte OS lui-même ni le super administrateur ne peuvent changer le mot de passe ou
  le nom d'un compte OS depuis l'application (409) ; le CLI `set-password` refuse aussi.

## Fichiers modifiés

- `app/config.py` : `auth_mode` (`local|pam`), `auth_os_service`, `auth_os_auto_creer`.
- `app/services/auth_os.py` : **nouveau** — vérification PAM (jamais de log du secret).
- `app/core/security.py` : **nouvelle** `empreinte_session` (jetons sans hash local).
- `app/api/routes/auth.py` : login à deux chemins (pam / local), provisionnement au premier accès,
  échec factorisé ; jetons liés à l'empreinte de session.
- `app/api/deps.py` : validation de jeton via `empreinte_session`.
- `app/services/users/crud.py` : **nouveau** `provisionner_compte_os` ; `update_profile` et `update_user`
  refusent mot de passe et renommage sur un compte OS ; `source_compte` exposé dans `UserOut`.
- `app/db/metier.py`, `app/schemas/user.py` : `mot_de_passe_hash` nullable + `source_compte`.
- `app/cli.py` : `set-password` refuse les comptes OS (procédure de secours = côté OS).
- `database/01_schema.sql` : `_user` avec `source_compte` (`local|os`) et `mot_de_passe_hash` nullable ;
  `database/03_verification.sql` : l'invariant « utilisateur sans agent » ignore les comptes `os` en
  attente de rattachement.
- `pyproject.toml` : dépendance `python-pam`.
- `tests/test_auth_os.py` : **nouveau** — provisionnement et réutilisation, refus sans création
  (mauvais mot de passe ou auto-création désactivée), compte local valable en mode pam, immutabilité du
  mot de passe et du nom d'un compte OS (profil + admin).
- `README.md`, `.env.example`, `docs/authentification_os.md` : **nouveau** (installation PAM, accès
  `/etc/shadow`, chemin AD via SSSD/realmd, limites assumées).

Les tests tournent sans le module PAM réel (il est simulé par monkeypatch) et restent valables en mode
local : `TEST_DATABASE_URL=postgresql://... uv run pytest`.

---

# Démo complète sur Windows 11 — même OS pour le serveur et les comptes

> **ABANDONNÉ (11/2026, refonte « classes de fichiers »)** : la démo/dev reste possible sur Windows 11
> (Python, PostgreSQL, OCR : rien ne dépend du système) mais **sans comptes Windows ni LogonUser** —
> `docs/demo_windows11.md` et `docs/authentification_os.md` sont supprimés. Voir `docs/refonte_classes.md`.
> Le texte ci-dessous est conservé pour l'historique.

L'authentification déléguée au système n'est plus réservée à Linux : `services/auth_os.py` choisit le
mécanisme selon l'OS qui héberge l'API — **PAM sous Linux, `LogonUser` (pywin32) sous Windows**. Le SAM
local (ou l'annuaire du domaine si la machine y est jointe) valide lui-même le mot de passe ; l'application
reste un intermédiaire qui ne stocke rien. Guide complet — installation, administration des comptes
Windows, privilège LogonUser/service, liaison à l'app et scénario de démonstration :
**`docs/demo_windows11.md`**. Positionnement assumé : Windows 11 pour la **démo et le développement**,
**Linux reste la cible de production** — le § 9 du guide liste ce qui change à la bascule (PAM, systemd,
LibreOffice, paquet pgvector PGDG) et ce qui ne change pas (code, base, interface).

## Fichiers modifiés

- `app/services/auth_os.py` : répartiteur par plateforme + `_authentifier_windows` (LogonUser,
  `LOGON32_LOGON_NETWORK`, aucun profil chargé) et `_probleme_serveur_windows` — l'erreur 1314 (privilège
  « Agir comme partie du système d'exploitation » manquant) donne un message d'exploitation au lieu d'un
  refus trompeur ; 1326 et refus normaux → 401. Aucun secret journalisé, aucun profil/session Windows créé.
- `app/config.py` : `auth_os_domain` (`AUTH_OS_DOMAIN`, « . » = comptes locaux Windows, sinon NetBIOS/domaine).
- `pyproject.toml` : `pywin32>=306; sys_platform == 'win32'` (n'installe rien sous Linux).
- `ocr_server/pyproject.toml` : `required-environments` accepte enfin Windows (`win_amd64`) — les wheels
  paddlepaddle 3.4.0 cp313 win_amd64 existent sur l'index paddle CPU utilisé par le projet (vérifié) ;
  `uv sync` de l'OCR fonctionne donc sous Windows 11.
- `tests/test_auth_os.py` : `_probleme_serveur_windows` testée hors Windows (1314 → message, 1326 → None).
- `README.md`, `docs/authentification_os.md` : branche Windows documentée (LogonUser, privilège, domaine).
- `docs/demo_windows11.md` : **nouveau** — guide de bout en bout sur une seule machine Windows 11
  (Python/Node/uv, PostgreSQL natif + pgvector compilé ou Docker, comptes `net user`, service `sc create`,
  pare-feu, `.env`, scénario de démonstration avec les « preuves » que l'OS pilote : changement de mot de
  passe suivi immédiatement, désactivation refusée sur-le-champ, audit des échecs, 409 sur toute tentative
  de changement de mot de passe depuis l'app).

La conversion bureautique était déjà multi-OS (`conversion_office.py` : Office COM/PowerShell sous Windows,
LibreOffice sinon) ; aucun changement côté stockage, aucun appel POSIX dans le backend.

---

# Refonte « classes de fichiers » — plus de comptes système, un stockage unique, l'IA par division et classe

Décision après complications (confirmée avec l'encadreur, détails : `docs/refonte_classes.md`) :
**l'authentification déléguée au système est abandonnée** — l'application gère elle-même ses comptes
(scrypt, interface + CLI) ; **tous les fichiers vivent à plat dans `storage/uploads/`** du serveur
applicatif, sans répertoires par division ni par dossier et sans partage système ; le partage actuel
reste sur les anciens serveurs, le déploiement se fera sur un nouveau serveur. La hiérarchie ne change
pas, mais ses pouvoirs sont redessinés : le **super administrateur ne fait qu'administrer** (ni fichiers
ni IA), les **chefs de division et de service assignent les classes des fichiers** (le rôle de division
devient la classe), les **agents ne voient que les fichiers de leur division classés selon leurs rôles**,
et **l'IA suit exactement ce périmètre** (chef de service : toutes les divisions de son service ;
chef de division : sa division ; agent : ses classes).

## Fichiers modifiés

- **Auth** : `services/auth_os.py` et `tests/test_auth_os.py` supprimés ; login scrypt uniquement ;
  `provisionner_compte_os` retiré ; `empreinte_session(hash)` simplifiée (plus d'empreinte « os: ») ;
  colonne `source_compte` retirée (modèle, schéma Pydantic, `01_schema.sql`, invariant de
  `03_verification.sql`) ; `auth_mode`/`auth_os_service`/`auth_os_domain`/`auth_os_auto_creer` retirés
  de la config ; `python-pam` et `pywin32` retirés des dépendances (l'environnement OCR garde Windows).
- **Code mort supprimé** : `services/securite.py` + `routes/securite.py` + `schemas/securite.py`
  (verrouillage par « mot de passe de dossier »), `services/partage.py` + `routes/partage.py`
  (partages/liens, imports cassés), `routes/me.py` (doublon), `tests/test_partage_collaboration.py`.
- **Stockage** : `services/stockage.py` réécrit (`chemin()` à plat, uuid4) ; `_save_upload` et les
  dépôts n'utilisent plus `repertoire()` ; plus de retrait de répertoire à la suppression d'un dossier.
- **Super admin** : `condition_acces_fichiers` sans clause ROOT (ne lit rien) ; `role_sur_document`
  sans rôle SUPERIEUR ; `load_permissions` retire `document.lister`/`chat.utiliser` au niveau ROOT ;
  `/chat` refuse explicitement le super administrateur ; `est_superieur` supprimé, l'administration des
  dossiers (VOIR/GERER) reste ouverte à ROOT, la gestion du contenu reste aux chefs ; les classes se
  posent via les endpoints existants (`PUT /documents/{id}/roles`, `POST /documents/classer-lot`)
  déjà réservés aux gérants (chefs de division et de service).
- **Frontend** : arbre legacy et écrans orphelins supprimés (ancien `App.tsx`, `api/`, `hooks/`,
  `types/`, `components/ui`, panneaux AdminPage/AuditPanel/Chatbot/DossiersPanel/panels structure et
  users, écran « Mots de passe » — déjà orphelin) ; FAB chat conditionné à `chat.utiliser` ;
  « Historique » reste visible au super admin (`audit.consulter`) ; textes de l'assistant et du README
  actualisés ; `StatusBadge` re-importé depuis les types actifs.
- **Tests** : suite mise à jour aux nouvelles règles (ROOT isolé, stockage plat, dossiers administrés
  par ROOT sans contenu) ; **110 tests passent** (la suite comportait déjà deux échecs à l'état
  antérieur : partage cassé, chat isolation — corrigés).
- **Docs** : `docs/refonte_classes.md` **nouveau** ; `docs/authentification_os.md` et
  `docs/demo_windows11.md` supprimés ; README (auth, rôles, stockage), `architecture.md` (note de
  tête), `.env.example` (plus d'AUTH_OS_*, plus de DEVERROUILLAGE_MINUTES) mis à jour ;
  les deux sections ci-dessus sont marquées ABANDONNÉ.
