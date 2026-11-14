# Architecture

## Rôles et droits
Deux niveaux (tables `_role`, `permission`, `role_permission` pour le global ; `dossier_membre`, `dossier_service` pour les dossiers).

**Rôle global**
- **ADMIN** : toutes les permissions, dont `dossier.gerer`. Crée dossiers, directions, services, agents, utilisateurs ; peut tout faire dans tous les dossiers (contenu compris) ; consulte l'audit.
- **UTILISATEUR** : `document.lister` et `chat.utiliser` seulement. Aucun droit propre sur les fichiers : tout vient de ses rôles de dossier.

**Rôle de dossier** : LECTEUR, CONTRIBUTEUR, GESTIONNAIRE_DE_CONTENU, donné par l'admin à un utilisateur (`dossier_membre`) ou à un service
entier (`dossier_service` : tous les agents actifs du service). Le rôle effectif est le plus élevé des deux, **recalculé à chaque requête** :
un retrait ou un changement de rôle prend effet tout de suite (aperçu, téléchargement, chat, historique).

| Action | LECTEUR | CONTRIBUTEUR | GESTIONNAIRE |
|---|---|---|---|
| voir (liste, versions), aperçu, téléchargement, chat | oui | oui | oui |
| ajouter fichier / version, modifier titre et cases | non | oui | oui |
| supprimer fichier / version | non | non | oui |

La matrice est la constante `MATRICE` de `core/permissions.py` (seule source de vérité). Codes : dossier inconnu **ou** hors des accès : 404 (l'existence n'est pas révélée) ;
rôle insuffisant : 403 ; dossier archivé (lecture seule, exclu du chat) : 409 sur toute écriture.
Seul l'admin crée, renomme, archive ou supprime un dossier (suppression refusée s'il contient des fichiers) et gère ses accès. Les dossiers sont plats,
sans lien avec les directions ; un service n'intervient que comme bénéficiaire d'un rôle.

Le service d'un compte est celui de son agent (`_user.agent_id -> agent.service_id`) ; l'accès par service ne vaut que si l'agent **et** le service sont actifs.
Règles de comptes : un UTILISATEUR doit être lié à un agent actif ayant un service ; un agent n'a qu'un compte ; on ne peut ni se rétrograder, ni se désactiver,
ni retirer le dernier admin actif. Un admin ne peut pas être membre d'un dossier (il a déjà tout).

