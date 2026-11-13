from types import SimpleNamespace

from app.services.classement import definir_classement_manuel


class FakeSession:
    def __init__(self):
        self.tags = [SimpleNamespace(id=1, nom="finance"), SimpleNamespace(id=2, nom="rh")]
        self.document_tags = [
            SimpleNamespace(document_id=42, tag_id=1, source="manuel"),
            SimpleNamespace(document_id=42, tag_id=99, source="regle"),
        ]

    def query(self, model):
        if model.__name__ == "Tag":
            return FakeQuery(self.tags)
        if model.__name__ == "DocumentTag":
            return FakeQuery(self.document_tags)
        raise TypeError(f"modèle non supporté : {model!r}")

    def add(self, obj):
        self._last = obj

    def commit(self):
        return None

    def flush(self):
        return None


class FakeQuery:
    def __init__(self, rows):
        self.rows = list(rows)

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self.rows[0] if self.rows else None

    def delete(self):
        self.rows.clear()
        return 1


def test_definir_classement_manuel_remplace_les_tags_manuels_sans_effacer_les_tags_regles():
    session = FakeSession()
    doc = SimpleNamespace(
        id=42,
        categorie_id=None,
        type_document_id=None,
        confidentialite="INTERNE",
        classement_source="aucun",
    )

    definir_classement_manuel(
        session,
        doc,
        categorie_id=8,
        type_document_id=12,
        tags=["finance", "urgent"],
        confidentialite="CONFIDENTIEL",
    )

    assert doc.categorie_id == 8
    assert doc.type_document_id == 12
    assert doc.confidentialite == "CONFIDENTIEL"
    assert doc.classement_source == "manuel"
