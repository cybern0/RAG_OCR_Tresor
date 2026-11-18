"""Sonde de santé du serveur OCR (clients/ocr_paddle.ping_ocr).

Un serveur OCR local personnalisé n'expose pas forcément /health : toute réponse HTTP
(404 comprise) prouve que l'hôte répond et l'indexation via POST /ocr fonctionne.
Seule l'impossibilité de joindre l'hôte rend le badge « Serveur OCR » rouge.
"""

import httpx
import pytest

from app.clients.ocr_paddle import ping_ocr


class _Reponse:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


@pytest.mark.parametrize("statut", [200, 404, 405])
def test_ping_ocr_joignable_des_reponse_http(monkeypatch, statut):
    """Toute réponse du host — même un 404 sur /health — est « opérationnel »."""
    monkeypatch.setattr("app.clients.ocr_paddle.httpx.get", lambda *a, **k: _Reponse(statut))
    assert ping_ocr() is True


@pytest.mark.parametrize("erreur", [httpx.ConnectError("refusé"), httpx.ConnectTimeout("lent"), httpx.ReadTimeout("dépassement")])
def test_ping_ocr_injoignable(monkeypatch, erreur):
    monkeypatch.setattr("app.clients.ocr_paddle.httpx.get", lambda *a, **k: (_ for _ in ()).throw(erreur))
    assert ping_ocr() is False
