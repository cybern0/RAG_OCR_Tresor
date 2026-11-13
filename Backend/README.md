# Backend

API FastAPI du projet (Python 3.13, géré avec uv).

## Démarrage

```
uv sync
cp ../.env.example ../.env        # puis renseigner SECRET_KEY (voir le fichier)
uv run python -m app.cli set-password admin     # active le compte admin (créé verrouillé par database/04)
uv run uvicorn app.main:app --reload --port 8000
```

Documentation interactive : http://localhost:8000/docs · état des services : `GET /health`.
LibreOffice doit être installé pour lire Word, PowerPoint, Excel ancien format et OpenDocument (PDF, images, CSV, XLSX et TXT n'en ont pas besoin).

## Rôles

| | ADMIN | UTILISATEUR |
|---|---|---|
| Créer / renommer / archiver / supprimer un dossier, gérer ses membres et rôles | oui | non |
| Fichiers et chat | tous les dossiers | selon son rôle dans chaque dossier (LECTEUR, CONTRIBUTEUR, GESTIONNAIRE_DE_CONTENU) |
| Créer / modifier des utilisateurs, agents, services, directions | oui | non |
| Journal d'audit | oui | non |

Un rôle de dossier est donné à un utilisateur ou à un service entier ; le rôle effectif est le plus élevé des deux, recalculé à chaque requête
(un retrait prend effet immédiatement). La matrice des actions par rôle est la constante `MATRICE` de `app/core/permissions.py`.
Un compte UTILISATEUR doit rester lié à un agent rattaché à un service (c'est ce service qui porte l'accès par service).
Les droits sont vérifiés côté serveur ; l'interface ne fait que masquer les boutons.

## Tests

```
uv run pytest                    # tests unitaires (aucun service externe)
TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/rag_test uv run pytest   # + tests d'API
```

La base de test doit avoir reçu les scripts `database/01` à `05`. Ollama et l'OCR sont simulés pendant les tests.
Voir `../docs/architecture.md` pour le rôle de chaque dossier.
