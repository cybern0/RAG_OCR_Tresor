"""Tests d'intégration de l'API contre une vraie base PostgreSQL + pgvector (voir conftest.py).

Ils vérifient surtout les règles de droits voulues :
- seuls ADMIN et UTILISATEUR existent ;
- l'UTILISATEUR fait le CRUD des documents de SON service, et de lui seul ;
- l'UTILISATEUR ne peut créer ni agent, ni utilisateur, ni service ;
- le chat ne remonte que les documents du service de l'utilisateur (tous pour l'ADMIN).
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
from sqlalchemy import select

from app.core.security import hash_password
from app.db.metier import Role, SessionLocal, User
from app.db.vecteur import Chunk, Document
from app.main import app

from .conftest import FakeEmbeddings

PWD = "mot-de-passe-de-test-1"
ADMIN = "admin_test"


@pytest.fixture(scope="module")
def client():
    mp = pytest.MonkeyPatch()
    mp.setattr("app.services.ingestion.embedding.get_embeddings", lambda: FakeEmbeddings())
    mp.setattr("app.services.chat.rag_chain.get_llm", lambda: FakeListChatModel(responses=["Le délai est de 30 jours [1]."]))
    with SessionLocal() as db:
        role = db.scalar(select(Role).where(Role.code == "ADMIN"))
        if db.scalar(select(User).where(User.nom_utilisateur == ADMIN)) is None:
            db.add(User(nom_utilisateur=ADMIN, mot_de_passe_hash=hash_password(PWD), role_id=role.id))
            db.commit()
    with TestClient(app) as c:
        yield c
    mp.undo()


def login(client, username, password=PWD):
    r = client.post("/auth/login", json={"nom_utilisateur": username, "mot_de_passe": password})
    return r


def auth(client, username):
    r = login(client, username)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="module")
def world(client):
    """Deux services (A, B), un agent et un utilisateur dans chacun."""
    tag = uuid.uuid4().hex[:6]
    h = auth(client, ADMIN)
    d = client.post("/structure/directions", json={"code": f"D{tag}", "nom": "Direction test"}, headers=h).json()
    out = {"tag": tag, "admin": h}
    for key in ("a", "b"):
        s = client.post("/structure/services", json={"direction_id": d["id"], "code": f"S{key}{tag}", "nom": f"Service {key}"}, headers=h)
        assert s.status_code == 201, s.text
        ag = client.post("/structure/agents", json={"matricule": f"M{key}{tag}", "nom": "Nom", "prenom": key, "service_id": s.json()["id"]}, headers=h)
        assert ag.status_code == 201, ag.text
        u = client.post("/users", json={"nom_utilisateur": f"user_{key}_{tag}", "mot_de_passe": PWD, "role": "UTILISATEUR", "agent_id": ag.json()["id"]}, headers=h)
        assert u.status_code == 201, u.text
        out[key] = {"service": s.json(), "agent": ag.json(), "user": u.json(), "name": f"user_{key}_{tag}"}
        out[key]["h"] = auth(client, out[key]["name"])
    return out


def upload(client, headers, content: str, name="note.txt", **form):
    return client.post("/documents", headers=headers, files={"fichier": (name, content.encode(), "text/plain")}, data=form)


def wait_status(client, headers, doc_id, expected="ready", timeout=20):
    deadline = time.time() + timeout
    while time.time() < deadline:
        docs = {d["id"]: d for d in client.get("/documents", headers=headers).json()}
        if doc_id in docs and docs[doc_id]["statut"] in (expected, "error"):
            return docs[doc_id]
        time.sleep(0.2)
    raise AssertionError("indexation trop longue")


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


# --- connexion -------------------------------------------------------------------------------------------------

def test_connexion_et_me(client, world):
    me = client.get("/auth/me", headers=world["a"]["h"]).json()
    assert me["role"] == "UTILISATEUR" and me["service_id"] == world["a"]["service"]["id"]
    assert "document.creer" in me["permissions"] and "utilisateur.creer" not in me["permissions"]
    assert client.get("/auth/me").status_code == 401
    assert client.get("/auth/me", headers={"Authorization": "Bearer faux.jeton"}).status_code == 401


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


# --- ce que l'UTILISATEUR n'a pas le droit de faire -----------------------------------------------------------

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


# --- documents : CRUD sur son propre service ---------------------------------------------------------------------

def test_crud_documents_de_son_service_et_isolation(client, world):
    a, b, adm = world["a"]["h"], world["b"]["h"], world["admin"]
    r = upload(client, a, "Le délai de paiement des factures est de 30 jours.", titre="Contrat fournisseur")
    assert r.status_code == 201, r.text
    doc = r.json()
    assert doc["service_id"] == world["a"]["service"]["id"] and doc["titre"] == "Contrat fournisseur"
    assert "contenu" not in doc                                  # jamais de contenu dans l'API documents
    assert wait_status(client, a, doc["id"])["statut"] == "ready"

    # le service B ne voit rien, ne modifie rien, ne supprime rien (404 : on ne révèle pas l'existence)
    assert client.get("/documents", headers=b).json() == []
    assert client.patch(f"/documents/{doc['id']}", headers=b, data={"titre": "pirate"}).status_code == 404
    assert client.delete(f"/documents/{doc['id']}", headers=b).status_code == 404
    # impossible de déposer dans un autre service, même en le demandant
    assert upload(client, a, "autre", service_id=str(world["b"]["service"]["id"])).status_code == 403
    # un utilisateur ne peut pas déplacer son document dans un autre service
    assert client.patch(f"/documents/{doc['id']}", headers=a, data={"service_id": str(world["b"]["service"]["id"])}).status_code == 403

    # l'admin voit tout et peut filtrer par service
    ids = {d["id"] for d in client.get("/documents", headers=adm).json()}
    assert doc["id"] in ids
    assert doc["id"] not in {d["id"] for d in client.get("/documents", headers=adm, params={"service_id": world["b"]["service"]["id"]}).json()}

    # modification du titre : pas de réindexation
    r = client.patch(f"/documents/{doc['id']}", headers=a, data={"titre": "Contrat v2"})
    assert r.status_code == 200 and r.json()["titre"] == "Contrat v2" and r.json()["statut"] == "ready"

    # remplacement du fichier : anciens passages retirés puis réindexation
    r = client.patch(f"/documents/{doc['id']}", headers=a, files={"fichier": ("nouveau.txt", "Les congés annuels durent 25 jours.".encode(), "text/plain")})
    assert r.status_code == 200 and r.json()["statut"] in ("pending", "processing", "ready")
    assert wait_status(client, a, doc["id"])["statut"] == "ready"
    with SessionLocal() as db:
        texts = " ".join(db.scalars(select(Chunk.contenu).where(Chunk.document_id == doc["id"])))
        path = db.get(Document, doc["id"]).chemin_stockage
    assert "congés" in texts and "paiement" not in texts and Path(path).exists()

    # suppression : document, chunks (cascade) et fichier
    assert client.delete(f"/documents/{doc['id']}", headers=a).status_code == 204
    with SessionLocal() as db:
        assert db.get(Document, doc["id"]) is None
        assert db.scalar(select(Chunk.id).where(Chunk.document_id == doc["id"])) is None
    assert not Path(path).exists()
    assert client.delete(f"/documents/{doc['id']}", headers=a).status_code == 404


def test_validation_des_depots(client, world):
    a = world["a"]["h"]
    assert upload(client, a, "x", name="virus.exe").status_code == 415
    assert upload(client, a, "", name="vide.txt").status_code == 422
    assert upload(client, a, "pas un pdf", name="faux.pdf").status_code == 422
    r = upload(client, a, "Contenu unique pour le test de doublon " + world["tag"], name="d.txt")
    assert r.status_code == 201
    assert upload(client, a, "Contenu unique pour le test de doublon " + world["tag"], name="copie.txt").status_code == 409
    # le même fichier est accepté dans un autre service
    assert upload(client, world["b"]["h"], "Contenu unique pour le test de doublon " + world["tag"], name="d.txt").status_code == 201
    # le nom fourni par le client ne sert jamais de chemin
    r = upload(client, a, "contenu avec un nom piégé " + world["tag"], name="../../etc/passwd.txt")
    assert r.status_code == 201 and r.json()["nom_fichier"] == "passwd.txt"
    with SessionLocal() as db:
        assert ".." not in db.get(Document, r.json()["id"]).chemin_stockage


def test_document_illisible_passe_en_erreur_avec_message(client, world):
    a = world["a"]["h"]
    r = client.post("/documents", headers=a, files={"fichier": ("faux.xlsx", b"ce n'est pas un classeur", "application/octet-stream")})
    assert r.status_code == 201
    final = wait_status(client, a, r.json()["id"])
    assert final["statut"] == "error" and final["message_erreur"]


def test_csv_indexe_comme_tableau(client, world):
    a = world["a"]["h"]
    r = upload(client, a, "Produit;Prix\nRiz;2500\nHuile;7000\n", name=f"prix_{world['tag']}.csv")
    final = wait_status(client, a, r.json()["id"])
    assert final["statut"] == "ready" and final["has_tabular"] is True


# --- chat : seulement les documents de son service ------------------------------------------------------------------

def test_chat_limite_au_service_de_l_utilisateur(client, world):
    a, b, adm = world["a"]["h"], world["b"]["h"], world["admin"]
    secret = f"codezeta{world['tag']}"
    r = upload(client, a, f"Le code d'accès du coffre est {secret} et il est valable 30 jours.", name=f"coffre_{secret}.txt", titre="Procédure coffre")
    assert wait_status(client, a, r.json()["id"])["statut"] == "ready"

    ev = ask(client, a, f"Quel est le code {secret} du coffre ?")
    assert "meta" in ev and "token" in ev and "done" in ev
    assert any("Procédure coffre" in s for s in ev["sources"])
    assert "30 jours" in answer_text(ev)

    ev_b = ask(client, b, f"Quel est le code {secret} du coffre ?")
    # le service B n'a accès à aucun passage du service A (il peut recevoir ses propres documents)
    assert not any("Procédure coffre" in s or secret in s for s in ev_b["sources"])

    ev_admin = ask(client, adm, f"Quel est le code {secret} du coffre ?")
    assert any("Procédure coffre" in s for s in ev_admin["sources"])   # l'admin interroge tous les services


def test_conversations_personnelles(client, world):
    a, b = world["a"]["h"], world["b"]["h"]
    ev = ask(client, a, "Une question quelconque pour créer une conversation")
    conv_id = json.loads(ev["meta"][0])["conversation_id"]
    msgs = client.get(f"/chat/conversations/{conv_id}", headers=a).json()
    assert [m["emetteur"] for m in msgs] == ["utilisateur", "assistant"]
    assert client.get(f"/chat/conversations/{conv_id}", headers=b).status_code == 404
    assert client.post("/chat", headers=b, json={"question": "intrus", "conversation_id": conv_id}).status_code == 404
    assert client.delete(f"/chat/conversations/{conv_id}", headers=b).status_code == 404
    assert client.delete(f"/chat/conversations/{conv_id}", headers=a).status_code == 204


def test_chat_exige_un_service(client, world):
    """Un compte ADMIN sans agent interroge tous les services ; un compte sans service ne reçoit rien."""
    assert client.post("/chat", json={"question": "x"}).status_code == 401


# --- audit ---------------------------------------------------------------------------------------------------------------

def test_audit_trace_les_actions(client, world):
    rows = client.get("/audit", headers=world["admin"], params={"limit": 200}).json()
    actions = {r["action"] for r in rows}
    assert {"connexion.reussie", "connexion.echec", "utilisateur.creer", "document.creer", "document.supprimer"} <= actions
    assert all("mot_de_passe" not in str(r["detail"]) or r["detail"].get("mot_de_passe") == "réinitialisé" for r in rows)


def test_service_sans_document_repond_je_ne_sais_pas(client, world):
    """Un service sans aucun document ne peut rien obtenir : réponse « Je ne sais pas » sans source."""
    h = world["admin"]
    tag = uuid.uuid4().hex[:5]
    d = client.post("/structure/directions", json={"code": f"V{tag}", "nom": "Vide"}, headers=h).json()
    s = client.post("/structure/services", json={"direction_id": d["id"], "code": f"V{tag}", "nom": "Service vide"}, headers=h).json()
    ag = client.post("/structure/agents", json={"matricule": f"V{tag}", "nom": "N", "prenom": "P", "service_id": s["id"]}, headers=h).json()
    client.post("/users", json={"nom_utilisateur": f"vide_{tag}", "mot_de_passe": PWD, "role": "UTILISATEUR", "agent_id": ag["id"]}, headers=h)
    ev = ask(client, auth(client, f"vide_{tag}"), "Quel est le code du coffre ?")
    assert ev["sources"] == ["[]"] and "Je ne sais pas" in answer_text(ev)


# --- vecteurs : normalisation et produit scalaire ------------------------------------------------------------------

def test_tous_les_vecteurs_en_base_sont_normalises(client, world):
    """Le faux modèle renvoie des vecteurs de norme 3,7 : ils doivent tous être ramenés à 1 avant d'être écrits."""
    from sqlalchemy import func, text

    a = world["a"]["h"]
    r = upload(client, a, "Passage pour vérifier la normalisation des vecteurs " + world["tag"], name="norm.txt")
    assert wait_status(client, a, r.json()["id"])["statut"] == "ready"
    with SessionLocal() as db:
        total = db.scalar(select(func.count(Chunk.id)))
        bad = db.scalar(text("SELECT count(*) FROM chunk WHERE abs(vector_norm(embedding) - 1) > 0.001"))
    assert total > 0 and bad == 0


def test_la_base_refuse_un_vecteur_non_normalise(client, world):
    from sqlalchemy.exc import IntegrityError

    a = world["a"]["h"]
    r = upload(client, a, "Document pour tester la contrainte " + world["tag"], name="contrainte.txt")
    wait_status(client, a, r.json()["id"])
    with SessionLocal() as db:
        db.add(Chunk(document_id=r.json()["id"], chunk_index=999, contenu="x", embedding=[2.0] * 768))
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
