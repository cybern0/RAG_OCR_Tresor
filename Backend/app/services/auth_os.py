"""Authentification déléguée au système d'exploitation — l'application est un intermédiaire.

Les comptes et leurs mots de passe restent ceux de l'OS (gérés par l'administrateur système) : l'application
ne les stocke jamais et se contente de vérifier le couple nom/mot de passe auprès du système, puis donne
accès aux dossiers de la GED. Le mot de passe saisi n'est ni journalisé, ni mis en cache, ni stocké : il
est transmis à l'OS puis oublié.

Deux mécanismes, même code appelant — le choix suit le système qui héberge l'API :
- **Linux** (et un serveur joint à un domaine via SSSD/realmd) : PAM, service configuré (`/etc/pam.d/<service>`,
  voir docs/authentification_os.md). Import de `python-pam` paresseux, pour que le mode « local » et les
  tests fonctionnent sans la bibliothèque installée.
- **Windows** : `LogonUser` de pywin32 — le SAM local (ou l'annuaire si la machine est jointe à un domaine)
  valide lui-même le couple nom/mot de passe ; installation et administration : docs/demo_windows11.md.
  Le domaine est configurable (`AUTH_OS_DOMAIN`, « . » pour les comptes locaux).
"""

import sys

from app.config import get_settings


class ErreurAuthOS(RuntimeError):
    """L'OS est indisponible ou refuse l'authentification pour une raison côté serveur ; message générique."""


def authentifier(nom_utilisateur: str, mot_de_passe: str) -> bool:
    """Vérifie le couple nom/mot de passe auprès du système. Ne journalise rien, ne stocke rien."""
    if not nom_utilisateur or not mot_de_passe:
        return False
    if sys.platform.startswith("win"):
        return _authentifier_windows(nom_utilisateur, mot_de_passe)
    return _authentifier_pam(nom_utilisateur, mot_de_passe)


def _authentifier_pam(nom_utilisateur: str, mot_de_passe: str) -> bool:
    try:
        import pam  # python-pam : import paresseux, inutile en mode AUTH_MODE=local
    except ImportError as exc:
        raise ErreurAuthOS("Le module « python-pam » est absent du serveur : pip install python-pam (mode AUTH_MODE=pam).") from exc
    service = get_settings().auth_os_service
    try:
        return bool(pam.pam().authenticate(nom_utilisateur, mot_de_passe, service=service))
    except Exception as exc:  # refus PAM ou erreur du module : réponse nette, sans détail sensible
        raise ErreurAuthOS(f"PAM (service « {service} ») a refusé l'authentification : vérifier /etc/pam.d/{service}.") from exc


def _authentifier_windows(nom_utilisateur: str, mot_de_passe: str) -> bool:
    try:
        import pywintypes
        import win32security  # pywin32 : installé sous Windows (pyproject), import paresseux ailleurs
    except ImportError as exc:
        raise ErreurAuthOS("Le module « pywin32 » est absent du serveur : pip install pywin32 (mode AUTH_MODE=pam sous Windows).") from exc
    domaine = get_settings().auth_os_domain  # « . » = comptes locaux ; sinon nom NetBIOS ou du domaine
    try:
        # LOGON32_LOGON_NETWORK : simple validation des identifiants, aucun profil ni session réelle chargés
        return bool(win32security.LogonUser(
            nom_utilisateur, domaine, mot_de_passe,
            win32security.LOGON32_LOGON_NETWORK, win32security.LOGON32_PROVIDER_DEFAULT,
        ))
    except pywintypes.error as exc:
        probleme = _probleme_serveur_windows(getattr(exc, "winerror", None))
        if probleme is not None:  # le blocage est côté serveur : le message doit dire quoi corriger
            raise ErreurAuthOS(probleme) from exc
        return False  # 1326 (identifiants refusés), compte désactivé, verrouillé, expiré... : refus net
    except Exception as exc:  # toute autre erreur LogonUser : réponse nette, sans détail sensible
        raise ErreurAuthOS("Windows a refusé la vérification des identifiants : vérifier l'installation de pywin32.") from exc


def _probleme_serveur_windows(winerror: int | None) -> str | None:
    """Traduit un code d'erreur LogonUser : None = refus d'identifiants normal (1326, compte désactivé...) ;
    sinon le blocage est côté serveur et le message indique quoi corriger."""
    if winerror == 1314:  # ERROR_PRIVILEGE_NOT_HELD : le process n'a pas le droit de valider des mots de passe
        return (
            "Windows refuse la vérification des mots de passe : le privilège « Agir comme partie du système "
            "d'exploitation » est absent du compte qui lance l'API. Lancer l'API en tant qu'administrateur, la "
            "déployer comme service sous LocalSystem, ou accorder le droit via secpol.msc (voir docs/demo_windows11.md)."
        )
    return None
