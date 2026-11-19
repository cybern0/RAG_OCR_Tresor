# Livraison : /historique nettoyé, recherche et filtres sur /admin/utilisateurs et /admin/agents, poste de chef affiché

> Demandes du 19/11/2026 : « dans /historique nettoyer le dictionnaire de filtre "types", ainsi dans
> /admin/utilisateurs ajouter des filtres et recherche, de même que dans /admin/agents, aussi nommé
> chef de service y est absent. » — puis : « supprimer le filtre demande dans /historique, comment
> nomme-t-on un chef de service dans /admin/agents ? » — enfin : « dans agent, modifier aussi
> direction, service et division ; enlever le bouton "Nommer chef de division" et le mettre dans le
> formulaire de modification, toujours en bouton, sans email ni fonction ; deux boutons : chef de
> service ou chef de division, par défaut vide (agent). » — et : « /admin/structure et /admin/agents
> devraient avoir un CRUD complet — /admin/agents ne manque que delete. » — enfin : « dans /admin/agents
> enlever le bouton "retirer le poste", car dans la modification on peut déjà le changer ; puis nettoyer
> les notifications, il y en a déjà beaucoup et pourtant certaines sont déjà résolues. »

## 0 quater. Compléments du cinquième tour — « Retirer le poste » en moins, notifications nettoyées

- **/admin/agents** : le bouton « Retirer le poste » disparaît de la liste. Le poste se change ou se vide dans
  la modal « Modifier » (désélectionner « chef de division » / « chef de service » = agent simple, avec le même
  transfert tracé et notifié). La liste garde la nomination rapide d'un chef de service, Désactiver/Réactiver
  et Supprimer.
- **Notifications — la source du désordre traitée à la racine** : quand une demande d'accès est **acceptée,
  refusée ou annulée**, ses notifications « demande_acces » chez les décideurs (chefs, super administrateurs en
  intérim) sont **purgées** — la demande n'est plus à traiter ; le demandeur, lui, garde la notification de
  décision (`purger_demande`, appelée par `decider` et `annuler` dans services/demandes.py).
- **Nettoyage manuel** : nouveau bouton **« Nettoyer »** dans la cloche de notifications, adossé à la route
  `POST /notifications/nettoyer` — supprime les notifications **lues** ET celles des demandes **déjà tranchées
  ou annulées**, puis affiche le compte rendu (« Nettoyage : N notification(s) supprimée(s). »). Le bouton
  « Tout marquer comme lu » existant est conservé.
- **Test** : `test_notifications_resolues_purgees_et_nettoyage` (purge à la décision et à l'annulation côté
  décideur, décision conservée côté demandeur, nettoyage du demandeur). Comme tous les tests d'API, il attend
  `TEST_DATABASE_URL` : aucun Postgres dans cet environnement, la suite locale reste « 93 réussis,
  3 ignorés ». Vérifié ici : imports de l'application OK, routes `/notifications` complètes (GET, /lues,
  /nettoyer, /{id}/lue) enregistrées, `npm run build` OK.

## 0 ter. Compléments du quatrième tour — CRUD complet : la suppression

- **Backend — 4 routes DELETE** (super administrateur uniquement) :
  `DELETE /structure/agents/{id}`, `DELETE /structure/directions/{id}`, `DELETE /structure/services/{id}`,
  `DELETE /structure/divisions/{id}`. La doctrine « pas de suppression physique » du module structure est
  remplacée par une **suppression gardée** : refus **409** tant que des éléments dépendent encore de l'objet —
  une direction contient des services ; un service, des divisions ou des agents ; une division, des agents,
  des rôles, des **documents** (FK obligatoire) ou des demandes d'accès. Le message 409 liste ce qui bloque et
  en quelle quantité (ex. « encore utilisée : 2 agent(s), 1 document »). Les documents ne bloquent pas la
  suppression d'un **service** (`cree_par_service_id` en SET NULL).
