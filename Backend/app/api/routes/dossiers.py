"""Routes des dossiers d'une division (un seul niveau). Les dossiers ne sont jamais créés à la main :
ils naissent automatiquement du modèle configuré à la création de la division (services/structure/crud.py).
Renommer, archiver, supprimer : super administrateur. Accès : voir core/acces.py (404 / 403 / 409)."""

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import Session

from app.api.deps import client_ip, get_db, get_principal
from app.core.permissions import Principal
from app.schemas.dossier import DossierOut, DossierUpdate
from app.services.dossiers import crud

router = APIRouter(prefix="/dossiers", tags=["dossiers"])


@router.get("", response_model=list[DossierOut])
def lister(
    division_id: int | None = Query(default=None, description="Division (par défaut celle du compte)"),
    principal: Principal = Depends(get_principal), db: Session = Depends(get_db),
):
    return crud.lister(db, principal, division_id)


@router.get("/{dossier_id}", response_model=DossierOut)
def detail(dossier_id: int, principal: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    return crud.detail(db, principal, dossier_id)


@router.patch("/{dossier_id}", response_model=DossierOut)
def modifier(dossier_id: int, data: DossierUpdate, request: Request, principal: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    return crud.modifier(db, principal, dossier_id, data, client_ip(request))


@router.delete("/{dossier_id}", status_code=204)
def supprimer(dossier_id: int, request: Request, principal: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    crud.supprimer(db, principal, dossier_id, client_ip(request))
    return Response(status_code=204)
