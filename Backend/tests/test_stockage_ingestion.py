"""Fichier absent du disque : l'ingestion l'explique clairement au lieu de laisser un FileNotFoundError brut.

Tests sans base ni service externe : le stockage pointe vers un dossier temporaire et la session est simulée.
"""

from types import SimpleNamespace

import pytest

from app.services import stockage
from app.services.ingestion import pipeline


@pytest.fixture
def upload_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(stockage, "get_settings", lambda: SimpleNamespace(upload_dir=tmp_path))
    return tmp_path


def test_trouver_chemin_absolu_existant(upload_dir):
    f = upload_dir / "a.pdf"
    f.write_bytes(b"%PDF")
    assert stockage.trouver(str(f)) == f.resolve()


def test_trouver_fichier_absent(upload_dir):
    assert stockage.trouver(str(upload_dir / "absent.pdf")) is None


def test_trouver_chemin_relatif(upload_dir):
    (upload_dir / "b.pdf").write_bytes(b"%PDF")
    assert stockage.trouver("b.pdf") == (upload_dir / "b.pdf").resolve()


def test_trouver_chemin_perime_d_une_autre_machine(upload_dir):
    """Base importée / projet déplacé : le chemin absolu ne correspond plus, mais le fichier est dans upload_dir."""
    (upload_dir / "c.pdf").write_bytes(b"%PDF")
    ancien = r"D:\Ancien Projet\Backend\storage\uploads\c.pdf"
    assert stockage.trouver(ancien) == (upload_dir / "c.pdf").resolve()


def test_trouver_refuse_les_chemins_hors_stockage(upload_dir, tmp_path_factory):
    dehors = tmp_path_factory.mktemp("dehors") / "secret.pdf"
    dehors.write_bytes(b"%PDF")
    assert stockage.trouver(str(dehors)) is None
    assert stockage.trouver("../../etc/passwd") is None


class _FakeSession:
    def __init__(self, version):
        self._version = version

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get(self, _model, _id):
        return self._version

    def commit(self):
        pass


def test_ingestion_fichier_introuvable_marque_une_erreur_claire(upload_dir, monkeypatch, caplog):
    doc = SimpleNamespace(id=1, has_tabular=False, has_image=False)
    version = SimpleNamespace(
        id=1, document=doc, nom_fichier="Budget 2026.pdf", statut="pending", message_erreur=None,
        chemin_stockage=str(upload_dir / "15557a6701454810ae7cfce6fa6d764c.pdf"),
    )
    erreurs: list[tuple[int, str]] = []
    monkeypatch.setattr(pipeline, "SessionLocal", lambda: _FakeSession(version))
    monkeypatch.setattr(pipeline, "_mark_error", lambda vid, msg: erreurs.append((vid, msg)))

    with caplog.at_level("WARNING", logger=pipeline.logger.name):
        pipeline.run_ingestion(1)  # ne doit pas lever

    assert len(erreurs) == 1 and erreurs[0][0] == 1
    assert "Budget 2026.pdf" in erreurs[0][1] and "introuvable" in erreurs[0][1]
    assert "FileNotFoundError" not in erreurs[0][1]
    assert not any(r.exc_info for r in caplog.records)  # pas de trace complète pour une cause attendue
