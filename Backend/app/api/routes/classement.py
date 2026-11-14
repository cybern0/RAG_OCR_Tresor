"""Routes d'administration du classement documentaire."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_db, require
from app.core.permissions import CLASSEMENT_GERER, STATISTIQUES_GLOBALES, Principal
from app.db.metier import Categorie, RegleClassement, Tag, TypeDocument
from app.schemas.classement import (
    CategorieIn,
    CategorieOut,
    CategorieUpdate,
    ClassementResultOut,
    RegleClassementIn,
    RegleClassementOut,
    RegleClassementUpdate,
    SimulerClassementIn,
    TagIn,
    TagOut,
    TagUpdate,
    TypeDocumentIn,
    TypeDocumentOut,
    TypeDocumentUpdate,
)
from app.services.classement import build_dashboard_stats, charger_noms
from app.services.classement.moteur import evaluer_regles
from app.api.deps import get_principal

router = APIRouter(prefix="/classement", tags=["classement"])
_admin = lambda: Depends(get_principal)


def _require_classement(principal: Principal = Depends(get_principal)) -> Principal:
    if not principal.can(CLASSEMENT_GERER):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Action non autorisée pour votre rôle.")
    return principal


def _rule_to_dict(rule: RegleClassement) -> dict[str, Any]:
    return {
        "_rule_id": rule.id,
        "nom": rule.nom,
        "priorite": rule.priorite,
        "categorie_id": rule.categorie_id,
        "type_document_id": rule.type_document_id,
        "tags": list(rule.tags or []),
        "confidentialite": rule.confidentialite,
        "criteres": rule.critere or {},
    }


class ReferentielOut(BaseModel):
    categories: list[CategorieOut]
    types: list[TypeDocumentOut]
    tags: list[TagOut]
    confidentialites: list[str]


@router.get("/referentiel", response_model=ReferentielOut)
def referentiel(db: Session = Depends(get_db), _: Principal = Depends(get_principal)):
    """Catégories et types actifs, étiquettes : de quoi classer ou filtrer un fichier, sans droit d'administration du classement."""
    return ReferentielOut(
        categories=db.query(Categorie).filter(Categorie.actif.is_(True)).order_by(Categorie.ordre.asc(), Categorie.nom.asc()).all(),
        types=db.query(TypeDocument).filter(TypeDocument.actif.is_(True)).order_by(TypeDocument.nom.asc()).all(),
        tags=db.query(Tag).order_by(Tag.nom.asc()).all(),
        confidentialites=["PUBLIC", "INTERNE", "CONFIDENTIEL"],
    )


@router.get("/categories", response_model=list[CategorieOut])
def list_categories(db: Session = Depends(get_db), _: Principal = Depends(_require_classement)):
    return db.query(Categorie).order_by(Categorie.ordre.asc(), Categorie.id.asc()).all()


