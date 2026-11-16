"""Tableaux de bord par niveau : root, service, division, agent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TableauDeBord:
    niveau: str
    resume: dict[str, Any] = field(default_factory=dict)
    sections: dict[str, Any] = field(default_factory=dict)


def build_dashboard(*, niveau: str, contexte: dict[str, Any] | None = None) -> TableauDeBord:
    contexte = contexte or {}
    dashboard = TableauDeBord(niveau=niveau.upper())
    dashboard.resume = {
        "niveaux": niveau.upper(),
        "service_id": contexte.get("service_id"),
        "division_id": contexte.get("division_id"),
        "total_fichiers": contexte.get("total_fichiers", 0),
        "total_demandes": contexte.get("total_demandes", 0),
    }
    dashboard.sections = {
        "agences": contexte.get("agences", []),
        "divisions": contexte.get("divisions", []),
        "fichiers_a_classement": contexte.get("fichiers_a_classement", []),
    }
    return dashboard
