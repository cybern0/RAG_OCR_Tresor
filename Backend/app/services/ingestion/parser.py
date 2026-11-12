"""Parsing des fichiers vers du texte au format LangChain (Document).

- PDF, Office, OpenDocument : LiteParse (markdown page par page, OCR via le serveur PaddleOCR si besoin).
  Les formats Office/OpenDocument demandent LibreOffice sur la machine du backend.
- Images : client OCR (clients/ocr_paddle.py), avec reconstruction des tableaux par position des boîtes.
- CSV / XLSX : lecture directe, chaque feuille devient un tableau markdown (est_tableau).
- TXT / MD : lecture directe.

Chaque Document porte en métadonnées : page (numéro de page, de feuille pour un classeur) et est_tableau.
"""

import csv
import re
import statistics
from dataclasses import dataclass
from pathlib import Path

from langchain_core.documents import Document

from app.clients.ocr_paddle import OcrBox, OcrError, ocr_image
from app.config import get_settings

TEXT_EXT = {".txt", ".md"}
TABULAR_EXT = {".csv", ".xlsx"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}
DOCUMENT_EXT = {".pdf", ".docx", ".doc", ".pptx", ".ppt", ".odt", ".ods", ".odp", ".rtf", ".xls"}
ALLOWED_EXT = TEXT_EXT | TABULAR_EXT | IMAGE_EXT | DOCUMENT_EXT

MAX_TABLE_ROWS = 50_000
_TABLE_SEPARATOR = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$")


class IngestionError(RuntimeError):
    """Erreur affichable à l'utilisateur dans le champ message_erreur du document."""


@dataclass
class ParsedFile:
    documents: list[Document]
    nb_pages: int | None
    ocr_utilise: bool
    has_tabular: bool


# --- Outils markdown -----------------------------------------------------------------------------------------

def _cell(value: object) -> str:
    text = "" if value is None else str(value)
    return " ".join(text.replace("|", "\\|").split())


def rows_to_markdown(rows: list[list[object]]) -> str:
    """La première ligne sert d'en-tête. Les lignes plus courtes sont complétées."""
    rows = [r for r in rows if any(_cell(c) for c in r)]
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    header = [_cell(c) or f"col{i + 1}" for i, c in enumerate(rows[0] + [None] * (width - len(rows[0])))]
    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join("---" for _ in header) + " |"]
    for r in rows[1:]:
        cells = [_cell(c) for c in r] + [""] * (width - len(r))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def split_markdown_tables(markdown: str) -> list[tuple[str, bool]]:
    """Sépare un texte markdown en segments (texte, est_tableau). Un tableau = lignes consécutives
    commençant par « | » et contenant une ligne de séparation (---)."""
    segments: list[tuple[str, bool]] = []
    buffer: list[str] = []
    in_table = False

    def flush() -> None:
        nonlocal buffer
        text = "\n".join(buffer).strip()
        if text:
            is_table = in_table and any(_TABLE_SEPARATOR.match(ln) for ln in buffer)
            segments.append((text, is_table))
        buffer = []

    for line in markdown.splitlines():
        is_row = line.lstrip().startswith("|")
        if is_row != in_table:
            flush()
            in_table = is_row
        buffer.append(line)
    flush()
    return segments


def _documents_from_markdown(markdown: str, page: int | None) -> list[Document]:
    docs = []
    for text, is_table in split_markdown_tables(markdown):
        docs.append(Document(page_content=text, metadata={"page": page, "est_tableau": is_table}))
    return docs


# --- Tableaux (CSV, XLSX) --------------------------------------------------------------------------------------

def _read_csv_rows(path: Path) -> list[list[object]]:
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            sample = path.read_text(encoding=encoding)[:8192]
            break
        except UnicodeDecodeError:
            continue
    else:
        raise IngestionError("Encodage du fichier CSV non reconnu.")
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    with path.open(newline="", encoding=encoding) as f:
        rows = []
        for row in csv.reader(f, dialect):
            rows.append(row)
            if len(rows) > MAX_TABLE_ROWS:
                raise IngestionError(f"Tableau trop grand (plus de {MAX_TABLE_ROWS} lignes).")
        return rows


