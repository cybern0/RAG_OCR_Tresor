"""Outils en ligne de commande, à lancer depuis le dossier Backend :

  uv run python -m app.cli set-password <nom_utilisateur>

Définit (ou réinitialise) le mot de passe d'un compte, sans jamais l'écrire dans un fichier.
Sert surtout à activer le compte « admin » créé verrouillé par database/04_seed_roles_permissions.sql.
"""

import argparse
import getpass
import sys

from sqlalchemy import select

from app.core.security import PASSWORD_MIN_LENGTH, hash_password
from app.db.metier import SessionLocal, User
from app.services.audit import log_action


def set_password(username: str) -> int:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.nom_utilisateur == username.strip().lower()))
        if user is None:
            print(f"Compte introuvable : {username}", file=sys.stderr)
            return 1
        password = getpass.getpass("Nouveau mot de passe : ")
        if len(password) < PASSWORD_MIN_LENGTH:
            print(f"Au moins {PASSWORD_MIN_LENGTH} caractères.", file=sys.stderr)
            return 1
        if password != getpass.getpass("Confirmer : "):
            print("Les deux saisies diffèrent.", file=sys.stderr)
            return 1
        user.mot_de_passe_hash = hash_password(password)
        user.actif = True
        log_action(db, None, "utilisateur.mot_de_passe_cli", "utilisateur", user.id, {"nom_utilisateur": user.nom_utilisateur})
        db.commit()
        print(f"Mot de passe défini pour « {user.nom_utilisateur} ».")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="commande", required=True)
    sp = sub.add_parser("set-password", help="définir le mot de passe d'un compte")
    sp.add_argument("nom_utilisateur")
    args = parser.parse_args()
    return set_password(args.nom_utilisateur)


if __name__ == "__main__":
    raise SystemExit(main())
