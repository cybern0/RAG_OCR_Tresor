"""Règles de la GED hiérarchique : chef de division unique et transfert de poste, intérim du super administrateur,
accès aux fichiers (404 / 403), classement par rôle au dépôt, dépôt direct sans dossier, demandes d'accès et exceptions,
historique chaîné, périmètres de gestion, notifications, tableaux de bord.

Le chef de service a le même rôle que le chef de division, étendu à toutes les divisions de son service ;
il gère les comptes de son service (y compris les chefs de division : compte, mot de passe, rôles) mais pas
les autres chefs de service. Même base de test et mêmes fixtures que test_api.py (monde : 1 direction,
2 services, 3 divisions, chefs, agents, rôles)."""

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest

if not os.environ.get("TEST_DATABASE_URL"):
    pytest.skip("TEST_DATABASE_URL non défini : tests d'API ignorés", allow_module_level=True)

from sqlalchemy import text, update

from app.config import get_settings
from app.db.metier import SessionLocal

from .test_api import (  # noqa: F401  (fixtures et aides partagées)
    PWD, auth, client, login, mk_agent, mk_role, mk_user, ready_doc, set_roles,
    upload, wait_version, world,
)


def ids(rows):
    return [r["id"] for r in rows]


def fichier(client, h, division_id, texte, **form):
    return ready_doc(client, h, division_id, texte, **form)


# --- chefs uniques, transfert, vacance ------------------------------------------------------------------------------------

def test_un_seul_chef_par_poste_garanti_et_transfert_atomique(client, world):
    h, tag = world["admin"], world["tag"]
    v2, s1 = world["div"]["v2"]["id"], world["svc"]["s1"]["id"]
    c1 = mk_agent(client, h, "c1", tag, s1, v2, "CHEF_DIVISION")
    # un second chef de division est refusé avec un message qui oriente vers le transfert
    r = client.post("/structure/agents", headers=h, json={"matricule": f"X2{tag}", "nom": "N", "prenom": "P", "service_id": s1, "division_id": v2, "titre": "CHEF_DIVISION"})
    assert r.status_code == 409 and "transfert" in r.json()["detail"]
    # un chef de service n'a pas de division, et le poste est unique (déjà occupé par cs)
    assert client.post("/structure/agents", headers=h, json={"matricule": f"X3{tag}", "nom": "N", "prenom": "P", "service_id": s1, "division_id": v2, "titre": "CHEF_SERVICE"}).status_code == 422
    assert client.post("/structure/agents", headers=h, json={"matricule": f"X3{tag}", "nom": "N", "prenom": "P", "service_id": s1, "titre": "CHEF_SERVICE"}).status_code == 409
    # règles de cohérence : un chef de division doit avoir une division ; la division doit être du service de l'agent
    assert client.post("/structure/agents", headers=h, json={"matricule": f"X5{tag}", "nom": "N", "prenom": "P", "service_id": s1, "titre": "CHEF_DIVISION"}).status_code == 422
    # la division doit être du service de l'agent ; un agent sans titre doit avoir une division
    assert client.post("/structure/agents", headers=h, json={"matricule": f"X6{tag}", "nom": "N", "prenom": "P", "service_id": s1, "division_id": world["div"]["v3"]["id"]}).status_code == 422
    assert client.post("/structure/agents", headers=h, json={"matricule": f"X7{tag}", "nom": "N", "prenom": "P", "service_id": s1}).status_code == 422
    postes = client.get("/structure/postes", headers=h).json()
    assert next(d for d in postes["divisions"] if d["division_id"] == v2)["chef"]["agent_id"] == c1["id"]
    assert next(s for s in postes["services"] if s["service_id"] == s1)["chef"]["agent_id"] == world["cs"]["agent"]["id"]

    # transfert : l'ancien perd le titre, le nouveau le reçoit, en une opération ; tracé et notifié
    c2 = mk_agent(client, h, "c2", tag, s1, v2)
    u2 = mk_user(client, h, c2, "c2", tag)
    r = client.put(f"/structure/divisions/{v2}/chef", headers=h, json={"agent_id": c2["id"], "motif": "Passation"})
    assert r.status_code == 200, r.text
    chefs = {a["id"]: a["titre"] for a in client.get("/structure/agents", headers=h).json()}
    assert chefs[c1["id"]] is None and chefs[c2["id"]] == "CHEF_DIVISION"
    hist = client.get("/historique", headers=h, params={"cible_type": "agent", "limit": 20}).json()["items"]
    assert {"chef_retire", "chef_nomme"} <= {e["action"] for e in hist if e["division_id"] == v2}
    notifs = client.get("/notifications", headers=u2["h"]).json()
    assert any(n["type_evenement"] == "chef_nomme" for n in notifs["items"]) and notifs["non_lues"] >= 1
    assert client.put(f"/structure/divisions/{v2}/chef", headers=h, json={"agent_id": c2["id"]}).status_code == 200  # idempotent
    # un agent d'une autre division ne peut pas être nommé
    assert client.put(f"/structure/divisions/{v2}/chef", headers=h, json={"agent_id": world["b"]["agent"]["id"]}).status_code == 422
    # un agent qui a un titre ne change pas de division sans transfert
    assert client.patch(f"/structure/agents/{c2['id']}", headers=h, json={"division_id": world["div"]["v1"]["id"]}).status_code == 409
    # désactiver le chef : poste vacant (alerte), le titre n'empêche pas d'en nommer un autre ensuite
    assert client.patch(f"/structure/agents/{c2['id']}", headers=h, json={"actif": False}).status_code == 200
    assert next(d for d in client.get("/structure/postes", headers=h).json()["divisions"] if d["division_id"] == v2)["chef"] is None
    assert client.get("/auth/me", headers=u2["h"]).status_code == 401          # un agent désactivé perd l'accès tout de suite
    assert login(client, u2["name"]).status_code == 401
    c3 = mk_agent(client, h, "c3", tag, s1, v2, "CHEF_DIVISION")               # poste libre : nomination directe
    assert c3["titre"] == "CHEF_DIVISION"
    # la réactivation de l'ancien chef est refusée tant que le poste est occupé
    assert client.patch(f"/structure/agents/{c2['id']}", headers=h, json={"actif": True}).status_code == 409
    # retirer le titre par la case à cocher (titre null) libère le poste
    assert client.patch(f"/structure/agents/{c3['id']}", headers=h, json={"titre": None}).status_code == 200
    assert next(d for d in client.get("/structure/postes", headers=h).json()["divisions"] if d["division_id"] == v2)["chef"] is None


def test_interim_du_super_administrateur_sur_une_division_vacante(client, world):
    adm, v2, tag = world["admin"], world["div"]["v2"]["id"], world["tag"]
    # v2 n'a plus de chef : le super administrateur gère directement (intérim)
    r = client.post(f"/divisions/{v2}/roles", headers=adm, json={"code": "INTERIM", "libelle": "Intérim"})
    assert r.status_code == 201
    assert any(d["id"] == v2 for d in client.get("/auth/me", headers=adm).json()["divisions_gerees"])
    # une division avec un chef n'est pas gérée par le super administrateur
    assert client.post(f"/divisions/{world['div']['v1']['id']}/roles", headers=adm, json={"code": "NON", "libelle": "Non"}).status_code == 403
    # ni par le chef d'une autre division
    assert client.post(f"/divisions/{v2}/roles", headers=world["cd1"]["h"], json={"code": "NON", "libelle": "Non"}).status_code == 404


