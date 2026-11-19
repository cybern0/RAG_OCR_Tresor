import time

from app.core.acces import AUTEUR, GERANT, LECTEUR, MATRICE, SUPERIEUR
from app.core.security import (
    LoginThrottle, create_access_token, hash_password, is_locked_hash, read_token, token_matches_password,
    verify_password,
)


def test_hash_et_verification():
    h = hash_password("un-mot-de-passe-solide")
    assert h.startswith("scrypt$") and "solide" not in h
    assert verify_password("un-mot-de-passe-solide", h)
    assert not verify_password("autre-mot-de-passe", h)
    assert hash_password("un-mot-de-passe-solide") != h  # sel différent à chaque fois


def test_compte_verrouille_refuse_toute_connexion():
    assert is_locked_hash("!A_DEFINIR")
    assert not verify_password("!A_DEFINIR", "!A_DEFINIR")
    assert not verify_password("", "!A_DEFINIR")


def test_hash_invalide_ne_plante_pas():
    for bad in ("", "n'importe quoi", "scrypt$1$2", "scrypt$a$b$c$d$e"):
        assert not verify_password("x", bad)


def test_jeton_valide_expire_et_falsifie():
    h = hash_password("mot-de-passe-1234")
    token, ttl = create_access_token(42, h)
    payload = read_token(token)
    assert payload and payload["sub"] == 42 and ttl > 0
    assert token_matches_password(payload, h)
    assert read_token(token, now=time.time() + ttl + 5) is None          # expiré
    body, sig = token.split(".")
    assert read_token(body + "." + sig[:-2] + "AA") is None              # signature altérée
    assert read_token("n.importe.quoi") is None and read_token("") is None


def test_jeton_invalide_apres_changement_de_mot_de_passe():
    token, _ = create_access_token(1, hash_password("ancien-mot-de-passe"))
    payload = read_token(token)
    assert not token_matches_password(payload, hash_password("nouveau-mot-de-passe"))


def test_limitation_des_essais():
    t = LoginThrottle(max_failures=3, window_seconds=60)
    for _ in range(3):
        assert not t.is_blocked("ip|bob", now=100)
        t.record_failure("ip|bob", now=100)
    assert t.is_blocked("ip|bob", now=101)
    assert not t.is_blocked("ip|alice", now=101)      # clés indépendantes
    assert not t.is_blocked("ip|bob", now=161)        # la fenêtre a expiré
    t.record_failure("ip|bob", now=200); t.reset("ip|bob")
    assert not t.is_blocked("ip|bob", now=200)


def test_matrice_des_roles_effectifs_sur_un_fichier():
    # le gérant fait tout ; le rôle de classement des fichiers et la purge lui sont réservés
    assert {"classer", "purger"} <= MATRICE[GERANT] and not ({"classer", "purger"} & MATRICE[AUTEUR])
    # l'auteur gère ses dépôts mais ne supprime jamais (corbeille et purge réservées au gérant)
    assert {"modifier", "ajouter_version"} <= MATRICE[AUTEUR] and not ({"supprimer", "purger"} & MATRICE[AUTEUR])
    assert "supprimer" in MATRICE[GERANT]
    # le lecteur lit et commente seulement
    assert MATRICE[LECTEUR] == {"voir", "apercu", "telecharger", "chat", "commenter"}
    # l'administrateur supérieur est en lecture seule : ni commentaire, ni écriture
    assert MATRICE[SUPERIEUR] == {"voir", "apercu", "telecharger", "chat"}
