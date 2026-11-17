"""Tests d'intégration de l'API contre une vraie base PostgreSQL + pgvector (voir conftest.py).

Ils vérifient surtout, sur la GED hiérarchique (voir test_hierarchie.py pour les règles d'accès) :
- les comptes et leur sécurité (jetons, verrouillage, périmètre de création) ;
- les versions de fichiers (ajout sans suppression, historique daté, suppression) ;
- la règle des cases « tableaux / images », le top-k dynamique, la sécurité de l'aperçu et du téléchargement ;
- le chat limité aux fichiers lisibles, l'historique, la mémoire, et l'effet immédiat d'un retrait de rôle.
"""

import json
import os
import time
import uuid
from pathlib import Path

import pytest

if not os.environ.get("TEST_DATABASE_URL"):
    pytest.skip("TEST_DATABASE_URL non défini : tests d'API ignorés", allow_module_level=True)

from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.messages import AIMessageChunk
from langchain_core.outputs import ChatGenerationChunk
from sqlalchemy import select

from app.core.security import hash_password
from app.db.metier import MemoireChat, Role, SessionLocal, User
from app.db.vecteur import Chunk, Document, DocumentVersion
from app.main import app

from .conftest import FakeEmbeddings

PWD = "mot-de-passe-de-test-1"
SECRET = "dossier-de-test-1"
ADMIN = "admin_test"
ANSWER = "Le délai est de 30 jours [1]."
STANDALONE = "délai de paiement des factures"
LLM_CALLS: list[list] = []  # messages reçus par le faux LLM, pour vérifier historique et mémoire


class ScriptedLLM(FakeListChatModel):
    """Faux LLM : renvoie une question autonome pour la reformulation, ANSWER sinon ; enregistre ses entrées."""

    def _pick(self, messages) -> str:
        LLM_CALLS.append(list(messages))
        return STANDALONE if str(messages[0].content).startswith("Tu reformules") else ANSWER

    def _call(self, messages, stop=None, run_manager=None, **kwargs) -> str:
        return self._pick(messages)

    def _stream(self, messages, stop=None, run_manager=None, **kwargs):
        text = self._pick(messages)
        for part in (text[:6], text[6:]):
            yield ChatGenerationChunk(message=AIMessageChunk(content=part))


def qa_calls() -> list[list]:
    return [c for c in LLM_CALLS if not str(c[0].content).startswith("Tu reformules")]


def condense_calls() -> list[list]:
    return [c for c in LLM_CALLS if str(c[0].content).startswith("Tu reformules")]


class ApiClient(TestClient):
    """Client de test : l'API vit sous le préfixe /api (les tests écrivent les chemins sans lui)."""

    def request(self, method, url, *args, **kwargs):
        return super().request(method, "/api" + url, *args, **kwargs)


@pytest.fixture(scope="module")
def client():
    mp = pytest.MonkeyPatch()
    mp.setattr("app.services.ingestion.embedding.get_embeddings", lambda: FakeEmbeddings())
    mp.setattr("app.services.chat.rag_chain.get_llm", lambda: ScriptedLLM(responses=["x"]))
    with SessionLocal() as db:
        role = db.scalar(select(Role).where(Role.code == "ADMIN"))
        if db.scalar(select(User).where(User.nom_utilisateur == ADMIN)) is None:
            db.add(User(nom_utilisateur=ADMIN, mot_de_passe_hash=hash_password(PWD), role_id=role.id))
            db.commit()
    with ApiClient(app) as c:
        yield c
    mp.undo()


def login(client, username, password=PWD):
    return client.post("/auth/login", json={"nom_utilisateur": username, "mot_de_passe": password})


def auth(client, username):
    r = login(client, username)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def mk_agent(client, h, key, tag, service_id, division_id=None, titre=None):
    body = {"matricule": f"M{key}{tag}", "nom": "Nom", "prenom": key, "service_id": service_id, "division_id": division_id, "titre": titre}
    ag = client.post("/structure/agents", json=body, headers=h)
    assert ag.status_code == 201, ag.text
    return ag.json()


def mk_user(client, h, agent, key, tag):
    name = f"user_{key}_{tag}"
    u = client.post("/users", json={"nom_utilisateur": name, "mot_de_passe": PWD, "role": "UTILISATEUR", "agent_id": agent["id"]}, headers=h)
    assert u.status_code == 201, u.text
    return {"agent": agent, "user": u.json(), "name": name, "h": auth(client, name)}


def mk_role(client, h, division_id, code, libelle):
    r = client.post(f"/divisions/{division_id}/roles", json={"code": code, "libelle": libelle}, headers=h)
    assert r.status_code == 201, r.text
    return r.json()


def set_roles(client, h, user_id, role_ids):
    r = client.put(f"/users/{user_id}/roles", json={"role_ids": role_ids}, headers=h)
    assert r.status_code == 200, r.text


def mk_dossier(client, h, nom, **extra):
    r = client.post("/dossiers", json={"nom": nom, **extra}, headers=h)
    assert r.status_code == 201, r.text
    return r.json()


def secret_et_deverrouillage(client, h, type_unite, unite_id):
    """Définit le mot de passe de dossier puis déverrouille l'unité (super administrateur)."""
    r = client.put("/securite/secrets", json={"type": type_unite, "unite_id": unite_id, "nouveau_mot_de_passe": SECRET}, headers=h)
    assert r.status_code in (204, 400), r.text
    r = client.post("/securite/deverrouiller", json={"type": type_unite, "unite_id": unite_id, "mot_de_passe": SECRET}, headers=h)
    assert r.status_code == 200, r.text


