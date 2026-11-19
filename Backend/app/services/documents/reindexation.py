"""Réindexation d'une version déjà stockée : quand est-elle permise ?

Réindexer ne crée PAS de version : le fichier déjà sur le disque est relu avec de nouveaux paramètres
(cases « tableaux » / « images »), ou relu simplement parce que la première indexation avait échoué.

Règles :
  - une indexation en attente ou en cours : refusé (elle va déjà se faire) ;
  - une version en erreur : toujours permise (nouvelle tentative), avec ou sans changement de case ;
  - une version prête : permise SEULEMENT si une case change par rapport à la dernière indexation réussie.
    Cocher « tableaux » alors qu'elle avait déjà été indexée avec « tableaux » ne ferait que refaire le même travail.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Parametres:
    tableaux: bool
    images: bool

    def libelle(self) -> str:
        oui = lambda b: "oui" if b else "non"  # noqa: E731
        return f"tableaux : {oui(self.tableaux)}, images : {oui(self.images)}"


def refus(statut: str, deja_indexe: Parametres, demande: Parametres) -> str | None:
    """Message de refus (affiché tel quel à l'utilisateur), ou None si la réindexation est permise."""
    if statut in ("pending", "processing"):
        return "Une indexation est déjà en attente ou en cours pour cette version : attendre sa fin."
    if statut == "error":
        return None
    if demande == deja_indexe:
        return (
            f"Rien à réindexer : cette version a déjà été indexée avec ces paramètres ({deja_indexe.libelle()}). "
            "Modifier au moins une case (tableaux ou images) pour relancer l'indexation."
        )
    return None
