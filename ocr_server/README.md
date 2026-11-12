# ocr_server

Serveur OCR PaddleOCR, lancé séparément du backend car ses dépendances sont fragiles.
Source : dossier `ocr/paddleocr` du dépôt run-llama/liteparse (`server.py` copié ici, seul changement : écoute sur 127.0.0.1 par défaut).

- Lancement local : `uv run server.py` (port 8829 par défaut ; `OCR_HOST` et `OCR_PORT` pour changer)
- Réglages CPU par variables d'environnement : PADDLE_CPU_THREADS, PADDLE_TEXTLINE_ORIENTATION, PADDLE_DET_LIMIT_SIDE_LEN
- Si l'erreur ConvertPirAttribute2RuntimeAttribute apparaît : désactiver oneDNN (enable_mkldnn=False)
- Appelé par `Backend/app/clients/ocr_paddle.py` (images) et par LiteParse (PDF scannés) via POST /ocr ; GET /health pour la santé
- Le backend demande l'OCR en français (`OCR_LANGUAGE=fr`)