## Authentification
Connexion `POST /auth/login` -> jeton signé (HMAC-SHA256) envoyé en `Authorization: Bearer`. Mots de passe hachés avec scrypt.
Le jeton devient invalide si le mot de passe change ou si le compte est désactivé. Un hash commençant par `!` verrouille le compte
(l'admin du seed). Cinq échecs en cinq minutes bloquent temporairement la connexion (par IP + nom).

## Fichiers et versions
- `document` : le fichier logique (dossier, titre, cases `has_tabular` / `has_image`). `document_version` : chaque dépôt, numéroté (1, 2, 3...) et daté (`cree_le`), avec auteur, nom d'origine, hash, chemin, statut d'ingestion.
- Ajouter une version **ajoute** : l'ancienne reste indexée, téléchargeable, interrogeable. La **version courante** (qui fait foi) est la plus récente au statut `ready`.
  Une version identique à la dernière est refusée (restaurer une plus ancienne reste possible). Un même fichier est refusé deux fois dans un même dossier, pas entre dossiers.
- Supprimer une version retire ses chunks ; la dernière version restante ne se supprime pas (supprimer le fichier entier).
- **Cases tableaux / images** : un tableur (`.csv .xlsx .xls .ods`) impose « tableaux », une image impose « images » (cases cochées, non décochables, règle recalculée côté serveur) ; pour les autres types
  l'utilisateur coche. « Images » = les images embarquées d'un PDF ou d'un document sont extraites (LiteParse `extract_images`) puis lues par OCR **en plus** du texte natif ; les pages déjà scannées ne sont pas relues deux fois.
  Changer une case relance la lecture de la version la plus récente seulement.

## Aperçu et téléchargement
`GET /documents/{id}/versions/{n}/apercu` et `/telecharger`, protégés par le rôle de dossier. Types sûrs en « inline » : PDF, PNG/JPEG/WebP/BMP, texte brut (txt, md, csv servis en `text/plain`).
Word, PowerPoint, Excel, ODF : convertis en PDF par LibreOffice (cache par version). `.tif` : pas d'aperçu. Le type MIME vient de l'extension validée au dépôt, jamais du client ;
jamais de HTML ni de SVG ; `nosniff` et CSP `sandbox` partout ; téléchargement en `attachment` + `application/octet-stream`. Le frontend récupère un Blob avec le jeton (pas d'URL publique).
Fichier absent du disque : 410.

## Flux d'ingestion
1. Le frontend envoie le fichier (features/documents/api.ts) vers `POST /documents` (dossier choisi) ou `POST /documents/{id}/versions`.
2. Le backend contrôle le rôle de dossier, enregistre le fichier sous un nom généré, crée la version avec le statut `pending` (services/documents/crud.py).
3. Le worker (workers/ingestion_worker.py, un seul thread) exécute services/ingestion/pipeline.py **pour cette version** :
   parsing LiteParse (OCR seulement si une page n'a pas de texte natif, ou pour les images si la case l'impose), découpage, embeddings Ollama, écriture dans pgvector
   (chaque chunk garde `document_version_id` et `taille_ref`, le nombre de chunks de sa version).
4. Le statut de la version passe à `processing`, puis `ready` ou `error` (avec `message_erreur`) ; le tableau de bord le suit.
Au redémarrage de l'API, les versions restées `pending` ou `processing` sont remises en file.

## Flux de question
1. Le chatbot envoie la question (api/chat.ts) vers `POST /chat`.
2. Les dossiers interrogeables = ceux où l'on a un rôle, non archivés (tous pour l'admin). Aucun : 403.
3. **Historique (mémoire dans la session, obligatoire)** : les derniers messages de la conversation sont relus en base (`services/chat/history.py`, un `BaseChatMessageHistory` LangChain),
   donc ils survivent à une déconnexion ; l'interface rouvre la dernière conversation. Une question de suivi est reformulée en question autonome par le LLM avant la recherche.
   Une réponse dont une source vient d'un dossier devenu inaccessible est **masquée** (affichage, LLM, reformulation) ; elle réapparaît si l'accès revient.
4. services/retrieval/similarity_search.py renvoie les chunks les plus proches (vecteurs + plein texte, fusionnés RRF) des versions `ready` de ces dossiers.
   Option personnelle « dernière version seulement » : seule la version courante de chaque fichier est cherchée.
   **Top-k dynamique** : le nombre de passages = racine carrée de la médiane de `taille_ref` des 5 meilleurs candidats, borné entre `RETRIEVAL_K_MIN` (3) et `RETRIEVAL_K_MAX` (8),
   puis limité à `CONTEXT_MAX_CHARS` caractères pour tenir dans la fenêtre du LLM.
5. services/chat/rag_chain.py construit le prompt : chaque passage porte fichier, **numéro de version et date**, et « la plus récente » ou « ancienne version » ;
   le LLM doit citer la date, préférer la version récente, et décrire les changements pour une question d'évolution. Sans passage trouvé, le LLM n'est pas appelé : « Je ne sais pas ».
   Réponse streamée en SSE (meta, sources, token, done) ; les sources portent dossier, version, date, page.
6. **Mémoire entre sessions (option, désactivée par défaut)** : après chaque réponse sourcée, un résumé tronqué (question + début de réponse, sans appel au LLM) est retenu avec les dossiers sources
   (`memoire_chat`). Aux sessions suivantes il enrichit le prompt **seulement si l'utilisateur a encore accès à tous ces dossiers**.

## Vecteurs : normalisation et produit scalaire
- Tous les embeddings (passages **et** questions) sont normalisés en norme L2 = 1 par `services/ingestion/embedding.py`, puis vérifiés
  (tolérance 1e-6) avant tout usage : un vecteur nul, non fini ou mal normalisé provoque une erreur explicite.
- La recherche classe par produit scalaire : opérateur `<#>` (qui renvoie le produit scalaire négatif, d'où `ORDER BY` croissant),
  servi par l'index HNSW `vector_ip_ops`. Sur des vecteurs unitaires, le classement est identique à celui du cosinus.
- Trois garde-fous : normalisation dans le backend, contrôle du vecteur de la question avant la requête, et contrainte SQL
  `ck_chunk_embedding_normalise` (`vector_norm(embedding)` entre 0,999 et 1,001) qui refuse tout vecteur non normalisé.
- Changer de modèle d'embeddings : adapter `EMBEDDING_DIM` et `vector(768)` dans `database/02` ; la normalisation reste valable.
- Ne pas mélanger les opérateurs : `<=>` ou `<->` ne seraient plus servis par l'index `vector_ip_ops`.
- `database/verif_vecteurs_normalises.sql` (facultatif) compte les vecteurs non normalisés ; le résultat attendu est 0.

## Rôle des dossiers du backend
- `api/` : HTTP seulement, sans logique métier
- `services/` : logique métier par domaine (dossiers, documents, ingestion, retrieval, chat, users, structure, audit)
- `clients/` : accès à Ollama et au serveur OCR
- `db/` : connexion et modèles (métier et vecteurs)
- `core/` : sécurité et permissions (rôles de dossier, matrice des droits)
- `schemas/` : formats d'entrée et de sortie de l'API
- `workers/` : tâches lentes en arrière-plan
- `cli.py` : définition du mot de passe d'un compte (`python -m app.cli set-password`)

## Migrations
Schéma : `database/01` à `05` (voir `docs/migration_05.md`). `05_dossiers_versions.sql` installe ou migre ; `05_retour_arriere.sql` défait ; `05_verification.sql` contrôle.

## Interface
Thème : fonds vert végétal, texte blanc cassé, composants (boutons, bordures, badges, éléments actifs) jaune doré ;
définis une seule fois dans `frontend/src/styles/index.css`.
Application monopage (React Router, TanStack Query) : une route par écran, liens profonds et boutons précédent/suivant du navigateur (voir `frontend/README.md` pour la table des routes).
L'API vit sous `/api` ; le backend sert aussi `frontend/dist` (repli sur `index.html`) quand il existe.
Pages : « Dossiers et fichiers » (dossiers, fichiers avec recherche, filtres, tri, pagination, corbeille, fiche avec aperçu, versions, classement, commentaires), « Assistant » (historique dans l'URL, options personnelles, sources avec version et date),
« Administration » (tableau de bord, dossiers et accès, demandes d'accès, utilisateurs, agents, directions et services, classement, audit). Chaque formulaire a un bouton « Remplir avec exemple » (fausses données, champs vides avant le clic, sans drapeau de désactivation).
