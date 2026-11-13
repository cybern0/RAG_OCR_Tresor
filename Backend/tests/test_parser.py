"""Tests du parsing et du découpage : texte, CSV/XLSX, tableaux markdown, reconstruction de tableaux OCR."""

from pathlib import Path

import pytest
from langchain_core.documents import Document

from app.clients.ocr_paddle import OcrBox
from app.services.ingestion.chunking import chunk_documents, split_table
from app.services.ingestion.parser import (
    IngestionError, ocr_boxes_to_documents, parse_file, rows_to_markdown, split_markdown_tables,
)


def test_texte_simple(tmp_path: Path):
    f = tmp_path / "note.txt"
    f.write_text("Réunion du 3 mai.\nPrésents : Rabe, Soa.", encoding="utf-8")
    parsed = parse_file(f)
    assert not parsed.has_tabular and not parsed.ocr_utilise
    assert "Rabe" in parsed.documents[0].page_content


def test_csv_point_virgule_et_accents(tmp_path: Path):
    f = tmp_path / "stock.csv"
    f.write_text("Produit;Quantité;Prix\nRiz;10;2 500 Ar\nHuile;4;7 000 Ar\n", encoding="utf-8")
    parsed = parse_file(f)
    assert parsed.has_tabular
    md = parsed.documents[0].page_content
    assert "| Produit | Quantité | Prix |" in md and "| Riz | 10 | 2 500 Ar |" in md
    assert parsed.documents[0].metadata["est_tableau"] is True


def test_xlsx_une_feuille_par_document(tmp_path: Path):
    from openpyxl import Workbook

    wb = Workbook()
    wb.active.title = "Janvier"
    wb.active.append(["Agent", "Montant"]); wb.active.append(["Rabe", 1200])
    wb.create_sheet("Février").append(["Agent", "Montant"])
    wb["Février"].append(["Soa", 800])
    f = tmp_path / "paie.xlsx"
    wb.save(f)
    parsed = parse_file(f)
    assert parsed.nb_pages == 2 and len(parsed.documents) == 2
    assert "Janvier" in parsed.documents[0].page_content and "| Rabe | 1200 |" in parsed.documents[0].page_content
    assert parsed.documents[1].metadata["page"] == 2


def test_fichier_vide_ou_inconnu(tmp_path: Path):
    vide = tmp_path / "vide.txt"; vide.write_text("   \n")
    with pytest.raises(IngestionError):
        parse_file(vide)
    inconnu = tmp_path / "prog.exe"; inconnu.write_bytes(b"MZ")
    with pytest.raises(IngestionError):
        parse_file(inconnu)


def test_split_markdown_tables():
    md = "Intro\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\nFin"
    segs = split_markdown_tables(md)
    assert [s[1] for s in segs] == [False, True, False]
    # des lignes commençant par | sans séparateur ne sont pas un tableau
    assert split_markdown_tables("| juste | une ligne |")[0][1] is False


def test_rows_to_markdown_complete_et_echappe():
    md = rows_to_markdown([["a", "b|c"], ["1"], [None, None]])
    assert md.splitlines()[0] == "| a | b\\|c |"
    assert md.splitlines()[2] == "| 1 |  |"
    assert len(md.splitlines()) == 3  # ligne vide supprimée


def test_chunk_de_tableau_repete_l_en_tete():
    rows = [["Produit", "Qté"]] + [[f"article {i}", i] for i in range(120)]
    pieces = split_table(rows_to_markdown(rows), 500)
    assert len(pieces) > 1
    for p in pieces:
        assert p.splitlines()[0] == "| Produit | Qté |" and p.splitlines()[1].startswith("| ---")
    # aucune ligne perdue ni dupliquée
    body = [ln for p in pieces for ln in p.splitlines()[2:]]
    assert len(body) == 120


def test_chunk_documents_metadonnees_et_index():
    docs = [
        Document(page_content="Phrase. " * 400, metadata={"page": 2, "est_tableau": False}),
        Document(page_content="| a |\n|---|\n| 1 |", metadata={"page": 3, "est_tableau": True}),
    ]
    chunks = chunk_documents(docs, doc_id=7, nom_fichier="x.pdf")
    assert [c.metadata["chunk_index"] for c in chunks] == list(range(len(chunks)))
    assert all(c.metadata["doc_id"] == 7 and c.metadata["nom_fichier"] == "x.pdf" for c in chunks)
    assert chunks[-1].metadata["est_tableau"] is True and chunks[-1].metadata["page"] == 3
    assert max(len(c.page_content) for c in chunks if not c.metadata["est_tableau"]) <= 1000


