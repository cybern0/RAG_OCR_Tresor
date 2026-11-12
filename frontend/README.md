# frontend

Interface React 19 + TypeScript (Vite, Tailwind 4).

```
npm install
npm run dev      # http://localhost:5173, /api relayé vers http://localhost:8000
npm run build    # vérification TypeScript + build de production
npm run lint
```

`VITE_API_URL` (optionnel) change l'adresse de l'API (par défaut `/api`).

## Écrans

- Connexion
- Documents : liste des métadonnées (jamais le contenu), ajout, modification, suppression, suivi de l'indexation
- Chatbot : réponses en streaming avec sources citées, historique des conversations
- Administration (ADMIN) : utilisateurs, agents, services, journal d'audit

Les boutons sont masqués selon les permissions du compte ; le contrôle réel est fait par le backend.

## Thème

Défini dans `src/index.css` (bloc `@theme`) : fonds vert végétal (`leaf-*`), texte blanc cassé (`cream-*`),
composants jaune doré (`gold-*`). Les classes `.card`, `.btn`, `.btn-ghost`, `.input`, `.badge` en découlent.
