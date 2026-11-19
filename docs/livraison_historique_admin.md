# Livraison : /historique nettoyé, recherche et filtres sur /admin/utilisateurs et /admin/agents, poste de chef affiché

> Demande du 19/11/2026 : « dans /historique nettoyer le dictionnaire de filtre "types", ainsi dans
> /admin/utilisateurs ajouter des filtres et recherche, de même que dans /admin/agents, aussi nommé
> chef de service y est absent. »

## 1. `/historique` — dictionnaire du filtre « types » nettoyé

Le menu « Type de cible » listait des valeurs qui **ne correspondaient à rien** : `user`, `service`,
`division` n'existent pas dans le registre (le backend écrit `utilisateur`, et les verrouillages d'unité ou
les dossiers appartenaient à des modules retirés), et la valeur réelle `utilisateur` était introuvable.

Nouveau dictionnaire — uniquement les valeurs réellement journalisées, avec libellés lisibles :
**Tous les types · Document · Utilisateur · Rôle de division · Demande · Agent**.

Au passage, les modules backend morts qui produisaient les valeurs fantômes sont supprimés :
`routes/dossiers.py`, `routes/securite.py`, `services/dossiers/`, `services/securite.py`,
`schemas/dossier.py`, `schemas/securite.py` — jamais montés dans `main.py`, donc jamais appelables
(complément de la suppression des dossiers décidée à la refonte). Tests : 93 réussis, 3 ignorés.

## 2. `/admin/utilisateurs` — recherche, filtres, et le « chef de service » désormais affiché

- **Recherche** : compte, nom/prénom de l'agent lié, service.
- **Filtres** : rôle du compte (Administrateur / Utilisateur), **poste de l'agent**, état (actif /
  désactivé), service ; bouton « Effacer les filtres ».
- **Colonne « Poste » ajoutée** : c'est l'absence constatée — le backend fournit déjà le titre de l'agent
  (`AgentBrief.titre`), mais la liste ne l'affichait pas. Le compte d'un **chef de service** (et de chef de
  division) porte maintenant son badge, et le poste devient un filtre.
- Filtres côté client (la liste complète est déjà chargée) ; aucune modification d'API nécessaire.

## 3. `/admin/agents` — recherche et filtres

- **Recherche** : matricule, nom, prénom, fonction, email, service/division, compte.
- **Filtres** : service, **poste** (Chef de service / Chef de division / Sans poste), état (actif /
  désactivé), avec/sans compte utilisateur ; bouton « Effacer les filtres ».
- Vérifié : les agents nommés **chef de service** figurent bien dans la liste backend
  (`list_agents` ne filtre pas les agents sans division) et le badge existe déjà dans cette page —
  l'absence était donc dans `/admin/utilisateurs`, corrigée ci-dessus.

## Vérifications exécutées

- `npm run build` (tsc + vite) : **OK**.
- `uv run pytest` : **93 réussis, 3 ignorés** (ceux sans `TEST_DATABASE_URL`).
- `MODIFICATIONS.md` : entrée en tête.

## Fichiers modifiés

- `frontend/src/features/historique/HistoriquePage.tsx` (dictionnaire TYPES + libellés)
- `frontend/src/features/admin/users/UsersPage.tsx` (recherche, filtres, colonne Poste)
- `frontend/src/features/admin/structure/AgentsPage.tsx` (recherche, filtres)
- Backend : suppression des 6 modules morts listés ci-dessus (aucun autre changement d'API)
- `MODIFICATIONS.md`