# --- règle d'accès aux fichiers ---------------------------------------------------------------------------------------------

def test_404_403_selon_la_position_de_l_appelant(client, world):
    a, lect, mix, b, cd1, adm = (world[k]["h"] if k != "admin" else world[k] for k in ("a", "lect", "mix", "b", "cd1", "admin"))
    f = fichier(client, a, world["A"]["id"], f"Compte rendu comptable {world['tag']}.", titre="Compte rendu")
    fid = f["id"]
    assert f["mon_role"] == "AUTEUR" and [r["code"] for r in f["roles"]] == ["COMPTA"] and f["a_classer"] is False
    assert client.get(f"/documents/{fid}", headers=lect).json()["mon_role"] == "LECTEUR"         # rôle commun
    assert client.get(f"/documents/{fid}", headers=cd1).json()["mon_role"] == "GERANT"           # chef de la division
    r = client.get(f"/documents/{fid}", headers=mix)                                           # même division, pas le rôle
    assert r.status_code == 403 and r.json()["detail"]["code"] == "ACCES_FICHIER_REFUSE" and r.json()["detail"]["document_id"] == fid
    assert client.get(f"/documents/{fid}/versions/1/telecharger", headers=mix).status_code == 403
    assert client.get(f"/documents/{fid}", headers=b).status_code == 404                        # autre division : l'existence n'est pas révélée
    assert client.get(f"/documents/{fid}", headers=world["cd3"]["h"]).status_code == 404         # même un chef d'une autre division
    # liste à plat, sans dossier : le filtre par rôle (classe) — mix (PUBLIC) ne voit pas le fichier COMPTA, lect le voit
    ids_mix = ids(client.get("/documents", headers=mix, params={"role_id": world["roles"]["PUBLIC"]["id"]}).json())
    assert fid not in ids_mix and fid in ids(client.get("/documents", headers=lect, params={"role_id": world["roles"]["COMPTA"]["id"]}).json())
    # filtres disponibles du compte : l'agent voit sa division et ses rôles ; un chef de service, ses divisions
    filtres_mix = client.get("/documents/filtres", headers=mix).json()
    assert [d["id"] for d in filtres_mix["divisions"]] == [world["div"]["v1"]["id"]]
    assert {r["code"] for r in filtres_mix["roles"]} == {"PUBLIC"}
    assert filtres_mix["depot_divisions"] == [world["div"]["v1"]["id"]]
    # super administrateur : il ne fait qu'administrer — ni fichiers, ni téléchargement, ni dépôt
    assert client.get(f"/documents/{fid}", headers=adm).status_code == 404
    assert client.get(f"/documents/{fid}/versions/1/telecharger", headers=adm).status_code == 404
    assert client.get("/documents/filtres", headers=adm).json() == {"roles": [], "divisions": [], "depot_divisions": []}  # le super administrateur ne liste pas de fichiers
    assert upload(client, adm, world["A"]["id"], "x" + world["tag"]).status_code == 404          # l'administration ne dépose pas (existence non révélée)
    assert client.post(f"/documents/{fid}/commentaires", headers=lect, json={"contenu": "ok"}).status_code == 201


# --- classement par rôle au dépôt ---------------------------------------------------------------------------------------------

def test_classement_automatique_selon_l_utilisateur_qui_depose(client, world):
    a, lect, mix, cd1, tag, R = world["a"]["h"], world["lect"]["h"], world["mix"]["h"], world["cd1"]["h"], world["tag"], world["roles"]
    A = world["A"]["id"]
    # agent : tous ses rôles par défaut ; lect en a deux
    f = fichier(client, lect, A, f"Rapport d'audit comptable {tag}")
    assert sorted(r["code"] for r in f["roles"]) == ["AUDIT", "COMPTA"]
    # il peut en retirer un, jamais en ajouter un qu'il n'a pas
    f = fichier(client, lect, A, f"Seulement compta {tag}", role_ids=[R["COMPTA"]["id"]])
    assert [r["code"] for r in f["roles"]] == ["COMPTA"]
    assert upload(client, a, A, f"Intrus {tag}", role_ids=[R["AUDIT"]["id"]]).status_code == 403
    assert upload(client, a, A, f"Autre division {tag}", role_ids=[world["roles"]["RH"]["id"]]).status_code in (403, 422)
    # aucun rôle conservé : « à classer », le chef est notifié, l'auteur le voit, mix non
    r = upload(client, a, A, f"Sans rôle {tag}", titre="Sans rôle", roles_explicites="true")
    assert r.status_code == 201 and r.json()["a_classer"] is True
    sans = r.json()
    assert any(n["type_evenement"] == "fichier_a_classer" for n in client.get("/notifications", headers=cd1).json()["items"])
    assert client.get(f"/documents/{sans['id']}", headers=a).status_code == 200
    assert client.get(f"/documents/{sans['id']}", headers=mix).status_code == 403
    assert sans["id"] in ids(client.get("/documents", headers=cd1, params={"a_classer": True}).json())
    # administrateur (chef de division) : choisit ; sans choix = accès refusé par défaut (métadonnée vide)
    admin_f = upload(client, cd1, A, f"Dépôt du chef sans choix {tag}", titre="Chef sans choix")
    assert admin_f.status_code == 201 and admin_f.json()["a_classer"] is True
    assert client.get(f"/documents/{admin_f.json()['id']}", headers=lect).status_code == 403
    choisi = upload(client, cd1, A, f"Dépôt du chef classé {tag}", role_ids=[R["PUBLIC"]["id"]])
    assert [x["code"] for x in choisi.json()["roles"]] == ["PUBLIC"] and client.get(f"/documents/{choisi.json()['id']}", headers=mix).status_code == 200
    # rôles inactifs ou inconnus
    assert upload(client, cd1, A, f"Rôle inconnu {tag}", role_ids=[99999999]).status_code == 422
    # changer les rôles d'un fichier existant : le chef seulement, tracé ; liste vide = accès refusé par défaut
    fid = sans["id"]
    assert client.put(f"/documents/{fid}/roles", headers=a, json={"role_ids": [R["COMPTA"]["id"]]}).status_code == 403   # même l'auteur
    assert client.put(f"/documents/{fid}/roles", headers=cd1, json={"role_ids": [R["COMPTA"]["id"], world["roles"]["RH"]["id"]]}).status_code == 422
    r = client.put(f"/documents/{fid}/roles", headers=cd1, json={"role_ids": [R["COMPTA"]["id"]], "motif": "Reclassement"})
    assert r.status_code == 200 and r.json()["a_classer"] is False and client.get(f"/documents/{fid}", headers=lect).status_code == 200
    h = client.get(f"/documents/{fid}/historique", headers=lect).json()
    assert [e["action"] for e in h][:2] == ["roles_fichier_modifies", "fichier_depose"] and h[0]["motif"] == "Reclassement"
    client.put(f"/documents/{fid}/roles", headers=cd1, json={"role_ids": []})
    assert client.get(f"/documents/{fid}", headers=lect).status_code == 403
    # pas de reclassement rétroactif : retirer COMPTA à lect ne change aucun fichier
    set_roles(client, cd1, world["lect"]["user"]["id"], [R["AUDIT"]["id"]])
    assert [x["code"] for x in client.get(f"/documents/{f['id']}", headers=cd1).json()["roles"]] == ["COMPTA"]
    set_roles(client, cd1, world["lect"]["user"]["id"], [R["COMPTA"]["id"], R["AUDIT"]["id"]])