def parse_tabular(path: Path, ext: str) -> ParsedFile:
    """CSV et XLSX : un tableau markdown par feuille (page = numéro de feuille)."""
    sheets: list[tuple[str, list[list[object]]]] = []
    if ext == ".csv":
        sheets.append(("", _read_csv_rows(path)))
    else:
        from openpyxl import load_workbook

        try:
            workbook = load_workbook(path, read_only=True, data_only=True)
        except Exception as e:  # fichier corrompu ou protégé
            raise IngestionError(f"Classeur illisible : {e}") from e
        for ws in workbook.worksheets:
            rows = []
            for row in ws.iter_rows(values_only=True):
                rows.append(list(row))
                if len(rows) > MAX_TABLE_ROWS:
                    raise IngestionError(f"Feuille « {ws.title} » trop grande (plus de {MAX_TABLE_ROWS} lignes).")
            sheets.append((ws.title, rows))
        workbook.close()

    docs = []
    for index, (title, rows) in enumerate(sheets, start=1):
        markdown = rows_to_markdown(rows)
        if markdown:
            text = f"Feuille : {title}\n\n{markdown}" if title else markdown
            docs.append(Document(page_content=text, metadata={"page": index, "feuille": title, "est_tableau": True}))
    return ParsedFile(docs, nb_pages=len(sheets) or None, ocr_utilise=False, has_tabular=bool(docs))


# --- Images (OCR) ------------------------------------------------------------------------------------------------

def _group_lines(boxes: list[OcrBox]) -> list[list[OcrBox]]:
    """Regroupe les boîtes OCR par ligne visuelle (même hauteur), triées de gauche à droite."""
    if not boxes:
        return []
    tolerance = 0.6 * statistics.median(b.height for b in boxes)
    lines: list[list[OcrBox]] = []
    for box in sorted(boxes, key=lambda b: b.cy):
        if lines and abs(box.cy - statistics.mean(b.cy for b in lines[-1])) <= tolerance:
            lines[-1].append(box)
        else:
            lines.append([box])
    return [sorted(line, key=lambda b: b.x1) for line in lines]


def _column_starts(table_lines: list[list[OcrBox]]) -> list[float]:
    """Positions de colonnes : regroupe les x de départ des boîtes proches les unes des autres."""
    xs = sorted(b.x1 for line in table_lines for b in line)
    gap = 2 * statistics.median(b.height for line in table_lines for b in line)
    starts = [xs[0]]
    for x in xs[1:]:
        if x - starts[-1] > gap:
            starts.append(x)
    return starts


def _table_markdown(table_lines: list[list[OcrBox]]) -> str:
    starts = _column_starts(table_lines)
    rows: list[list[object]] = []
    for line in table_lines:
        cells = [""] * len(starts)
        for box in line:
            col = max(i for i, s in enumerate(starts) if s <= box.x1 + 1e-6) if box.x1 >= starts[0] else 0
            cells[col] = (cells[col] + " " + box.text).strip()
        rows.append(cells)
    return rows_to_markdown(rows)


def ocr_boxes_to_documents(boxes: list[OcrBox], force_tabular: bool = False) -> list[Document]:
    """Texte courant + tableaux détectés (au moins 3 lignes consécutives à plusieurs colonnes ;
    au moins 2 lignes si l'utilisateur a indiqué que le document contient des tableaux)."""
    min_cols = 2 if force_tabular else 3
    min_rows = 2 if force_tabular else 3
    lines = _group_lines(boxes)
    wide = [len(line) >= min_cols for line in lines]

    docs: list[Document] = []
    text_buffer: list[str] = []

    def flush_text() -> None:
        if text_buffer:
            docs.append(Document(page_content="\n".join(text_buffer), metadata={"page": 1, "est_tableau": False}))
            text_buffer.clear()

    i = 0
    while i < len(lines):
        if wide[i]:
            j = i
            while j < len(lines) and wide[j]:
                j += 1
            if j - i >= min_rows:
                flush_text()
                docs.append(
                    Document(page_content=_table_markdown(lines[i:j]), metadata={"page": 1, "est_tableau": True})
                )
                i = j
                continue
        text_buffer.append(" ".join(b.text for b in lines[i]))
        i += 1
    flush_text()
    return docs