@pytest.fixture(scope="module")
def world(client):
    """Une direction, deux services (s1, s2), trois divisions (v1 et v2 dans s1, v3 dans s2) avec leurs chefs.
    Agents : a (v1, rôle COMPTA), lect (v1, COMPTA + AUDIT), mix (v1, rôle PUBLIC), b (v3, rôle RH),
    cs (chef de service de s1, sans division). Dossiers : A (racine de v1) et B (racine de v3)."""
    tag = uuid.uuid4().hex[:6]
    h = auth(client, ADMIN)
    d = client.post("/structure/directions", json={"code": f"D{tag}", "nom": "Direction test"}, headers=h).json()
    out = {"tag": tag, "admin": h, "dir": d}
    svc = {}
    for k in ("s1", "s2"):
        r = client.post("/structure/services", json={"direction_id": d["id"], "code": f"S{k}{tag}", "nom": f"Service {k} {tag}"}, headers=h)
        assert r.status_code == 201, r.text
        svc[k] = r.json()
    div = {}
    for k, s in (("v1", "s1"), ("v2", "s1"), ("v3", "s2")):
        r = client.post("/structure/divisions", json={"service_id": svc[s]["id"], "nom": f"Division {k} {tag}", "code": f"{k}{tag}"}, headers=h)
        assert r.status_code == 201, r.text
        div[k] = r.json()
    out["svc"], out["div"] = svc, div
    out["cd1"] = mk_user(client, h, mk_agent(client, h, "cd1", tag, svc["s1"]["id"], div["v1"]["id"], "CHEF_DIVISION"), "cd1", tag)
    out["cd3"] = mk_user(client, h, mk_agent(client, h, "cd3", tag, svc["s2"]["id"], div["v3"]["id"], "CHEF_DIVISION"), "cd3", tag)
    out["cs"] = mk_user(client, h, mk_agent(client, h, "cs", tag, svc["s1"]["id"], None, "CHEF_SERVICE"), "cs", tag)
    for key, (s, v) in {"a": ("s1", "v1"), "lect": ("s1", "v1"), "mix": ("s1", "v1"), "b": ("s2", "v3")}.items():
        agent = mk_agent(client, h, key, tag, svc[s]["id"], div[v]["id"])
        out[key] = {**mk_user(client, out["cd1"]["h"] if v == "v1" else out["cd3"]["h"], agent, key, tag), "service": svc[s], "division": div[v]}
    out["roles"] = {k: mk_role(client, out["cd1"]["h"], div["v1"]["id"], k, k.title()) for k in ("COMPTA", "AUDIT", "PUBLIC")}
    out["roles"]["RH"] = mk_role(client, out["cd3"]["h"], div["v3"]["id"], "RH", "Rh")
    R = out["roles"]
    set_roles(client, out["cd1"]["h"], out["a"]["user"]["id"], [R["COMPTA"]["id"]])
    set_roles(client, out["cd1"]["h"], out["lect"]["user"]["id"], [R["COMPTA"]["id"], R["AUDIT"]["id"]])
    set_roles(client, out["cd1"]["h"], out["mix"]["user"]["id"], [R["PUBLIC"]["id"]])
    set_roles(client, out["cd3"]["h"], out["b"]["user"]["id"], [R["RH"]["id"]])
    for k in ("a", "lect", "mix", "b"):
        out[k]["h"] = auth(client, out[k]["name"])
    out["A"] = mk_dossier(client, out["a"]["h"], f"Dossier A {tag}")
    out["B"] = mk_dossier(client, out["b"]["h"], f"Dossier B {tag}")
    return out


def upload(client, headers, dossier_id, content, name="note.txt", **form):
    data = {"dossier_id": str(dossier_id), **form}
    raw = content if isinstance(content, bytes) else content.encode()
    return client.post("/documents", headers=headers, files={"fichier": (name, raw, "text/plain")}, data=data)


def add_version(client, headers, doc_id, content, name="note.txt", **form):
    raw = content if isinstance(content, bytes) else content.encode()
    return client.post(f"/documents/{doc_id}/versions", headers=headers, files={"fichier": (name, raw, "text/plain")}, data=form)


def wait_version(client, headers, doc_id, numero, expected="ready", timeout=20):
    deadline = time.time() + timeout
    while time.time() < deadline:
        versions = client.get(f"/documents/{doc_id}/versions", headers=headers).json()
        v = next((x for x in versions if x["numero"] == numero), None)
        if v and v["statut"] in (expected, "error"):
            return v
        time.sleep(0.2)
    raise AssertionError("indexation trop longue")


def ready_doc(client, headers, dossier_id, content, name="note.txt", **form):
    r = upload(client, headers, dossier_id, content, name, **form)
    assert r.status_code == 201, r.text
    assert wait_version(client, headers, r.json()["id"], 1)["statut"] == "ready"
    return r.json()


def ask(client, headers, question, **extra):
    r = client.post("/chat", headers=headers, json={"question": question, **extra})
    assert r.status_code == 200, r.text
    events = {}
    for block in r.text.strip().split("\n\n"):
        name, data = block.split("\n", 1)
        events.setdefault(name[7:], []).append(data[6:])
    return events


def answer_text(events) -> str:
    return "".join(json.loads(t)["t"] for t in events.get("token", []))


def sources_of(events) -> list[dict]:
    return json.loads(events["sources"][0])


def conv_id(events) -> int:
    return json.loads(events["meta"][0])["conversation_id"]