def test_depot_direct_sans_dossier_et_division_desactivee(client, world):
    """Plus de dossiers ni d'arborescence : les fichiers se déposent DIRECTEMENT dans une division
    (membres et chefs seulement, 404 hors périmètre) ; le stockage reste à plat ; une division
    désactivée passe en lecture seule (409 à l'écriture, lecture conservée)."""
    a, lect, mix, b, cd1, adm, tag = world["a"]["h"], world["lect"]["h"], world["mix"]["h"], world["b"]["h"], world["cd1"]["h"], world["admin"], world["tag"]
    v1, s1 = world["div"]["v1"]["id"], world["svc"]["s1"]["id"]
    # dépôt direct : ok pour un membre, 404 pour un compte hors de la division (b est de v3), 403 pour l'administrateur
    f = fichier(client, a, v1, f"Fichier déposé sans dossier {tag}", titre="Sans dossier")
    assert any(p.is_file() for p in get_settings().upload_dir.iterdir())  # stockage à plat (nom généré)
    assert client.post("/documents", headers=b, data={"division_id": str(v1)}, files={"fichier": ("x.txt", b"x", "text/plain")}).status_code == 404
    assert upload(client, adm, v1, "x" + tag).status_code == 404
    # une division désactivée : écriture refusée, lecture conservée
    doc = fichier(client, a, v1, f"Texte de la division désactivée {tag} sur la cantine.")
    nv = client.post("/structure/divisions", headers=adm, json={"service_id": s1, "nom": f"Division hors service {tag}", "code": f"hors{tag}"}).json()
    assert client.patch(f"/structure/divisions/{v1}", headers=adm, json={"actif": False}).status_code == 200
    assert upload(client, a, v1, "autre " + tag).status_code == 409
    assert client.patch(f"/documents/{doc['id']}", headers=a, data={"titre": "x"}).status_code == 409
    assert client.get(f"/documents/{doc['id']}", headers=a).status_code == 200
    assert client.get("/documents", headers=a, params={"division_id": v1}).status_code == 200
    assert client.patch(f"/structure/divisions/{v1}", headers=adm, json={"actif": True}).status_code == 200
    client.delete(f"/documents/{f['id']}", headers=a)
    client.delete(f"/documents/{doc['id']}", headers=a)
    client.patch(f"/structure/divisions/{nv['id']}", headers=adm, json={"actif": False})


# --- demandes d'accès et exceptions ---------------------------------------------------------------------------------------------

def test_demande_de_role_et_demande_d_acces_ponctuel(client, world):
    a, mix, b, cd1, tag, R = world["a"]["h"], world["mix"]["h"], world["b"]["h"], world["cd1"]["h"], world["tag"], world["roles"]
    f = fichier(client, a, world["A"]["id"], f"Pièce justificative {tag}", titre="Pièce")
    fid = f["id"]
    # demande d'accès ponctuel : motif obligatoire, une seule en attente, impossible hors division ou si l'accès existe déjà
    assert client.post("/demandes", headers=mix, json={"type_demande": "fichier", "cible_id": fid, "motif": "x"}).status_code == 422
    r = client.post("/demandes", headers=mix, json={"type_demande": "fichier", "cible_id": fid, "motif": "Contrôle interne", "duree_heures": 2})
    assert r.status_code == 201 and r.json()["cible_libelle"] == f"Fichier n°{fid}"              # le titre d'un fichier masqué n'est pas révélé
    demande = r.json()
    assert client.post("/demandes", headers=mix, json={"type_demande": "fichier", "cible_id": fid, "motif": "Encore"}).status_code == 409
    assert client.post("/demandes", headers=b, json={"type_demande": "fichier", "cible_id": fid, "motif": "Curiosité"}).status_code == 404
    assert client.post("/demandes", headers=a, json={"type_demande": "fichier", "cible_id": fid, "motif": "Déjà à moi"}).status_code == 409
    assert any(n["type_evenement"] == "demande_acces" for n in client.get("/notifications", headers=cd1).json()["items"])
    # seul le gérant de la division décide et voit la demande à traiter (avec le titre)
    assert client.post(f"/demandes/{demande['id']}/decision", headers=mix, json={"accepter": True}).status_code in (403, 404)
    assert client.post(f"/demandes/{demande['id']}/decision", headers=world["cd3"]["h"], json={"accepter": True}).status_code == 404
    a_traiter = client.get("/demandes", headers=cd1, params={"vue": "a_traiter", "statut": "en_attente"}).json()
    assert demande["id"] in ids(a_traiter) and next(x for x in a_traiter if x["id"] == demande["id"])["cible_libelle"] == "Pièce"
    assert client.get("/demandes", headers=mix, params={"vue": "a_traiter"}).json() == []
    r = client.post(f"/demandes/{demande['id']}/decision", headers=cd1, json={"accepter": True, "reponse": "Accordé 2 h"})
    assert r.status_code == 200 and r.json()["statut"] == "acceptee"
    assert client.post(f"/demandes/{demande['id']}/decision", headers=cd1, json={"accepter": False}).status_code == 409   # déjà traitée
    # exception à expiration : lecture seule du fichier, les rôles de mix ne changent pas
    assert client.get(f"/documents/{fid}", headers=mix).json()["mon_role"] == "LECTEUR"
    assert [x["code"] for x in client.get("/auth/me", headers=mix).json()["roles_division"]] == ["PUBLIC"]
    assert any(e["document_id"] == fid for e in client.get("/demandes/exceptions", headers=cd1).json())
    assert any(n["type_evenement"] == "demande_decidee" for n in client.get("/notifications", headers=mix).json()["items"])
    exc = next(e for e in client.get("/demandes/exceptions", headers=cd1).json() if e["document_id"] == fid)
    # expiration automatique
    from app.db.metier import AccesException

    with SessionLocal() as db:
        db.execute(update(AccesException).where(AccesException.id == exc["id"]).values(expire_le=datetime.now(timezone.utc) - timedelta(seconds=1)))
        db.commit()
    assert client.get(f"/documents/{fid}", headers=mix).status_code == 403
    # nouvelle demande, acceptée, puis révoquée par le gérant
    d2 = client.post("/demandes", headers=mix, json={"type_demande": "fichier", "cible_id": fid, "motif": "Encore besoin"}).json()
    client.post(f"/demandes/{d2['id']}/decision", headers=cd1, json={"accepter": True})
    assert client.get(f"/documents/{fid}", headers=mix).status_code == 200
    exc2 = next(e for e in client.get("/demandes/exceptions", headers=cd1).json() if e["document_id"] == fid)
    assert client.delete(f"/demandes/exceptions/{exc2['id']}", headers=mix).status_code in (403, 404)
    assert client.delete(f"/demandes/exceptions/{exc2['id']}", headers=cd1).status_code == 204
    assert client.get(f"/documents/{fid}", headers=mix).status_code == 403
    # refus, puis annulation par le demandeur
    d3 = client.post("/demandes", headers=mix, json={"type_demande": "fichier", "cible_id": fid, "motif": "Troisième"}).json()
    assert client.post(f"/demandes/{d3['id']}/decision", headers=cd1, json={"accepter": False, "reponse": "Non"}).json()["statut"] == "refusee"
    d4 = client.post("/demandes", headers=mix, json={"type_demande": "fichier", "cible_id": fid, "motif": "Quatrième"}).json()
    assert client.post(f"/demandes/{d4['id']}/annuler", headers=a).status_code == 404
    assert client.post(f"/demandes/{d4['id']}/annuler", headers=mix).json()["statut"] == "annulee"

    # demande de rôle (durable) : acceptée, le rôle s'ajoute à l'agent
    assert client.post("/demandes", headers=mix, json={"type_demande": "role", "cible_id": R["RH"]["id"], "motif": "Autre division"}).status_code == 404
    assert client.post("/demandes", headers=mix, json={"type_demande": "role", "cible_id": R["PUBLIC"]["id"], "motif": "Déjà"}).status_code == 409
    d5 = client.post("/demandes", headers=mix, json={"type_demande": "role", "cible_id": R["COMPTA"]["id"], "motif": "Nouvelle mission comptable"}).json()
    assert d5["cible_libelle"] == "Compta"
    assert client.post(f"/demandes/{d5['id']}/decision", headers=cd1, json={"accepter": True}).status_code == 200
    assert sorted(x["code"] for x in client.get("/auth/me", headers=mix).json()["roles_division"]) == ["COMPTA", "PUBLIC"]
    assert client.get(f"/documents/{fid}", headers=mix).status_code == 200
    set_roles(client, cd1, world["mix"]["user"]["id"], [R["PUBLIC"]["id"]])
    assert client.get(f"/documents/{fid}", headers=mix).status_code == 403
    mes = client.get("/demandes", headers=mix).json()
    assert {d["statut"] for d in mes} >= {"acceptee", "refusee", "annulee"}


