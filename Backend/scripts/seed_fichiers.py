#!/usr/bin/env python3
"""Écrit les fichiers texte de démonstration dans Backend/storage/uploads/seed/.

Le script est volontairement simple et idempotent : il réécrit les fichiers de
la démonstration de façon déterministe afin de permettre l'aperçu et le
téléchargement dans l'interface de démonstration.
"""

from __future__ import annotations

import argparse
from pathlib import Path

FILES = {
    "budget_2026.txt": """DEMO - Budget 2026\n\nLe service Finances a validé le budget de 2026.\nLes engagements restants sont plafonnés à 12,4 M€.\n\nPoints clés :\n- suivi des crédits par programme ;\n- vérification trimestrielle ;\n- transmission aux services concernés.\n""",
    "factures.txt": """DEMO - Factures\n\nLes factures doivent être payées dans un délai de 15 jours à compter de la\nréception du document. Les écarts de TVA doivent être validés avant paiement.\n\nExigence :\n- contrôle de cohérence de la facture ;\n- vérification de la commande associée ;\n- validation du service comptable.\n""",
    "offres_emploi.txt": """DEMO - Offres d'emploi\n\nNous ouvrons une campagne de recrutement pour les postes de gestionnaire de\nservice et d'agent administratif. Les candidats sont évalués sur leur capacité\nà piloter des dossiers, à collaborer avec les services et à respecter les règles\nde confidentialité.\n\nLa procédure de sélection comprend :\n- analyse du dossier ;\n- entretien de positionnement ;\n- validation de la division d'affectation.\n""",
    "trimestre_1.txt": """DEMO - Trimestre 1\n\nLe trimestre 1 a permis de stabiliser la gestion documentaire et de consolider\nles premières validations de dossier. La prise en charge des demandes a été\nrenforcée par l'analyse des rôles de division et la traçabilité des versions.\n""",
}


def _default_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "storage" / "uploads" / "seed"


def main() -> int:
    parser = argparse.ArgumentParser(description="Créer les fichiers de démonstration pour la GED.")
    parser.add_argument("--out-dir", type=Path, default=_default_dir(), help="Répertoire où écrire les fichiers de démonstration.")
    args = parser.parse_args()

    out_dir = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    for name, content in FILES.items():
        target = out_dir / name
        target.write_text(content, encoding="utf-8")

    print(f"{len(FILES)} fichiers de démo écrits dans {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
