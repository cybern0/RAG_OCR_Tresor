# Démo complète sous Windows 11 — serveur et application sur la même machine

Tout tourne sur **un seul PC Windows 11** : PostgreSQL + pgvector, le serveur OCR, l'API FastAPI (qui sert
le frontend construit), et surtout **les comptes locaux Windows comme référentiel d'identités**. En mode
`AUTH_MODE=pam`, l'API vérifie les identifiants via `LogonUser` (pywin32) : le SAM local — ou l'annuaire
du domaine si la machine y est jointe — valide lui-même le mot de passe. L'application n'en stocke jamais
aucune trace ; elle provisionne le profil applicatif au premier accès et joue son rôle d'intermédiaire.

| Composant | Port | Source |
|---|---|---|
| PostgreSQL + pgvector | 5432 | installateur EDB (ou Docker) |
| Serveur OCR (PaddleOCR) | 8829 | `ocr_server/` |
| API FastAPI (sert aussi le frontend) | 8000 | `Backend/` |
| Comptes Windows | — | Gestion locale des utilisateurs (`lusrmgr.msc`) ou `net user` |

## 1. Installer les logiciels de base (une seule fois)

Dans un terminal PowerShell, puis redémarrer la session :

```powershell
winget install Python.Python.3.13        # Python x64 (« Add python.exe to PATH » coché)
winget install OpenJS.NodeJS.LTS         # pour construire le frontend
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"   # gestionnaire d'environnements
winget install Microsoft.VisualStudioCode   # facultatif
```

Installer aussi (téléchargements officiels) :

