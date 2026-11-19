"""Diagnostic de la conversion Office -> PDF : mesure, étape par étape, la durée pour chaque fichier donné.

Sert à comparer un Word et un Excel sur le serveur (là où Word bloque et Excel passe) :
    cd Backend
    python scripts/diagnostic_conversion.py "C:\\chemin\\rapport.docx" "C:\\chemin\\budget.xlsx"
    python scripts/diagnostic_conversion.py rapport.docx --timeout 300
    python scripts/diagnostic_conversion.py rapport.docx --imprimante "Microsoft Print to PDF"
    python scripts/diagnostic_conversion.py --temoin                       # Word converti sur un document minimal
    python scripts/diagnostic_conversion.py rapport.docx --visible         # Word visible : on voit une boîte de dialogue
    python scripts/diagnostic_conversion.py rapport.docx --methode saveas  # autre méthode d'export Word
    python scripts/diagnostic_conversion.py rapport.docx --moteur libreoffice   # essai via LibreOffice, sans toucher au .env

Pour chaque fichier : taille, délai accordé, moteur utilisé, durée totale, et le journal des étapes du script PowerShell
(démarrage d'Office, imprimante de Word, ouverture du document, export PDF, fermeture) avec l'heure de chacune, la
durée du script elle-même et le temps passé HORS du script (démarrage de PowerShell, attente d'Office). Si le délai est dépassé,
l'étape où la conversion est restée bloquée est indiquée, et Office est fermé.

Le script passe par la même `convertir_vers_pdf` que l'application : il suit donc le réglage CONVERSION_MOTEUR_WORD
(« auto » : Word reçoit un délai court puis LibreOffice prend le relais ; « libreoffice » : Word contourné ;
« office » : Word seul). L'option --moteur le change pour l'essai, sans toucher au .env.
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services import conversion_office as conv  # noqa: E402


def _sortie_utf8(script: str) -> str:
    """Commande PowerShell dont la sortie (redirigée) est forcée en UTF-8 : sinon elle arrive dans la page de code
    OEM de la console et les accents des noms d'imprimantes sont mal affichés (cosmétique, sans effet fonctionnel)."""
    return f"[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; {script}"


def _imprimantes_windows() -> None:
    if os.name != "nt":
        return
    commande = _sortie_utf8("Get-CimInstance Win32_Printer | Select-Object Name, Default, Network, WorkOffline, PrinterStatus "
                            "| Format-Table -AutoSize | Out-String -Width 200")
    try:
        sortie = subprocess.run(["powershell", "-NoProfile", "-Command", commande], capture_output=True, timeout=60)
        print("    imprimantes Windows (Default = imprimante par défaut ; Network/WorkOffline = suspects pour Word) :")
        for ligne in sortie.stdout.decode("utf-8", "replace").strip().splitlines():
            print(f"      {ligne}")
    except Exception as e:  # noqa: BLE001
        print(f"    imprimantes illisibles : {e}")


def creer_temoin(dossier: Path) -> Path:
    """Document Word minimal (« Bonjour ») : s'il se convertit vite, Word fonctionne et le blocage vient du document."""
    chemin = dossier / "temoin.docx"
    with zipfile.ZipFile(chemin, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                   '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                   '<Default Extension="xml" ContentType="application/xml"/>'
                   '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
                   '</Types>')
        z.writestr("_rels/.rels", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
                   '</Relationships>')
        z.writestr("word/document.xml", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
                   '<w:p><w:r><w:t>Bonjour : document témoin du diagnostic de conversion.</w:t></w:r></w:p></w:body></w:document>')
    return chemin


def _service_spooler() -> None:
    if os.name != "nt":
        return
    try:
        sortie = subprocess.run(["powershell", "-NoProfile", "-Command", _sortie_utf8("(Get-Service Spooler).Status")],
                                capture_output=True, timeout=30)
        print(f"    service Spooler d'impression : {sortie.stdout.decode('utf-8', 'replace').strip() or 'inconnu'}")
    except Exception as e:  # noqa: BLE001
        print(f"    service Spooler illisible : {e}")