def test_connexion_et_me(client, world):
    me = client.get("/auth/me", headers=world["a"]["h"]).json()
    assert me["role"] == "UTILISATEUR" and me["niveau"] == "AGENT" and me["service_id"] == world["a"]["service"]["id"]
    assert me["division_id"] == world["a"]["division"]["id"] and [r["code"] for r in me["roles_division"]] == ["COMPTA"]
    # un agent n'administre rien : ni comptes, ni structure
    assert "utilisateur.creer" not in me["permissions"] and "structure.gerer" not in me["permissions"]
    assert "chat.utiliser" in me["permissions"] and me["unites_protegees"] is False and me["divisions_gerees"] == []
    chef = client.get("/auth/me", headers=world["cd1"]["h"]).json()
    assert chef["niveau"] == "DIVISION" and "utilisateur.creer" in chef["permissions"] and [d["id"] for d in chef["divisions_gerees"]] == [world["div"]["v1"]["id"]]
    assert client.get("/auth/me", headers=world["admin"]).json()["unites_protegees"] is True
    assert client.get("/auth/me", headers=world["admin"]).json()["niveau"] == "ROOT"
    assert client.get("/auth/me").status_code == 401
    assert client.get("/auth/me", headers={"Authorization": "Bearer faux.jeton"}).status_code == 401


def test_document_corbeille_soft_delete_et_restore(client, world):
    h = world["a"]["h"]  # l'auteur met son fichier à la corbeille et le restaure
    dossier_id = world["A"]["id"]
    doc = ready_doc(client, h, dossier_id, "Document de test corbeille")
    doc_id = doc["id"]
    assert client.delete(f"/documents/{doc_id}", headers=h).status_code == 204
    assert doc_id not in [item["id"] for item in client.get("/documents", headers=h, params={"dossier_id": dossier_id}).json()]
    assert doc_id in [item["id"] for item in client.get("/documents", headers=h, params={"dossier_id": dossier_id, "corbeille": True}).json()]
    assert client.post(f"/documents/{doc_id}/restore", headers=h).status_code == 204
    assert doc_id in [item["id"] for item in client.get("/documents", headers=h, params={"dossier_id": dossier_id}).json()]
    # la purge définitive est réservée au chef de division : l'auteur reçoit 403, le chef 204
    assert client.delete(f"/documents/{doc_id}", headers=h, params={"force": True}).status_code == 403
    assert client.delete(f"/documents/{doc_id}", headers=world["cd1"]["h"], params={"force": True}).status_code == 204


def test_mauvais_mot_de_passe_et_compte_verrouille(client, world):
    assert login(client, world["a"]["name"], "mauvais-mot-de-passe").status_code == 401
    assert login(client, "compte_qui_n_existe_pas").status_code == 401
    with SessionLocal() as db:
        u = db.scalar(select(User).where(User.nom_utilisateur == world["a"]["name"]))
        # un compte verrouillé ('!') ne se connecte jamais, même avec la bonne chaîne
        u.mot_de_passe_hash = "!A_DEFINIR"; db.commit()
    assert login(client, world["a"]["name"]).status_code == 401
    with SessionLocal() as db:
        u = db.scalar(select(User).where(User.nom_utilisateur == world["a"]["name"]))
        u.mot_de_passe_hash = hash_password(PWD); db.commit()
    world["a"]["h"] = auth(client, world["a"]["name"])  # nouveau hash : l'ancien jeton n'est plus valable


def test_desactiver_un_compte_coupe_sa_session(client, world):
    h = world["admin"]
    victim = world["b"]["user"]["id"]
    token = auth(client, world["b"]["name"])
    assert client.patch(f"/users/{victim}", json={"actif": False}, headers=h).status_code == 200
    assert client.get("/auth/me", headers=token).status_code == 401
    assert login(client, world["b"]["name"]).status_code == 401
    assert client.patch(f"/users/{victim}", json={"actif": True}, headers=h).status_code == 200
    world["b"]["h"] = auth(client, world["b"]["name"])


def test_changement_de_mot_de_passe_invalide_les_anciens_jetons(client, world):
    old = auth(client, world["b"]["name"])
    r = client.patch(f"/users/{world['b']['user']['id']}", json={"mot_de_passe": "nouveau-mot-de-passe-2"}, headers=world["admin"])
    assert r.status_code == 200
    assert client.get("/auth/me", headers=old).status_code == 401
    assert login(client, world["b"]["name"], "nouveau-mot-de-passe-2").status_code == 200
    client.patch(f"/users/{world['b']['user']['id']}", json={"mot_de_passe": PWD}, headers=world["admin"])
    world["b"]["h"] = auth(client, world["b"]["name"])


def test_utilisateur_ne_peut_creer_ni_agent_ni_utilisateur_ni_structure(client, world):
    h, svc = world["a"]["h"], world["a"]["service"]["id"]
    tag = uuid.uuid4().hex[:5]
    assert client.post("/users", headers=h, json={"nom_utilisateur": f"x{tag}", "mot_de_passe": PWD, "role": "ADMIN"}).status_code == 403
    assert client.post("/structure/agents", headers=h, json={"matricule": f"Z{tag}", "nom": "a", "prenom": "b", "service_id": svc}).status_code == 403
    assert client.post("/structure/services", headers=h, json={"direction_id": 1, "code": f"Z{tag}", "nom": "x"}).status_code == 403
    assert client.post("/structure/directions", headers=h, json={"code": f"Z{tag}", "nom": "x"}).status_code == 403
    assert client.get("/users", headers=h).status_code == 403
    assert client.get("/structure/agents", headers=h).status_code == 403
    assert client.get("/audit", headers=h).status_code == 403
    assert client.patch(f"/users/{world['b']['user']['id']}", headers=h, json={"role": "ADMIN"}).status_code == 403
    # un chef de division ne crée pas de super administrateur ni de structure
    c = world["cd1"]["h"]
    assert client.post("/users", headers=c, json={"nom_utilisateur": f"y{tag}", "mot_de_passe": PWD, "role": "ADMIN"}).status_code == 403
    assert client.post("/structure/agents", headers=c, json={"matricule": f"Y{tag}", "nom": "a", "prenom": "b", "service_id": svc}).status_code == 403