- **Microsoft Visual C++ Redistributable 2015-2022 x64** — requis par Paddle sous Windows.
- **LibreOffice** : aperçu et indexation des fichiers Word/Excel/PowerPoint/OpenDocument (moteur unique de
  conversion, Microsoft Office n'est plus utilisé). Sans lui, l'aperçu répond 501 et le téléchargement reste possible.

## 2. PostgreSQL + pgvector

**Option A — natif (recommandé pour la démo « même OS », montre l'administration)**

1. Installer PostgreSQL depuis [enterprisedb.com/downloads/postgres-postgresql-downloads](https://www.enterprisedb.com/downloads/postgres-postgresql-downloads) ; noter le mot de passe `postgres`.
2. Compiler pgvector (pas d'installateur officiel sous Windows) : installer **Visual Studio Build Tools**
   avec la charge « Développement Desktop en C++ », puis dans « x64 Native Tools Command Prompt » :

```bat
git clone https://github.com/pgvector/pgvector.git
cd pgvector
set "PGROOT=C:\Program Files\PostgreSQL\17"
nmake /F Makefile.windows
nmake /F Makefile.windows install   (terminal Administrateur)
```

3. Vérifier : `psql -U postgres -c "SELECT * FROM pg_available_extensions WHERE name='vector';"`

**Option B — Docker (si la compilation bloque)** : installer Docker Desktop puis
`docker run -d --name ged-db -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=rag -p 5432:5432 pgvector/pgvector:pg17`
— l'extension vector est déjà dans l'image ; le reste du guide est identique.

## 3. Administration Windows : les comptes utilisateurs

Terminal **Administrateur** (clic droit → « Exécuter en tant qu'administrateur »). Le super administrateur
de l'application restera un compte `local` créé au CLI (démarrage, secours) ; les agents, eux, utilisent
leurs vrais comptes Windows :

```bat
net user budget1  MotDePasseFort1! /add   /fullname:"Agent Budget"
net user compta1  MotDePasseFort2! /add   /fullname:"Agent Comptabilité"
net user divbud   MotDePasseFort3! /add   /fullname:"Chef de division Budget"
```

- **Ne pas** les ajouter au groupe Administrateurs (principe du moindre privilège — un argument à dire en soutenance).
- Sur Windows 11 **Famille**, `lusrmgr.msc` et `secpol.msc` n'existent pas : tout se fait avec `net user`
  et un terminal élevé ; sur **Pro**, la Gestion locale des utilisateurs (`lusrmgr.msc`) fait pareil en graphique.
- Facultatif (préparation de la phase « groupes ») : `net localgroup TRESOR_BUDGET /add` puis
  `net localgroup TRESOR_BUDGET budget1 /add` — l'app n'en dépend pas encore, mais la structure est là.
- Préparer un compte de service pour l'API (propre pour l'exploitation) : `net user svc-ged ... /add`
  puis, sur Pro, `secpol.msc` → Stratégies locales → Attribution des droits utilisateur →
  **« Agir comme partie du système d'exploitation »** → ajouter `svc-ged` → déconnexion/reconnexion.
  C'est ce privilège qui autorise l'API à valider les mots de passe (`LogonUser`) ; pour la démo,
  lancer simplement l'API dans un terminal Administrateur suffit (LocalSystem l'a aussi, voir § 6).

## 4. Préparer le projet

```bat
C:
mkdir \GED
(décompresser RAG_OCR_Tresor_sans_sous_dossiers.zip dans C:\GED\RAG_OCR_Tresor)

:: OCR (premier lancement : Paddle télécharge les modèles, connexion internet requise une fois)
cd C:\GED\RAG_OCR_Tresor\ocr_server
uv sync

:: Backend (pywin32 s'installe automatiquement sous Windows)
cd C:\GED\RAG_OCR_Tresor\Backend
uv sync

:: Frontend : construit une fois, puis servi par l'API elle-même
cd C:\GED\RAG_OCR_Tresor\frontend
npm ci
npm run build
```

Créer `C:\GED\RAG_OCR_Tresor\.env` :

```ini
DATABASE_URL=postgresql+psycopg://postgres:VOTRE_MOT_DE_PASSE@localhost:5432/rag
OCR_URL=http://localhost:8829
SECRET_KEY=(python -c "import secrets; print(secrets.token_urlsafe(48))")
AUTH_MODE=pam
AUTH_OS_DOMAIN=.
AUTH_OS_AUTO_CREER=true
CORS_ORIGINS=http://localhost:8000
```

Créer la base puis exécuter les scripts dans l'ordre (`psql -U postgres`, ordre détaillé :
`docs/ordre_execution_sql.md`) :

```bat
psql -U postgres -c "CREATE DATABASE rag;"
psql -U postgres -d rag -v ON_ERROR_STOP=1 -f database\01_schema.sql
psql -U postgres -d rag -v ON_ERROR_STOP=1 -f database\02_donnees_reference.sql
psql -U postgres -d rag -f database\03_verification.sql
psql -U postgres -d rag -f database\seed.sql   :: facultatif : démonstration DEMO

:: Super administrateur de l'application (compte app « local », valable même en mode pam)
cd C:\GED\RAG_OCR_Tresor\Backend
uv run python -m app.cli creer-admin
```

## 5. Démarrer les services (terminal Administrateur)

```bat
:: Terminal 1 — OCR
cd C:\GED\RAG_OCR_Tresor\ocr_server
uv run uvicorn server:app --host 0.0.0.0 --port 8829

:: Terminal 2 — API (sert aussi le frontend : http://localhost:8000)
cd C:\GED\RAG_OCR_Tresor\Backend
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Accès depuis un autre poste du réseau : ouvrir le pare-feu une fois (et rester `--host 0.0.0.0`) :

```bat
netsh advfirewall firewall add rule name="GED API"    dir=in action=allow protocol=TCP localport=8000
netsh advfirewall firewall add rule name="GED OCR"    dir=in action=allow protocol=TCP localport=8829
```

## 6. Exploitation propre : l'API en service Windows (facultatif mais recommandé)

Un service tourne sans fenêtre, démarre seul, et **LocalSystem possède déjà le privilège LogonUser** :

```bat
sc create GED-Tresor binPath= "\"C:\GED\RAG_OCR_Tresor\Backend\.venv\Scripts\python.exe\" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --app-dir C:\GED\RAG_OCR_Tresor\Backend" start= auto
sc description GED-Tresor "API de la GED du Trésor (authentification déléguée aux comptes Windows)"
sc start GED-Tresor
```

## 7. La liaison à l'application : scénario de démonstration

1. **Structure** : naviguer vers `http://localhost:8000` (ou `http://IP-du-PC:8000` depuis un poste client),
   se connecter avec le compte créé au CLI (`creer-admin`) → créer direction, services, divisions, agents.
2. **Comptes Windows** : en administrateur, `net user budget1 ... /add` (§ 3) — l'OS est le seul référentiel.
3. **Premier accès** : se connecter à l'interface avec `budget1` et **le mot de passe Windows** → l'API
   vérifie via LogonUser, puis provisionne le profil (rôle `UTILISATEUR`, sans agent). La gestion des
   comptes affiche la source « OS » (`source_compte`).
4. **Rattachement** : reconnecté en super administrateur, rattacher `budget1` à l'agent de la division
   Budget → la division, ses dossiers et ses rôles s'ouvrent.
5. **Preuves que l'OS pilote tout** (le point fort devant l'encadreur) :
   - `net user budget1 *` (nouveau mot de passe Windows) → la connexion applicative suit immédiatement le
     nouveau mot de passe, sans rien changer dans l'app ;
   - `net user budget1 /active:no` → connexion refusée sur-le-champ, même avec le bon mot de passe ;
   - mauvais mot de passe → 401 + `connexion.echec` dans l'audit ; 5 échecs → blocage temporaire de l'IP ;
   - changer le mot de passe depuis l'app est **refusé** (409) : il appartient au système.

## 8. Dépannage

- **503 « privilège... »** (erreur Windows 1314) : l'API n'a pas le droit de valider des mots de passe →
  terminal Administrateur, service LocalSystem (§ 6), ou attribuer le droit via `secpol.msc` (§ 3, Pro).
- **`CREATE EXTENSION vector` échoue** : pgvector non installé → finir l'option A du § 2.
- **OCR lent au premier appel** : téléchargement des modèles Paddle (une seule fois, cache utilisateur) ;
  vérifier la connexion internet au premier lancement.
- **Aperçu Word/Excel 501** : Office absent du serveur — l'installer (§ 1) ou accepter le repli.
- **« python-pam absent »** ne doit pas apparaître sous Windows : le message signale qu'on a forcé le
  chemin PAM hors Windows — normal seulement sur Linux.
- **Connexion depuis un poste client impossible** : pare-feu (§ 5), `--host 0.0.0.0`, puis
  `http://IP-du-PC:8000` (ne pas oublier que CORS est déjà servi par l'API elle-même).
