"""Dépendances FastAPI partagées : session de base de données, utilisateur courant, vérification de permission."""

import ipaddress
from collections.abc import Callable, Iterator

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.permissions import Principal, load_permissions
from app.core.security import read_token, token_matches_password
from app.db.metier import SessionLocal, User

_bearer = HTTPBearer(auto_error=False)


def get_db() -> Iterator[Session]:
    with SessionLocal() as db:
        yield db


def client_ip(request: Request) -> str | None:
    """Adresse du client, ou None si ce n'est pas une IP valide (socket unix, test...) : la colonne est de type INET."""
    host = request.client.host if request.client else None
    try:
        return str(ipaddress.ip_address(host)) if host else None
    except ValueError:
        return None


def get_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> Principal:
    unauthorized = HTTPException(
        status.HTTP_401_UNAUTHORIZED, "Session invalide ou expirée.", headers={"WWW-Authenticate": "Bearer"}
    )
    if credentials is None:
        raise unauthorized
    payload = read_token(credentials.credentials)
    if payload is None:
        raise unauthorized
    user = db.get(User, int(payload["sub"]))
    if user is None or not user.actif or not token_matches_password(payload, user.mot_de_passe_hash):
        raise unauthorized
    return Principal(user=user, permissions=load_permissions(db, user))


def require(*permissions: str) -> Callable[[Principal], Principal]:
    """Dépendance qui exige TOUTES les permissions listées, sinon 403."""

    def checker(principal: Principal = Depends(get_principal)) -> Principal:
        missing = [p for p in permissions if not principal.can(p)]
        if missing:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Action non autorisée pour votre rôle.")
        return principal

    return checker
