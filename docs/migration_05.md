# Migration 05 : dossiers, rôles de dossier, versions

Objet : passer d'une organisation par service à des dossiers partagés avec rôles et versions de fichiers.
Fichiers : `database/05_dossiers_versions.sql` (migration ou installation), `database/05_retour_arriere.sql`, `database/05_verification.sql`.
Les scripts 01 à 04 ne sont pas modifiés.

## Ce que fait la migration
- Crée `dossier`, `dossier_membre` (rôle direct), `dossier_service` (rôle d'un service entier), `document_version`, `preference_utilisateur`, `memoire_chat`.
- Ajoute la permission `dossier.gerer` (ADMIN) et retire à UTILISATEUR `document.creer|modifier|supprimer`.
- Migre les données **une seule fois** (détecté par la présence de `document.service_id`) :
  - un dossier par service, nommé `<nom du service> (<code>)`, ouvert à ce service avec le rôle GESTIONNAIRE_DE_CONTENU
    (ce que pouvait faire un utilisateur du service avant) ; chaque document est rangé dans le dossier de son ancien service ;
  - chaque document reçoit une version 1 ; les colonnes du fichier (nom, hash, chemin, statut...) passent de `document` à `document_version` ;
  - chaque chunk est rattaché à la version 1 ; embeddings et chunks ne sont pas recalculés ; `chunk.taille_ref` = nombre de chunks de la version ;
  - l'ancien `service_id` est sauvegardé dans `migration_05_document_service`.
- Les fichiers sur disque ne bougent pas ; les conversations existantes sont conservées.

## Pas à pas
1. **Arrêter l'API** (et le worker), puis sauvegarder : `pg_dump -U postgres -Fc rag > rag_avant_05.dump`.
2. `psql -U postgres -d rag -v ON_ERROR_STOP=1 -f database/05_dossiers_versions.sql` (une transaction : à la moindre erreur, rien n'est changé).
3. `psql -U postgres -d rag -f database/05_verification.sql` : chaque contrôle doit afficher son résultat attendu (0 sauf mention).
4. Démarrer l'API (nouvelle version), se connecter en admin : onglet « Dossiers et accès », renommer les dossiers créés,
   ajuster les accès (ajouter d'autres services ou des utilisateurs, passer certains en LECTEUR).

## Retour arrière
`psql -U postgres -d rag -v ON_ERROR_STOP=1 -f database/05_retour_arriere.sql`, avec l'API arrêtée, puis redéployer l'ancienne version du code.
Ce que le retour arrière **perd** : dossiers, membres, rôles, préférences, mémoire du chat, et l'historique des versions (seule la plus récente
de chaque document est gardée, avec ses chunks ; les fichiers des anciennes versions restent sur le disque, orphelins).
En cas de doute, restaurer le dump de l'étape 1 est plus sûr.

## Si le changement devient trop gros
La base de démonstration est jetable : on peut la supprimer et réécrire 01 à 05 en un seul jeu de scripts neufs.