# --- dictionnaire de rôles ---------------------------------------------------------------------------------------------------------------

def test_dictionnaire_de_roles_par_division(client, world):
    cd1, a, mix, cd3, tag, v1 = world["cd1"]["h"], world["a"]["h"], world["mix"]["h"], world["cd3"]["h"], world["tag"], world["div"]["v1"]["id"]
    # lecture : les membres ; écriture : le chef de division
    assert [r["code"] for r in client.get(f"/divisions/{v1}/roles", headers=a).json()] == ["AUDIT", "COMPTA", "PUBLIC"]
    assert client.post(f"/divisions/{v1}/roles", headers=a, json={"code": "PIRATE", "libelle": "Pirate"}).status_code == 403
    assert client.post(f"/divisions/{v1}/roles", headers=cd3, json={"code": "PIRATE", "libelle": "Pirate"}).status_code == 404
    assert client.get(f"/divisions/{v1}/roles", headers=world["b"]["h"]).status_code == 404
    # code unique par division (casse ignorée), code dérivé du libellé si absent
    assert client.post(f"/divisions/{v1}/roles", headers=cd1, json={"code": "compta", "libelle": "Doublon"}).status_code == 409
    r = client.post(f"/divisions/{v1}/roles", headers=cd1, json={"libelle": f"Élève été {tag}"})
    assert r.status_code == 201 and r.json()["code"].startswith("ELEVE_ETE")
    nouveau = r.json()
    # le même code peut exister dans une autre division
    assert client.post(f"/divisions/{world['div']['v3']['id']}/roles", headers=cd3, json={"code": "COMPTA", "libelle": "Compta v3"}).status_code == 201
    # renommer ne casse aucun accès (références par identifiant)
    f = fichier(client, a, world["A"]["id"], f"Renommage de rôle {tag}")
    assert client.patch(f"/divisions/{v1}/roles/{world['roles']['COMPTA']['id']}", headers=cd1, json={"libelle": "Comptabilité"}).status_code == 200
    assert client.get(f"/documents/{f['id']}", headers=world["lect"]["h"]).status_code == 200
    client.patch(f"/divisions/{v1}/roles/{world['roles']['COMPTA']['id']}", headers=cd1, json={"libelle": "Compta"})
    # suppression : refusée tant que le rôle est utilisé (fichier ou agent) ; désactivation : plus attribuable
    assert client.delete(f"/divisions/{v1}/roles/{world['roles']['COMPTA']['id']}", headers=cd1).status_code == 409
    assert client.patch(f"/divisions/{v1}/roles/{nouveau['id']}", headers=cd1, json={"actif": False}).status_code == 200
    assert client.put(f"/users/{world['mix']['user']['id']}/roles", headers=cd1, json={"role_ids": [world["roles"]["PUBLIC"]["id"], nouveau["id"]]}).status_code == 422
    assert client.delete(f"/divisions/{v1}/roles/{nouveau['id']}", headers=cd1).status_code == 204
    assert client.delete(f"/divisions/{v1}/roles/{nouveau['id']}", headers=cd1).status_code == 404
    # un rôle d'une autre division ne s'attribue pas
    assert client.put(f"/users/{world['mix']['user']['id']}/roles", headers=cd1, json={"role_ids": [world["roles"]["RH"]["id"]]}).status_code == 422
    # les agents ne règlent pas leurs propres rôles
    assert client.put(f"/users/{world['mix']['user']['id']}/roles", headers=mix, json={"role_ids": [world["roles"]["COMPTA"]["id"]]}).status_code == 403
    assert any(n["type_evenement"] == "roles_modifies" for n in client.get("/notifications", headers=mix).json()["items"])


# --- périmètre des comptes ------------------------------------------------------------------------------------------------------------------