def test_regles_de_creation_de_compte(client, world):
    h = world["admin"]
    tag = uuid.uuid4().hex[:5]
    # un utilisateur sans agent est refusé : son service n'existerait pas
    r = client.post("/users", headers=h, json={"nom_utilisateur": f"sans_agent_{tag}", "mot_de_passe": PWD, "role": "UTILISATEUR"})
    assert r.status_code == 422
    # un agent n'a qu'un compte
    r = client.post("/users", headers=h, json={"nom_utilisateur": f"doublon_{tag}", "mot_de_passe": PWD, "role": "UTILISATEUR", "agent_id": world["a"]["agent"]["id"]})
    assert r.status_code == 409
    # mot de passe trop court, nom d'utilisateur invalide, doublon de nom
    assert client.post("/users", headers=h, json={"nom_utilisateur": f"court_{tag}", "mot_de_passe": "court", "role": "ADMIN"}).status_code == 422
    assert client.post("/users", headers=h, json={"nom_utilisateur": "A B", "mot_de_passe": PWD, "role": "ADMIN"}).status_code == 422
    assert client.post("/users", headers=h, json={"nom_utilisateur": world["a"]["name"], "mot_de_passe": PWD, "role": "ADMIN", "agent_id": None}).status_code == 409
    # le rôle GESTIONNAIRE n'existe plus
    assert client.post("/users", headers=h, json={"nom_utilisateur": f"g_{tag}", "mot_de_passe": PWD, "role": "GESTIONNAIRE"}).status_code == 422


def test_garde_fous_admin(client, world):
    h = world["admin"]
    me = client.get("/auth/me", headers=h).json()
    assert client.patch(f"/users/{me['id']}", headers=h, json={"actif": False}).status_code == 409
    assert client.patch(f"/users/{me['id']}", headers=h, json={"role": "UTILISATEUR", "agent_id": world["a"]["agent"]["id"]}).status_code in (409, 422)




# --- fichiers, versions, cases ----------------------------------------------------------------------------------------

def test_creation_ajout_de_version_et_historique(client, world):
    a = world["a"]["h"]
    A = world["A"]["id"]
    doc = ready_doc(client, a, A, "Le délai de paiement des factures est de 15 jours.", titre="Contrat fournisseur")
    assert doc["dossier_id"] == A and doc["titre"] == "Contrat fournisseur" and doc["nb_versions"] == 1
    assert "contenu" not in doc and doc["version"]["numero"] == 1
    r = add_version(client, a, doc["id"], "Le délai de paiement des factures est de 30 jours.", name="contrat_v2.txt")
    assert r.status_code == 201 and r.json()["nb_versions"] == 2 and r.json()["version"]["numero"] == 2
    assert wait_version(client, a, doc["id"], 2)["statut"] == "ready"

    versions = client.get(f"/documents/{doc['id']}/versions", headers=a).json()
    assert [v["numero"] for v in versions] == [2, 1]                      # la plus récente d'abord
    assert [v["est_courante"] for v in versions] == [True, False]
    assert versions[0]["nom_fichier"] == "contrat_v2.txt" and versions[1]["nom_fichier"] == "note.txt"
    assert versions[0]["cree_le"] >= versions[1]["cree_le"] and versions[0]["cree_par_nom"] == world["a"]["name"]

    # l'ancienne version n'a pas été touchée : fichier, chunks, contenu
    with SessionLocal() as db:
        v1, v2 = db.scalars(select(DocumentVersion).where(DocumentVersion.document_id == doc["id"]).order_by(DocumentVersion.numero)).all()
        assert Path(v1.chemin_stockage).exists() and Path(v2.chemin_stockage).exists() and v1.chemin_stockage != v2.chemin_stockage
        t1 = " ".join(db.scalars(select(Chunk.contenu).where(Chunk.document_version_id == v1.id)))
        t2 = " ".join(db.scalars(select(Chunk.contenu).where(Chunk.document_version_id == v2.id)))
    assert "15 jours" in t1 and "30 jours" in t2
    dl1 = client.get(f"/documents/{doc['id']}/versions/1/telecharger", headers=a)
    assert dl1.status_code == 200 and b"15 jours" in dl1.content

    # une version identique à la dernière est refusée ; la restauration d'une plus ancienne reste possible
    assert add_version(client, a, doc["id"], "Le délai de paiement des factures est de 30 jours.").status_code == 409
    assert add_version(client, a, doc["id"], "Le délai de paiement des factures est de 15 jours.").status_code == 201

    # suppression de la version la plus récente : la précédente redevient la version courante
    wait_version(client, a, doc["id"], 3)
    g = world["cd1"]["h"]  # supprimer une version est réservé au chef de division
    assert client.delete(f"/documents/{doc['id']}/versions/3", headers=a).status_code == 403
    assert client.delete(f"/documents/{doc['id']}/versions/3", headers=g).status_code == 204
    assert client.delete(f"/documents/{doc['id']}/versions/3", headers=g).status_code == 404
    assert [v["est_courante"] for v in client.get(f"/documents/{doc['id']}/versions", headers=a).json()] == [True, False]

    # suppression du fichier : versions, chunks et fichiers du disque partent
    paths = [v.chemin_stockage for v in (v1, v2)]
    assert client.delete(f"/documents/{doc['id']}", headers=g, params={"force": True}).status_code == 204
    with SessionLocal() as db:
        assert db.get(Document, doc["id"]) is None
        assert db.scalar(select(DocumentVersion.id).where(DocumentVersion.document_id == doc["id"])) is None
        assert db.scalar(select(Chunk.id).where(Chunk.document_id == doc["id"])) is None
    assert not any(Path(p).exists() for p in paths)


