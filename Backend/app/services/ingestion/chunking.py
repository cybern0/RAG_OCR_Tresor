"""Découpage en chunks (RecursiveCharacterTextSplitter) ; garde doc_id, page et nom de fichier
en métadonnées pour citer les sources.

Les tableaux (est_tableau) ne sont jamais coupés au milieu d'une ligne : chaque morceau reprend
l'en-tête du tableau, pour que le LLM sache à quelle colonne correspond chaque valeur.
"""

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import get_settings


def split_table(text: str, max_chars: int) -> list[str]:
    """Découpe un tableau markdown par groupes de lignes, en répétant les deux lignes d'en-tête."""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(text) <= max_chars or len(lines) <= 3:
        return [text.strip()]
    header = lines[:2] if len(lines) > 1 and set(lines[1].replace("|", "").strip()) <= set("-: ") else lines[:1]
    body = lines[len(header):]
    head_text = "\n".join(header)
    parts: list[str] = []
    current: list[str] = []
    size = len(head_text)
    for line in body:
        if current and size + len(line) + 1 > max_chars:
            parts.append(head_text + "\n" + "\n".join(current))
            current, size = [], len(head_text)
        current.append(line)
        size += len(line) + 1
    if current:
        parts.append(head_text + "\n" + "\n".join(current))
    return parts


def chunk_documents(docs: list[Document], doc_id: int, nom_fichier: str) -> list[Document]:
    s = get_settings()
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=s.chunk_size,
        chunk_overlap=s.chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks: list[Document] = []
    for doc in docs:
        text = doc.page_content.strip()
        if not text:
            continue
        if doc.metadata.get("est_tableau"):
            pieces = split_table(text, s.chunk_size * 2)
        else:
            pieces = splitter.split_text(text)
        for piece in pieces:
            if not piece.strip():
                continue
            meta = {**doc.metadata, "doc_id": doc_id, "nom_fichier": nom_fichier}
            meta.setdefault("est_tableau", False)
            chunks.append(Document(page_content=piece, metadata=meta))
    for index, chunk in enumerate(chunks):
        chunk.metadata["chunk_index"] = index
    return chunks