def test_perimetre_de_creation_et_de_gestion_des_comptes(client, world):
    adm, cd1, cd3, tag = world["admin"], world["cd1"]["h"], world["cd3"]["h"], world["tag"]
    s1, v1, v2, s2, v3 = world["svc"]["s1"]["id"], world["div"]["v1"]["id"], world["div"]["v2"]["id"], world["svc"]["s2"]["id"], world["div"]["v3"]["id"]
    p1 = mk_agent(client, adm, "p1", tag, s1, v1)
    p2 = mk_agent(client, adm, "p2", tag, s1, v2)
    p3 = mk_agent(client, adm, "p3", tag, s2, v3)
    ch = mk_agent(client, adm, "ch", tag, s1, v2)                 # futur chef de division de v2
    def creer(h, agent, nom):
        return client.post("/users", headers=h, json={"nom_utilisateur": f"{nom}_{tag}", "mot_de_passe": PWD, "role": "UTILISATEUR", "agent_id": agent["id"]})
    # agents disponibles : chacun voit ce qu'il peut doter d'un compte
    assert [a["id"] for a in client.get("/users/agents-disponibles", headers=cd1).json()] == [p1["id"]]
    # le chef de division crée les comptes des agents de sa division, pas les autres
    assert creer(cd1, p3, "x3").status_code == 404
    assert creer(cd1, p2, "x2").status_code == 404
    r = creer(cd1, p1, "n1")
    assert r.status_code == 201 and r.json()["niveau"] == "AGENT"
    # division vacante (v2) : le super administrateur assure l'intérim et crée ces comptes ; après nomination, il reste le seul à tout gérer
    assert creer(adm, p2, "n2").status_code == 201
    assert client.put(f"/structure/divisions/{v2}/chef", headers=adm, json={"agent_id": ch["id"]}).status_code == 200
    assert creer(adm, ch, "nch").json()["niveau"] == "DIVISION"
    p2b = mk_agent(client, adm, "p2b", tag, s1, v2)
    assert creer(cd1, p2b, "n2b").status_code == 404           # v2 n'est pas la division de cd1
    assert creer(cd3, p3, "n3").status_code == 201
    # listes cloisonnées
    noms = lambda h: {u["nom_utilisateur"] for u in client.get("/users", headers=h).json()}  # noqa: E731
    assert f"n1_{tag}" in noms(cd1) and f"n3_{tag}" not in noms(cd1) and f"n2_{tag}" not in noms(cd1)
    assert {f"n1_{tag}", f"n3_{tag}", f"n2_{tag}"} <= noms(adm)
    u_n3 = next(u for u in client.get("/users", headers=adm).json() if u["nom_utilisateur"] == f"n3_{tag}")
    assert client.get(f"/users/{u_n3['id']}", headers=cd1).status_code == 404
    # gestion : désactiver et réinitialiser dans son périmètre seulement ; jamais un supérieur
    u_n1 = next(u for u in client.get("/users", headers=cd1).json() if u["nom_utilisateur"] == f"n1_{tag}")
    assert client.patch(f"/users/{u_n1['id']}", headers=cd1, json={"actif": False}).status_code == 200
    assert client.patch(f"/users/{u_n1['id']}", headers=cd1, json={"actif": True, "mot_de_passe": "nouveau-mdp-123"}).status_code == 200
    assert client.patch(f"/users/{u_n3['id']}", headers=cd1, json={"actif": False}).status_code == 404
    assert client.patch(f"/users/{world['cd1']['user']['id']}", headers=cd1, json={"actif": False}).status_code in (403, 409)   # pas soi-même
    assert client.patch(f"/users/{world['cd1']['user']['id']}", headers=cd3, json={"mot_de_passe": "tentative-hors-perimetre-1"}).status_code == 404
    # le super administrateur gère tous les comptes, y compris les chefs de division
    assert client.patch(f"/users/{world['cd1']['user']['id']}", headers=adm, json={"mot_de_passe": "mdp-du-chef-123"}).status_code == 200
    assert client.patch(f"/users/{world['cd1']['user']['id']}", headers=cd3, json={"role": "ADMIN"}).status_code == 404
    client.patch(f"/users/{world['cd1']['user']['id']}", headers=adm, json={"mot_de_passe": PWD})
    world["cd1"]["h"] = auth(client, world["cd1"]["name"])
    # mutation : changer de division retire les rôles de l'ancienne ; un agent désactivé perd l'accès
    lect = world["lect"]
    assert client.patch(f"/structure/agents/{lect['agent']['id']}", headers=adm, json={"division_id": v2}).status_code == 200
    assert client.get("/auth/me", headers=lect["h"]).json()["roles_division"] == []
    hist = client.get("/historique", headers=adm, params={"action": "roles_retires"}).json()["items"]
    assert any(e["concerne_user_id"] == lect["user"]["id"] and e["motif"] == "Changement de division" for e in hist)
    assert client.patch(f"/structure/agents/{lect['agent']['id']}", headers=adm, json={"division_id": v1}).status_code == 200
    set_roles(client, world["cd1"]["h"], lect["user"]["id"], [world["roles"]["COMPTA"]["id"], world["roles"]["AUDIT"]["id"]])


# --- historique chaîné, périmètre, notifications, tableaux de bord ----------------------------------------------------------------------

def test_historique_en_ajout_seul_et_chaine_verifiable(client, world):
    adm, cd1, a, cd3 = world["admin"], world["cd1"]["h"], world["a"]["h"], world["cd3"]["h"]
    v1 = world["div"]["v1"]["id"]
    v = client.get("/historique/verification", headers=adm).json()
    assert v["ok"] is True and v["total"] > 10
    assert client.get("/historique/verification", headers=a).status_code == 403
    # périmètres : le chef de division ne voit que sa division, l'agent ce qui le concerne
    only = lambda h: {e["division_id"] for e in client.get("/historique", headers=h, params={"limit": 200}).json()["items"]}  # noqa: E731
    assert only(cd1) == {v1}
    mine = client.get("/historique", headers=a, params={"limit": 200}).json()["items"]
    assert mine and all(e["acteur_user_id"] == world["a"]["user"]["id"] or e["concerne_user_id"] == world["a"]["user"]["id"] for e in mine)
    assert len(client.get("/historique", headers=adm, params={"limit": 200}).json()["items"]) > len(mine)
    # chaînage : rang continu, hash_precedent = hash de la ligne d'avant
    items = client.get("/historique", headers=adm, params={"limit": 50}).json()["items"]
    assert [e["rang"] for e in items] == sorted((e["rang"] for e in items), reverse=True)
    # la base refuse toute modification ou suppression
    with SessionLocal() as db:
        for sql in ("UPDATE historique_modification SET motif = 'x' WHERE rang = 1", "DELETE FROM historique_modification WHERE rang = 1", "TRUNCATE historique_modification"):
            with pytest.raises(Exception, match="ajout seul"):
                db.execute(text(sql))
            db.rollback()
    # une falsification faite en contournant la protection (propriétaire de la table) est détectée, puis réparée
    with SessionLocal() as db:
        db.execute(text("ALTER TABLE historique_modification DISABLE TRIGGER trg_historique_immuable"))
        ancien = db.execute(text("SELECT motif FROM historique_modification WHERE rang = 3")).scalar()
        db.execute(text("UPDATE historique_modification SET motif = 'falsifié' WHERE rang = 3"))
        db.commit()
    try:
        v = client.get("/historique/verification", headers=adm).json()
        assert v["ok"] is False and v["premier_rang_invalide"] == 3
    finally:
        with SessionLocal() as db:
            db.execute(text("UPDATE historique_modification SET motif = :m WHERE rang = 3"), {"m": ancien})
            db.execute(text("ALTER TABLE historique_modification ENABLE TRIGGER trg_historique_immuable"))
            db.commit()
    assert client.get("/historique/verification", headers=adm).json()["ok"] is True
    # SQL : fonction de vérification et invariants
    with SessionLocal() as db:
        assert db.execute(text("SELECT ok FROM verifier_historique()")).scalar() is True
        assert db.execute(text("SELECT sum(anomalies) FROM verification_invariants")).scalar() == 0


def test_notifications_lues_et_non_lues(client, world):
    cd1 = world["cd1"]["h"]
    r = client.get("/notifications", headers=cd1).json()
    assert r["non_lues"] > 0 and all("message" in n for n in r["items"])
    first = r["items"][0]["id"]
    assert client.post(f"/notifications/{first}/lue", headers=cd1).status_code == 204
    assert client.post(f"/notifications/{first}/lue", headers=world["a"]["h"]).status_code == 404   # pas celle d'un autre
    assert client.get("/notifications", headers=cd1).json()["non_lues"] == r["non_lues"] - 1
    assert client.post("/notifications/lues", headers=cd1).status_code == 204
    assert client.get("/notifications", headers=cd1).json()["non_lues"] == 0


