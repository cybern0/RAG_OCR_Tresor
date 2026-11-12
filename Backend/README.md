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
| Documents (liste, ajout, modification, suppression) | tous les services | son service uniquement |
| Chatbot | tous les services | son service uniquement |
| Créer / modifier des utilisateurs | oui | non |
| Créer / modifier agents, services, directions | oui | non |
| Journal d'audit | oui | non |

Le service d'un utilisateur est celui de l'agent auquel son compte est lié : un compte UTILISATEUR doit donc être lié à un agent rattaché à un service.
Les droits sont vérifiés côté serveur (`app/core/permissions.py`, `app/api/deps.py`) ; l'interface ne fait que masquer les boutons.

## Tests

```
uv run pytest                    # tests unitaires (aucun service externe)
TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/rag_test uv run pytest   # + tests d'API
```

La base de test doit avoir reçu les scripts `database/01` à `04`. Ollama et l'OCR sont simulés pendant les tests.
Voir `../docs/architecture.md` pour le rôle de chaque dossier.
