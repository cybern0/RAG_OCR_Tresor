# Clients Ollama (LLM + embeddings), créés une fois et réutilisés.
# Attention : la classe LangChain s'appelle OllamaEmbeddings (et non EmbeddingOllama) : l'import ci-dessous est à corriger.
# L'URL vient de config.py (par défaut http://localhost:11434).

#  ollama list
# NAME                             ID              SIZE      MODIFIED
# qwen3:4b-instruct-2507-q4_K_M    0edcdef34593    2.5 GB    48 minutes ago
# embeddinggemma:300m-qat-q4_0     101341d65c2c    238 MB    2 hours ago

from langchain_ollama import ChatOllama, EmbeddingOllama