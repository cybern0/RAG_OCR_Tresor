"""Routes d'authentification : connexion, déconnexion, utilisateur courant (côté UI : features/auth)."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.api.deps import client_ip, get_db, get_principal
from app.core.permissions import Principal, load_permissions
from app.core.security import (
    DUMMY_HASH, create_access_token, login_throttle, verify_password,
)
from app.db.metier import Agent, User
from app.schemas.user import LoginIn, MeOut, TokenOut
from app.services.audit import log_action
from app.services.users.crud import to_me_out

router = APIRouter(prefix="/auth", tags=["auth"])

_INVALID = "Nom d'utilisateur ou mot de passe incorrect."


@router.post("/login", response_model=TokenOut)
def login(data: LoginIn, request: Request, db: Session = Depends(get_db)) -> TokenOut:
    username = data.nom_utilisateur.strip().lower()
    ip = client_ip(request)
    throttle_key = f"{ip}|{username}"
    if login_throttle.is_blocked(throttle_key):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Trop de tentatives. Réessayer dans quelques minutes.")

    user = db.scalars(
        select(User).options(joinedload(User.role), joinedload(User.agent).joinedload(Agent.service))
        .where(User.nom_utilisateur == username)
    ).unique().one_or_none()

    # on vérifie toujours un hash (factice si le compte n'existe pas) pour ne pas révéler les comptes par le temps de réponse
    password_ok = verify_password(data.mot_de_passe, user.mot_de_passe_hash if user else DUMMY_HASH)
    if user is None or not user.actif or not password_ok:
        login_throttle.record_failure(throttle_key)
        # le nom saisi n'est pas journalisé s'il est inconnu (il pourrait être un mot de passe tapé au mauvais endroit)
        log_action(db, user.id if user else None, "connexion.echec", "utilisateur", user.id if user else None,
                   {} if user else {"compte_inconnu": True}, ip)
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, _INVALID)

    login_throttle.reset(throttle_key)
    user.derniere_connexion = datetime.now(UTC)
    log_action(db, user.id, "connexion.reussie", "utilisateur", user.id, {}, ip)
    db.commit()
    token, ttl = create_access_token(user.id, user.mot_de_passe_hash)
    principal = Principal(user=user, permissions=load_permissions(db, user))
    return TokenOut(access_token=token, expires_in=ttl, user=to_me_out(principal))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, principal: Principal = Depends(get_principal), db: Session = Depends(get_db)) -> None:
    """Les jetons sont sans état : la déconnexion efface le jeton côté navigateur ; ici on la journalise."""
    log_action(db, principal.user.id, "connexion.deconnexion", "utilisateur", principal.user.id, {}, client_ip(request))
    db.commit()


@router.get("/me", response_model=MeOut)
def me(principal: Principal = Depends(get_principal)) -> MeOut:
    return to_me_out(principal)
