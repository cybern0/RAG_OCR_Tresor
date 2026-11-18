"""Outils en ligne de commande, à lancer depuis le dossier Backend :

  uv run python -m app.cli creer-admin [--nom-utilisateur admin] [--direction-code DIRECTION --direction-nom "Direction générale"]
  uv run python -m app.cli set-password <nom_utilisateur>

`creer-admin` crée la direction (si elle n'existe pas) et le compte du super administrateur (rôle ADMIN). Ce compte n'a PAS d'agent
ni de titre : le niveau racine vient du rôle global, pas d'un poste, de sorte qu'il n'occupe aucun poste de chef. Le mot de passe est saisi
(jamais écrit dans le code ni affiché) ; en automatisation, il peut venir de la variable d'environnement ADMIN_PASSWORD.
"""

import argparse
import getpass
import os
import sys

from sqlalchemy import select

from app.core.security import PASSWORD_MIN_LENGTH, hash_password
from app.db.metier import Direction, Division, Role, Service, SessionLocal, User
from app.services.audit import log_action
from app.services.historique import ecrire_historique


def _saisir_mot_de_passe(libelle: str = "Mot de passe") -> str | None:
    password = os.environ.get("ADMIN_PASSWORD") or getpass.getpass(f"{libelle} : ")
    if len(password) < PASSWORD_MIN_LENGTH:
        print(f"Au moins {PASSWORD_MIN_LENGTH} caractères.", file=sys.stderr)
        return None
    if not os.environ.get("ADMIN_PASSWORD") and password != getpass.getpass("Confirmer : "):
        print("Les deux saisies diffèrent.", file=sys.stderr)
        return None
    return password


def creer_admin(nom_utilisateur: str, direction_code: str, direction_nom: str) -> int:
    nom_utilisateur = nom_utilisateur.strip().lower()
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.nom_utilisateur == nom_utilisateur)) is not None:
            print(f"Le compte « {nom_utilisateur} » existe déjà.")
            return 0
        role = db.scalar(select(Role).where(Role.code == "ADMIN"))
        if role is None:
            print("Rôle ADMIN absent : exécuter database/02_donnees_reference.sql.", file=sys.stderr)
            return 1
        password = _saisir_mot_de_passe()
        if password is None:
            return 1
        if db.scalar(select(Direction).where(Direction.code == direction_code)) is None:
            db.add(Direction(code=direction_code, nom=direction_nom, actif=True))
        user = User(nom_utilisateur=nom_utilisateur, mot_de_passe_hash=hash_password(password), role_id=role.id, actif=True)
        db.add(user)
        db.flush()
        log_action(db, None, "utilisateur.creer_cli", "utilisateur", user.id, {"nom_utilisateur": nom_utilisateur, "role": "ADMIN"})
        ecrire_historique(db, acteur=None, cible_type="utilisateur", cible_id=user.id, action="compte_cree",
                          apres={"nom_utilisateur": nom_utilisateur, "role": "ADMIN", "via": "cli"}, concerne_user_id=user.id)
        db.commit()
        print(f"Super administrateur « {nom_utilisateur} » créé. Pensez à en créer un second (point de défaillance unique).")
        return 0


def set_password(username: str) -> int:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.nom_utilisateur == username.strip().lower()))
        if user is None:
            print(f"Compte introuvable : {username}", file=sys.stderr)
            return 1
        if user.mot_de_passe_hash is None:
            print("Ce compte n'a pas de mot de passe (compte dégradé) : recréer le compte via l'interface.", file=sys.stderr)
            return 1
        password = _saisir_mot_de_passe("Nouveau mot de passe")
        if password is None:
            return 1
        user.mot_de_passe_hash = hash_password(password)
        user.actif = True
        log_action(db, None, "utilisateur.mot_de_passe_cli", "utilisateur", user.id, {"nom_utilisateur": user.nom_utilisateur})
        ecrire_historique(db, acteur=None, cible_type="utilisateur", cible_id=user.id, action="mot_de_passe_reinitialise",
                          motif="Procédure de secours (CLI)", concerne_user_id=user.id)
        db.commit()
        print(f"Mot de passe défini pour « {user.nom_utilisateur} ».")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="commande", required=True)
    sa = sub.add_parser("creer-admin", help="créer un super administrateur (et la direction si besoin)")
    sa.add_argument("--nom-utilisateur", default="admin")
    sa.add_argument("--direction-code", default="DIRECTION")
    sa.add_argument("--direction-nom", default="Direction")
    sp = sub.add_parser("set-password", help="définir le mot de passe d'un compte")
    sp.add_argument("nom_utilisateur")
    args = parser.parse_args()
    if args.commande == "creer-admin":
        return creer_admin(args.nom_utilisateur, args.direction_code, args.direction_nom)
    return set_password(args.nom_utilisateur)


if __name__ == "__main__":
    raise SystemExit(main())
