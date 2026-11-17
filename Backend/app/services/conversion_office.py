"""Conversion bureautique Office/OpenDocument → PDF, adaptée au système du serveur.

L'application doit pouvoir être déployée sur un serveur Linux OU Windows :

- Linux : LibreOffice en mode headless (soffice), comme depuis l'origine ;
- Windows : Microsoft Office installé sur le serveur, piloté via COM (PowerShell) —
  Word pour les documents, Excel pour les tableurs, PowerPoint pour les présentations ;
  si Office est absent, repli sur LibreOffice (soffice.exe) s'il est installé.

LiteParse n'a pas de point d'extension : il appelle LibreOffice en interne. Sur Windows,
l'ingestion pré-convertit donc ici les fichiers Office/OpenDocument en PDF (Microsoft Office)
avant de les donner à LiteParse, qui les lit nativement. Sous Linux, rien ne change
(LiteParse + LibreOffice, comportement d'origine).

Les trois erreurs possibles sont distinctes : suite bureautique absente (OfficeIndisponibleError),
conversion refusée (ConversionImpossibleError), délai dépassé (ConversionTropLongueError).
Note : si le délai est dépassé sous Windows, le process PowerShell est tué mais l'application
Office (WINWORD.EXE...) peut rester en arrière-plan ; elle se refermera à sa prochaine utilisation.
"""

import os
import shutil
import subprocess
import threading
from pathlib import Path

IS_WINDOWS = os.name == "nt"

# Formats pilotables par les applications Office (côté aperçu comme côté ingestion)
WORD_EXT = {".doc", ".docx", ".rtf", ".odt"}
EXCEL_EXT = {".xls", ".xlsx", ".ods"}
POWERPOINT_EXT = {".ppt", ".pptx", ".odp"}
OFFICE_EXT = WORD_EXT | EXCEL_EXT | POWERPOINT_EXT

CONVERSION_TIMEOUT = 120
_lock = threading.Lock()  # Office COM comme LibreOffice tolèrent mal les conversions simultanées