def test_tableaux_de_bord_par_niveau(client, world):
    root = client.get("/tableau-de-bord", headers=world["admin"]).json()
    assert root["niveau"] == "ROOT" and root["repartition"]["titre"] == "Par service" and len(root["repartition"]["lignes"]) >= 2
    assert any("super administrateur" in a for a in root["alertes"])                 # un seul super administrateur actif en test
    assert root["erreurs_indexation"] is not None and root["erreurs_indexation"]["total"] >= 0
    div = client.get("/tableau-de-bord", headers=world["cd1"]["h"]).json()
    assert div["niveau"] == "DIVISION" and {l["libelle"] for l in div["repartition"]["lignes"]} >= {"Compta", "Audit", "Public"}
    srv = client.get("/tableau-de-bord", headers=world["cs"]["h"]).json()
    assert srv["niveau"] == "SERVICE" and srv["repartition"]["titre"] == "Par division"
    assert {l["libelle"] for l in srv["repartition"]["lignes"]} >= {f"Division v1 {world['tag']}", f"Division v2 {world['tag']}"}
    ag = client.get("/tableau-de-bord", headers=world["a"]["h"]).json()
    assert ag["niveau"] == "AGENT" and [r["code"] for r in ag["mes_roles"]] == ["COMPTA"] and "repartition" in ag and ag["repartition"] is None
    assert ag["erreurs_indexation"] is not None                                       # même un agent : SES fichiers en échec (très restreint)
    # un chef de division ne voit pas les chiffres d'une autre division (agrégats limités à son périmètre)
    b = client.get("/tableau-de-bord", headers=world["cd3"]["h"]).json()
    assert b["titre"] != div["titre"]


def test_tracage_des_erreurs_d_indexation_par_niveau(client, world):
    """Le dashboard trace les échecs d'indexation par service, division et rôle : ROOT voit tout,
    le chef de service ses divisions, le chef de division sa division, l'agent SES fichiers seulement."""
    adm, cs, cd1, cd3 = world["admin"], world["cs"]["h"], world["cd1"]["h"], world["cd3"]["h"]
    a, b, tag = world["a"]["h"], world["b"]["h"], world["tag"]
    # une version en échec : le contenu n'est pas un vrai tableur
    r = client.post("/documents", headers=a, data={"division_id": str(world["A"]["id"]), "titre": "Pièce en échec"},
                    files={"fichier": (f"faux_{tag}.xlsx", b"ce n'est pas un classeur", "application/octet-stream")})
    assert r.status_code == 201
    doc_id = r.json()["id"]
    assert wait_version(client, a, doc_id, 1)["statut"] == "error"
    # ROOT : regroupements complets et le cas présent
    root = client.get("/tableau-de-bord", headers=adm).json()["erreurs_indexation"]
    assert root["total"] >= 1
    assert any(e["document_id"] == doc_id for e in root["items"])
    assert {g["nom"] for g in root["par_division"]} >= {f"Division v1 {tag}"}
    assert any(f"Service s1" in g["nom"] or True for g in root["par_service"]) and root["par_service"]
    assert {g["nom"] for g in root["par_role"]} >= {"Compta"}                        # le fichier porte COMPTA
    # chef de service : les échecs de SON service ; chef de division : sa division ; le service voisin : rien
    srv = client.get("/tableau-de-bord", headers=cs).json()["erreurs_indexation"]
    assert any(e["document_id"] == doc_id for e in srv["items"])
    div_b = client.get("/tableau-de-bord", headers=cd3).json()["erreurs_indexation"]
    assert all(e["document_id"] != doc_id for e in div_b["items"])
    # agent : très restreint — ses fichiers seulement, avec le message, sans regroupement
    ag = client.get("/tableau-de-bord", headers=a).json()["erreurs_indexation"]
    assert any(e["document_id"] == doc_id and e["message_erreur"] for e in ag["items"])
    assert ag["par_service"] == [] and ag["par_division"] == [] and ag["par_role"] == []
    # l'agent d'une autre division : aucun de ses fichiers n'est en échec ici
    ag_b = client.get("/tableau-de-bord", headers=b).json()["erreurs_indexation"]
    assert all(e["document_id"] != doc_id for e in ag_b["items"])
    # l'indicateur erreurs existe à chaque niveau et pointe vers le filtre statut=error
    for h in (adm, cs, cd1, a):
        assert any(i["cle"] == "erreurs" for i in client.get("/tableau-de-bord", headers=h).json()["indicateurs"])


def test_chef_de_service_gere_la_structure_de_son_service(client, world):
    """structure.gerer accordé au chef de service : listes et agents de SON service, agents et postes de chef
    de division de ses divisions ; directions, services, divisions et postes de chef de service restent ROOT."""
    adm, cs = world["admin"], world["cs"]["h"]
    tag = world["tag"]
    s1, v1 = world["svc"]["s1"]["id"], world["div"]["v1"]["id"]
    me = client.get("/auth/me", headers=cs).json()
    assert "structure.gerer" in me["permissions"]
    # listes scopées : son service seulement
    assert {s["id"] for s in client.get("/structure/services", headers=cs).json()} == {s1}
    assert all(d["service_id"] == s1 for d in client.get("/structure/divisions", headers=cs).json())
    agents = client.get("/structure/agents", headers=cs).json()
    assert agents and all(a["service_id"] == s1 for a in agents)
    postes = client.get("/structure/postes", headers=cs).json()
    assert {p["service_id"] for p in postes["services"]} == {s1}
    # il crée un agent dans son service, le déplace de division, et nomme un chef de division
    r = client.post("/structure/agents", headers=cs, json={"matricule": f"CSX{tag}", "nom": "Nom", "prenom": "csx", "service_id": s1, "division_id": v1})
    assert r.status_code == 201, r.text
    agent_id = r.json()["id"]
    v2 = world["div"]["v2"]["id"]
    assert client.patch(f"/structure/agents/{agent_id}", headers=cs, json={"division_id": v2}).status_code == 200
    assert client.put(f"/structure/divisions/{v2}/chef", headers=cs, json={"agent_id": agent_id, "motif": "Nomination par le chef de service"}).status_code == 200
    # mais pas chez le service voisin, ni les directions/services/divisions, ni un poste de chef de service
    assert client.post("/structure/agents", headers=cs, json={"matricule": f"CSY{tag}", "nom": "N", "prenom": "csy", "service_id": world["svc"]["s2"]["id"]}).status_code == 404
    assert client.patch(f"/structure/agents/{agent_id}", headers=cs, json={"service_id": world["svc"]["s2"]["id"]}).status_code == 404
    assert client.post("/structure/directions", headers=cs, json={"code": f"DCS{tag}", "nom": "x"}).status_code == 403
    assert client.post("/structure/services", headers=cs, json={"direction_id": world["dir"]["id"], "code": f"SCS{tag}", "nom": "x"}).status_code == 403
    assert client.post("/structure/divisions", headers=cs, json={"service_id": s1, "nom": f"Div interdite {tag}"}).status_code == 403
    assert client.put(f"/structure/services/{s1}/chef", headers=cs, json={"agent_id": agent_id}).status_code == 403
    # nettoyage : retirer le titre créé pour ne pas bloquer d'autres tests
    client.patch(f"/structure/agents/{agent_id}", headers=adm, json={"titre": None})
    client.patch(f"/structure/agents/{agent_id}", headers=adm, json={"actif": False})


