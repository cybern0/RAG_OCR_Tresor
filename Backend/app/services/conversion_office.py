"""Conversion bureautique Office/OpenDocument → PDF par LibreOffice, sur tous les systèmes.

Microsoft Office a été abandonné comme moteur de conversion (décision 11/2026) : son export PDF piloté
par COM se bloquait sur le serveur Windows, pour tout document (diagnostic scripts/diagnostic_conversion.py),
et la cible de production est Linux. Un seul moteur désormais, LibreOffice en mode headless (soffice) :

- Linux : `soffice` (ou `libreoffice`) dans le PATH ;
- Windows : `soffice.exe` aux chemins standards (LiteParse cherche les mêmes).

Plus de pilotage COM/PowerShell, plus d'imprimante à imposer à Word, plus d'application Office à fermer.

LiteParse n'a pas de point d'extension : il appelle LibreOffice en interne. Sous Windows, l'ingestion
pré-convertit donc ici les fichiers Office/OpenDocument en PDF avant de les donner à LiteParse, qui les
lit nativement ; le même PDF est mis en cache pour l'aperçu. Sous Linux, LiteParse lit ces formats
directement (comportement d'origine).

Les trois erreurs possibles sont distinctes : suite bureautique absente (OfficeIndisponibleError),
conversion refusée (ConversionImpossibleError), délai dépassé (ConversionTropLongueError).
"""

import os
import shutil
import subprocess
import threading
from pathlib import Path

IS_WINDOWS = os.name == "nt"

# Formats convertibles en PDF (côté aperçu comme côté ingestion)
WORD_EXT = {".doc", ".docx", ".rtf", ".odt"}
EXCEL_EXT = {".xls", ".xlsx", ".ods"}
POWERPOINT_EXT = {".ppt", ".pptx", ".odp"}
OFFICE_EXT = WORD_EXT | EXCEL_EXT | POWERPOINT_EXT

CONVERSION_TIMEOUT = 120  # valeur de repli si les réglages sont illisibles ; le délai réel dépend de la taille (timeout_pour)
_lock = threading.Lock()  # LibreOffice tolère mal les conversions simultanées

# Chemins standards de LibreOffice sous Windows (LiteParse cherche les mêmes)
_LIBREOFFICE_EXE = [
    Path(r"C:\Program Files\LibreOffice\program\soffice.exe"),
    Path(r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"),
]


class OfficeIndisponibleError(RuntimeError):
    """LibreOffice n'est pas installé sur le serveur."""


class ConversionImpossibleError(RuntimeError):
    """La conversion a été refusée."""


class ConversionTropLongueError(RuntimeError):
    """La conversion a dépassé le délai imparti."""


def timeout_pour(source: Path) -> int:
    """Délai (secondes) accordé à la conversion d'un fichier, selon sa taille :
    base + secondes par Mo (arrondi au Mo supérieur), plafonné. Un fichier de 2 Mo : 90 s ; de 50 Mo : 810 s
    (réglages conversion_timeout_base_s / _par_mo_s / _max_s)."""
    try:
        from app.config import get_settings

        reglages = get_settings()
        base, par_mo, maxi = reglages.conversion_timeout_base_s, reglages.conversion_timeout_par_mo_s, reglages.conversion_timeout_max_s
    except Exception:  # noqa: BLE001 - réglages indisponibles : valeurs par défaut
        base, par_mo, maxi = 60, 15, 1800
    try:
        taille = source.stat().st_size
    except OSError:
        return min(maxi, max(base, CONVERSION_TIMEOUT))
    mo = -(-taille // (1024 * 1024))  # arrondi supérieur
    return max(1, min(maxi, base + mo * par_mo))


def _soffice() -> Path | None:
    binaire = shutil.which("soffice") or shutil.which("libreoffice")
    if binaire:
        return Path(binaire)
    if IS_WINDOWS:
        for chemin in _LIBREOFFICE_EXE:
            if chemin.is_file():
                return chemin
    return None


def suites_disponibles() -> list[str]:
    """Suites bureautiques utilisables sur ce serveur : LibreOffice seul moteur (Microsoft Office abandonné)."""
    return ["LibreOffice"] if _soffice() else []


def _convertir_avec_soffice(source: Path, sortie_dir: Path, timeout: int) -> Path:
    """Conversion headless avec un profil isolé (profil et sorties restent dans sortie_dir, jetable)."""
    binaire = _soffice()
    if binaire is None:
        raise OfficeIndisponibleError(
            "LibreOffice n'est pas installé sur le serveur ; il est nécessaire pour convertir les documents en PDF."
        )
    profil = sortie_dir / "_profil_libreoffice"
    profil.mkdir(exist_ok=True)
    try:
        subprocess.run(
            [str(binaire), f"-env:UserInstallation={profil.as_uri()}", "--headless", "--norestore",
             "--convert-to", "pdf", "--outdir", str(sortie_dir), str(source)],
            check=True, capture_output=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise ConversionTropLongueError(f"La conversion LibreOffice a dépassé le délai imparti ({timeout} s).") from None
    except subprocess.CalledProcessError as e:
        detail = (e.stderr or b"").decode("utf-8", "replace").strip()
        cause = f" : {detail[-300:]}" if detail else "."
        raise ConversionImpossibleError("LibreOffice a refusé la conversion de ce fichier" + cause) from None
    produit = sortie_dir / (source.stem + ".pdf")
    if not produit.is_file():
        raise ConversionImpossibleError("La conversion LibreOffice n'a produit aucun PDF.")
    return produit


def convertir_vers_pdf(source: Path, sortie_dir: Path, timeout: int | None = None) -> Path:
    """Convertit un fichier Office/OpenDocument en PDF dans sortie_dir (même nom, extension .pdf), via LibreOffice.

    Lève OfficeIndisponibleError si LibreOffice n'est pas installé, ConversionImpossibleError si le fichier
    est refusé, ConversionTropLongueError en cas de dépassement du délai (par défaut calculé d'après la
    taille du fichier : timeout_pour).
    """
    if timeout is None:
        timeout = timeout_pour(source)
    if source.suffix.lower() not in OFFICE_EXT:
        raise ConversionImpossibleError(f"Type non convertible en PDF : {source.suffix or 'sans extension'}.")
    with _lock:
        return _convertir_avec_soffice(source, sortie_dir, timeout)
