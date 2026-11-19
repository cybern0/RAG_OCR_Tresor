# Livraison : conversion Word → PDF débloquée par LibreOffice

Suite au diagnostic mesuré sur le serveur (Word figé à l'étape `export_pdf` dès qu'il est piloté par COM,
pour tout document y compris le témoin minimal, sans boîte de dialogue, alors qu'Excel convertit en ~2,5 s) :
le moteur de conversion sait maintenant contourner Word avec LibreOffice au lieu d'attendre le délai complet.

## Ce qui change

- Nouveau réglage `CONVERSION_MOTEUR_WORD` (fichier `.env`) pour les documents Word (WORD_EXT :
  .doc/.docx/.rtf/.odt), trois valeurs :
  - `auto` (défaut) : Word d'abord avec un délai court — `CONVERSION_WORD_DELAI_OFFICE_S`, 35 s par défaut,
    jamais plus que le délai total — puis LibreOffice avec le délai complet si Word n'a pas terminé. Word
    bloqué est fermé (PID noté par le journal d'étapes), LibreOffice convertit en quelques secondes : la perte
    de temps est bornée au délai court au lieu des 75 s et plus observées.
  - `libreoffice` : LibreOffice directement avec le délai complet, Word jamais démarré (à choisir si Word se
    bloque aussi en usage manuel, c'est-à-dire si la cause est l'installation Office elle-même).
  - `office` : comportement d'avant (Word seul, délai complet, LibreOffice seulement en cas d'absence ou de
    refus d'Office ; un blocage reste une erreur).
- Sans LibreOffice installé, `auto` redonne à Word le délai complet : aucun changement de comportement tant
  que LibreOffice n'est pas installé sur le serveur.
- Excel et PowerPoint ne changent pas (Office d'abord — mesuré fonctionnel sur le serveur —, LibreOffice en
  repli en cas d'absence ou de refus, délai dépassé = échec).
- Journal d'étapes PowerShell écrit en UTF-8 et relevés PowerShell du diagnostic en UTF-8
  (`[Console]::OutputEncoding`) : les accents des noms d'imprimantes s'affichent correctement (problème
  cosmétique signalé dans le handoff).
- `scripts/diagnostic_conversion.py` : nouvelle option `--moteur auto|libreoffice|office` pour essayer un
  moteur sans toucher au `.env`, et affichage du réglage courant (moteur Word, délai court).

## Déploiement sur le serveur Windows

1. Installer LibreOffice (chemin standard `C:\Program Files\LibreOffice\program\soffice.exe` détecté
   automatiquement ; le chemin x86 est aussi accepté).
2. Rien à ajouter au `.env` : `auto` est le défaut. Facultatif :
   - `CONVERSION_MOTEUR_WORD=libreoffice` si Word reste bloqué même hors automatisation (point 2 du handoff) ;
   - `CONVERSION_WORD_DELAI_OFFICE_S=40` pour ajuster le délai court (30 à 40 s recommandés).
3. Redémarrer le backend, puis vérifier depuis `Backend/` :
   - `python scripts/diagnostic_conversion.py --temoin` : doit réussir en quelques secondes (Word interrompu
     à 35 s au plus, puis LibreOffice) ;
   - `python scripts/diagnostic_conversion.py --temoin --moteur libreoffice` : doit réussir sans même
     démarrer Word ;
   - déposer un .docx dans l'application : aperçu et indexation doivent suivre.

## Suite de l'enquête (Word reste en cause)

La bascule contourne le blocage sans en identifier la cause. Si l'export manuel (Fichier > Exporter > PDF sur
`temoin.docx`) se fige aussi : Réparation rapide puis en ligne d'Office (Paramètres > Applications >
Microsoft 365 > Modifier), désactiver les compléments COM ou `winword /safe` + renommer
`%APPDATA%\Microsoft\Templates\Normal.dotm`, vérifier l'activation de la licence, tester une exclusion
antivirus/EDR pour `WINWORD.EXE` et le dossier `storage`, consulter l'Observateur d'événements (journal
Application, événements « Application Hang » de WINWORD). Si l'export manuel passe, la cause est propre à
l'automatisation COM (profil de session du service, complément d'automatisation).

## Fichiers modifiés

- `Backend/app/services/conversion_office.py` — plan de moteurs par type de fichier (délai court Word puis
  bascule, modes `auto`/`libreoffice`/`office`), journal UTF-8, docstrings à jour.
- `Backend/app/config.py` — réglages `conversion_moteur_word` (défaut `auto`) et
  `conversion_word_delai_office_s` (défaut 35).
- `Backend/tests/test_conversion_office.py` — 10 nouveaux tests : délai court 35 s, délai configurable et
  borné, modes `libreoffice` (direct, et repli Office si absent) et `office` (délai complet, pas de bascule),
  `auto` sans LibreOffice (délai complet), échec des deux moteurs (message complet), Excel inchangé,
  normalisation du réglage.
- `Backend/scripts/diagnostic_conversion.py` — option `--moteur`, encodage UTF-8 des relevés PowerShell
  (imprimantes, Spooler).
- `.env.example`, `README.md`, `docs/architecture.md` — documentation des deux réglages.

## Vérifications exécutées (Linux, sans Windows ni Office)

- `uv sync` puis `uv run pytest` : **106 réussis, 3 ignorés** (les 3 fichiers de tests d'API attendent
  `TEST_DATABASE_URL`), dont les 27 de `tests/test_conversion_office.py`.
- Les 2 échecs historiques liés au paquet `liteparse` disparaissent : `uv sync` l'installe depuis le lock.
- `python scripts/diagnostic_conversion.py --help` et les réglages par défaut vérifiés
  (`moteur_word = auto`, `delai_court = 35`).

## Hors périmètre : test_partage_collaboration.py cassé dans le dépôt

À HEAD du dépôt cloné (commit « issues »), `Backend/tests/test_partage_collaboration.py` ne se collecte pas :
`app/services/partage.py` importe `DocumentLienPartage`, `DocumentPartage`, `DossierMembre`, `Favori` et
`NotificationInterne`, tous absents de `app/db/metier.py` (le routeur partage n'est pas monté dans
`app/main.py`, l'API démarre donc). Cassé avant cette livraison, sans lien avec la conversion, non corrigé ici
(décision de modèle de données à prendre côté projet). La suite a été lancée avec
`--ignore=tests/test_partage_collaboration.py`.

## Non exécuté (même limite que la livraison précédente)

Le script PowerShell et la conversion Office réelle n'ont pas pu l'être ici (pas de Windows ni d'Office dans
l'environnement) ; la logique Python est testée, pas le pilotage COM réel. Sur le serveur, les deux commandes
de diagnostic ci-dessus mesurent le comportement réel bout en bout.
