"""Demandes d'accès (rôle ou fichier) et accès ponctuels."""

from typing import Literal

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.api.deps import client_ip, get_db, get_principal
from app.core.permissions import Principal
from app.schemas.demande import DemandeDecisionIn, DemandeIn, DemandeOut, ExceptionOut
from app.services import demandes as svc

router = APIRouter(prefix="/demandes", tags=["demandes"])


@router.get("", response_model=list[DemandeOut])
def lister(
    vue: Literal["mes", "a_traiter"] = "mes", statut: Literal["en_attente", "acceptee", "refusee", "annulee"] | None = None,
    principal: Principal = Depends(get_principal), db: Session = Depends(get_db),
):
    """mes : mes propres demandes ; a_traiter : demandes des divisions dont je suis gérant (chef de division ou de service, intérim compris)."""
    return svc.lister(db, principal, vue, statut)


@router.post("", response_model=DemandeOut, status_code=201)
def creer(data: DemandeIn, request: Request, principal: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    return svc.creer(db, principal, data, client_ip(request))


@router.get("/exceptions", response_model=list[ExceptionOut])
def exceptions(principal: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    return svc.lister_exceptions(db, principal)


@router.delete("/exceptions/{exception_id}", status_code=204)
def revoquer(exception_id: int, principal: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    svc.revoquer_exception(db, principal, exception_id)
    return Response(status_code=204)


@router.post("/{demande_id}/decision", response_model=DemandeOut)
def decider(demande_id: int, data: DemandeDecisionIn, request: Request, principal: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    return svc.decider(db, principal, demande_id, data.accepter, data.reponse, data.duree_heures, client_ip(request))


@router.post("/{demande_id}/annuler", response_model=DemandeOut)
def annuler(demande_id: int, principal: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    return svc.annuler(db, principal, demande_id)
