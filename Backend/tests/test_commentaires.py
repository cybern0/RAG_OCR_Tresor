"""Commentaires : validation de la saisie (sans base de données)."""

import pytest
from pydantic import ValidationError

from app.api.routes.commentaires import CommentaireIn


def test_commentaire_est_nettoye():
    assert CommentaireIn(contenu="  Version relue.  ").contenu == "Version relue."


def test_commentaire_vide_ou_trop_long_est_refuse():
    with pytest.raises(ValidationError, match="vide"):
        CommentaireIn(contenu="   ")
    with pytest.raises(ValidationError, match="2000"):
        CommentaireIn(contenu="x" * 2001)