@router.post("/categories", response_model=CategorieOut, status_code=201)
def create_category(data: CategorieIn, db: Session = Depends(get_db), _: Principal = Depends(_require_classement)):
    item = Categorie(**data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/categories/{category_id}", response_model=CategorieOut)
def update_category(
    category_id: int,
    data: CategorieUpdate,
    db: Session = Depends(get_db),
    _: Principal = Depends(_require_classement),
):
    item = db.get(Categorie, category_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Catégorie introuvable.")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/categories/{category_id}")
def delete_category(category_id: int, db: Session = Depends(get_db), _: Principal = Depends(_require_classement)):
    item = db.get(Categorie, category_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Catégorie introuvable.")
    item.actif = False
    db.commit()
    return item


@router.get("/types", response_model=list[TypeDocumentOut])
def list_types(db: Session = Depends(get_db), _: Principal = Depends(_require_classement)):
    return db.query(TypeDocument).order_by(TypeDocument.nom.asc()).all()


@router.post("/types", response_model=TypeDocumentOut, status_code=201)
def create_type(data: TypeDocumentIn, db: Session = Depends(get_db), _: Principal = Depends(_require_classement)):
    item = TypeDocument(**data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/types/{type_id}", response_model=TypeDocumentOut)
def update_type(
    type_id: int,
    data: TypeDocumentUpdate,
    db: Session = Depends(get_db),
    _: Principal = Depends(_require_classement),
):
    item = db.get(TypeDocument, type_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Type de document introuvable.")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/types/{type_id}")
def delete_type(type_id: int, db: Session = Depends(get_db), _: Principal = Depends(_require_classement)):
    item = db.get(TypeDocument, type_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Type de document introuvable.")
    item.actif = False
    db.commit()
    return item


@router.get("/tags", response_model=list[TagOut])
def list_tags(db: Session = Depends(get_db), _: Principal = Depends(_require_classement)):
    return db.query(Tag).order_by(Tag.nom.asc()).all()


@router.post("/tags", response_model=TagOut, status_code=201)
def create_tag(data: TagIn, db: Session = Depends(get_db), _: Principal = Depends(_require_classement)):
    existing = db.query(Tag).filter(Tag.nom == data.nom.strip()).first()
    if existing is not None:
        return existing
    item = Tag(nom=data.nom.strip())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/tags/{tag_id}", response_model=TagOut)
def update_tag(
    tag_id: int,
    data: TagUpdate,
    db: Session = Depends(get_db),
    _: Principal = Depends(_require_classement),
):
    item = db.get(Tag, tag_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tag introuvable.")
    if data.nom is not None:
        item.nom = data.nom.strip()
    db.commit()
    db.refresh(item)
    return item


@router.delete("/tags/{tag_id}")
def delete_tag(tag_id: int, db: Session = Depends(get_db), _: Principal = Depends(_require_classement)):
    item = db.get(Tag, tag_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tag introuvable.")
    db.delete(item)
    db.commit()
    return item


@router.get("/regles", response_model=list[RegleClassementOut])
def list_rules(db: Session = Depends(get_db), _: Principal = Depends(_require_classement)):
    return db.query(RegleClassement).order_by(RegleClassement.priorite.asc(), RegleClassement.id.asc()).all()


@router.post("/regles", response_model=RegleClassementOut, status_code=201)
def create_rule(data: RegleClassementIn, db: Session = Depends(get_db), _: Principal = Depends(_require_classement)):
    item = RegleClassement(
        nom=data.nom,
        priorite=data.priorite,
        actif=data.actif,
        critere=data.critere,
        categorie_id=data.categorie_id,
        type_document_id=data.type_document_id,
        tags=list(data.tags),
        confidentialite=data.confidentialite,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/regles/{rule_id}", response_model=RegleClassementOut)
def update_rule(
    rule_id: int,
    data: RegleClassementUpdate,
    db: Session = Depends(get_db),
    _: Principal = Depends(_require_classement),
):
    item = db.get(RegleClassement, rule_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Règle de classement introuvable.")
    for field, value in data.model_dump(exclude_unset=True).items():
        if field == "tags" and value is not None:
            setattr(item, field, list(value))
        else:
            setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/regles/{rule_id}")
def delete_rule(rule_id: int, db: Session = Depends(get_db), _: Principal = Depends(_require_classement)):
    item = db.get(RegleClassement, rule_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Règle de classement introuvable.")
    db.delete(item)
    db.commit()
    return item


@router.post("/simuler", response_model=ClassementResultOut)
def simulate_classification(
    data: SimulerClassementIn,
    db: Session = Depends(get_db),
    _: Principal = Depends(_require_classement),
):
    regles = (
        db.query(RegleClassement)
        .filter(RegleClassement.actif.is_(True))
        .order_by(RegleClassement.priorite.asc(), RegleClassement.id.asc())
        .all()
    )
    contexte = data.model_dump(exclude_none=True)
    resultat = evaluer_regles([_rule_to_dict(r) for r in regles], contexte)
    return ClassementResultOut(
        categorie_id=resultat.get("categorie_id"),
        type_document_id=resultat.get("type_document_id"),
        tags=resultat.get("tags", []),
        confidentialite=resultat.get("confidentialite"),
    )


@router.get("/stats")
def stats_dashboard(
    db: Session = Depends(get_db),
    _: Principal = Depends(require(STATISTIQUES_GLOBALES)),
):
    db.execute(text("SELECT 1"))
    if db.bind is None:
        return build_dashboard_stats([])
    try:
        row = db.execute(text("SELECT to_regclass('rag_sys.vue_document_stats')")).scalar_one_or_none()
    except Exception:
        return build_dashboard_stats([])
    if row is None:
        return build_dashboard_stats([])

    rows = db.execute(
        text(
            "SELECT document_id, dossier_id, categorie_id, type_document_id, confidentialite, statut, extension, service_id, direction_id, corbeille_le, taille_octets, nb_versions FROM rag_sys.vue_document_stats"
        )
    ).mappings().all()
    return build_dashboard_stats([dict(item) for item in rows], charger_noms(db))


@router.post("/reclasser")
def reclassify_documents(
    payload: dict | None = None,
    db: Session = Depends(get_db),
    _: Principal = Depends(_require_classement),
):
    ids = (payload or {}).get("ids") or []
    if not ids:
        return {"ok": 0, "ids": []}
    from app.db.vecteur import Document

    for document_id in ids:
        doc = db.get(Document, document_id)
        if doc is None or not doc.versions:
            continue
        latest = doc.versions[-1]
        texte = "\n".join(chunk.contenu for chunk in latest.chunks)[:20_000] if getattr(latest, "chunks", None) else ""
        from app.services.classement import appliquer

        appliquer(db, doc, latest, texte)
    db.commit()
    return {"ok": len(ids), "ids": ids}