# Chemins standards de LibreOffice sous Windows (LiteParse cherche les mêmes) et de PowerShell
_LIBREOFFICE_EXE = [
    Path(r"C:\Program Files\LibreOffice\program\soffice.exe"),
    Path(r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"),
]
_POWERSHELL = [Path(r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe")]


class OfficeIndisponibleError(RuntimeError):
    """Aucune suite bureautique utilisable sur le serveur."""


class ConversionImpossibleError(RuntimeError):
    """La suite bureautique a refusé le fichier."""


class ConversionTropLongueError(RuntimeError):
    """La conversion a dépassé le délai imparti."""


def _soffice() -> Path | None:
    binaire = shutil.which("soffice") or shutil.which("libreoffice")
    if binaire:
        return Path(binaire)
    if IS_WINDOWS:
        for chemin in _LIBREOFFICE_EXE:
            if chemin.is_file():
                return chemin
    return None


def _powershell() -> Path | None:
    if not IS_WINDOWS:
        return None
    binaire = shutil.which("powershell")
    if binaire:
        return Path(binaire)
    for chemin in _POWERSHELL:
        if chemin.is_file():
            return chemin
    return None


def _message_indisponible() -> str:
    if IS_WINDOWS:
        return ("Aucune suite bureautique disponible sur le serveur : installer Microsoft Office "
                "ou LibreOffice pour convertir les documents en PDF.")
    return ("LibreOffice n'est pas installé sur le serveur ; il est nécessaire pour convertir les documents "
            "en PDF (sur un serveur Windows, Microsoft Office serait utilisé à la place).")


def suites_disponibles() -> list[str]:
    """Noms des suites bureautiques utilisables sur ce serveur, dans l'ordre de préférence."""
    suites: list[str] = []
    if IS_WINDOWS and _powershell():
        suites.append("Microsoft Office")
    if _soffice():
        suites.append("LibreOffice")
    return suites


# --- Moteur Microsoft Office (Windows, via COM piloté en PowerShell) -------------------------------------------------

_SCRIPT_PS = r"""
param(
    [Parameter(Mandatory = $true)][string]$Source,
    [Parameter(Mandatory = $true)][string]$OutDir
)
$ErrorActionPreference = "Stop"

function Fail([string]$Message) {
    [Console]::Error.WriteLine($Message)
    exit 2
}
function OfficeAbsent {
    [Console]::Error.WriteLine("OFFICE_ABSENT")
    exit 3
}

$source = (Resolve-Path -LiteralPath $Source).Path
$outDir = (Resolve-Path -LiteralPath $OutDir).Path
$out = Join-Path $outDir (([System.IO.Path]::GetFileNameWithoutExtension($source)) + ".pdf")
$ext = [System.IO.Path]::GetExtension($source).ToLower()

switch ($ext) {
    { $_ -in ".doc", ".docx", ".rtf", ".odt" } { $progId = "Word.Application" }
    { $_ -in ".xls", ".xlsx", ".ods" }         { $progId = "Excel.Application" }
    { $_ -in ".ppt", ".pptx", ".odp" }         { $progId = "PowerPoint.Application" }
    default { Fail ("Type not convertible by Microsoft Office: " + $ext) }
}

try { $app = New-Object -ComObject $progId } catch { OfficeAbsent }

try {
    switch ($ext) {
        { $_ -in ".doc", ".docx", ".rtf", ".odt" } {
            $app.Visible = $false
            $app.DisplayAlerts = 0
            $doc = $app.Documents.Open($source, $false, $true)   # ConfirmConversions=False, ReadOnly=True
            try { $doc.SaveAs2($out, 17) } finally { $doc.Close($false) }   # 17 = wdFormatPDF
        }
        { $_ -in ".xls", ".xlsx", ".ods" } {
            $app.Visible = $false
            $app.DisplayAlerts = $false
            $wb = $app.Workbooks.Open($source, 0, $true)          # UpdateLinks=0, ReadOnly=True
            try { $wb.ExportAsFixedFormat(0, $out) } finally { $wb.Close($false) }   # 0 = xlTypePDF
        }
        { $_ -in ".ppt", ".pptx", ".odp" } {
            # PowerPoint ne peut pas tourner masque (contrainte du modele COM) ; sans fenetre
            $pres = $app.Presentations.Open($source, $true, $false, $false)   # ReadOnly=True, WithWindow=False
            try { $pres.SaveAs($out, 32) } finally { $pres.Close() }   # 32 = ppSaveAsPDF
        }
    }
} finally {
    $app.Quit()
    [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($app)
}

if (-not (Test-Path -LiteralPath $out)) { Fail "PDF not produced by Microsoft Office." }
exit 0
"""


def _convertir_avec_office(source: Path, sortie_dir: Path, timeout: int) -> Path:
    powershell = _powershell()
    if powershell is None:
        raise OfficeIndisponibleError("PowerShell est introuvable sur ce serveur Windows.")
    script = sortie_dir / "_conversion_office.ps1"
    script.write_text(_SCRIPT_PS, encoding="utf-8-sig")  # BOM requis par PowerShell 5.1
    try:
        proc = subprocess.run(
            [str(powershell), "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
             "-File", str(script), "-Source", str(source), "-OutDir", str(sortie_dir)],
            capture_output=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise ConversionTropLongueError("La conversion Microsoft Office a dépassé le délai imparti.") from None
    produit = sortie_dir / (source.stem + ".pdf")
    stderr = (proc.stderr or b"").decode("utf-8", "replace").strip()
    if proc.returncode == 3:
        raise OfficeIndisponibleError("Microsoft Office n'est pas installé ou inaccessible via COM sur le serveur.")
    if proc.returncode != 0 or not produit.is_file():
        raise ConversionImpossibleError(f"Microsoft Office a refusé la conversion : {stderr[-300:]}")
    return produit


# --- Moteur LibreOffice (Linux, et repli sous Windows) ---------------------------------------------------------------

def _convertir_avec_soffice(source: Path, sortie_dir: Path, timeout: int) -> Path:
    binaire = _soffice()
    if binaire is None:
        raise OfficeIndisponibleError(_message_indisponible())
    profil = sortie_dir / "_profil_libreoffice"
    profil.mkdir()
    try:
        subprocess.run(
            [str(binaire), f"-env:UserInstallation={profil.as_uri()}", "--headless", "--norestore",
             "--convert-to", "pdf", "--outdir", str(sortie_dir), str(source)],
            check=True, capture_output=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise ConversionTropLongueError("La conversion LibreOffice a dépassé le délai imparti.") from None
    except subprocess.CalledProcessError:
        raise ConversionImpossibleError("LibreOffice a refusé la conversion de ce fichier.") from None
    produit = sortie_dir / (source.stem + ".pdf")
    if not produit.is_file():
        raise ConversionImpossibleError("La conversion LibreOffice n'a produit aucun PDF.")
    return produit


# --- Point d'entrée --------------------------------------------------------------------------------------------------

def convertir_vers_pdf(source: Path, sortie_dir: Path, timeout: int = CONVERSION_TIMEOUT) -> Path:
    """Convertit un fichier Office/OpenDocument en PDF dans sortie_dir (même nom, extension .pdf).

    Sous Windows : Microsoft Office d'abord, LibreOffice en repli (l'un des deux peut manquer,
    une erreur de l'un tente l'autre). Ailleurs : LibreOffice. Lève OfficeIndisponibleError si
    aucune suite n'est installée, ConversionImpossibleError si le fichier est refusé,
    ConversionTropLongueError en cas de dépassement du délai.
    """
    if source.suffix.lower() not in OFFICE_EXT:
        raise ConversionImpossibleError(f"Type non convertible en PDF : {source.suffix or 'sans extension'}.")
    moteurs = [_convertir_avec_office, _convertir_avec_soffice] if IS_WINDOWS else [_convertir_avec_soffice]
    erreurs: list[str] = []
    tentatives = 0  # moteurs réellement présents et ayant essayé (échec de conversion ≠ absence)
    with _lock:
        for moteur in moteurs:
            try:
                return moteur(source, sortie_dir, timeout)
            except OfficeIndisponibleError as e:
                erreurs.append(str(e))
            except ConversionImpossibleError as e:
                tentatives += 1
                erreurs.append(str(e))
    if tentatives == 0:
        raise OfficeIndisponibleError(" ".join(dict.fromkeys(erreurs)) or _message_indisponible())
    raise ConversionImpossibleError(" ; ".join(erreurs))
