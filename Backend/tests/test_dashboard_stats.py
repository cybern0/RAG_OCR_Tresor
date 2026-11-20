from types import SimpleNamespace

from app.api.routes.classement import delete_category, delete_rule, delete_tag, delete_type, stats_dashboard
from app.core.permissions import Principal
from app.services.classement import build_dashboard_stats


class DummyRows:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return [dict(item) for item in self._rows]


class DummyResult:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return DummyRows(self._rows)

    def scalar_one_or_none(self):
        return 1

    def all(self):  # requêtes de libellés (charger_noms)
        return []


class DummySession:
    bind = object()

    def __init__(self):
        self.calls = []

    def execute(self, statement, *args, **kwargs):
        self.calls.append(statement)
        if isinstance(statement, str):
            raise AssertionError("execute() a reçu du SQL brut : utilisez text(...)")
        if "to_regclass" in str(statement):
            return DummyResult([])
        if "vue_document_stats" in str(statement):
            return DummyResult([
                {"document_id": 1, "categorie_id": 5, "type_document_id": 2, "confidentialite": "INTERNE", "statut": "ready", "extension": "pdf", "service_id": 7, "direction_id": 3, "corbeille_le": None},
            ])
        return DummyResult([])


def test_build_dashboard_stats_agregates_documents():
    rows = [
        {"document_id": 1, "categorie_id": 5, "type_document_id": 2, "confidentialite": "INTERNE", "statut": "ready", "extension": "pdf", "service_id": 7, "direction_id": 3, "corbeille_le": None},
        {"document_id": 2, "categorie_id": 5, "type_document_id": 2, "confidentialite": "CONFIDENTIEL", "statut": "processing", "extension": "pdf", "service_id": 7, "direction_id": 3, "corbeille_le": None},
        {"document_id": 3, "categorie_id": None, "type_document_id": 4, "confidentialite": "PUBLIC", "statut": "error", "extension": "docx", "service_id": None, "direction_id": None, "corbeille_le": "2024-03-01"},
    ]

    stats = build_dashboard_stats(rows)

    assert stats["total_documents"] == 3
    assert stats["statut"]["ready"] == 1
    assert stats["statut"]["processing"] == 1
    assert stats["statut"]["error"] == 1
    assert stats["par_categorie"][0]["categorie_id"] == 5
    assert stats["par_categorie"][0]["total"] == 2
    assert stats["par_confidentialite"]["INTERNE"] == 1
    assert stats["par_extension"]["pdf"] == 2
    assert stats["actifs"] == 2
    assert stats["corbeille"] == 1
    assert stats["sans_classement"] == 0
    assert stats["par_categorie"][0]["nom"] is None  # sans table de libellés


def test_build_dashboard_stats_adds_names_and_storage():
    rows = [
        {"document_id": 1, "categorie_id": 5, "type_document_id": None, "confidentialite": "INTERNE", "statut": "ready",
         "extension": "pdf", "service_id": 7, "direction_id": 3, "corbeille_le": None, "taille_octets": 1000, "nb_versions": 2},
        {"document_id": 2, "categorie_id": None, "type_document_id": None, "confidentialite": "PUBLIC", "statut": "ready",
         "extension": "txt", "service_id": None, "direction_id": None, "corbeille_le": None, "taille_octets": 500, "nb_versions": 1},
    ]
    noms = {"categorie": {5: {"nom": "Finance", "couleur": "#d9a92b"}}}

    stats = build_dashboard_stats(rows, noms)

    assert stats["par_categorie"] == [{"categorie_id": 5, "total": 1, "nom": "Finance", "couleur": "#d9a92b"}]
    assert stats["stockage_octets"] == 1500 and stats["nb_versions"] == 3
    assert stats["sans_classement"] == 1


def test_stats_dashboard_uses_sqlalchemy_text_statements():
    principal = Principal(user=SimpleNamespace(role=SimpleNamespace(code="ADMIN")), permissions=frozenset({"statistiques.globales"}), niveau="ROOT")
    db = DummySession()

    payload = stats_dashboard(db=db, _=principal)

    assert payload["total_documents"] == 1
    assert payload["statut"]["ready"] == 1
    assert any("text" in str(call) or "SELECT" in str(call) for call in db.calls)


def test_delete_methods_mark_or_remove_ged_entities():
    class DummyItem:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class DummyDeleteSession:
        def __init__(self):
            self.deleted = []
            self.items = {}

        def get(self, model, id_):
            return self.items.get((model.__name__, id_))

        def delete(self, item):
            self.deleted.append(item)

        def commit(self):
            return None

    db = DummyDeleteSession()
    cat = DummyItem(id=1, actif=True)
    typ = DummyItem(id=2, actif=True)
    tag = DummyItem(id=3)
    rule = DummyItem(id=4)
    db.items = {('Categorie', 1): cat, ('TypeDocument', 2): typ, ('Tag', 3): tag, ('RegleClassement', 4): rule}

    deleted_cat = delete_category(1, db=db)
    deleted_type = delete_type(2, db=db)
    deleted_tag = delete_tag(3, db=db)
    deleted_rule = delete_rule(4, db=db)

    assert deleted_cat.actif is False
    assert deleted_type.actif is False
    assert deleted_tag is tag
    assert deleted_rule is rule
    assert len(db.deleted) == 2


def test_charger_roles_et_classement_trie_et_numerote():
    from app.services.classement import charger_roles_et_classement

    class FakeResult:
        def __init__(self, rows):
            self._rows = rows

        def all(self):
            return self._rows

    class FakeDb:
        def __init__(self):
            self.answers = [
                [("Agent", 2), ("Chef de division", 5)],  # utilisateurs par rôle
                [("alice", 3), ("bob", 7), ("carl", 3)],  # fichiers déposés par utilisateur
            ]

        def execute(self, _statement):
            return FakeResult(self.answers.pop(0))

    out = charger_roles_et_classement(FakeDb(), limite=2)

    assert out["par_role"] == [{"nom": "Chef de division", "total": 5}, {"nom": "Agent", "total": 2}]
    assert out["classement"] == [{"rang": 1, "nom": "bob", "total": 7}, {"rang": 2, "nom": "alice", "total": 3}]
