"""Périmètre administratif des comptes dans la hiérarchie Direction -> Service -> Division.
Ce module sert de couche de lecture pour les dashboards et les filtres de données.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


@dataclass(frozen=True)
class PorteeAdministrateur:
    niveau: str
    direction_ids: set[int] = field(default_factory=set)
    service_ids: set[int] = field(default_factory=set)
    division_ids: set[int] = field(default_factory=set)

    @property
    def est_root(self) -> bool:
        return self.niveau == "ROOT"

    @property
    def est_service(self) -> bool:
        return self.niveau in {"ROOT", "SERVICE"}

    @property
    def est_division(self) -> bool:
        return self.niveau in {"ROOT", "SERVICE", "DIVISION"}


def portee_administrateur(*, niveau: str, direction_ids: Iterable[int] | None = None, service_ids: Iterable[int] | None = None, division_ids: Iterable[int] | None = None) -> PorteeAdministrateur:
    return PorteeAdministrateur(
        niveau=niveau.upper(),
        direction_ids=set(direction_ids or ()),
        service_ids=set(service_ids or ()),
        division_ids=set(division_ids or ()),
    )
