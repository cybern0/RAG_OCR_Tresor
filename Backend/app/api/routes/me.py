"""Profil de l'utilisateur connecté."""

from fastapi import APIRouter, Depends

from app.api.deps import get_principal
from app.core.permissions import Principal

router = APIRouter(tags=["profil"])


@router.get("/me")
def me(principal: Principal = Depends(get_principal)):
    agent = principal.user.agent
    return {
        "id": principal.user.id,
        "nom_utilisateur": principal.user.nom_utilisateur,
        "role_code": principal.user.role.code,
        "permissions": sorted(principal.permissions),
        "service_id": agent.service_id if agent else None,
        "division_id": agent.division_id if agent else None,
        "titre": agent.titre if agent else None,
        "nom": f"{agent.prenom} {agent.nom}".strip() if agent else principal.user.nom_utilisateur,
    }

