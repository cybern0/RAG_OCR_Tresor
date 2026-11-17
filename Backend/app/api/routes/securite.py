"""Mots de passe de dossier : liste des unités, définition, déverrouillage temporaire. Réservé au super administrateur."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.api.deps import client_ip, get_db, get_principal
from app.core.permissions import NIVEAU_ROOT, Principal
from app.schemas.securite import DeverrouillageOut, DeverrouillerIn, SecretIn, UniteSecretOut, VerrouillerIn
from app.services import securite as svc

router = APIRouter(prefix="/securite", tags=["securite"])


def _verifier_super_admin(principal: Principal) -> None:
    if principal.niveau != NIVEAU_ROOT:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Réservé au super administrateur.")


@router.get("/unites", response_model=list[UniteSecretOut])
def unites(principal: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    _verifier_super_admin(principal)
    return svc.lister_unites(db, principal)


@router.put("/secrets", status_code=204)
def definir(data: SecretIn, request: Request, principal: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    _verifier_super_admin(principal)
    svc.definir_secret(db, principal, data, client_ip(request))
    return Response(status_code=204)


@router.post("/deverrouiller", response_model=DeverrouillageOut)
def deverrouiller(data: DeverrouillerIn, request: Request, principal: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    _verifier_super_admin(principal)
    return svc.deverrouiller(db, principal, data.type, data.unite_id, data.mot_de_passe, client_ip(request))


@router.post("/verrouiller", status_code=204)
def verrouiller(data: VerrouillerIn, principal: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    _verifier_super_admin(principal)
    svc.verrouiller(db, principal, data.type, data.unite_id)
    return Response(status_code=204)
