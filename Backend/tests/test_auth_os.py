"""Authentification déléguée au système (mode AUTH_MODE=pam) : l'application est un intermédiaire.

Le module PAM réel n'existe pas dans l'environnement de test : `auth_os.authentifier` est simulé
(monkeypatch) et l'on vérifie le flux applicatif — provisionnement du profil au premier accès, réutilisation
du profil aux accès suivants, refus sans création, comptes locaux toujours valables en mode pam (démarrage
du système), et impossibilité de toucher au mot de passe ou au nom d'un compte OS depuis l'application.
Même base de test et mêmes fixtures que test_api.py."""

import os

import pytest

if not os.environ.get("TEST_DATABASE_URL"):
    pytest.skip("TEST_DATABASE_URL non défini : tests d'API ignorés", allow_module_level=True)

from sqlalchemy import select

from app.config import get_settings
from app.db.metier import SessionLocal, User
from app.services import auth_os

from .test_api import (  # noqa: F401  (fixtures et aides partagées)
    ADMIN, PWD, client, world,
)


def _mode_pam(monkeypatch, auto_creer=True):
    monkeypatch.setattr(get_settings(), "auth_mode", "pam")
    monkeypatch.setattr(get_settings(), "auth_os_auto_creer", auto_creer)


def _user(nom_utilisateur):
    with SessionLocal() as db:
        return db.scalar(select(User).where(User.nom_utilisateur == nom_utilisateur))


def test_erreur_windows_1314_donne_un_message_d_exploitation():
    """1314 (privilège LogonUser manquant) : le message doit expliquer quoi corriger côté serveur ;
    1326 et les refus normaux ne lèvent pas d'erreur, ils refusent simplement la connexion."""
    from app.services.auth_os import _probleme_serveur_windows

    message = _probleme_serveur_windows(1314)
    assert message is not None and "secpol" in message
    assert _probleme_serveur_windows(1326) is None  # identifiants refusés : cas normal, 401 suffit
    assert _probleme_serveur_windows(None) is None


def test_pam_provisionne_le_profil_au_premier_acces(client, world, monkeypatch):
    """Identifiants acceptés par le système pour un compte inconnu de l'app : profil créé (source « os »,
    sans mot de passe local), réutilisé au second accès ; le jeton fonctionne et l'API montre un compte OS."""
    _mode_pam(monkeypatch)
    nom = f"os.{world['tag']}.nouveau"
    monkeypatch.setattr(auth_os, "authentifier", lambda u, mdp: u == nom and mdp == "MotDePasseOS1")

    premier = client.post("/auth/login", json={"nom_utilisateur": nom, "mot_de_passe": "MotDePasseOS1"})
    assert premier.status_code == 200, premier.text
    profil = premier.json()["user"]
    assert profil["source_compte"] == "os"
    u = _user(nom)
    assert u is not None and u.source_compte == "os" and u.mot_de_passe_hash is None and u.agent_id is None

    second = client.post("/auth/login", json={"nom_utilisateur": nom, "mot_de_passe": "MotDePasseOS1"})
    assert second.status_code == 200 and second.json()["user"]["id"] == profil["id"]  # pas de doublon
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {second.json()['access_token']}"}).status_code == 200


def test_pam_refuse_sans_profil_si_auto_creer_desactive(client, world, monkeypatch):
    """AUTH_OS_AUTO_CREER=false : un compte OS sans profil applicatif ne peut pas entrer, et rien n'est créé."""
    _mode_pam(monkeypatch, auto_creer=False)
    nom = f"os.{world['tag']}.ferme"
    monkeypatch.setattr(auth_os, "authentifier", lambda u, mdp: u == nom and mdp == "MotDePasseOS1")

    r = client.post("/auth/login", json={"nom_utilisateur": nom, "mot_de_passe": "MotDePasseOS1"})
    assert r.status_code == 401 and _user(nom) is None


def test_pam_mauvais_mot_de_passe_ne_cree_rien(client, world, monkeypatch):
    """Le système refuse : 401, aucun profil applicatif créé, même pour un nom que le système connaît."""
    _mode_pam(monkeypatch)
    nom = f"os.{world['tag']}.faux"
    monkeypatch.setattr(auth_os, "authentifier", lambda u, mdp: False)

    r = client.post("/auth/login", json={"nom_utilisateur": nom, "mot_de_passe": "n'importe quoi"})
    assert r.status_code == 401 and _user(nom) is None


def test_pam_compte_local_reste_valide_en_mode_pam(client, world, monkeypatch):
    """Compte de démarrage (source « local », hash scrypt) : il se connecte comme avant même en mode pam."""
    _mode_pam(monkeypatch)
    monkeypatch.setattr(auth_os, "authentifier", lambda u, mdp: False)  # le système ne connaît que les comptes OS

    r = client.post("/auth/login", json={"nom_utilisateur": ADMIN, "mot_de_passe": PWD})
    assert r.status_code == 200 and r.json()["user"]["source_compte"] == "local"


def test_compte_os_ne_change_pas_son_mot_de_passe_ni_son_nom(client, world, monkeypatch):
    """Depuis l'application, un compte OS ne peut ni changer son mot de passe (côté OS) ni être renommé."""
    _mode_pam(monkeypatch)
    nom = f"os.{world['tag']}.profil"
    monkeypatch.setattr(auth_os, "authentifier", lambda u, mdp: u == nom and mdp == "MotDePasseOS1")
    jeton = client.post("/auth/login", json={"nom_utilisateur": nom, "mot_de_passe": "MotDePasseOS1"}).json()
    h = {"Authorization": f"Bearer {jeton['access_token']}"}

    r = client.patch("/auth/me", headers=h, json={"ancien_mot_de_passe": "MotDePasseOS1", "nouveau_mot_de_passe": "AutreMDP123", "confirmation_mot_de_passe": "AutreMDP123"})
    assert r.status_code == 409
    r = client.patch("/auth/me", headers=h, json={"nom_utilisateur": "pirate"})
    assert r.status_code == 409
    assert _user(nom).mot_de_passe_hash is None  # rien n'a été écrit


def test_admin_ne_reinitialise_pas_le_mot_de_passe_d_un_compte_os(client, world, monkeypatch):
    """Le super administrateur non plus : la réinitialisation passe par le système, pas par l'application."""
    _mode_pam(monkeypatch)
    nom = f"os.{world['tag']}.admin"
    monkeypatch.setattr(auth_os, "authentifier", lambda u, mdp: u == nom and mdp == "MotDePasseOS1")
    client.post("/auth/login", json={"nom_utilisateur": nom, "mot_de_passe": "MotDePasseOS1"})
    user_id = _user(nom).id

    r = client.patch(f"/users/{user_id}", headers=world["admin"], json={"mot_de_passe": "Force1234"})
    assert r.status_code == 409
    assert _user(nom).mot_de_passe_hash is None
