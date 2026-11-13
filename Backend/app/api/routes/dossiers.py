"""Routes des dossiers.

- GET /dossiers : les dossiers auxquels on a accès (tous pour l'ADMIN), avec son rôle effectif.
- Création, renommage, archivage, suppression et gestion des membres et des rôles : ADMIN seul (permission dossier.gerer).
  Pas d'invitation ni de partage par lien : c'est l'admin qui définit les accès.
"""

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import client_ip, get_db, get_principal, require
from app.core.permissions import DOSSIER_GERER, Principal, roles_par_dossier
from app.db.vecteur import Document
from app.schemas.dossier import AccesDossierOut, DossierIn, DossierOut, DossierUpdate, RoleIn
from app.services.dossiers import crud

router = APIRouter(prefix="/dossiers", tags=["dossiers"])
_admin = require(DOSSIER_GERER)


def _out(db: Session, principal: Principal, dossier) -> DossierOut:
    n = db.scalar(select(func.count(Document.id)).where(Document.dossier_id == dossier.id)) or 0
    return crud.to_out(dossier, roles_par_dossier(db, principal)[dossier.id], n)


@router.get("", response_model=list[DossierOut])
def list_dossiers(principal: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    return crud.list_dossiers(db, principal)


@router.post("", response_model=DossierOut, status_code=201)
def create_dossier(data: DossierIn, request: Request, actor: Principal = Depends(_admin), db: Session = Depends(get_db)):
    return _out(db, actor, crud.create_dossier(db, actor, data, client_ip(request)))


@router.patch("/{dossier_id}", response_model=DossierOut)
def update_dossier(
    dossier_id: int, data: DossierUpdate, request: Request,
    actor: Principal = Depends(_admin), db: Session = Depends(get_db),
):
    return _out(db, actor, crud.update_dossier(db, actor, dossier_id, data, client_ip(request)))


@router.delete("/{dossier_id}", status_code=204)
def delete_dossier(
    dossier_id: int, request: Request, actor: Principal = Depends(_admin), db: Session = Depends(get_db)
) -> Response:
    crud.delete_dossier(db, actor, dossier_id, client_ip(request))
    return Response(status_code=204)


@router.get("/{dossier_id}/acces", response_model=AccesDossierOut)
def list_acces(dossier_id: int, _: Principal = Depends(_admin), db: Session = Depends(get_db)):
    return crud.list_acces(db, dossier_id)


@router.put("/{dossier_id}/membres/{user_id}", status_code=204)
def set_membre(
    dossier_id: int, user_id: int, data: RoleIn, request: Request,
    actor: Principal = Depends(_admin), db: Session = Depends(get_db),
) -> Response:
    crud.set_membre(db, actor, dossier_id, user_id, data.role, client_ip(request))
    return Response(status_code=204)


@router.delete("/{dossier_id}/membres/{user_id}", status_code=204)
def remove_membre(
    dossier_id: int, user_id: int, request: Request, actor: Principal = Depends(_admin), db: Session = Depends(get_db)
) -> Response:
    crud.remove_membre(db, actor, dossier_id, user_id, client_ip(request))
    return Response(status_code=204)


@router.put("/{dossier_id}/services/{service_id}", status_code=204)
def set_service(
    dossier_id: int, service_id: int, data: RoleIn, request: Request,
    actor: Principal = Depends(_admin), db: Session = Depends(get_db),
) -> Response:
    crud.set_service(db, actor, dossier_id, service_id, data.role, client_ip(request))
    return Response(status_code=204)


@router.delete("/{dossier_id}/services/{service_id}", status_code=204)
def remove_service(
    dossier_id: int, service_id: int, request: Request, actor: Principal = Depends(_admin), db: Session = Depends(get_db)
) -> Response:
    crud.remove_service(db, actor, dossier_id, service_id, client_ip(request))
    return Response(status_code=204)
