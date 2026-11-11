# ocr_server

Serveur OCR PaddleOCR, lancé séparément du backend car ses dépendances sont fragiles.
Source : dossier `ocr/paddleocr` du dépôt run-llama/liteparse (à copier ici : `server.py`).

- Lancement local : `uv run server.py` (port 8829 par défaut)
- Réglages CPU par variables d'environnement : PADDLE_CPU_THREADS, PADDLE_TEXTLINE_ORIENTATION, PADDLE_DET_LIMIT_SIDE_LEN
- Si l'erreur ConvertPirAttribute2RuntimeAttribute apparaît : désactiver oneDNN (enable_mkldnn=False)
- Appelé par `backend/app/clients/ocr_paddle.py` via POST /ocr
