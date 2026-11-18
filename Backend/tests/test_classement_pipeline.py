from types import SimpleNamespace

from app.services.classement import appliquer


class Query:
    def __init__(self, rows):
        self._rows = list(rows)
        self._filters = []
        self._filter_by = {}

    def filter(self, *criteria, **kwargs):
        self._filters.extend(criteria)
        return self

    def filter_by(self, **kwargs):
        self._filter_by.update(kwargs)
        return self

    def order_by(self, *args, **kwargs):
        return self

    def first(self):
        rows = self._matching_rows()
        return rows[0] if rows else None

    def all(self):
        return self._matching_rows()

    def delete(self):
        rows = self._matching_rows()
        self._rows = [row for row in self._rows if row not in rows]
        return len(rows)

    def _matching_rows(self):
        rows = list(self._rows)
        for criterion in self._filters:
            if hasattr(criterion, "left") and hasattr(criterion, "right"):
                left = criterion.left
                right = criterion.right
                if isinstance(left, property):
                    left = left.fget
                rows = [row for row in rows if getattr(row, left.name, None) == right]
            else:
                rows = [row for row in rows if criterion(row)]
        for key, value in self._filter_by.items():
            rows = [row for row in rows if getattr(row, key, None) == value]
        return rows


class FakeSession:
    def __init__(self):
        self.tags = [SimpleNamespace(id=1, nom="finance"), SimpleNamespace(id=2, nom="rh")]
        self.document_tags = [
            SimpleNamespace(document_id=42, tag_id=1, source="manuel"),
            SimpleNamespace(document_id=42, tag_id=99, source="regle"),
        ]
        self.rules = [
            SimpleNamespace(
                id=7,
                nom="rh",
                priorite=10,
                actif=True,
                categorie_id=3,
                type_document_id=11,
                tags=["rh", "personnel"],
                confidentialite="CONFIDENTIEL",
                critere={"tous": [{"champ": "texte", "op": "contient_un_de", "valeur": ["arrêté", "décret"]}]},
            )
        ]
        self.added = []

    def query(self, model):
        if model.__name__ == "Tag":
            return Query(self.tags)
        if model.__name__ == "DocumentTag":
            return Query(self.document_tags)
        if model.__name__ == "RegleClassement":
            return Query(self.rules)
        raise TypeError(f"modèle non supporté : {model!r}")

    def add(self, obj):
        self.added.append(obj)

    def flush(self):
        return None

    def commit(self):
        return None


def test_appliquer_remplace_les_tags_regles_sans_ecraser_les_tags_manuels():
    session = FakeSession()
    doc = SimpleNamespace(
        id=42,
        service_createur_id=None,
        categorie_id=None,
        type_document_id=None,
        confidentialite="INTERNE",
        classement_source="aucun",
        regle_id=None,
        cree_par_service_id=4,
    )
    version = SimpleNamespace(
        id=18,
        nom_fichier="decret_nomination.pdf",
        taille_octets=1500,
        nb_pages=2,
        ocr_utilise=False,
    )

    appliquer(session, doc, version, "Arrêté de nomination du personnel")

    assert doc.categorie_id == 3
    assert doc.type_document_id == 11
    assert doc.confidentialite == "CONFIDENTIEL"
    assert doc.classement_source == "regle"
    assert doc.regle_id == 7
    assert all(tag.source == "regle" for tag in session.document_tags if tag.document_id == 42 and tag.tag_id != 1)
    assert any(tag.tag_id == 1 for tag in session.document_tags if tag.document_id == 42)
