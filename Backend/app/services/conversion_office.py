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

CONVERSION_TIMEOUT = 120  # valeur de repli si les réglages sont illisibles ; le délai réel dépend de la taille (timeout_pour)
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
    [Parameter(Mandatory = $true)][string]$OutDir,
    [string]$Imprimante = "",
    [switch]$Visible,                                   # diagnostic : Word/Excel visibles (on voit une éventuelle boîte de dialogue)
    [string]$Methode = "export"                         # diagnostic Word : "export" (ExportAsFixedFormat) ou "saveas" (SaveAs2)
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
# Journal d'étapes lu par Python : en cas de délai dépassé, il dit OÙ la conversion est restée bloquée
# (démarrage d'Office, ouverture du document, export PDF) et donne le PID d'Office à fermer.
function Etape([string]$Texte) {
    try { Add-Content -LiteralPath $script:journal -Value ((Get-Date -Format "HH:mm:ss.fff") + " " + $Texte) } catch { }
}

$source = (Resolve-Path -LiteralPath $Source).Path
$outDir = (Resolve-Path -LiteralPath $OutDir).Path
$out = Join-Path $outDir (([System.IO.Path]::GetFileNameWithoutExtension($source)) + ".pdf")
$ext = [System.IO.Path]::GetExtension($source).ToLower()
$script:journal = Join-Path $outDir "_etapes.txt"

switch ($ext) {
    { $_ -in ".doc", ".docx", ".rtf", ".odt" } { $progId = "Word.Application"; $procName = "WINWORD" }
    { $_ -in ".xls", ".xlsx", ".ods" }         { $progId = "Excel.Application"; $procName = "EXCEL" }
    { $_ -in ".ppt", ".pptx", ".odp" }         { $progId = "PowerPoint.Application"; $procName = "POWERPNT" }
    default { Fail ("Type not convertible by Microsoft Office: " + $ext) }
}

$t0 = (Get-Date).AddSeconds(-2)
Etape ("demarrage_office " + $progId)
try { $app = New-Object -ComObject $progId } catch { OfficeAbsent }
try {
    $p = Get-Process -Name $procName -ErrorAction SilentlyContinue | Where-Object { $_.StartTime -ge $t0 } | Select-Object -First 1
    if ($p) { Etape ("PID " + $p.Id) }
} catch { }
Etape "office_demarre"