def _secondes(ligne: str) -> float | None:
    try:
        h, m, sec = ligne.split(" ", 1)[0].split(":")
        return int(h) * 3600 + int(m) * 60 + float(sec)
    except ValueError:
        return None


def diagnostiquer(fichier: Path, timeout: int | None) -> bool:
    delai = timeout or conv.timeout_pour(fichier)
    print(f"\n=== {fichier.name} ({fichier.stat().st_size / 1024 / 1024:.2f} Mo) — délai accordé : {delai} s")
    print(f"    suites disponibles : {', '.join(conv.suites_disponibles()) or 'aucune'}")
    if fichier.suffix.lower() in conv.WORD_EXT:
        _service_spooler()
        _imprimantes_windows()
    travail = Path(tempfile.mkdtemp(prefix="diag_conversion_"))
    debut = time.perf_counter()
    try:
        pdf = conv.convertir_vers_pdf(fichier, travail, timeout=delai)
        print(f"    OK en {time.perf_counter() - debut:.1f} s -> PDF de {pdf.stat().st_size / 1024:.0f} Ko")
        resultat = True
    except Exception as e:  # noqa: BLE001 - on veut afficher n'importe quelle cause
        print(f"    ÉCHEC après {time.perf_counter() - debut:.1f} s : {type(e).__name__} : {e}")
        resultat = False
    total = time.perf_counter() - debut
    journal = conv.lire_journal(travail)
    if journal:
        print("    étapes (heure locale) :")
        for ligne in journal:
            print(f"      {ligne}")
        premier, dernier = _secondes(journal[0]), _secondes(journal[-1])
        if premier is not None and dernier is not None and dernier >= premier:
            script = dernier - premier
            print(f"    durée du script : {script:.1f} s ; hors script (PowerShell, attente d'Office) : {max(0.0, total - script):.1f} s")
    shutil.rmtree(travail, ignore_errors=True)
    return resultat


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("fichiers", nargs="*", type=Path)
    parser.add_argument("--temoin", action="store_true", help="convertit aussi un document Word minimal créé pour l'occasion")
    parser.add_argument("--visible", action="store_true", help="Word/Excel visibles sur le serveur : on voit une boîte de dialogue éventuelle")
    parser.add_argument("--methode", choices=("export", "saveas"), default=None, help="méthode d'export Word (défaut : export)")
    parser.add_argument("--moteur", choices=conv._MOTEURS_WORD, default=None,
                        help="moteur pour les documents Word (défaut : réglage CONVERSION_MOTEUR_WORD, « auto ») : "
                             "« auto » = Word puis LibreOffice, « libreoffice » = LibreOffice seul, « office » = Word seul")
    parser.add_argument("--timeout", type=int, default=None, help="délai en secondes (défaut : calculé d'après la taille)")
    parser.add_argument("--imprimante", default=None, help="imprimante imposée à Word pendant la conversion")
    args = parser.parse_args()
    from app.config import get_settings

    reglages = get_settings()
    if args.imprimante:
        reglages.conversion_word_imprimante = args.imprimante
    if args.visible:
        reglages.conversion_office_visible = True
    if args.methode:
        reglages.conversion_word_methode = args.methode
    if args.moteur:
        reglages.conversion_moteur_word = args.moteur
    delai_court = getattr(reglages, "conversion_word_delai_office_s", 35)
    print(f"moteur pour les documents Word : {reglages.conversion_moteur_word or 'auto'} "
          f"(délai court d'Office avant bascule : {delai_court} s) — suites disponibles : "
          f"{', '.join(conv.suites_disponibles()) or 'aucune'}")
    fichiers = list(args.fichiers)
    if args.temoin:
        fichiers.insert(0, creer_temoin(Path(tempfile.mkdtemp(prefix="diag_temoin_"))))
    if not fichiers:
        parser.error("donner au moins un fichier, ou --temoin")
    bons = [diagnostiquer(f, args.timeout) for f in fichiers if f.is_file() or print(f"Introuvable : {f}")]
    return 0 if bons and all(bons) else 1


if __name__ == "__main__":
    raise SystemExit(main())
