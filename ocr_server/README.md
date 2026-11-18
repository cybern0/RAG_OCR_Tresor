# ocr_server

Serveur OCR PaddleOCR, lancé séparément du backend car ses dépendances sont fragiles.
Source : dossier `ocr/paddleocr` du dépôt run-llama/liteparse (`server.py` copié ici, seul changement : écoute sur 127.0.0.1 par défaut).

- Lancement local : `uv run server.py` (port 8829 par défaut ; `OCR_HOST` et `OCR_PORT` pour changer)
- Réglages CPU par variables d'environnement : PADDLE_CPU_THREADS, PADDLE_TEXTLINE_ORIENTATION, PADDLE_DET_LIMIT_SIDE_LEN
- Si l'erreur ConvertPirAttribute2RuntimeAttribute apparaît : désactiver oneDNN (enable_mkldnn=False)
- Appelé par `Backend/app/clients/ocr_paddle.py` (images) et par LiteParse (PDF scannés) via POST /ocr ; GET /health pour la santé
- Le backend demande l'OCR en français (`OCR_LANGUAGE=fr`)
- **Serveur OCR personnalisé sans /health accepté** : la sonde de santé du backend (`ping_ocr`) considère
  le serveur « opérationnel » dès qu'il répond — un 404 sur /health suffit, POST /ocr reste ce qui compte.
  Seul un hôte injoignable (serveur arrêté, mauvais port) affiche « Serveur OCR : Indisponible » dans
  l'administration. Utiliser le `server.py` de CE dossier (copie avec /health, écoute 127.0.0.1 par
  défaut — pas 0.0.0.0) plutôt que l'original liteparse.
