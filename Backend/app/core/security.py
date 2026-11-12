"""Sécurité : hash des mots de passe (champ mot_de_passe_hash de _user) et jetons de session.

Uniquement la bibliothèque standard : scrypt pour les mots de passe, HMAC-SHA256 pour les jetons signés.
"""

import base64
import binascii
import hashlib
import hmac
import json
import secrets
import time
from collections import defaultdict, deque

from app.config import get_settings

PASSWORD_MIN_LENGTH = 10

_SCRYPT_N, _SCRYPT_R, _SCRYPT_P = 2**14, 8, 1


def _b64e(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64d(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


# --- Mots de passe -------------------------------------------------------------------------------------------

def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=32)
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${_b64e(salt)}${_b64e(digest)}"


def is_locked_hash(stored: str) -> bool:
    """Un hash commençant par '!' est un compte verrouillé (voir database/04_seed_roles_permissions.sql)."""
    return stored.startswith("!")


def verify_password(password: str, stored: str) -> bool:
    if not stored or is_locked_hash(stored):
        return False
    try:
        scheme, n, r, p, salt, expected = stored.split("$")
        if scheme != "scrypt":
            return False
        digest = hashlib.scrypt(
            password.encode(), salt=_b64d(salt), n=int(n), r=int(r), p=int(p), dklen=32, maxmem=128 * 1024 * 1024
        )
        return hmac.compare_digest(digest, _b64d(expected))
    except (ValueError, binascii.Error):
        return False


# Hash factice pour que la durée d'un échec soit la même que le nom d'utilisateur existe ou non.
DUMMY_HASH = hash_password(secrets.token_urlsafe(16))


# --- Jetons de session ---------------------------------------------------------------------------------------

def _password_fingerprint(stored_hash: str) -> str:
    return hashlib.sha256(stored_hash.encode()).hexdigest()[:16]


def _sign(payload_b64: str) -> str:
    key = get_settings().secret_key.encode()
    return _b64e(hmac.new(key, payload_b64.encode(), hashlib.sha256).digest())


def create_access_token(user_id: int, password_hash: str, now: float | None = None) -> tuple[str, int]:
    """Renvoie (jeton, durée de validité en secondes). Le jeton devient invalide si le mot de passe change."""
    ttl = get_settings().token_ttl_minutes * 60
    payload = {"sub": user_id, "exp": int((now or time.time()) + ttl), "pf": _password_fingerprint(password_hash)}
    payload_b64 = _b64e(json.dumps(payload, separators=(",", ":")).encode())
    return f"{payload_b64}.{_sign(payload_b64)}", ttl


def read_token(token: str, now: float | None = None) -> dict | None:
    """Renvoie le contenu du jeton s'il est authentique et non expiré, sinon None."""
    try:
        payload_b64, signature = token.split(".")
        if not hmac.compare_digest(signature, _sign(payload_b64)):
            return None
        payload = json.loads(_b64d(payload_b64))
        if int(payload["exp"]) < (now or time.time()):
            return None
        int(payload["sub"])
        return payload
    except (ValueError, KeyError, TypeError, binascii.Error):
        return None


def token_matches_password(payload: dict, stored_hash: str) -> bool:
    return hmac.compare_digest(str(payload.get("pf", "")), _password_fingerprint(stored_hash))


# --- Limitation des essais de connexion ----------------------------------------------------------------------

class LoginThrottle:
    """Bloque temporairement après trop d'échecs pour une même clé (adresse IP + nom d'utilisateur).
    En mémoire : suffisant pour une instance unique, à remplacer par Redis si l'API est répliquée."""

    def __init__(self, max_failures: int = 5, window_seconds: int = 300) -> None:
        self.max_failures = max_failures
        self.window = window_seconds
        self._failures: dict[str, deque[float]] = defaultdict(deque)

    def _prune(self, key: str, now: float) -> deque[float]:
        q = self._failures[key]
        while q and q[0] < now - self.window:
            q.popleft()
        return q

    def is_blocked(self, key: str, now: float | None = None) -> bool:
        return len(self._prune(key, now or time.time())) >= self.max_failures

    def record_failure(self, key: str, now: float | None = None) -> None:
        now = now or time.time()
        self._prune(key, now).append(now)

    def reset(self, key: str) -> None:
        self._failures.pop(key, None)


login_throttle = LoginThrottle()
