# Livraison : LibreOffice seul moteur — Microsoft Office abandonné

> Décision du 19/11/2026, après le succès de la bascule Word → LibreOffice (livraison précédente,
> `livraison_conversion_word.md`) : plutôt que de garder deux moteurs dont un bloqué, tout passe par LibreOffice.

## Ce qui change

- **`Backend/app/services/conversion_office.py` réécrit** (~500 lignes → ~120) : un seul moteur, LibreOffice
  headless (`soffice` sous Linux, `soffice.exe` aux chemins standards sous Windows). Disparus : le script
  PowerShell, le pilotage COM de Word/Excel/PowerPoint, l'imprimante imposée à Word, le journal d'étapes,
  le PID Office à fermer, le relevé de fenêtres. Le stderr de LibreOffice est remonté dans le message
  « refusé » : la cause réelle (fichier corrompu, format non supporté...) devient lisible au lieu d'un refus générique.
- **Réglages retirés de la config** : `CONVERSION_WORD_IMPRIMANTE`, `CONVERSION_MOTEUR_WORD`,
  `CONVERSION_WORD_DELAI_OFFICE_S`, `CONVERSION_OFFICE_VISIBLE`, `CONVERSION_WORD_METHODE`. S'il en reste dans un
  `.env` existant, ils sont simplement ignorés (aucune erreur). Restent les réglages de délai `CONVERSION_TIMEOUT_*`.
- **`Backend/scripts/diagnostic_conversion.py` simplifié** : plus d'imprimantes, de Spooler, de `--visible`,
  `--methode`, `--moteur`, `--imprimante`. Il affiche le `soffice` trouvé, convertit chaque fichier donné (ou le
  témoin `--temoin`) et remonte l'erreur réelle. Usage :
  ```
  cd Backend
  python scripts/diagnostic_conversion.py --temoin
  python scripts/diagnostic_conversion.py "C:\chemin\rapport.docx"
  ```
- **Restes de partage supprimés** — décision déjà prise à la refonte « classes de fichiers » mais appliquée
  incomplètement dans le dépôt : `services/partage.py`, `api/routes/partage.py` (route jamais montée dans
  `main.py`) et `tests/test_partage_collaboration.py` importaient des modèles inexistants
  (`DocumentLienPartage`, `DocumentPartage`, `DossierMembre`, `Favori`, `NotificationInterne`) et faisaient
  échouer la collecte de toute la suite de tests. Les classes Pydantic de partage restées dans
  `schemas/document.py` sont sans effet et n'ont pas été touchées.
- **Docs actualisées** : `README.md` (section « Serveur Linux ou Windows »), `docs/architecture.md`,
  `docs/demo_windows11.md` (LibreOffice requis, Office supprimé de la liste d'installation),
  `.env.example`, docstrings (`parser.py`, `apercu.py`). `MODIFICATIONS.md` : nouvelle entrée en tête et les
  trois entrées COM Office marquées `> ABANDONNÉ (11/2026, décision « LibreOffice seul »)`.

## Ce qui ne change pas

- Les délais dynamiques selon la taille (`CONVERSION_TIMEOUT_BASE_S=60`, `PAR_MO_S=15`, `MAX_S=1800`).
- Le PDF préparé au dépôt : `preparer_apercu` convertit dès l'indexation et met le PDF en cache pour l'aperçu ;
  l'indexation lit ce PDF (une seule conversion).
- La pré-conversion des fichiers Office/OpenDocument sous Windows avant LiteParse (filet de sécurité avec nos
  délais et messages) ; sous Linux, LiteParse lit directement, comportement d'origine.
- Les trois erreurs distinctes : `OfficeIndisponibleError` (LibreOffice absent), `ConversionImpossibleError`
  (refus, avec le message de LibreOffice), `ConversionTropLongueError` (délai dépassé).

## Déploiement sur le serveur Windows

1. LibreOffice est déjà installé (la bascule l'a démontré) — rien d'autre à installer ; Microsoft Office peut
   être désinstallé du serveur si aucune autre application ne l'utilise.
2. Retirer les réglages `CONVERSION_WORD_*` / `CONVERSION_OFFICE_VISIBLE` du `.env` (facultatif : ignorés).
3. Redémarrer le backend, puis vérifier : `python scripts/diagnostic_conversion.py --temoin` (doit réussir en
   quelques secondes) et déposer un .docx et un .xlsx de contrôle.

## Vérifications exécutées

- `uv run pytest` : **93 réussis, 3 ignorés** (tests d'API attendent `TEST_DATABASE_URL`) — et surtout
  **la collecte redevient complète** (plus d'erreur d'import partage). Les 13 tests perdus sont ceux du fichier
  partage cassé, supprimé. `tests/test_conversion_office.py` : 14 tests réécrits (LibreOffice seul, Windows
  compris, pré-conversion ingestion, délai dynamique, stderr de refus).
- **Conversion réelle bout en bout** (environnement Linux avec LibreOffice) :
  `python scripts/diagnostic_conversion.py --temoin` → `OK en 1.3 s -> PDF de 13 Ko`. Le même témoin se figeait
  75 s sous Word/COM sur le serveur Windows.

## Non exécuté ici

Le comportement sous Windows réel (détection de `soffice.exe` aux chemins standards) n'a pas pu être exécuté —
pas de Windows dans l'environnement ; la logique est testée par `test_windows_chemin_standard_soffice` et
`test_windows_convertit_avec_soffice_exe` (binaires simulés). Sur le serveur, le diagnostic mesure le réel.
