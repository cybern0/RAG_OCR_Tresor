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


# --- Réglage CONVERSION_MOTEUR_WORD : contourner le blocage de l'export PDF de Word sous COM --------------------------
# Mesuré sur un serveur réel : Word ouvre le document en moins d'une seconde puis se fige pendant l'export PDF,
# pour tout document (même un témoin minimal), sans boîte de dialogue — alors qu'Excel convertit en 2,5 s.
# En « auto » (défaut), Word reçoit un délai court puis LibreOffice termine ; « libreoffice » contourne Word ;
# « office » conserve le comportement d'avant (délai complet, échec en cas de blocage).

def _reglages_stub(monkeypatch, **champs):
    """Remplace get_settings par un objet léger (les fonctions de conversion lisent les réglages elles-mêmes)."""
    base = {"conversion_moteur_word": "auto", "conversion_word_delai_office_s": 35}
    base.update(champs)
    monkeypatch.setattr("app.config.get_settings", lambda: SimpleNamespace(**base))


def _windows_deux_moteurs(monkeypatch, tmp_path: Path):
    """Windows avec Office et LibreOffice tous deux disponibles (binaires factices)."""
    _windows_sans_path(monkeypatch, tmp_path)
    soffice = tmp_path / "soffice.exe"; soffice.write_text("")
    monkeypatch.setattr(conv, "_LIBREOFFICE_EXE", [soffice])


def _nom(cmd) -> str:
    return Path(cmd[0]).name.lower()


def test_word_auto_delai_court_puis_libreoffice(monkeypatch, tmp_path: Path):
    _windows_deux_moteurs(monkeypatch, tmp_path)
    _reglages_stub(monkeypatch)                                   # mode par défaut
    appels: list[tuple[str, int]] = []

    def run(cmd, **kwargs):
        appels.append((_nom(cmd), kwargs["timeout"]))
        if "powershell" in _nom(cmd):
            raise subprocess.TimeoutExpired(cmd, kwargs["timeout"])   # Word bloqué pendant l'export PDF
        (tmp_path / "rapport.pdf").write_bytes(b"%PDF-1.4")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(conv, "subprocess", _subprocess_stub(run))
    source = tmp_path / "rapport.docx"; source.write_bytes(b"fake docx")
    assert convertir_vers_pdf(source, tmp_path, timeout=75) == tmp_path / "rapport.pdf"
    assert appels == [("powershell.exe", 35), ("soffice.exe", 75)]    # délai court pour Word, complet pour LibreOffice


def test_word_delai_court_configurable(monkeypatch, tmp_path: Path):
    _windows_deux_moteurs(monkeypatch, tmp_path)
    _reglages_stub(monkeypatch, conversion_word_delai_office_s=40)   # CONVERSION_WORD_DELAI_OFFICE_S=40
    appels: list[tuple[str, int]] = []

    def run(cmd, **kwargs):
        appels.append((_nom(cmd), kwargs["timeout"]))
        if "powershell" in _nom(cmd):
            raise subprocess.TimeoutExpired(cmd, kwargs["timeout"])
        (tmp_path / "rapport.pdf").write_bytes(b"%PDF-1.4")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(conv, "subprocess", _subprocess_stub(run))
    source = tmp_path / "rapport.docx"; source.write_bytes(b"fake docx")
    assert convertir_vers_pdf(source, tmp_path, timeout=75) == tmp_path / "rapport.pdf"
    assert appels == [("powershell.exe", 40), ("soffice.exe", 75)]


def test_word_delai_court_jamais_plus_que_le_delai_total(monkeypatch, tmp_path: Path):
    _windows_deux_moteurs(monkeypatch, tmp_path)
    _reglages_stub(monkeypatch, conversion_word_delai_office_s=300)  # réglage aberrant : au-delà du délai total
    vu: list[int] = []

    def run(cmd, **kwargs):
        vu.append(kwargs["timeout"])
        if "powershell" in _nom(cmd):
            raise subprocess.TimeoutExpired(cmd, kwargs["timeout"])
        (tmp_path / "rapport.pdf").write_bytes(b"%PDF-1.4")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(conv, "subprocess", _subprocess_stub(run))
    source = tmp_path / "rapport.docx"; source.write_bytes(b"fake docx")
    convertir_vers_pdf(source, tmp_path, timeout=75)
    assert vu[0] == 75  # borné au délai total, pas 300