def parse_image(path: Path, force_tabular: bool = False) -> ParsedFile:
    try:
        boxes = ocr_image(path)
    except OcrError as e:
        raise IngestionError(str(e)) from e
    docs = ocr_boxes_to_documents(boxes, force_tabular)
    return ParsedFile(docs, nb_pages=1, ocr_utilise=True, has_tabular=any(d.metadata["est_tableau"] for d in docs))


# --- PDF, Word, PowerPoint... (LiteParse) --------------------------------------------------------------------------

MIN_NATIVE_CHARS = 30  # en dessous, une page est considérée comme un scan (pas de couche texte)


def _liteparse(ocr: bool):
    from liteparse import LiteParse

    s = get_settings()
    return LiteParse(
        output_format="markdown",
        image_mode="off",
        ocr_enabled=ocr,
        ocr_server_url=s.ocr_endpoint if ocr else None,
        ocr_language=s.ocr_language,
        ocr_failure_fatal=True,  # mieux vaut une erreur claire qu'un document indexé avec des pages vides
        quiet=True,
    )


def parse_document(path: Path) -> ParsedFile:
    """Lecture en deux temps : d'abord sans OCR (rapide, et le serveur OCR peut être éteint) ;
    l'OCR n'est lancé que si une page n'a pas de texte natif (scan)."""
    from liteparse import ParseError

    try:
        result = _liteparse(ocr=False).parse(str(path))
        needs_ocr = any(len((p.markdown or p.text).strip()) < MIN_NATIVE_CHARS for p in result.pages)
        if needs_ocr:
            result = _liteparse(ocr=True).parse(str(path))
    except ParseError as e:
        raise IngestionError(f"Lecture du document impossible : {str(e)[:400]}") from e

    docs: list[Document] = []
    ocr_used = False
    for page in result.pages:
        # confidence n'est renseignée que pour le texte venant de l'OCR
        ocr_used = ocr_used or any(item.confidence is not None for item in page.text_items)
        docs.extend(_documents_from_markdown(page.markdown or page.text, page.page_num))
    return ParsedFile(
        docs,
        nb_pages=result.total_pages,
        ocr_utilise=ocr_used,
        has_tabular=any(d.metadata["est_tableau"] for d in docs),
    )


def parse_text(path: Path) -> ParsedFile:
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            text = path.read_text(encoding=encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise IngestionError("Encodage du fichier texte non reconnu.")
    docs = _documents_from_markdown(text, None)
    return ParsedFile(docs, nb_pages=None, ocr_utilise=False, has_tabular=any(d.metadata["est_tableau"] for d in docs))


# --- Point d'entrée ------------------------------------------------------------------------------------------------

def parse_file(path: Path, force_tabular: bool = False) -> ParsedFile:
    ext = path.suffix.lower()
    if ext in TABULAR_EXT:
        parsed = parse_tabular(path, ext)
    elif ext in IMAGE_EXT:
        parsed = parse_image(path, force_tabular)
    elif ext in TEXT_EXT:
        parsed = parse_text(path)
    elif ext in DOCUMENT_EXT:
        parsed = parse_document(path)
    else:
        raise IngestionError(f"Type de fichier non pris en charge : {ext or 'sans extension'}.")
    if not any(d.page_content.strip() for d in parsed.documents):
        raise IngestionError("Aucun texte n'a pu être extrait de ce fichier.")
    # l'indication de l'utilisateur (« contient des tableaux ») compte même si la détection n'a rien trouvé
    parsed.has_tabular = parsed.has_tabular or force_tabular
    return parsed
