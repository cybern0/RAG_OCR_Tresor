"""Outils en ligne de commande, à lancer depuis le dossier Backend :

  uv run python -m app.cli creer-admin
  uv run python -m app.cli set-password <nom_utilisateur>

Le command `creer-admin` initialise le compte root et la structure selon le modèle
Direction -> Service -> Division, sans demander de mot de passe interactif.
"""

import argparse
import getpass
import sys

from sqlalchemy import select

from app.core.security import PASSWORD_MIN_LENGTH, hash_password
from app.db.metier import Agent, Direction, Role, Service, SessionLocal, User
from app.services.audit import log_action


def creer_admin() -> int:
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.nom_utilisateur == "admin")) is not None:
            print("Le compte admin existe déjà.")
            return 0
        direction = db.scalar(select(Direction).where(Direction.code == "DIRECTION"))
        if direction is None:
            direction = Direction(code="DIRECTION", nom="Direction", actif=True)
            db.add(direction)
            db.flush()

        service = db.scalar(select(Service).where(Service.code == "DIR"))
        if service is None:
            service = Service(direction_id=direction.id, code="DIR", nom="Direction", actif=True)
            db.add(service)
            db.flush()

        agent = db.scalar(select(Agent).where(Agent.matricule == "ADMIN_ROOT"))
        if agent is None:
            agent = Agent(
                matricule="ADMIN_ROOT",
                nom="Administrateur",
                prenom="Root",
                fonction="Super administrateur",
                service_id=service.id,
                division_id=None,
                titre="CHEF_SERVICE",
                actif=True,
            )
            db.add(agent)
            db.flush()

        role = db.scalar(select(Role).where(Role.code == "ADMIN"))
        if role is None:
            role = Role(code="ADMIN", libelle="Super administrateur")
            db.add(role)
            db.flush()

        user = User(
            agent_id=agent.id,
            nom_utilisateur="admin",
            mot_de_passe_hash=hash_password("Admin123!"),
            role_id=role.id,
            actif=True,
        )
        db.add(user)
        db.commit()
        print("Compte admin créé avec le login admin / mot de passe Admin123! .")
        return 0


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
    sub.add_parser("creer-admin", help="créer le compte root conforme au modèle hiérarchique")
    sp = sub.add_parser("set-password", help="définir le mot de passe d'un compte")
    sp.add_argument("nom_utilisateur")
    args = parser.parse_args()
    if args.commande == "creer-admin":
        return creer_admin()
    return set_password(args.nom_utilisateur)


if __name__ == "__main__":
    raise SystemExit(main())