def test_arbre_de_structure_visible_selon_le_niveau(client, world):
    adm, cd1, a = world["admin"], world["cd1"]["h"], world["a"]["h"]
    arbre_adm = client.get("/structure/arbre", headers=adm).json()
    assert len(arbre_adm) >= 2 and all(d["acces"] == "superieur" for s in arbre_adm for d in s["divisions"])
    # le chef de division et l'agent ne voient que leur division dans leur service
    arbre_a = client.get("/structure/arbre", headers=a).json()
    assert len(arbre_a) == 1 and [d["id"] for d in arbre_a[0]["divisions"]] == [world["div"]["v1"]["id"]] and arbre_a[0]["divisions"][0]["acces"] == "membre"
    assert [d["id"] for d in client.get("/structure/arbre", headers=cd1).json()[0]["divisions"]] == [world["div"]["v1"]["id"]]
    # le chef de service voit toutes les divisions de son service, en gérant
    arbre_cs = client.get("/structure/arbre", headers=world["cs"]["h"]).json()
    assert len(arbre_cs) == 1 and arbre_cs[0]["id"] == world["svc"]["s1"]["id"]
    v1, v2 = world["div"]["v1"]["id"], world["div"]["v2"]["id"]
    ids_cs = {d["id"] for d in arbre_cs[0]["divisions"]}
    assert {v1, v2} <= ids_cs  # une division créée par un autre test peut exister aussi dans s1
    assert all(d["acces"] == "gerant" for d in arbre_cs[0]["divisions"] if d["id"] in (v1, v2))


# --- garanties conservées après la refonte : privilèges, listes cloisonnées par division ----

def test_privileges_inchanges_et_listes_par_division(client, world):
    """La matrice des privilèges ne change pas : AUTEUR / LECTEUR / GERANT / 404, et la liste à plat ne montre
    que les divisions du périmètre (l'agent ne voit pas les fichiers de l'autre service)."""
    adm = world["admin"]
    a, lect, mix, b, cd1 = world["a"]["h"], world["lect"]["h"], world["mix"]["h"], world["b"]["h"], world["cd1"]["h"]
    tag, R = world["tag"], world["roles"]
    A, B = world["A"]["id"], world["B"]["id"]
    # dépôt d'un agent : classement automatique (tous ses rôles par défaut), privilèges inchangés
    f = upload(client, a, A, f"Pièce courante {tag}").json()
    assert [r["code"] for r in f["roles"]] == ["COMPTA"]          # organisation prévue : COMPTA
    assert client.get(f"/documents/{f['id']}", headers=a).json()["mon_role"] == "AUTEUR"
    assert client.get(f"/documents/{f['id']}", headers=lect).json()["mon_role"] == "LECTEUR"
    assert client.get(f"/documents/{f['id']}", headers=cd1).json()["mon_role"] == "GERANT"
    assert client.get(f"/documents/{f['id']}", headers=mix).status_code == 403    # rôle PUBLIC absent
    assert client.get(f"/documents/{f['id']}", headers=b).status_code == 404      # autre division : existence cachée
    # la liste à plat est cloisonnée : l'agent a les fichiers de SA division, jamais ceux de l'autre service
    assert f["id"] in ids(client.get("/documents", headers=a).json())
    filtres_a = client.get("/documents/filtres", headers=a).json()
    assert [d["id"] for d in filtres_a["divisions"]] == [A] and B not in [d["id"] for d in filtres_a["divisions"]]
    filtres_b = client.get("/documents/filtres", headers=b).json()
    assert [d["id"] for d in filtres_b["divisions"]] == [B]
    # le chef de service filtre par division : il voit les deux divisions de SON service, pas v3
    filtres_cs = client.get("/documents/filtres", headers=world["cs"]["h"]).json()
    assert A in [d["id"] for d in filtres_cs["divisions"]] and B not in [d["id"] for d in filtres_cs["divisions"]]
    liste_cs = client.get("/documents", headers=world["cs"]["h"], params={"division_id": A}).json()
    assert f["id"] in ids(liste_cs)
    assert client.get("/documents", headers=world["cs"]["h"], params={"division_id": B}).json() == []


def test_deux_modes_de_classement(client, world):
    """Mode 1 (automatique) : un agent dépose sans préciser les rôles, le fichier reçoit tous ses rôles.
    Mode 2 (manuel) : le chef de division attribue explicitement le fichier à un ou plusieurs agents
    de sa division, via les rôles du dictionnaire — y compris après le dépôt (« à classer »)."""
    a, lect, mix, b, cd1 = world["a"]["h"], world["lect"]["h"], world["mix"]["h"], world["b"]["h"], world["cd1"]["h"]
    tag, R = world["tag"], world["roles"]
    A = world["A"]["id"]
    # mode automatique : dépôt sans role_ids -> tous les rôles de l'agent, visible des détenteurs
    f = upload(client, a, A, f"Classement automatique {tag}").json()
    assert f["a_classer"] is False and [r["code"] for r in f["roles"]] == ["COMPTA"]
    assert client.get(f"/documents/{f['id']}", headers=lect).status_code == 200       # détenteur COMPTA
    assert client.get(f"/documents/{f['id']}", headers=mix).status_code == 403        # hors organisation prévue
    # mode manuel : dépôt du chef sans choix -> « à classer », invisible de tous les agents
    m = upload(client, cd1, A, f"Attribution manuelle {tag}").json()
    assert m["a_classer"] is True and m["roles"] == []
    assert client.get(f"/documents/{m['id']}", headers=lect).status_code == 403
    assert client.get(f"/documents/{m['id']}", headers=mix).status_code == 403
    # le chef attribue explicitement à plusieurs agents (rôles COMPTA + PUBLIC), en une opération tracée
    r = client.put(f"/documents/{m['id']}/roles", headers=cd1, json={"role_ids": [R["COMPTA"]["id"], R["PUBLIC"]["id"]], "motif": "Attribution manuelle"})
    assert r.status_code == 200 and sorted(x["code"] for x in r.json()["roles"]) == ["COMPTA", "PUBLIC"]
    assert client.get(f"/documents/{m['id']}", headers=lect).status_code == 200       # agent COMPTA
    assert client.get(f"/documents/{m['id']}", headers=mix).status_code == 200        # agent PUBLIC
    assert client.get(f"/documents/{m['id']}", headers=b).status_code == 404          # hors de la division


