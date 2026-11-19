"""Diagnostic de la conversion LibreOffice -> PDF : mesure, pour chaque fichier donné, la conversion réelle.

Sert à séparer un problème d'installation LibreOffice d'un problème de document :
    cd Backend
    python scripts/diagnostic_conversion.py "C:\\chemin\\rapport.docx" "C:\\chemin\\budget.xlsx"
    python scripts/diagnostic_conversion.py rapport.docx --timeout 300
    python scripts/diagnostic_conversion.py --temoin                       # document Word minimal créé pour l'occasion

Pour chaque fichier : taille, délai accordé (calculé d'après la taille), durée réelle et résultat. En cas d'échec,
l'erreur de la conversion est affichée (LibreOffice absent, fichier refusé — avec le message de LibreOffice —,
délai dépassé). Le témoin (« Bonjour », 0,00 Mo) convertit en quelques secondes quand LibreOffice fonctionne :
s'il échoue aussi, l'installation est en cause, pas le document.
"""

import argparse
import shutil
import sys
import tempfile
import time
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services import conversion_office as conv  # noqa: E402


def creer_temoin(dossier: Path) -> Path:
    """Document Word minimal (« Bonjour ») : s'il se convertit vite, LibreOffice fonctionne et le problème vient du document."""
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


def diagnostiquer(fichier: Path, timeout: int | None) -> bool:
    delai = timeout or conv.timeout_pour(fichier)
    print(f"\n=== {fichier.name} ({fichier.stat().st_size / 1024 / 1024:.2f} Mo) — délai accordé : {delai} s")
    print(f"    suites disponibles : {', '.join(conv.suites_disponibles()) or 'aucune — installer LibreOffice'}")
    travail = Path(tempfile.mkdtemp(prefix="diag_conversion_"))
    debut = time.perf_counter()
    try:
        pdf = conv.convertir_vers_pdf(fichier, travail, timeout=delai)
        print(f"    OK en {time.perf_counter() - debut:.1f} s -> PDF de {pdf.stat().st_size / 1024:.0f} Ko")
        resultat = True
    except Exception as e:  # noqa: BLE001 - on veut afficher n'importe quelle cause
        print(f"    ÉCHEC après {time.perf_counter() - debut:.1f} s : {type(e).__name__} : {e}")
        resultat = False
    shutil.rmtree(travail, ignore_errors=True)
    return resultat


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("fichiers", nargs="*", type=Path)
    parser.add_argument("--temoin", action="store_true", help="convertit aussi un document Word minimal créé pour l'occasion")
    parser.add_argument("--timeout", type=int, default=None, help="délai en secondes (défaut : calculé d'après la taille)")
    args = parser.parse_args()
    soffice = conv._soffice()
    print(f"LibreOffice (soffice) : {soffice if soffice else 'introuvable — installer LibreOffice sur le serveur'}")
    fichiers = list(args.fichiers)
    if args.temoin:
        fichiers.insert(0, creer_temoin(Path(tempfile.mkdtemp(prefix="diag_temoin_"))))
    if not fichiers:
        parser.error("donner au moins un fichier, ou --temoin")
    bons = [diagnostiquer(f, args.timeout) for f in fichiers if f.is_file() or print(f"Introuvable : {f}")]
    return 0 if bons and all(bons) else 1


if __name__ == "__main__":
    raise SystemExit(main())
