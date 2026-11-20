"""Changement d'agent d'un compte : chef de division et chef de service (périmètre de leur service), jamais le rôle."""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.core.permissions import Principal
from app.schemas.user import UserUpdate
from app.services.users import crud


def _agent(id_, service_id, titre=None):
    return SimpleNamespace(id=id_, service_id=service_id, division_id=10, titre=titre, actif=True, service=None, division=None)


def _user(id_, agent, role="UTILISATEUR"):
    return SimpleNamespace(id=id_, agent=agent, agent_id=agent.id if agent else None, role=SimpleNamespace(code=role),
                           role_id=1, actif=True, mot_de_passe_hash="x")


def _principal(niveau, service_id=1, user_id=100):
    agent = _agent(900, service_id, "CHEF_DIVISION" if niveau == "DIVISION" else "CHEF_SERVICE")
    user = _user(user_id, agent)
    return Principal(user=user, permissions=frozenset({"utilisateur.modifier"}), niveau=niveau)


class FakeDb:
    def commit(self):
        pass


@pytest.fixture
def patched(monkeypatch):
    agents = {20: _agent(20, 1), 21: _agent(21, 2), 22: _agent(22, 1, "CHEF_SERVICE")}
    cible = _user(5, _agent(30, 1))
    monkeypatch.setattr(crud, "get_user", lambda db, uid: cible)
    monkeypatch.setattr(crud, "_check_agent", lambda db, aid, ignore_user_id=None: agents[aid])
    monkeypatch.setattr(crud, "log_action", lambda *a, **k: None)
    monkeypatch.setattr(crud, "ecrire_historique", lambda *a, **k: None)
    return cible


@pytest.mark.parametrize("niveau", ["DIVISION", "SERVICE"])
def test_chef_change_l_agent_dans_son_service(patched, niveau):
    crud.update_user(FakeDb(), _principal(niveau), 5, UserUpdate(agent_id=20), None)
    assert patched.agent_id == 20


@pytest.mark.parametrize("niveau", ["DIVISION", "SERVICE"])
def test_chef_ne_change_pas_le_role(patched, niveau):
    with pytest.raises(HTTPException) as e:
        crud.update_user(FakeDb(), _principal(niveau), 5, UserUpdate(role="ADMIN"), None)
    assert e.value.status_code == 403


def test_chef_division_agent_hors_service_refuse(patched):
    with pytest.raises(HTTPException) as e:
        crud.update_user(FakeDb(), _principal("DIVISION"), 5, UserUpdate(agent_id=21), None)
    assert e.value.status_code == 404
    assert patched.agent_id == 30


def test_chef_division_ne_nomme_pas_un_chef_de_service(patched):
    with pytest.raises(HTTPException) as e:
        crud.update_user(FakeDb(), _principal("DIVISION"), 5, UserUpdate(agent_id=22), None)
    assert e.value.status_code == 403


def test_chef_ne_change_pas_son_propre_agent(patched, monkeypatch):
    moi = _principal("DIVISION", user_id=5)
    monkeypatch.setattr(crud, "get_user", lambda db, uid: moi.user)
    with pytest.raises(HTTPException) as e:
        crud.update_user(FakeDb(), moi, 5, UserUpdate(agent_id=20), None)
    assert e.value.status_code == 403


def test_chef_ne_touche_pas_a_un_super_admin(patched):
    patched.role = SimpleNamespace(code="ADMIN")
    with pytest.raises(HTTPException) as e:
        crud.update_user(FakeDb(), _principal("DIVISION"), 5, UserUpdate(agent_id=20), None)
    assert e.value.status_code == 403
