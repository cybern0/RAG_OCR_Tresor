import pytest

from app.services.classement.moteur import evaluer_regles


def test_priorite_des_regles_et_acces_au_texte():
    regles = [
        {
            "nom": "vt",
            "priorite": 20,
            "categorie_id": 5,
            "type_document_id": 11,
            "tags": ["finance"],
            "confidentialite": "INTERNE",
            "criteres": [{"champ": "extension", "op": "dans", "valeur": ["pdf"]}],
        },
        {
            "nom": "rh",
            "priorite": 10,
            "categorie_id": 9,
            "type_document_id": 12,
            "tags": ["rh", "personnel"],
            "confidentialite": "CONFIDENTIEL",
            "criteres": [{"champ": "texte", "op": "contient_un_de", "valeur": ["arrêté", "décret"]}],
        },
    ]

    contexte = {"extension": "pdf", "texte": "Arrêté de nomination du personnel", "classement_source": "regle"}
    result = evaluer_regles(regles, contexte)

    assert result["categorie_id"] == 9
    assert result["type_document_id"] == 12
    assert set(result["tags"]) == {"finance", "rh", "personnel"}
    assert result["confidentialite"] == "CONFIDENTIEL"


def test_tags_s_ajoutent_et_la_main_l_emporte():
    regles = [
        {
            "nom": "r1",
            "priorite": 5,
            "categorie_id": 2,
            "type_document_id": 3,
            "tags": ["automatique"],
            "criteres": [{"champ": "nom_fichier", "op": "regex", "valeur": r"^FACTURE-"}],
        },
        {
            "nom": "r2",
            "priorite": 8,
            "categorie_id": 2,
            "type_document_id": 3,
            "tags": ["urgent"],
            "criteres": [{"champ": "extension", "op": "=", "valeur": "csv"}],
        },
    ]

    res = evaluer_regles(regles, {"nom_fichier": "FACTURE-2024-01.csv", "extension": "csv", "classement_source": "regle"})
    assert set(res["tags"]) == {"automatique", "urgent"}

    manual = evaluer_regles(regles, {"nom_fichier": "FACTURE-2024-01.csv", "extension": "csv", "classement_source": "manuel"})
    assert manual == {"categorie_id": None, "type_document_id": None, "tags": [], "confidentialite": None}


def test_regle_regex_invalide_ou_trop_longue_refusee():
    bad_pattern = "["
    too_long = "a" * 257
    with pytest.raises(ValueError):
        evaluer_regles([
            {"nom": "bad", "priorite": 1, "criteres": [{"champ": "nom_fichier", "op": "regex", "valeur": bad_pattern}]}
        ], {"nom_fichier": "x.pdf"})

    with pytest.raises(ValueError):
        evaluer_regles([
            {"nom": "too-long", "priorite": 1, "criteres": [{"champ": "nom_fichier", "op": "regex", "valeur": too_long}]}
        ], {"nom_fichier": "x.pdf"})
