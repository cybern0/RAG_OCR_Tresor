from datetime import datetime, timedelta, timezone

from app.services.documents import crud


class DummyVersion:
    def __init__(self, numero, nom_fichier, statut, cree_le=None):
        self.numero = numero
        self.nom_fichier = nom_fichier
        self.statut = statut
        self.cree_le = cree_le or datetime(2024, 1, 1, tzinfo=timezone.utc)


class DummyDoc:
    def __init__(self, id, titre, dossier_id, cree_par, cree_le, versions):
        self.id = id
        self.titre = titre
        self.dossier_id = dossier_id
        self.cree_par = cree_par
        self.cree_le = cree_le
        self.versions = versions


def test_document_filters_and_pagination():
    now = datetime.now(timezone.utc)
    docs = [
        DummyDoc(1, "Facture RH", 10, 3, now - timedelta(days=3), [DummyVersion(1, "facture-rh.pdf", "ready", now - timedelta(days=3))]),
        DummyDoc(2, "Note de service", 10, 1, now - timedelta(days=2), [DummyVersion(1, "note.docx", "ready", now - timedelta(days=2))]),
        DummyDoc(3, "Facture juridique", 10, 3, now - timedelta(days=1), [DummyVersion(1, "facture-legal.pdf", "error", now - timedelta(days=1))]),
    ]

    page = crud.apply_document_filters(
        docs,
        q="facture",
        extension="pdf",
        statut="ready",
        du=now - timedelta(days=10),
        au=now,
        tri="date_desc",
        page=1,
        taille=1,
    )

    assert page["total"] == 1
    assert page["page"] == 1
    assert page["taille"] == 1
    assert page["items"][0].id == 1

    page_2 = crud.apply_document_filters(docs, tri="titre_asc", page=2, taille=2)
    assert page_2["total"] == 3
    assert [d.id for d in page_2["items"]] == [2]


def test_document_filters_by_classement():
    from types import SimpleNamespace

    now = datetime.now(timezone.utc)

    def doc(id, categorie, type_, conf, tags):
        d = DummyDoc(id, f"Doc {id}", 10, 1, now, [DummyVersion(1, f"d{id}.pdf", "ready", now)])
        d.categorie_id, d.type_document_id, d.confidentialite = categorie, type_, conf
        d.tag_liens = [SimpleNamespace(tag_id=t) for t in tags]
        return d

    docs = [doc(1, 5, 2, "INTERNE", [1, 2]), doc(2, 5, 3, "PUBLIC", [1]), doc(3, None, None, "INTERNE", [])]

    assert [d.id for d in crud.apply_document_filters(docs, categorie_id=5, tri="titre_asc")["items"]] == [1, 2]
    assert [d.id for d in crud.apply_document_filters(docs, type_id=3)["items"]] == [2]
    assert [d.id for d in crud.apply_document_filters(docs, confidentialite="interne", tri="titre_asc")["items"]] == [1, 3]
    assert [d.id for d in crud.apply_document_filters(docs, tag_ids=[1, 2])["items"]] == [1]