def test_validation_des_depots(client, world):
    a, A = world["a"]["h"], world["A"]["id"]
    assert upload(client, a, A, "x", name="virus.exe").status_code == 415
    assert upload(client, a, A, "<html></html>", name="page.html").status_code == 415   # jamais de HTML
    assert upload(client, a, A, "", name="vide.txt").status_code == 422
    assert upload(client, a, A, "pas un pdf", name="faux.pdf").status_code == 422
    assert client.post("/documents", headers=a, files={"fichier": ("n.txt", b"x", "text/plain")}).status_code == 422  # sans dossier
    content = "Contenu unique pour le test de doublon " + world["tag"]
    first = upload(client, a, A, content, name="d.txt")
    assert first.status_code == 201
    assert upload(client, a, A, content, name="copie.txt").status_code == 409            # doublon dans le même dossier
    assert upload(client, world["b"]["h"], world["B"]["id"], content, name="d.txt").status_code == 201  # autre dossier : accepté
    r = upload(client, a, A, "contenu avec un nom piégé " + world["tag"], name="../../etc/passwd.txt")
    assert r.status_code == 201 and r.json()["version"]["nom_fichier"] == "passwd.txt"
    with SessionLocal() as db:
        assert ".." not in db.scalar(select(DocumentVersion.chemin_stockage).where(DocumentVersion.document_id == r.json()["id"]))


def test_document_illisible_passe_en_erreur_avec_message(client, world):
    a = world["a"]["h"]
    r = client.post("/documents", headers=a, data={"dossier_id": str(world["A"]["id"])}, files={"fichier": ("faux.xlsx", b"ce n'est pas un classeur", "application/octet-stream")})
    assert r.status_code == 201
    v = wait_version(client, a, r.json()["id"], 1)
    assert v["statut"] == "error" and v["message_erreur"]


def test_regle_des_cases_tableaux_et_images(client, world):
    a, A = world["a"]["h"], world["A"]["id"]
    tag = world["tag"]
    # tableur : case imposée, même si le client envoie faux ; non décochable
    csv = ready_doc(client, a, A, f"Produit;Prix\nRiz;2500\nHuile;7000 {tag}\n", name=f"prix_{tag}.csv", contient_tableaux="false")
    assert csv["has_tabular"] is True and csv["tableaux_imposes"] is True and csv["has_image"] is False
    r = client.patch(f"/documents/{csv['id']}", headers=a, data={"contient_tableaux": "false"})
    assert r.json()["has_tabular"] is True
    # image : case images imposée (l'OCR n'est pas lancé ici, l'indexation échoue sans serveur OCR : sans importance)
    img = upload(client, a, A, b"\x89PNG\r\n\x1a\n" + tag.encode(), name=f"scan_{tag}.png")
    assert img.status_code == 201 and img.json()["has_image"] is True and img.json()["images_imposees"] is True
    assert client.patch(f"/documents/{img.json()['id']}", headers=a, data={"contient_images": "false"}).json()["has_image"] is True
    # texte : cases libres ; un changement relance la lecture de la version la plus récente
    txt = ready_doc(client, a, A, f"Note simple {tag}")
    assert txt["has_tabular"] is False and txt["tableaux_imposes"] is False
    r = client.patch(f"/documents/{txt['id']}", headers=a, data={"contient_tableaux": "true", "contient_images": "true"})
    assert r.status_code == 200 and r.json()["has_tabular"] is True and r.json()["has_image"] is True
    assert r.json()["version"]["statut"] in ("pending", "processing", "ready")
    assert wait_version(client, a, txt["id"], 1)["statut"] == "ready"
    # une nouvelle version d'un autre type applique la règle du nouveau type
    r = add_version(client, a, txt["id"], f"Col;Val\nA;1 {tag}\n", name="tab.csv", contient_tableaux="false")
    assert r.json()["has_tabular"] is True and r.json()["tableaux_imposes"] is True


def test_taille_ref_et_top_k_dynamique(client, world):
    a, A = world["a"]["h"], world["A"]["id"]
    long_text = "\n\n".join(f"Paragraphe {i} sur le règlement intérieur {world['tag']}. " + "mot " * 220 for i in range(12))
    doc = ready_doc(client, a, A, long_text, name="long.txt")
    with SessionLocal() as db:
        v = db.scalar(select(DocumentVersion).where(DocumentVersion.document_id == doc["id"]))
        rows = db.execute(select(Chunk.taille_ref).where(Chunk.document_version_id == v.id)).scalars().all()
    assert len(rows) > 5 and set(rows) == {len(rows)}                 # taille_ref = nombre de chunks de la version
    ev = ask(client, a, f"règlement intérieur {world['tag']} paragraphe")
    n = len(sources_of(ev))
    assert 3 <= n <= 8 and n >= 3