try {
    switch ($ext) {
        { $_ -in ".doc", ".docx", ".rtf", ".odt" } {
            $app.Visible = [bool]$Visible
            $app.DisplayAlerts = 0                                  # wdAlertsNone
            # Reglages anti-blocage propres a Word (Excel : UpdateLinks=0 ci-dessous) : jamais de macro ni d'invite,
            # pas de mise a jour des liens a l'ouverture, pas de repagination en arriere-plan.
            try { $app.AutomationSecurity = 3 } catch { }           # msoAutomationSecurityForceDisable
            try { $app.Options.UpdateLinksAtOpen = $false } catch { }
            try { $app.Options.ConfirmConversions = $false } catch { }
            try { $app.Options.Pagination = $false } catch { }
            # Word calcule la mise en page avec le pilote de l'imprimante active : une imprimante réseau hors ligne ou un
            # pilote défaillant fait « geler » l'export. L'étape est tracée ; Imprimante (réglage facultatif) la remplace.
            if ($Imprimante) {
                Etape ("imprimante_demandee " + $Imprimante)
                try { $app.ActivePrinter = $Imprimante } catch { Etape "imprimante_refusee" }
            }
            Etape "lecture_imprimante"
            try { Etape ("imprimante_active " + $app.ActivePrinter) } catch { Etape "imprimante_illisible" }
            Etape "ouverture_document"
            $doc = $app.Documents.Open($source, $false, $true, $false)   # ConfirmConversions=False, ReadOnly=True, AddToRecentFiles=False
            Etape "export_pdf"
            try {
                # meme methode que Excel ; repli sur SaveAs2 si l'export direct est refuse
                if ($Methode -eq "saveas") { $doc.SaveAs2($out, 17) }
                else { try { $doc.ExportAsFixedFormat($out, 17) } catch { $doc.SaveAs2($out, 17) } }   # 17 = wdExportFormatPDF / wdFormatPDF
            } finally { $doc.Close($false) }
        }
        { $_ -in ".xls", ".xlsx", ".ods" } {
            $app.Visible = [bool]$Visible
            $app.DisplayAlerts = $false
            Etape "ouverture_document"
            $wb = $app.Workbooks.Open($source, 0, $true)          # UpdateLinks=0, ReadOnly=True
            Etape "export_pdf"
            try { $wb.ExportAsFixedFormat(0, $out) } finally { $wb.Close($false) }   # 0 = xlTypePDF
        }
        { $_ -in ".ppt", ".pptx", ".odp" } {
            # PowerPoint ne peut pas tourner masque (contrainte du modele COM) ; sans fenetre
            Etape "ouverture_document"
            $pres = $app.Presentations.Open($source, $true, $false, $false)   # ReadOnly=True, WithWindow=False
            Etape "export_pdf"
            try { $pres.SaveAs($out, 32) } finally { $pres.Close() }   # 32 = ppSaveAsPDF
        }
    }
} finally {
    Etape "fermeture_office"
    $app.Quit()
    [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($app)
}
Etape "termine"

if (-not (Test-Path -LiteralPath $out)) { Fail "PDF not produced by Microsoft Office." }
exit 0
"""


_ETAPES = {
    "demarrage_office": "démarrage de l'application Office",
    "office_demarre": "démarrage de l'application Office",
    "lecture_imprimante": "lecture de l'imprimante active de Word (pilote d'imprimante bloqué ?)",
    "ouverture_document": "ouverture du document",
    "export_pdf": "export en PDF",
    "fermeture_office": "fermeture d'Office",
}


def lire_journal(sortie_dir: Path) -> list[str]:
    """Lignes « HH:MM:SS.mmm étape » écrites par le script PowerShell (vide si absent)."""
    try:
        return (sortie_dir / "_etapes.txt").read_text(encoding="utf-8-sig", errors="replace").splitlines()
    except OSError:
        return []


def _etape_bloquee(sortie_dir: Path) -> str | None:
    """Dernière étape atteinte avant le blocage, en clair."""
    for ligne in reversed(lire_journal(sortie_dir)):
        nom = ligne.split(" ", 1)[-1].split(" ", 1)[0]
        if nom in _ETAPES:
            return _ETAPES[nom]
    return None


_SCRIPT_FENETRES = r"""
param([Parameter(Mandatory = $true)][uint32]$ProcessId)
Add-Type -TypeDefinition @'
using System;
using System.Text;
using System.Collections.Generic;
using System.Runtime.InteropServices;
public class FenetresOffice {
    public delegate bool EnumProc(IntPtr h, IntPtr l);
    [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc p, IntPtr l);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetClassName(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
    public static List<string> De(uint pid) {
        List<string> r = new List<string>();
        EnumWindows(delegate(IntPtr h, IntPtr l) {
            uint p; GetWindowThreadProcessId(h, out p);
            if (p == pid) {
                StringBuilder t = new StringBuilder(256); GetWindowText(h, t, 256);
                StringBuilder c = new StringBuilder(256); GetClassName(h, c, 256);
                r.Add((IsWindowVisible(h) ? "visible" : "cachee") + " | " + c + " | " + t);
            }
            return true;
        }, IntPtr.Zero);
        return r;
    }
}
'@
[FenetresOffice]::De($ProcessId) | ForEach-Object { $_ }
"""


def _fenetres_office(sortie_dir: Path) -> list[str]:
    """Fenêtres du processus Office bloqué (titre, classe, visible ou cachée) : une boîte de dialogue invisible qui
    attend une réponse est la cause classique d'un blocage. Ne lève jamais ; vide si inconnu."""
    pid = next((m[2] for m in (l.split(" ") for l in lire_journal(sortie_dir)) if len(m) >= 3 and m[1] == "PID" and m[2].isdigit()), None)
    powershell = _powershell()
    if pid is None or powershell is None:
        return []
    try:
        script = sortie_dir / "_fenetres.ps1"
        script.write_text(_SCRIPT_FENETRES, encoding="utf-8-sig")
        sortie = subprocess.run(
            [str(powershell), "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(script), "-ProcessId", pid],
            capture_output=True, timeout=30,
        )
        lignes = (sortie.stdout or b"").decode("utf-8", "replace").splitlines()
    except Exception:  # noqa: BLE001 - diagnostic au mieux
        return []
    return [l.strip() for l in lignes if l.strip() and ("#32770" in l or l.rsplit("|", 1)[-1].strip())][:8]


def _fermer_office_bloque(sortie_dir: Path) -> None:
    """Délai dépassé : tuer PowerShell ne ferme pas Word/Excel/PowerPoint (processus COM à part). Un Office resté
    ouvert bloquerait les conversions suivantes : on le ferme d'après le PID noté par le script. Ne lève jamais."""
    for ligne in lire_journal(sortie_dir):
        morceaux = ligne.split(" ")
        if len(morceaux) >= 3 and morceaux[1] == "PID" and morceaux[2].isdigit():
            try:
                subprocess.run(["taskkill", "/F", "/T", "/PID", morceaux[2]], capture_output=True, timeout=15)
            except Exception:  # noqa: BLE001 - nettoyage au mieux
                pass


def _convertir_avec_office(source: Path, sortie_dir: Path, timeout: int) -> Path:
    powershell = _powershell()
    if powershell is None:
        raise OfficeIndisponibleError("PowerShell est introuvable sur ce serveur Windows.")
    script = sortie_dir / "_conversion_office.ps1"
    script.write_text(_SCRIPT_PS, encoding="utf-8-sig")  # BOM requis par PowerShell 5.1
    commande = [str(powershell), "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                "-File", str(script), "-Source", str(source), "-OutDir", str(sortie_dir)]
    imprimante = _imprimante_word()
    if imprimante:
        commande += ["-Imprimante", imprimante]
    reglages = _reglages_diagnostic()
    if reglages["visible"]:
        commande += ["-Visible"]
    if reglages["methode"] in ("export", "saveas"):
        commande += ["-Methode", reglages["methode"]]
    # Sortie redirigée vers des FICHIERS et non des tubes : Word/Excel héritent des tubes de PowerShell et les gardent
    # ouverts jusqu'à leur arrêt complet (parfois des dizaines de secondes), ce qui retenait subprocess.run bien après
    # la fin réelle du script.
    try:
        with open(sortie_dir / "_sortie.txt", "wb") as sortie, open(sortie_dir / "_erreur.txt", "wb") as erreur:
            proc = subprocess.run(commande, stdout=sortie, stderr=erreur, timeout=timeout)
    except subprocess.TimeoutExpired:
        etape = _etape_bloquee(sortie_dir)
        fenetres = _fenetres_office(sortie_dir)  # AVANT la fermeture d'Office
        _fermer_office_bloque(sortie_dir)
        detail = f" (bloquée à l'étape : {etape})" if etape else ""
        if fenetres:
            detail += " — fenêtres d'Office ouvertes : " + " ; ".join(fenetres)
        raise ConversionTropLongueError(
            f"La conversion Microsoft Office a dépassé le délai imparti ({timeout} s){detail}."
        ) from None
    _fermer_office_bloque(sortie_dir)  # Quit() a été demandé ; on s'assure qu'Office ne reste pas en arrière-plan
    produit = sortie_dir / (source.stem + ".pdf")
    brut = proc.stderr
    if not brut:
        try:
            brut = (sortie_dir / "_erreur.txt").read_bytes()
        except OSError:
            brut = b""
    stderr = brut.decode("utf-8", "replace").strip()
    if proc.returncode == 3:
        raise OfficeIndisponibleError("Microsoft Office n'est pas installé ou inaccessible via COM sur le serveur.")
    if proc.returncode != 0 or not produit.is_file():
        raise ConversionImpossibleError(f"Microsoft Office a refusé la conversion : {stderr[-300:]}")
    return produit


def _reglages_diagnostic() -> dict:
    """Réglages réservés au diagnostic (scripts/diagnostic_conversion.py) : Office visible, méthode d'export Word."""
    try:
        from app.config import get_settings

        r = get_settings()
        return {"visible": bool(r.conversion_office_visible), "methode": (r.conversion_word_methode or "export").lower()}
    except Exception:  # noqa: BLE001
        return {"visible": False, "methode": "export"}


def _imprimante_word() -> str:
    """Imprimante à imposer à Word pendant la conversion (réglage conversion_word_imprimante, vide par défaut)."""
    try:
        from app.config import get_settings

        return (get_settings().conversion_word_imprimante or "").strip()
    except Exception:  # noqa: BLE001
        return ""


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

def convertir_vers_pdf(source: Path, sortie_dir: Path, timeout: int | None = None) -> Path:
    """Convertit un fichier Office/OpenDocument en PDF dans sortie_dir (même nom, extension .pdf).

    Sous Windows : Microsoft Office d'abord, LibreOffice en repli (l'un des deux peut manquer,
    une erreur de l'un tente l'autre). Ailleurs : LibreOffice. Lève OfficeIndisponibleError si
    aucune suite n'est installée, ConversionImpossibleError si le fichier est refusé,
    ConversionTropLongueError en cas de dépassement du délai (par défaut calculé d'après la taille : timeout_pour).
    """
    if timeout is None:
        timeout = timeout_pour(source)
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