def test_word_reglage_libreoffice_direct(monkeypatch, tmp_path: Path):
    _windows_deux_moteurs(monkeypatch, tmp_path)
    _reglages_stub(monkeypatch, conversion_moteur_word="libreoffice")
    appels: list[str] = []

    def run(cmd, **kwargs):
        appels.append(_nom(cmd))
        assert kwargs["timeout"] == 75                                # LibreOffice reçoit le délai complet d'emblée
        (tmp_path / "rapport.pdf").write_bytes(b"%PDF-1.4")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(conv, "subprocess", _subprocess_stub(run))
    source = tmp_path / "rapport.docx"; source.write_bytes(b"fake docx")
    assert convertir_vers_pdf(source, tmp_path, timeout=75) == tmp_path / "rapport.pdf"
    assert appels == ["soffice.exe"]                                  # Word jamais démarré


def test_word_reglage_libreoffice_absent_repli_office(monkeypatch, tmp_path: Path):
    _windows_sans_path(monkeypatch, tmp_path)
    monkeypatch.setattr(conv, "_LIBREOFFICE_EXE", [])                 # LibreOffice absent du serveur
    _reglages_stub(monkeypatch, conversion_moteur_word="libreoffice")
    appels: list[tuple[str, int]] = []

    def run(cmd, **kwargs):
        appels.append((_nom(cmd), kwargs["timeout"]))
        (tmp_path / "rapport.pdf").write_bytes(b"%PDF-1.4")
        return SimpleNamespace(returncode=0, stderr=b"")

    monkeypatch.setattr(conv, "subprocess", _subprocess_stub(run))
    source = tmp_path / "rapport.docx"; source.write_bytes(b"fake docx")
    assert convertir_vers_pdf(source, tmp_path, timeout=75) == tmp_path / "rapport.pdf"
    assert appels == [("powershell.exe", 75)]                         # Office prend le relais, délai complet


def test_word_reglage_office_sans_bascule_si_delai(monkeypatch, tmp_path: Path):
    _windows_deux_moteurs(monkeypatch, tmp_path)
    _reglages_stub(monkeypatch, conversion_moteur_word="office")      # comportement d'avant
    appels: list[str] = []

    def run(cmd, **kwargs):
        appels.append(_nom(cmd))
        if "powershell" in _nom(cmd):
            assert kwargs["timeout"] == 75                            # délai complet, pas le délai court
            raise subprocess.TimeoutExpired(cmd, 75)                  # le blocage mesuré sur le serveur
        raise AssertionError("en mode « office », un délai dépassé ne bascule pas sur LibreOffice")

    monkeypatch.setattr(conv, "subprocess", _subprocess_stub(run))
    source = tmp_path / "rapport.docx"; source.write_bytes(b"fake docx")
    with pytest.raises(ConversionTropLongueError, match=r"75 s"):
        convertir_vers_pdf(source, tmp_path, timeout=75)
    assert appels == ["powershell.exe"]


def test_word_auto_sans_libreoffice_delai_complet(monkeypatch, tmp_path: Path):
    _windows_sans_path(monkeypatch, tmp_path)
    monkeypatch.setattr(conv, "_LIBREOFFICE_EXE", [])                 # rien où basculer : Word garde le délai complet
    _reglages_stub(monkeypatch)                                       # « auto » par défaut
    vu: list[int] = []

    def run(cmd, **kwargs):
        vu.append(kwargs["timeout"])
        raise subprocess.TimeoutExpired(cmd, kwargs["timeout"])

    monkeypatch.setattr(conv, "subprocess", _subprocess_stub(run))
    source = tmp_path / "rapport.docx"; source.write_bytes(b"fake docx")
    with pytest.raises(ConversionTropLongueError, match=r"75 s"):
        convertir_vers_pdf(source, tmp_path, timeout=75)
    assert vu == [75]


