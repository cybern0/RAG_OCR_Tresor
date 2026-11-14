# frontend

Application monopage (SPA) React 19 + TypeScript — Vite, Tailwind 4, React Router, TanStack Query.

```
npm install
npm run dev      # http://localhost:5173 — /api est relayé vers http://localhost:8000
npm run build    # vérification TypeScript + build de production (dist/)
npm run lint
```

- Autre adresse pour le backend en développement : `VITE_PROXY_TARGET=http://localhost:3000 npm run dev`.
- `VITE_API_URL` (optionnel) change le préfixe de l'API (par défaut `/api`).
- Production : le backend sert lui-même `frontend/dist` s'il existe (voir `FRONTEND_DIST` / `API_PREFIX` dans
  `Backend/app/config.py`), avec repli sur `index.html` : les liens profonds (`/dossiers/3`) fonctionnent après un rechargement.
  Avec un autre serveur web (nginx…), renvoyer tout chemin inconnu hors `/api` vers `index.html`.

## Routes

| Chemin | Page | Permission |
|---|---|---|
| `/connexion` | Connexion | — |
| `/dossiers` | Dossiers accessibles (cartes) | `document.lister` |
| `/dossiers/:id` | Fichiers du dossier : recherche, filtres, tri, pagination, sélection multiple, corbeille (filtres dans l'URL) | idem |
| `/dossiers/:id/fichiers/:docId` | Fiche d'un fichier : aperçu, classement, versions, commentaires | idem |
| `/chat/:conversationId?` | Assistant, historique des conversations | `chat.utiliser` |
| `/admin` | Tableau de bord (indicateurs, répartitions, état du système) | `statistiques.globales` |
| `/admin/dossiers`, `/admin/demandes` | Dossiers et accès, demandes d'accès | `dossier.gerer` |
| `/admin/utilisateurs` | Comptes | `utilisateur.lister` |
| `/admin/agents`, `/admin/structure` | Agents, directions et services | `structure.gerer` |
| `/admin/classement` | Catégories, types, étiquettes, règles, simulation | `classement.gerer` |
| `/admin/audit` | Journal d'audit | `audit.consulter` |

Les pages sont chargées à la demande (`lazy`). Les menus et boutons suivent les permissions du compte ; le contrôle réel est fait par le backend.

## Structure

```
src/
  app/          App, router (table des routes), gardes, navigation, cadre (layouts), page d'erreur / 404
  shared/
    api/        client HTTP (jeton, erreurs, 401 → déconnexion)
    ui/         composants de base : Modal, ConfirmDialog, Toast, Field, Badge, Pagination, FilePicker, FilePreview…
    hooks/      useToast, useDebounce
    lib/        format (dates, tailles), fichiers (types, CSV), exemples (bouton « Remplir avec exemple »), cn
  features/     un dossier par domaine : api.ts (appels), queries.ts (TanStack Query), types.ts, pages et composants
    auth/ dossiers/ documents/ chat/ admin/{stats,dossiers,demandes,users,structure,classement,audit}
  styles/       index.css (thème)
```

Règles : les appels HTTP restent dans `api.ts`, l'état serveur dans `queries.ts` (clés invalidées après écriture), les
pages ne font que composer. Fin de session (déconnexion, 401) : le cache des requêtes est vidé.

## Thème

Défini dans `src/styles/index.css` (bloc `@theme`) : fonds vert végétal (`leaf-*`), texte blanc cassé (`cream-*`),
composants jaune doré (`gold-*`). Les classes `.card`, `.btn`, `.btn-ghost`, `.btn-danger`, `.btn-icon`, `.input`, `.badge`, `.th`, `.td` en découlent.