# --- aperçu et téléchargement : sécurité ------------------------------------------------------------------------------

def test_apercu_et_telechargement_sont_surs(client, world, monkeypatch):
    a, A = world["a"]["h"], world["A"]["id"]
    doc = ready_doc(client, a, A, f"Texte <script>alert(1)</script> {world['tag']}", name="note é.txt")
    p = client.get(f"/documents/{doc['id']}/versions/1/apercu", headers=a)
    assert p.status_code == 200 and p.headers["content-type"].startswith("text/plain")   # jamais text/html
    assert p.headers["x-content-type-options"] == "nosniff" and "sandbox" in p.headers["content-security-policy"]
    assert p.headers["content-disposition"].startswith("inline")
    d = client.get(f"/documents/{doc['id']}/versions/1/telecharger", headers=a)
    assert d.headers["content-type"] == "application/octet-stream" and d.headers["x-content-type-options"] == "nosniff"
    assert d.headers["content-disposition"].startswith("attachment") and "UTF-8''note%20%C3%A9.txt" in d.headers["content-disposition"]
    assert client.get(f"/documents/{doc['id']}/versions/9/apercu", headers=a).status_code == 404
    assert client.get(f"/documents/{doc['id']}/versions/1/apercu").status_code == 401

    # Office : converti en PDF par LibreOffice ; sans LibreOffice, message clair (501)
    word = client.post("/documents", headers=a, data={"dossier_id": str(A)}, files={"fichier": ("lettre.docx", b"PK\x03\x04 pas un vrai docx " + world["tag"].encode(), "application/octet-stream")}).json()
    assert word["version"]["apercu"] == "pdf_converti"
    monkeypatch.setattr("app.services.documents.apercu.shutil.which", lambda _: None)
    assert client.get(f"/documents/{word['id']}/versions/1/apercu", headers=a).status_code == 501
    fake_pdf = Path(os.environ["UPLOAD_DIR"]) / "faux_apercu.pdf"
    fake_pdf.write_bytes(b"%PDF-1.4 test")
    monkeypatch.setattr("app.services.documents.apercu.convert_to_pdf", lambda version: fake_pdf)
    r = client.get(f"/documents/{word['id']}/versions/1/apercu", headers=a)
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf" and r.content.startswith(b"%PDF")
    assert client.get(f"/documents/{word['id']}/versions/1/telecharger", headers=a).headers["content-type"] == "application/octet-stream"

    # fichier absent du disque : 410, pas de 500
    with SessionLocal() as db:
        Path(db.scalar(select(DocumentVersion.chemin_stockage).where(DocumentVersion.document_id == doc["id"]))).unlink()
    assert client.get(f"/documents/{doc['id']}/versions/1/apercu", headers=a).status_code == 410
    # .tif : pas d'aperçu navigateur
    tif = upload(client, a, A, b"II*\x00" + world["tag"].encode(), name="scan.tif").json()
    assert client.get(f"/documents/{tif['id']}/versions/1/apercu", headers=a).status_code == 415


def test_chat_limite_aux_fichiers_lisibles(client, world):
    a, b, adm = world["a"]["h"], world["b"]["h"], world["admin"]
    secret = f"codezeta{world['tag']}"
    doc = ready_doc(client, a, world["A"]["id"], f"Le code d'accès du coffre est {secret} et il est valable 30 jours.", name=f"coffre_{secret}.txt", titre="Procédure coffre")
    ev = ask(client, a, f"Quel est le code {secret} du coffre ?")
    assert {"meta", "sources", "token", "done"} <= set(ev)
    src = sources_of(ev)
    assert any(s["titre"] == "Procédure coffre" and s["dossier_id"] == world["A"]["id"] and s["version"] == 1 and s["date"] for s in src)
    assert "30 jours" in answer_text(ev)
    # l'agent d'une autre division n'a aucun accès
    assert not any(s["document_id"] == doc["id"] for s in sources_of(ask(client, b, f"Quel est le code {secret} du coffre ?")))
    # le super administrateur ne lit rien sans déverrouiller la division : l'accès au chat est refusé tant qu'aucune n'est ouverte
    assert client.post("/chat", headers=adm, json={"question": "x"}).status_code == 403
    secret_et_deverrouillage(client, adm, "division", world["div"]["v1"]["id"])
    assert any(s["document_id"] == doc["id"] for s in sources_of(ask(client, adm, f"Quel est le code {secret} du coffre ?")))
    client.post("/securite/verrouiller", headers=adm, json={"type": "division", "unite_id": world["div"]["v1"]["id"]})
    assert client.post("/chat", headers=adm, json={"question": "x"}).status_code == 403
    # un agent qui n'a aucun fichier lisible : refus net (mix : rôle PUBLIC, aucun fichier déposé ni classé PUBLIC)
    assert client.post("/chat", headers=world["mix"]["h"], json={"question": "x"}).status_code == 403
    assert client.post("/chat", json={"question": "x"}).status_code == 401


def test_conversations_personnelles(client, world):
    a, b = world["a"]["h"], world["b"]["h"]
    ev = ask(client, a, "Une question quelconque pour créer une conversation")
    cid = conv_id(ev)
    msgs = client.get(f"/chat/conversations/{cid}", headers=a).json()
    assert [m["emetteur"] for m in msgs] == ["utilisateur", "assistant"]
    assert client.get(f"/chat/conversations/{cid}", headers=b).status_code == 404
    assert client.post("/chat", headers=b, json={"question": "intrus", "conversation_id": cid}).status_code == 404
    assert client.delete(f"/chat/conversations/{cid}", headers=b).status_code == 404
    assert client.delete(f"/chat/conversations/{cid}", headers=a).status_code == 204


