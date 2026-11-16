"""Routes de mots de passe d'unité et de déverrouillage."""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_principal
from app.core.permissions import Principal
from app.db.metier import Deverrouillage, SecretUnite
from app.schemas.securite import DeverrouillageOut, DeverrouillerIn, SecretUniteIn, SecretUniteOut

router = APIRouter(prefix="/securite", tags=["securite"])


@router.get("/unites", response_model=list[SecretUniteOut])
def list_unites(
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    if not principal.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Action non autorisée.")
    return db.query(SecretUnite).order_by(SecretUnite.modifie_le.desc()).all()


@router.put("/secrets", response_model=SecretUniteOut)
def set_secret(
    payload: SecretUniteIn,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    if not principal.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Action non autorisée.")
    item = SecretUnite(
        service_id=payload.service_id,
        division_id=payload.division_id,
        admin_user_id=principal.user.id,
        secret_hash=payload.secret_hash,
        modifie_le=datetime.utcnow(),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.post("/deverrouiller", response_model=DeverrouillageOut)
def deverrouiller(
    payload: DeverrouillerIn,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    secret = db.get(SecretUnite, payload.secret_unite_id)
    if secret is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Secret introuvable.")
    if principal.user.id != secret.admin_user_id and not principal.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Action non autorisée.")
    item = Deverrouillage(
        secret_unite_id=payload.secret_unite_id,
        user_id=principal.user.id,
        valide_jusqua=datetime.utcnow() + timedelta(minutes=payload.duree_minutes),
        actif=True,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.post("/verrouiller")
def verrouiller(
    secret_id: int,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    secret = db.get(SecretUnite, secret_id)
    if secret is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Secret introuvable.")
    if principal.user.id != secret.admin_user_id and not principal.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Action non autorisée.")
    for row in db.query(Deverrouillage).filter(Deverrouillage.secret_unite_id == secret_id, Deverrouillage.actif.is_(True)).all():
        row.actif = False
    db.commit()
    return {"ok": True, "secret_unite_id": secret_id}