- **Supprimer un agent** : son compte utilisateur éventuel est **dissocié, pas supprimé** (aucune route DELETE
  utilisateur n'existe — le compte survit, sans agent lié) ; la suppression est tracée dans l'historique chaîné
  (`agent_supprime`, avec matricule, titre et compte) et un poste de chef tenu par l'agent redevient vacant.
- **Frontend** : bouton « **Supprimer** » dans la liste des agents et dans les trois tableaux de
  `/admin/structure`, chacun derrière une fenêtre de confirmation (`ConfirmDialog`) qui énonce la règle et, pour
  un agent avec compte, ce que devient le compte ; l'erreur 409 du backend s'affiche dans la fenêtre sans la fermer.
- **Tests** : 3 tests d'API dans `tests/test_hierarchie.py` (dissociation du compte + historique + 403 chef de
  service ; libération du poste d'un chef supprimé ; garde 409 à chaque niveau puis chaîne complète
  direction → service → division avec purge `force=true` du document bloquant). **Ils attendent
  `TEST_DATABASE_URL`** : aucun Postgres n'est disponible dans cet environnement d'exécution, la suite locale
  reste « 93 réussis, 3 ignorés » (tests d'API ignorés sans base — cf. Backend/README.md). Vérifié ici :
  imports de l'application OK, 4 routes DELETE enregistrées sur le routeur structure, `npm run build` OK.

## 0 bis. Compléments du troisième tour — modal « Modifier » d'un agent

- **Affectation complète modifiable** : la modal suit désormais **direction → service → division**
  (la direction filtre les services ; l'agent reste rattaché au service, sa direction en découle).
- **Poste en deux boutons** dans la modal : « Chef de division » et « Chef de service », **par défaut
  aucun** (agent simple) ; cliquer un bouton sélectionné le désélectionne. « Chef de division » n'est
  actif qu'une fois une division choisie ; « Chef de service » remet la division à « Aucune ».
  **Le champ email et la fonction sortent du formulaire** (inchangés à la modification, toujours
  saisissables à la création).
- **Le bouton « Nommer chef de division » disparaît de la liste** : la nomination se fait par les
  boutons de la modal, avec le même comportement que les transferts dédiés — le titulaire précédent
  est remplacé (historique + notification). Soumission en trois temps, dans l'ordre des contraintes
  du backend : rendre l'ancien poste si le poste ou l'affectation change → PATCH identité/service/
  division → nomination (`transfererChef` / `transfererChefService`). La liste conserve
  « Retirer le poste » (les deux types) et la nomination rapide d'un chef de service.
- Vérifications : `npm run build` OK (tsc + vite) ; pytest 93 réussis / 3 ignorés.

## 0. Compléments du second tour

- **`/historique`** : l'option « Demande » est retirée du filtre « Type de cible ». Les entrées de type
  demande restent visibles dans « Tous les types » — le backend continue de les journaliser
  (`services/demandes.py` est monté et vivant) ; seul le filtre disparaît.
- **`/admin/agents`** : ajout d'une modal **« Modifier »** (icône crayon dans la colonne d'actions) —
  nom, prénom, fonction, email, service, division. Elle lève le blocage du parcours de nomination :
  le backend exige qu'un chef de service soit **sans division** (« retirez d'abord sa division »), mais
  l'interface ne permettait pas de retirer la division d'un agent existant (aucun formulaire, et la
  signature frontend de `updateAgent` était plus étroite que le `PATCH` backend). En modification,
  « Aucune » division est accepté pour un agent sans titre (la règle « division obligatoire » ne vaut
  qu'à la création — `_valider_etat(creation=...)`). Vérifications : `npm run build` OK,
  pytest 93 réussis / 3 ignorés.
- **Comment nommer un chef de service** — deux chemins :
  1. **À la création** (Nouvel agent) : champ « Poste » = « Chef de service » (la division est désactivée).
  2. **Pour un agent existant** : s'il est chef de division, « Retirer le poste » d'abord ; puis crayon
     « Modifier » → Division « **Aucune** » → Enregistrer ; le bouton « **Nommer chef de service** »
     apparaît alors dans la colonne d'actions. Conditions : agent **actif**, du service visé, sans
     division et sans titre — le titulaire précédent est remplacé (historique + notification). Un seul
     chef de service par service ; « Retirer le poste » rend le poste vacant.

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

- `frontend/src/features/historique/HistoriquePage.tsx` (dictionnaire TYPES + libellés, puis retrait de « Demande »)
- `frontend/src/features/admin/users/UsersPage.tsx` (recherche, filtres, colonne Poste)
- `frontend/src/features/admin/structure/AgentsPage.tsx` (recherche, filtres, modal « Modifier », suppression, retrait du bouton « Retirer le poste »)
- `frontend/src/features/admin/structure/StructurePage.tsx` (suppression gardée des trois niveaux)
- `frontend/src/features/admin/api.ts` (`updateAgent` élargie ; `deleteAgent`, `deleteDirection`, `deleteService`, `deleteDivision`)
- `frontend/src/features/notifications/api.ts` (`nettoyerNotifications`)
- `frontend/src/features/notifications/NotificationBell.tsx` (bouton « Nettoyer »)
- `Backend/app/api/routes/structure.py` (4 routes DELETE)
- `Backend/app/api/routes/notifications.py` (route `POST /notifications/nettoyer`)
- `Backend/app/services/notifications.py` (`purger_demande`, `nettoyer`)
- `Backend/app/services/demandes.py` (purge des « demande_acces » à la décision et à l'annulation)
- `Backend/app/schemas/notification.py` (`NettoyageOut`)
- `Backend/app/services/structure/crud.py` (4 fonctions de suppression gardées ; doctrine du module mise à jour)
- `Backend/tests/test_hierarchie.py` (3 tests de suppression + test de notifications nettoyées)
- Backend : suppression des 6 modules morts listés ci-dessus
- `MODIFICATIONS.md`
