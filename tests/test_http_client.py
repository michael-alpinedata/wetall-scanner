"""
Tests — fetch_with_fallback
==============================

Couverture visée :
  ✓ Réponse 200 normale         → retournée directement, curl non appelé
  ✓ Réponse 200 Decathlon       → retournée directement (pas de fallback)
  ✓ Réponse 403 URL générique   → pas un hard-target, curl non appelé
  ✓ Réponse 401 URL générique   → pas un hard-target, curl non appelé
  ✓ Réponse 403 Decathlon       → fallback curl_cffi déclenché
  ✓ Réponse 401 Decathlon       → fallback curl_cffi déclenché
  ✓ Réponse 403 Alltricks       → fallback curl_cffi déclenché
  ✓ curl_cffi réussit           → réponse curl retournée
  ✓ curl_cffi lève une Exception → réponse originale retournée en fallback
  ✓ curl_cffi non installé      → excepté, réponse originale retournée
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

DECATHLON_URL = "https://www.decathlon.fr/p/veste-trail/_/R-p-305611"
ALLTRICKS_URL = "https://www.alltricks.fr/produit/velo-route-1234"
NIKE_URL = "https://www.nike.com/fr/t/chaussure-react/AB1234"
GENERIC_URL = "https://www.unknown-shop.com/product/123"

HEADERS = {"User-Agent": "test-agent", "Accept": "text/html"}


def _make_client_returning(status_code: int, url: str = GENERIC_URL) -> MagicMock:
    """Crée un client httpx mock dont .get() retourne une réponse avec le code donné."""
    from tests.conftest import make_response

    client = MagicMock()
    client.get.return_value = make_response(status_code=status_code, url=url)
    return client


class TestFetchWithFallback:
    # ── Cas nominaux (pas de fallback) ───────────────────────────────────────

    def test_200_response_returned_directly(self, http_client_impl):
        client = _make_client_returning(200)
        fn = http_client_impl["fetch_with_fallback"]
        resp = fn(client, GENERIC_URL, HEADERS)
        assert resp.status_code == 200
        client.get.assert_called_once_with(GENERIC_URL, headers=HEADERS)

    def test_decathlon_triggers_curl_immediately(self, http_client_impl):
        """Decathlon est un hard-target : on utilise curl_cffi d'entrée de jeu (préventif)."""
        client = _make_client_returning(200, url=DECATHLON_URL)
        fn = http_client_impl["fetch_with_fallback"]

        with patch(http_client_impl["curl_get_path"]) as mock_curl:
            # Simule un objet httpx.Response car fetch_with_fallback attend ça
            mock_curl.return_value = MagicMock(status_code=200)
            fn(client, DECATHLON_URL, HEADERS)
            mock_curl.assert_called_once()
            # httpx ne doit PAS être appelé pour les hard targets
            client.get.assert_not_called()

    def test_403_generic_url_triggers_fallback(self, http_client_impl):
        """URL générique en 403 → déclenche désormais le fallback curl_cffi."""
        client = _make_client_returning(403)
        fn = http_client_impl["fetch_with_fallback"]

        with patch(http_client_impl["curl_get_path"]) as mock_curl:
            mock_curl.return_value = MagicMock(status_code=200)
            resp = fn(client, GENERIC_URL, HEADERS)
            mock_curl.assert_called_once()
        assert resp.status_code == 200

    def test_401_generic_url_triggers_fallback(self, http_client_impl):
        """URL générique en 401 → déclenche désormais le fallback curl_cffi."""
        client = _make_client_returning(401)
        fn = http_client_impl["fetch_with_fallback"]

        with patch(http_client_impl["curl_get_path"]) as mock_curl:
            mock_curl.return_value = MagicMock(status_code=200)
            resp = fn(client, GENERIC_URL, HEADERS)
            mock_curl.assert_called_once()
        assert resp.status_code == 200

    def test_403_nike_triggers_curl(self, http_client_impl):
        """Nike est désormais un hard-target → déclenche curl_cffi."""
        client = _make_client_returning(403, url=NIKE_URL)
        fn = http_client_impl["fetch_with_fallback"]

        mock_curl_resp = MagicMock()
        mock_curl_resp.status_code = 200

        with patch(http_client_impl["curl_get_path"], return_value=mock_curl_resp):
            resp = fn(client, NIKE_URL, HEADERS)

        assert resp.status_code == 200

    # ── Cas fallback curl_cffi déclenché ─────────────────────────────────────

    def test_403_decathlon_triggers_curl(self, http_client_impl):
        client = _make_client_returning(403, url=DECATHLON_URL)
        fn = http_client_impl["fetch_with_fallback"]

        mock_curl_resp = MagicMock()
        mock_curl_resp.status_code = 200

        with patch(http_client_impl["curl_get_path"], return_value=mock_curl_resp):
            resp = fn(client, DECATHLON_URL, HEADERS)

        assert resp.status_code == 200

    def test_401_decathlon_triggers_curl(self, http_client_impl):
        client = _make_client_returning(401, url=DECATHLON_URL)
        fn = http_client_impl["fetch_with_fallback"]

        mock_curl_resp = MagicMock()
        mock_curl_resp.status_code = 200

        with patch(http_client_impl["curl_get_path"], return_value=mock_curl_resp):
            resp = fn(client, DECATHLON_URL, HEADERS)

        assert resp.status_code == 200

    def test_403_alltricks_triggers_curl(self, http_client_impl):
        client = _make_client_returning(403, url=ALLTRICKS_URL)
        fn = http_client_impl["fetch_with_fallback"]

        mock_curl_resp = MagicMock()
        mock_curl_resp.status_code = 200

        with patch(http_client_impl["curl_get_path"], return_value=mock_curl_resp):
            resp = fn(client, ALLTRICKS_URL, HEADERS)

        assert resp.status_code == 200

    def test_curl_called_with_correct_args(self, http_client_impl):
        """curl_cffi doit être appelé avec impersonate='chrome' et timeout=30."""
        client = _make_client_returning(403, url=DECATHLON_URL)
        fn = http_client_impl["fetch_with_fallback"]

        with patch(http_client_impl["curl_get_path"]) as mock_curl:
            mock_curl.return_value = MagicMock(status_code=200)
            fn(client, DECATHLON_URL, HEADERS)

        mock_curl.assert_called_once_with(
            DECATHLON_URL,
            headers=HEADERS,
            impersonate="chrome",
            timeout=30,
        )

    # ── Cas d'erreur curl_cffi ────────────────────────────────────────────────

    def test_curl_exception_returns_original_response(self, http_client_impl):
        """Si curl_cffi lève une exception, la réponse originale (403) est retournée."""
        client = _make_client_returning(403, url=DECATHLON_URL)
        fn = http_client_impl["fetch_with_fallback"]

        with patch(http_client_impl["curl_get_path"], side_effect=Exception("timeout")):
            resp = fn(client, DECATHLON_URL, HEADERS)

        assert resp.status_code == 403

    def test_curl_import_error_returns_original_response(self, http_client_impl):
        """Simule curl_cffi non installé → import échoue → réponse originale."""
        client = _make_client_returning(403, url=DECATHLON_URL)
        fn = http_client_impl["fetch_with_fallback"]

        # Retire temporairement curl_cffi du cache des modules
        saved = sys.modules.pop("curl_cffi", None)
        saved_requests = sys.modules.pop("curl_cffi.requests", None)
        try:
            sys.modules["curl_cffi"] = None  # type: ignore
            resp = fn(client, DECATHLON_URL, HEADERS)
        finally:
            if saved is not None:
                sys.modules["curl_cffi"] = saved
            else:
                sys.modules.pop("curl_cffi", None)
            if saved_requests is not None:
                sys.modules["curl_cffi.requests"] = saved_requests
            else:
                sys.modules.pop("curl_cffi.requests", None)

        assert resp.status_code == 403
