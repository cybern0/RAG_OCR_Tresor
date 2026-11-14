"""Modification de son propre profil : validation des champs et règles du mot de passe (sans base de données)."""

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.core.security import hash_password, login_throttle
from app.schemas.user import ProfileUpdate
from app.services.users import crud


class FakeUser:
    id = 7
    nom_utilisateur = "tomefy"
    mot_de_passe_hash = hash_password("ancien-mdp-123")


class FakeDb:
    """Session minimale : aucun autre compte ne porte déjà le nom demandé."""

    def __init__(self, taken: int | None = None):
        self.taken, self.added, self.commits = taken, [], 0

    def scalar(self, _query):
        return self.taken

    def add(self, row):
        self.added.append(row)

    def commit(self):
        self.commits += 1


@pytest.fixture(autouse=True)
def _reset_throttle():
    login_throttle._failures.clear()


def test_new_password_requires_old_and_matching_confirmation():
    with pytest.raises(ValidationError, match="mot de passe actuel"):
        ProfileUpdate(nouveau_mot_de_passe="nouveau-mdp-456", confirmation_mot_de_passe="nouveau-mdp-456")
    with pytest.raises(ValidationError, match="confirmation"):
        ProfileUpdate(ancien_mot_de_passe="x", nouveau_mot_de_passe="nouveau-mdp-456", confirmation_mot_de_passe="autre-mdp-4567")
    with pytest.raises(ValidationError, match="10 caractères"):
        ProfileUpdate(ancien_mot_de_passe="x", nouveau_mot_de_passe="court", confirmation_mot_de_passe="court")
    with pytest.raises(ValidationError, match="Rien à modifier"):
        ProfileUpdate()


def test_username_is_normalised_and_validated():
    assert ProfileUpdate(nom_utilisateur="  Tomefy.Ny ").nom_utilisateur == "tomefy.ny"
    with pytest.raises(ValidationError):
        ProfileUpdate(nom_utilisateur="a b")


def test_password_change_with_correct_old_password():
    user, db = FakeUser(), FakeDb()
    old_hash = user.mot_de_passe_hash
    data = ProfileUpdate(ancien_mot_de_passe="ancien-mdp-123", nouveau_mot_de_passe="nouveau-mdp-456", confirmation_mot_de_passe="nouveau-mdp-456")

    assert crud.update_profile(db, user, data, "127.0.0.1") is True
    assert user.mot_de_passe_hash != old_hash
    assert db.commits == 1
    assert "nouveau-mdp-456" not in str(db.added[0].detail)  # jamais de mot de passe dans le journal


def test_wrong_old_password_is_refused_without_logging_the_user_out():
    user, db = FakeUser(), FakeDb()
    data = ProfileUpdate(ancien_mot_de_passe="faux-mdp-000000", nouveau_mot_de_passe="nouveau-mdp-456", confirmation_mot_de_passe="nouveau-mdp-456")

    with pytest.raises(HTTPException) as err:
        crud.update_profile(db, user, data, "127.0.0.1")
    assert err.value.status_code == 400  # pas 401 : l'interface y verrait une session expirée
    assert user.mot_de_passe_hash == FakeUser.mot_de_passe_hash


def test_repeated_wrong_old_password_is_throttled():
    user, db = FakeUser(), FakeDb()
    data = ProfileUpdate(ancien_mot_de_passe="faux-mdp-000000", nouveau_mot_de_passe="nouveau-mdp-456", confirmation_mot_de_passe="nouveau-mdp-456")
    for _ in range(5):
        with pytest.raises(HTTPException):
            crud.update_profile(db, user, data, "10.0.0.1")
    with pytest.raises(HTTPException) as err:
        crud.update_profile(db, user, data, "10.0.0.1")
    assert err.value.status_code == 429


def test_username_change_and_conflict():
    user = FakeUser()
    assert crud.update_profile(FakeDb(), user, ProfileUpdate(nom_utilisateur="nouveau.nom"), None) is False
    assert user.nom_utilisateur == "nouveau.nom"

    other = FakeUser()
    with pytest.raises(HTTPException) as err:
        crud.update_profile(FakeDb(taken=99), other, ProfileUpdate(nom_utilisateur="pris"), None)
    assert err.value.status_code == 409
    assert other.nom_utilisateur == "tomefy"


def test_new_password_must_differ_from_old():
    user = FakeUser()
    data = ProfileUpdate(ancien_mot_de_passe="ancien-mdp-123", nouveau_mot_de_passe="ancien-mdp-123", confirmation_mot_de_passe="ancien-mdp-123")
    with pytest.raises(HTTPException, match="différent"):
        crud.update_profile(FakeDb(), user, data, None)