def test_sources_portent_version_et_date_et_filtre_derniere_version(client, world):
    a, A = world["a"]["h"], world["A"]["id"]
    tag = world["tag"]
    doc = ready_doc(client, a, A, f"Règle indemnités {tag} : le plafond est de quinze jours.", titre="Indemnités")
    assert add_version(client, a, doc["id"], f"Règle indemnités {tag} : le plafond est de trente jours.").status_code == 201
    wait_version(client, a, doc["id"], 2)
    q = f"plafond indemnités {tag}"
    mine = lambda ev: sorted(s["version"] for s in sources_of(ev) if s["document_id"] == doc["id"])  # noqa: E731
    assert mine(ask(client, a, q)) == [1, 2]                        # toutes les versions sont interrogeables
    # le prompt indique la version la plus récente et l'ancienne
    contexte = str(qa_calls()[-1][-1].content)
    assert "version 2" in contexte and "(la plus récente)" in contexte and "(ancienne version)" in contexte
    assert client.put("/chat/preferences", headers=a, json={"derniere_version_seulement": True}).json() == {
        "memoire_inter_sessions": False, "derniere_version_seulement": True}
    assert mine(ask(client, a, q)) == [2]                           # dernière version seulement
    assert client.get("/chat/preferences", headers=a).json()["derniere_version_seulement"] is True
    # la préférence est personnelle
    assert client.get("/chat/preferences", headers=world["b"]["h"]).json()["derniere_version_seulement"] is False
    client.put("/chat/preferences", headers=a, json={"derniere_version_seulement": False})
    # si la version 2 est supprimée, la 1 redevient la version qui fait foi
    # purger une version est réservé au gérant (chef de la division), pas à l'auteur
    assert client.delete(f"/documents/{doc['id']}/versions/2", headers=a).status_code == 403
    assert client.delete(f"/documents/{doc['id']}/versions/2", headers=world["cd1"]["h"]).status_code == 204
    client.put("/chat/preferences", headers=a, json={"derniere_version_seulement": True})
    assert mine(ask(client, a, q)) == [1]
    client.put("/chat/preferences", headers=a, json={"derniere_version_seulement": False})
    client.delete(f"/documents/{doc['id']}", headers=a)


def test_memoire_dans_la_session_survit_a_la_reconnexion(client, world):
    a, A = world["a"], world["A"]["id"]
    tag = world["tag"]
    ready_doc(client, a["h"], A, f"Le délai de paiement des factures {tag} est de 30 jours.", titre="Factures")
    LLM_CALLS.clear()
    cid = conv_id(ask(client, a["h"], f"Quel est le délai de paiement des factures {tag} ?"))
    assert not condense_calls()                                      # première question : rien à reformuler
    # déconnexion/reconnexion : nouveau jeton, même conversation
    client.post("/auth/logout", headers=a["h"])
    again = auth(client, a["name"])
    assert len(client.get(f"/chat/conversations/{cid}", headers=again).json()) == 2
    LLM_CALLS.clear()
    ask(client, again, "Et pour les paiements en retard ?", conversation_id=cid)
    assert condense_calls(), "la question de suivi doit être reformulée à partir de l'historique"
    history = " ".join(str(m.content) for m in qa_calls()[-1][1:-1])   # messages entre le système et la question
    assert f"Quel est le délai de paiement des factures {tag}" in history and "30 jours" in history
    assert "Et pour les paiements en retard ?" in str(condense_calls()[-1][-1].content)
    # la recherche utilise la question reformulée : le contexte envoyé au LLM vient de STANDALONE (délai de paiement)
    assert "30 jours" in str(qa_calls()[-1][-1].content)
    # une nouvelle conversation ne reçoit pas l'historique de l'ancienne
    LLM_CALLS.clear()
    ask(client, again, "Autre sujet")
    assert not any(f"délai de paiement des factures {tag}" in str(m.content) for m in qa_calls()[-1][1:-1])