def test_word_auto_echec_des_deux_moteurs_message_complet(monkeypatch, tmp_path: Path):
    _windows_deux_moteurs(monkeypatch, tmp_path)
    _reglages_stub(monkeypatch)

    def run(cmd, **kwargs):
        if "powershell" in _nom(cmd):
            raise subprocess.TimeoutExpired(cmd, kwargs["timeout"])   # Word bloqué (délai court)
        raise subprocess.CalledProcessError(1, cmd)                   # LibreOffice refuse aussi

    monkeypatch.setattr(conv, "subprocess", _subprocess_stub(run))
    source = tmp_path / "rapport.docx"; source.write_bytes(b"fake docx")
    with pytest.raises(ConversionImpossibleError, match="dépassé le délai.*LibreOffice a refusé"):
        convertir_vers_pdf(source, tmp_path, timeout=75)


def test_excel_delai_depasse_ne_bascule_pas(monkeypatch, tmp_path: Path):
    """Excel fonctionne déjà via Office (mesuré : ~2,5 s) : hors Word, le comportement ne change pas."""
    _windows_deux_moteurs(monkeypatch, tmp_path)
    _reglages_stub(monkeypatch)
    appels: list[str] = []

    def run(cmd, **kwargs):
        appels.append(_nom(cmd))
        if "powershell" in _nom(cmd):
            raise subprocess.TimeoutExpired(cmd, kwargs["timeout"])
        raise AssertionError("Excel ne doit pas basculer sur LibreOffice en cas de délai dépassé")

    monkeypatch.setattr(conv, "subprocess", _subprocess_stub(run))
    source = tmp_path / "budget.xlsx"; source.write_bytes(b"fake xlsx")
    with pytest.raises(ConversionTropLongueError):
        convertir_vers_pdf(source, tmp_path, timeout=75)
    assert appels == ["powershell.exe"]


def test_reglage_moteur_word_normalise(monkeypatch):
    _reglages_stub(monkeypatch, conversion_moteur_word="  LibreOffice ")
    assert conv._reglage_moteur_word() == "libreoffice"               # casse et espaces tolérées
    _reglages_stub(monkeypatch, conversion_moteur_word="word")        # valeur inconnue : défaut
    assert conv._reglage_moteur_word() == "auto"
    _reglages_stub(monkeypatch, conversion_moteur_word="")
    assert conv._reglage_moteur_word() == "auto"


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


# --- Diagnostic : étape de blocage et fermeture d'Office après un délai dépassé ---------------------------------------

def test_delai_office_indique_l_etape_et_ferme_office(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(conv, "IS_WINDOWS", True)
    powershell = tmp_path / "powershell.exe"; powershell.write_text("")
    monkeypatch.setattr(conv, "_POWERSHELL", [powershell])
    monkeypatch.setattr(conv, "shutil", _shutil_stub())
    appels: list[list[str]] = []

    def run(cmd, **kwargs):
        appels.append([str(c) for c in cmd])
        if str(cmd[0]).endswith("powershell.exe"):   # le script a écrit son journal puis s'est bloqué à l'ouverture
            (tmp_path / "_etapes.txt").write_text(
                "10:00:00.100 demarrage_office Word.Application\n10:00:01.000 PID 4321\n"
                "10:00:01.500 office_demarre\n10:00:01.600 ouverture_document\n", encoding="utf-8")
            raise subprocess.TimeoutExpired(cmd, 5)
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr(conv, "subprocess", _subprocess_stub(run))
    source = tmp_path / "rapport.docx"; source.write_bytes(b"x")
    with pytest.raises(ConversionTropLongueError, match=r"5 s.*ouverture du document"):
        conv._convertir_avec_office(source, tmp_path, 5)
    assert ["taskkill", "/F", "/T", "/PID", "4321"] in appels   # Word bloqué est fermé, pas laissé en arrière-plan