def _box(text, x1, y1, x2=None, y2=None):
    return OcrBox(text, x1, y1, x2 or x1 + 80, y2 or y1 + 20, 0.99)


def test_ocr_reconstruit_un_tableau():
    boxes = [_box("Reçu de paiement", 50, 10)]
    for row, y in enumerate([60, 90, 120, 150]):
        boxes += [_box(["Nom", "Rabe", "Soa", "Lala"][row], 50, y),
                  _box(["Montant", "1200", "800", "950"][row], 250, y),
                  _box(["Date", "01/05", "02/05", "03/05"][row], 450, y)]
    boxes.append(_box("Fin du document", 50, 200))
    docs = ocr_boxes_to_documents(boxes)
    kinds = [d.metadata["est_tableau"] for d in docs]
    assert kinds == [False, True, False]
    assert "| Nom | Montant | Date |" in docs[1].page_content
    assert "| Rabe | 1200 | 01/05 |" in docs[1].page_content


def test_ocr_texte_sans_tableau():
    boxes = [_box("Bonjour", 50, 10), _box("le monde", 150, 10), _box("Deuxième ligne", 50, 50)]
    docs = ocr_boxes_to_documents(boxes)
    assert len(docs) == 1 and docs[0].page_content == "Bonjour le monde\nDeuxième ligne"
    assert not docs[0].metadata["est_tableau"]


# --- cases « tableaux / images » et OCR des images embarquées --------------------------------------------------------

def test_regle_des_cases_selon_le_type():
    from app.services.ingestion.parser import apply_flags, forced_flags

    assert forced_flags(".csv") == (True, False) and forced_flags(".XLSX") == (True, False)
    assert forced_flags(".xls") == (True, False) and forced_flags(".ods") == (True, False)
    assert forced_flags(".png") == (False, True) and forced_flags(".jpeg") == (False, True)
    assert forced_flags(".pdf") == (False, False) and forced_flags(".docx") == (False, False)
    assert apply_flags(".csv", False, False) == (True, False)        # imposé : l'envoi du client ne compte pas
    assert apply_flags(".png", True, False) == (True, True)          # libre + imposé
    assert apply_flags(".pdf", True, True) == (True, True)           # libre : ce que coche l'utilisateur
    assert apply_flags(".pdf", False, False) == (False, False)


def test_ocr_des_images_embarquees(monkeypatch):
    """Les images embarquées sont lues par l'OCR en plus du texte ; les petites, les doublons et celles des pages déjà
    passées en OCR intégral (scans) sont ignorées."""
    from types import SimpleNamespace as NS

    from app.services.ingestion import parser

    def img(page=1, w=300, h=200, dup=None, data=b"x"):
        return NS(page=page, width=w, height=h, duplicate_of=dup, bytes=data, format="png")

    images = [img(), img(w=30, h=30), img(dup="p1_1"), img(data=b""), img(page=2), img(page=3)]
    seen = []
    monkeypatch.setattr(
        parser, "ocr_image",
        lambda path: seen.append(path) or [OcrBox("Facture n° 42", 0, 0, 100, 10, 0.9)],
    )
    docs = parser._ocr_embedded_images(images, skip_pages={2})
    assert len(seen) == 2 and len(docs) == 2                     # page 1 (1 image utile) et page 3 ; pas la page 2
    assert [d.metadata["page"] for d in docs] == [1, 3] and all(d.metadata["image"] for d in docs)
    assert "Facture n° 42" in docs[0].page_content and "image de la page 1" in docs[0].page_content


def test_ocr_image_embarquee_en_echec_est_une_erreur_claire(monkeypatch):
    from types import SimpleNamespace as NS

    from app.clients.ocr_paddle import OcrError
    from app.services.ingestion import parser

    def boom(path):
        raise OcrError("serveur éteint")

    monkeypatch.setattr(parser, "ocr_image", boom)
    images = [NS(page=4, width=300, height=200, duplicate_of=None, bytes=b"x", format="png")]
    with pytest.raises(IngestionError, match="page 4"):
        parser._ocr_embedded_images(images, set())