def test_retrait_d_un_role_masque_l_historique_et_coupe_la_memoire(client, world):
    chef, mix, R = world["cd1"]["h"], world["mix"], world["roles"]
    tag = world["tag"]
    # le chef dépose un fichier classé AUDIT (mix n'a pas ce rôle) et un fichier classé PUBLIC (mix le lit toujours)
    def depose(texte, titre, role):
        r = upload(client, chef, world["A"]["id"], texte, titre=titre, role_ids=[role["id"]])
        assert r.status_code == 201, r.text
        assert wait_version(client, chef, r.json()["id"], 1)["statut"] == "ready"
        return r.json()
    depose(f"Note publique {tag} sur les horaires.", "Note publique", R["PUBLIC"])
    budget = depose(f"Le budget confidentiel {tag} de la mission est de 30 jours de travail.", "Budget audit", R["AUDIT"])
    assert client.get(f"/documents/{budget['id']}", headers=mix["h"]).status_code == 403
    set_roles(client, chef, mix["user"]["id"], [R["PUBLIC"]["id"], R["AUDIT"]["id"]])
    assert client.put("/chat/preferences", headers=mix["h"], json={"memoire_inter_sessions": True}).json()["memoire_inter_sessions"] is True
    ev = ask(client, mix["h"], f"budget confidentiel {tag} mission")
    cid = conv_id(ev)
    assert any(s["document_id"] == budget["id"] for s in sources_of(ev))
    with SessionLocal() as db:
        mem = db.scalars(select(MemoireChat).where(MemoireChat.user_id == mix["user"]["id"])).all()
    assert mem and budget["id"] in mem[-1].document_ids and "Résultat" in mem[-1].resume

    # nouvelle conversation, accès intact : la mémoire enrichit le prompt
    LLM_CALLS.clear()
    ask(client, mix["h"], f"budget confidentiel {tag} mission, rappel")
    assert "Résultat : " in str(qa_calls()[-1][-1].content)

    # retrait du rôle AUDIT : l'historique affiché est masqué, la mémoire devient muette, le LLM ne reçoit plus rien du fichier
    set_roles(client, chef, mix["user"]["id"], [R["PUBLIC"]["id"]])
    msgs = client.get(f"/chat/conversations/{cid}", headers=mix["h"]).json()
    assistant = [m for m in msgs if m["emetteur"] == "assistant"][0]
    assert assistant["masque"] is True and assistant["sources"] == [] and "masquée" in assistant["contenu"] and "30 jours" not in assistant["contenu"]
    LLM_CALLS.clear()
    ev = ask(client, mix["h"], "Et alors ?", conversation_id=cid)
    prompt = " ".join(str(m.content) for m in qa_calls()[-1])
    assert "30 jours" not in prompt and "Résultat : " not in prompt and "(aucune)" in prompt
    assert not any(s["document_id"] == budget["id"] for s in sources_of(ev))
    # le rôle revient : l'historique réapparaît
    set_roles(client, chef, mix["user"]["id"], [R["PUBLIC"]["id"], R["AUDIT"]["id"]])
    assistant = [m for m in client.get(f"/chat/conversations/{cid}", headers=mix["h"]).json() if m["emetteur"] == "assistant"][0]
    assert assistant["masque"] is False and assistant["sources"]
    set_roles(client, chef, mix["user"]["id"], [R["PUBLIC"]["id"]])
    client.put("/chat/preferences", headers=mix["h"], json={"memoire_inter_sessions": False})


def test_la_memoire_entre_sessions_est_desactivee_par_defaut(client, world):
    u = world["lect"]
    ready_doc(client, u["h"], world["A"]["id"], "Un fichier pour que lect puisse interroger " + world["tag"])
    assert client.get("/chat/preferences", headers=u["h"]).json() == {"memoire_inter_sessions": False, "derniere_version_seulement": False}
    ask(client, u["h"], "question sans mémoire")
    with SessionLocal() as db:
        assert db.scalars(select(MemoireChat).where(MemoireChat.user_id == u["user"]["id"])).first() is None


def test_audit_trace_les_actions(client, world):
    rows = client.get("/audit", headers=world["admin"], params={"limit": 500}).json()
    actions = {r["action"] for r in rows}
    assert {"connexion.reussie", "connexion.echec", "utilisateur.creer", "document.creer", "document.corbeille",
            "document.supprimer_definitivement", "document.version_ajouter", "document.version_supprimer", "dossier.creer",
            "structure.agent.creer", "securite.deverrouillage"} <= actions
    assert all("mot_de_passe" not in str(r["detail"]) or r["detail"].get("mot_de_passe") == "réinitialisé" for r in rows)


# --- vecteurs : normalisation et produit scalaire ------------------------------------------------------------------------

def test_tous_les_vecteurs_en_base_sont_normalises(client, world):
    """Le faux modèle renvoie des vecteurs de norme 3,7 : ils doivent tous être ramenés à 1 avant d'être écrits."""
    from sqlalchemy import func, text

    a = world["a"]["h"]
    ready_doc(client, a, world["A"]["id"], "Passage pour vérifier la normalisation des vecteurs " + world["tag"], name="norm.txt")
    with SessionLocal() as db:
        total = db.scalar(select(func.count(Chunk.id)))
        bad = db.scalar(text("SELECT count(*) FROM chunk WHERE abs(vector_norm(embedding) - 1) > 0.001"))
    assert total > 0 and bad == 0


def test_la_base_refuse_un_vecteur_non_normalise(client, world):
    from sqlalchemy.exc import IntegrityError

    a = world["a"]["h"]
    doc = ready_doc(client, a, world["A"]["id"], "Document pour tester la contrainte " + world["tag"], name="contrainte.txt")
    with SessionLocal() as db:
        vid = db.scalar(select(DocumentVersion.id).where(DocumentVersion.document_id == doc["id"]))
        db.add(Chunk(document_id=doc["id"], document_version_id=vid, chunk_index=999, contenu="x", embedding=[2.0] * 768))
        with pytest.raises(IntegrityError, match="ck_chunk_embedding_normalise"):
            db.commit()


def test_produit_scalaire_et_cosinus_donnent_le_meme_classement(client, world):
    """Sur des vecteurs normalisés, <#> = -(produit scalaire) et <=> = 1 - produit scalaire : donc cos = 1 + <#>,
    et classer par <#> classe aussi par cosinus (on compare les valeurs, car des textes identiques font des ex æquo)."""
    q = [x / FakeEmbeddings.scale for x in FakeEmbeddings().embed_query("code coffre procédure")]
    ip = Chunk.embedding.max_inner_product(q).label("ip")
    cos = Chunk.embedding.cosine_distance(q).label("cos")
    with SessionLocal() as db:
        rows = db.execute(select(Chunk.id, ip, cos).order_by(ip).limit(15)).all()
    assert len(rows) > 3
    assert all(abs((1 + r.ip) - r.cos) < 1e-4 for r in rows)
    cosines = [r.cos for r in rows]
    assert all(a <= b + 1e-6 for a, b in zip(cosines, cosines[1:]))