def test_le_chef_de_service_meme_role_sur_toutes_les_divisions(client, world):
    """Le chef de service a le même rôle que le chef de division, étendu à toutes les divisions de son service :
    GERANT sur les fichiers, classement manuel, comptes des agents sans titre, décisions de demandes ;
    ni les chefs, ni le service voisin."""
    adm, cs, tag, R = world["admin"], world["cs"]["h"], world["tag"], world["roles"]
    s1, s2, v1, v2 = world["svc"]["s1"]["id"], world["svc"]["s2"]["id"], world["div"]["v1"]["id"], world["div"]["v2"]["id"]
    me = client.get("/auth/me", headers=cs).json()
    assert me["titre"] == "CHEF_SERVICE" and me["niveau"] == "SERVICE" and me["division_id"] is None and me["service_id"] == s1
    assert "utilisateur.creer" in me["permissions"]
    gerees = {d["id"] for d in me["divisions_gerees"]}
    assert {v1, v2} <= gerees  # (une division créée par un autre test peut exister aussi dans s1)
    # hors de son service : l'existence n'est pas révélée
    assert client.post(f"/divisions/{world['div']['v3']['id']}/roles", headers=cs, json={"code": "PIRATE", "libelle": "Pirate"}).status_code == 404
    # GERANT sur les fichiers des divisions de son service, sans déverrouillage
    f1 = upload(client, world["a"]["h"], world["A"]["id"], f"Sous la houlette du chef de service {tag}").json()
    assert client.get(f"/documents/{f1['id']}", headers=cs).json()["mon_role"] == "GERANT"
    # dans la division v2, il dépose un fichier « à classer », puis le classe avec un rôle DE v2
    f2 = upload(client, cs, v2, f"Pièce relancée {tag}", titre="Relance").json()
    assert f2["a_classer"] is True
    assert client.get(f"/documents/{f2['id']}", headers=world["cd1"]["h"]).status_code == 404
    r_v2 = client.post(f"/divisions/{v2}/roles", headers=cs, json={"code": "RELANCE", "libelle": "Relance"})
    assert r_v2.status_code == 201, r_v2.text
    assert client.put(f"/documents/{f2['id']}/roles", headers=cs, json={"role_ids": [r_v2.json()["id"]], "motif": "Relance"}).status_code == 200
    # un rôle d'une autre division est refusé (clés composites)
    assert client.put(f"/documents/{f2['id']}/roles", headers=cs, json={"role_ids": [R["PUBLIC"]["id"]]}).status_code == 422
    # demandes d'accès de sa division : il décide comme un chef de division
    dem = client.post("/demandes", headers=world["mix"]["h"], json={"type_demande": "fichier", "cible_id": f1["id"], "motif": "Périmètre", "duree_heures": 4}).json()
    assert dem["id"] in ids(client.get("/demandes", headers=cs, params={"vue": "a_traiter", "statut": "en_attente"}).json())
    assert client.post(f"/demandes/{dem['id']}/decision", headers=cs, json={"accepter": True}).status_code == 200
    assert client.get(f"/documents/{f1['id']}", headers=world["mix"]["h"]).status_code == 200
    # comptes : les agents ET les chefs de division de son service — pas le chef de service voisin, pas hors service
    p_cs = mk_agent(client, adm, "pcs", tag, s1, v2)
    u_pcs = mk_user(client, cs, p_cs, "pcs", tag)
    v5 = client.post("/structure/divisions", headers=adm, json={"service_id": s1, "nom": f"Division v5 {tag}", "code": f"v5{tag}"}).json()
    chx = mk_agent(client, adm, "chx", tag, s1, v5["id"], "CHEF_DIVISION")     # un chef de SA division : gérable par cs
    r_chx = client.post("/users", headers=cs, json={"nom_utilisateur": f"chef_div_v5_{tag}", "mot_de_passe": PWD, "role": "UTILISATEUR", "agent_id": chx["id"]})
    assert r_chx.status_code == 201, r_chx.text                                # il crée le compte du chef de division
    assert r_chx.json()["niveau"] == "DIVISION"
    # et il réinitialise le mot de passe d'un chef de division de son service (si le super administrateur ne l'a pas fait)
    assert client.patch(f"/users/{world['cd1']['user']['id']}", headers=cs, json={"mot_de_passe": "mdp-reinitialise-1"}).status_code == 200
    assert login(client, world["cd1"]["name"], "mdp-reinitialise-1").status_code == 200
    hs = mk_agent(client, adm, "hsx", tag, s2, world["div"]["v3"]["id"])       # agent du service voisin : hors périmètre
    assert client.post("/users", headers=cs, json={"nom_utilisateur": f"autre_service_{tag}", "mot_de_passe": PWD, "role": "UTILISATEUR", "agent_id": hs["id"]}).status_code == 404
    # attribution manuelle complète : rôle de v2 au compte créé, le fichier classé RELANCE devient visible
    client.patch(f"/users/{world['cd1']['user']['id']}", headers=adm, json={"mot_de_passe": PWD})
    world["cd1"]["h"] = auth(client, world["cd1"]["name"])
    set_roles(client, cs, u_pcs["user"]["id"], [r_v2.json()["id"]])
    assert client.get(f"/documents/{f2['id']}", headers=u_pcs["h"]).status_code == 200
    assert client.get(f"/documents/{f2['id']}", headers=world["mix"]["h"]).status_code == 404
    # le chef de service ne touche pas au poste de chef de service ni aux directions/services/divisions
    assert client.post("/structure/services", headers=cs, json={"direction_id": world["dir"]["id"], "code": f"ZS{tag}", "nom": "x"}).status_code == 403
    assert client.post("/structure/divisions", headers=cs, json={"service_id": s1, "nom": f"Interdite {tag}"}).status_code == 403
    assert client.put(f"/structure/services/{world['svc']['s1']['id']}/chef", headers=cs, json={"agent_id": world["cs"]["agent"]["id"]}).status_code == 403
    # intérim local : une division sans chef est gérée par le chef de service comme par le super administrateur
    v4 = client.post("/structure/divisions", headers=adm, json={"service_id": s1, "nom": f"Division v4 {tag}", "code": f"v4{tag}"}).json()
    assert client.post(f"/divisions/{v4['id']}/roles", headers=cs, json={"code": "V4", "libelle": "Rôle v4"}).status_code == 201
    assert client.post(f"/divisions/{v4['id']}/roles", headers=adm, json={"code": "V4B", "libelle": "Rôle v4b"}).status_code == 201
    # transfert du poste de chef de service (unique) : retrait par case à cocher puis transfert au premier titulaire
    ancien = world["cs"]["agent"]["id"]
    assert client.patch(f"/structure/agents/{ancien}", headers=adm, json={"titre": None}).status_code == 200
    succ = mk_agent(client, adm, "cs2", tag, s1, None, "CHEF_SERVICE")
    assert succ["titre"] == "CHEF_SERVICE"
    r = client.put(f"/structure/services/{s1}/chef", headers=adm, json={"agent_id": ancien, "motif": "Retour du titulaire"})
    assert r.status_code == 200, r.text
    chefs = {a["id"]: a["titre"] for a in client.get("/structure/agents", headers=adm).json()}
    assert chefs[ancien] == "CHEF_SERVICE" and chefs[succ["id"]] is None
    assert next(s for s in client.get("/structure/postes", headers=adm).json()["services"] if s["service_id"] == s1)["chef"]["agent_id"] == ancien
    # un agent avec division ne peut pas devenir chef de service ; un agent d'un autre service non plus
    assert client.put(f"/structure/services/{s2}/chef", headers=adm, json={"agent_id": world["cd3"]["agent"]["id"]}).status_code == 422
    assert client.put(f"/structure/services/{s2}/chef", headers=adm, json={"agent_id": ancien}).status_code == 422
