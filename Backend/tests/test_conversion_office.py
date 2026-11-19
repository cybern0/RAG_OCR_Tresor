"""Tests de la conversion bureautique dépendante de l'OS : LibreOffice sous Linux,
Microsoft Office (COM/PowerShell, repli LibreOffice) sous Windows."""

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services import conversion_office as conv
from app.services.conversion_office import (
    ConversionImpossibleError, ConversionTropLongueError, OfficeIndisponibleError, convertir_vers_pdf, suites_disponibles,
)


def _shutil_stub(which=lambda name: None):
    return SimpleNamespace(which=which)


def _subprocess_stub(run):
    return SimpleNamespace(run=run, TimeoutExpired=subprocess.TimeoutExpired, CalledProcessError=subprocess.CalledProcessError)


# --- Détection des suites disponibles --------------------------------------------------------------------------------

def test_sous_linux_libreoffice_seul(monkeypatch):
    monkeypatch.setattr(conv, "IS_WINDOWS", False)
    monkeypatch.setattr(conv, "shutil", _shutil_stub(which=lambda name: "/usr/bin/soffice" if name == "soffice" else None))
    assert suites_disponibles() == ["LibreOffice"]


def test_sous_windows_office_puis_libreoffice(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(conv, "IS_WINDOWS", True)
    monkeypatch.setattr(conv, "shutil", _shutil_stub())
    powershell, soffice = tmp_path / "powershell.exe", tmp_path / "soffice.exe"
    powershell.write_text(""), soffice.write_text("")
    monkeypatch.setattr(conv, "_POWERSHELL", [powershell])
    monkeypatch.setattr(conv, "_LIBREOFFICE_EXE", [soffice])
    assert suites_disponibles() == ["Microsoft Office", "LibreOffice"]


def test_sous_windows_sans_office_libreoffice_seul(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(conv, "IS_WINDOWS", True)
    monkeypatch.setattr(conv, "shutil", _shutil_stub())          # rien dans le PATH
    soffice = tmp_path / "soffice.exe"; soffice.write_text("")
    monkeypatch.setattr(conv, "_LIBREOFFICE_EXE", [soffice])
    assert suites_disponibles() == ["LibreOffice"]


# --- Conversion sous Linux (comportement historique) -----------------------------------------------------------------

def test_conversion_linux_appelle_soffice(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(conv, "IS_WINDOWS", False)
    monkeypatch.setattr(conv, "shutil", _shutil_stub(which=lambda name: "/usr/bin/soffice"))
    appels = {}

    def fake_run(cmd, **kwargs):
        appels["cmd"] = cmd
        (tmp_path / "rapport.pdf").write_bytes(b"%PDF-1.4")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(conv, "subprocess", _subprocess_stub(fake_run))
    source = tmp_path / "rapport.docx"; source.write_bytes(b"fake docx")
    assert convertir_vers_pdf(source, tmp_path) == tmp_path / "rapport.pdf"
    cmd = appels["cmd"]
    assert cmd[0] == "/usr/bin/soffice" and "--headless" in cmd
    assert cmd[cmd.index("--convert-to") + 1] == "pdf" and cmd[cmd.index("--outdir") + 1] == str(tmp_path)
    assert "-env:UserInstallation=" in cmd[1]  # profil isolé


def test_linux_sans_libreoffice_erreur_claire(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(conv, "IS_WINDOWS", False)
    monkeypatch.setattr(conv, "shutil", _shutil_stub())
    with pytest.raises(OfficeIndisponibleError, match="LibreOffice"):
        convertir_vers_pdf(tmp_path / "rapport.docx", tmp_path)


def test_linux_timeout(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(conv, "IS_WINDOWS", False)
    monkeypatch.setattr(conv, "shutil", _shutil_stub(which=lambda name: "/usr/bin/soffice"))

    def lent(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, 120)

    monkeypatch.setattr(conv, "subprocess", _subprocess_stub(lent))
    source = tmp_path / "rapport.docx"; source.write_bytes(b"fake docx")
    with pytest.raises(ConversionTropLongueError):
        convertir_vers_pdf(source, tmp_path)


def test_type_non_convertible(tmp_path: Path):
    with pytest.raises(ConversionImpossibleError, match="non convertible"):
        convertir_vers_pdf(tmp_path / "image.png", tmp_path)


# --- Conversion sous Windows : Office d'abord, LibreOffice en repli ---------------------------------------------------

def _windows_sans_path(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(conv, "IS_WINDOWS", True)
    monkeypatch.setattr(conv, "shutil", _shutil_stub())
    powershell = tmp_path / "powershell.exe"; powershell.write_text("")
    monkeypatch.setattr(conv, "_POWERSHELL", [powershell])
    return powershell


def test_windows_office_absent_repli_sur_libreoffice(monkeypatch, tmp_path: Path):
    _windows_sans_path(monkeypatch, tmp_path)
    soffice = tmp_path / "soffice.exe"; soffice.write_text("")
    monkeypatch.setattr(conv, "_LIBREOFFICE_EXE", [soffice])
    appels = []

    def fake_run(cmd, **kwargs):
        appels.append(cmd[0])
        if "powershell" in cmd[0]:
            return SimpleNamespace(returncode=3, stderr=b"")   # Office absent (COM introuvable)
        (tmp_path / "rapport.pdf").write_bytes(b"%PDF-1.4")
        return SimpleNamespace(returncode=0, stderr=b"")

    monkeypatch.setattr(conv, "subprocess", _subprocess_stub(fake_run))
    source = tmp_path / "rapport.docx"; source.write_bytes(b"fake docx")
    assert convertir_vers_pdf(source, tmp_path) == tmp_path / "rapport.pdf"
    assert len(appels) == 2 and "powershell" in appels[0] and appels[1].endswith("soffice.exe")


def test_windows_sans_office_ni_libreoffice(monkeypatch, tmp_path: Path):
    _windows_sans_path(monkeypatch, tmp_path)
    monkeypatch.setattr(conv, "_LIBREOFFICE_EXE", [])
    monkeypatch.setattr(conv, "subprocess", _subprocess_stub(lambda cmd, **kw: SimpleNamespace(returncode=3, stderr=b"")))
    source = tmp_path / "rapport.docx"; source.write_bytes(b"fake docx")
    with pytest.raises(OfficeIndisponibleError, match="Microsoft Office"):
        convertir_vers_pdf(source, tmp_path)


def test_windows_echec_des_deux_moteurs(monkeypatch, tmp_path: Path):
    _windows_sans_path(monkeypatch, tmp_path)
    soffice = tmp_path / "soffice.exe"; soffice.write_text("")
    monkeypatch.setattr(conv, "_LIBREOFFICE_EXE", [soffice])
    appels = []

    def fake_run(cmd, **kwargs):
        appels.append(cmd[0])
        if "powershell" in cmd[0]:
            return SimpleNamespace(returncode=2, stderr=b"Word could not open the file")
        return SimpleNamespace(returncode=1, stderr=b"soffice failed")

    monkeypatch.setattr(conv, "subprocess", _subprocess_stub(fake_run))
    source = tmp_path / "rapport.docx"; source.write_bytes(b"fake docx")
    with pytest.raises(ConversionImpossibleError, match="Microsoft Office.*LibreOffice"):
        convertir_vers_pdf(source, tmp_path)
    assert len(appels) == 2  # les deux moteurs ont été tentés


def test_windows_office_reussit_sans_repli(monkeypatch, tmp_path: Path):
    _windows_sans_path(monkeypatch, tmp_path)
    monkeypatch.setattr(conv, "_LIBREOFFICE_EXE", [])
    appels = []

    def fake_run(cmd, **kwargs):
        appels.append(cmd[0])
        (tmp_path / "rapport.pdf").write_bytes(b"%PDF-1.4")
        return SimpleNamespace(returncode=0, stderr=b"")

    monkeypatch.setattr(conv, "subprocess", _subprocess_stub(fake_run))
    source = tmp_path / "rapport.docx"; source.write_bytes(b"fake docx")
    assert convertir_vers_pdf(source, tmp_path) == tmp_path / "rapport.pdf"
    assert len(appels) == 1  # Office a suffi, LibreOffice jamais appelé


# --- Ingestion : pré-conversion sous Windows, chemin direct sous Linux ------------------------------------------------

def _liteparse_simule(monkeypatch, parser_mod, markdown="Bonjour la division, voici le compte rendu de la réunion du service."):
    """Remplace LiteParse par un faux qui renvoie une page de texte ; retourne les chemins reçus par parse()."""
    paths = []

    def make(**kwargs):
        def parse(path):
            paths.append(Path(path))
            page = SimpleNamespace(page_num=1, markdown=markdown, text=markdown,
                                   text_items=[SimpleNamespace(confidence=None)])
            return SimpleNamespace(pages=[page], images=[], total_pages=1)

        return SimpleNamespace(parse=parse)

    monkeypatch.setattr(parser_mod, "_liteparse", make)
    return paths


def test_ingestion_windows_preconvertit_avant_liteparse(monkeypatch, tmp_path: Path):
    from app.services.ingestion import parser as p

    monkeypatch.setattr(p, "IS_WINDOWS", True)
    recus = {}

    def fake_convertir(source, sortie_dir, timeout=None):
        recus["source"] = source
        pdf = sortie_dir / (source.stem + ".pdf")
        pdf.write_bytes(b"%PDF-1.4")
        recus["pdf"] = pdf
        return pdf

    monkeypatch.setattr(p, "convertir_vers_pdf", fake_convertir)
    paths = _liteparse_simule(monkeypatch, p)
    source = tmp_path / "note.docx"; source.write_bytes(b"fake docx")
    parsed = p.parse_document(source)
    assert recus["source"] == source
    assert paths == [recus["pdf"]]  # LiteParse lit le PDF converti, pas le docx
    assert "Bonjour" in parsed.documents[0].page_content


def test_ingestion_linux_garde_le_chemin_direct(monkeypatch, tmp_path: Path):
    import liteparse

    from app.services.ingestion import parser as p

    monkeypatch.setattr(p, "IS_WINDOWS", False)

    def bomb(*args, **kwargs):
        raise AssertionError("sous Linux, LiteParse lit le document directement : pas de pré-conversion")

    monkeypatch.setattr(p, "convertir_vers_pdf", bomb)

    class FauxLiteParse:
        def __init__(self, **kwargs):
            pass

        def parse(self, path):
            raise liteparse.ParseError("simulation")

    monkeypatch.setattr(liteparse, "LiteParse", FauxLiteParse)
    source = tmp_path / "note.docx"; source.write_bytes(b"fake docx")
    with pytest.raises(p.IngestionError, match="Lecture du document"):
        p.parse_document(source)


# --- Délai dynamique selon la taille du fichier ----------------------------------------------------------------------

def _fichier(tmp_path: Path, octets: int, nom: str = "gros.docx") -> Path:
    f = tmp_path / nom
    with f.open("wb") as h:
        h.truncate(octets)
    return f


def test_delai_proportionnel_a_la_taille(tmp_path: Path):
    mo = 1024 * 1024
    petit, moyen, gros = _fichier(tmp_path, 1, "p.docx"), _fichier(tmp_path, 10 * mo, "m.docx"), _fichier(tmp_path, 50 * mo, "g.docx")
    assert conv.timeout_pour(petit) == 60 + 15          # arrondi au Mo supérieur : 1 Mo
    assert conv.timeout_pour(moyen) == 60 + 15 * 10
    assert conv.timeout_pour(gros) == 60 + 15 * 50
    assert conv.timeout_pour(petit) < conv.timeout_pour(moyen) < conv.timeout_pour(gros)


def test_delai_plafonne(tmp_path: Path):
    enorme = _fichier(tmp_path, 500 * 1024 * 1024, "enorme.docx")
    assert conv.timeout_pour(enorme) == 1800


def test_convertir_vers_pdf_utilise_le_delai_dynamique(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(conv, "IS_WINDOWS", False)
    source = _fichier(tmp_path, 4 * 1024 * 1024)
    vu: list[int] = []

    def faux_moteur(src, sortie, timeout):
        vu.append(timeout)
        pdf = sortie / (src.stem + ".pdf")
        pdf.write_bytes(b"%PDF")
        return pdf

    monkeypatch.setattr(conv, "_convertir_avec_soffice", faux_moteur)
    convertir_vers_pdf(source, tmp_path)
    assert vu == [60 + 15 * 4]
    convertir_vers_pdf(source, tmp_path, timeout=5)  # un délai explicite l'emporte
    assert vu[-1] == 5
