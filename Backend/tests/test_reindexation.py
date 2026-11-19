"""Règles de la réindexation (sans base ni service externe)."""

import pytest

from app.services.documents.reindexation import Parametres, refus

P = Parametres


@pytest.mark.parametrize("statut", ["pending", "processing"])
def test_refusee_pendant_une_indexation(statut):
    assert "déjà en attente ou en cours" in refus(statut, P(False, False), P(True, True))


@pytest.mark.parametrize("indexe", [P(False, False), P(True, False), P(True, True)])
def test_toujours_permise_apres_une_erreur(indexe):
    assert refus("error", indexe, indexe) is None


def test_prete_sans_changement_refusee_avec_les_parametres_dans_le_message():
    msg = refus("ready", P(True, False), P(True, False))
    assert msg and "tableaux : oui" in msg and "images : non" in msg


@pytest.mark.parametrize(
    "indexe,demande",
    [(P(False, False), P(True, False)), (P(False, False), P(False, True)), (P(True, True), P(True, False))],
)
def test_prete_avec_un_changement_permise(indexe, demande):
    assert refus("ready", indexe, demande) is None
