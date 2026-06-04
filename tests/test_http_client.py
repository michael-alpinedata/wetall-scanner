import pytest
import httpx
import respx
import logging
from src.scanner.http_client import HTTPClient

class TestHTTPClient:
    @pytest.fixture
    def client(self):
        return HTTPClient(timeout=5)

    @respx.mock
    def test_fetch_success_with_redirect(self, client, caplog):
        """Vérifie que les redirections sont suivies et l'URL finale capturée."""
        target_url = "https://wetall.fr/go/amazon-123"
        final_url = "https://www.amazon.fr/dp/B001"
        
        # Simulation d'une redirection
        respx.get(target_url).mock(return_value=httpx.Response(
            302, 
            headers={"Location": final_url}
        ))
        respx.get(final_url).mock(return_value=httpx.Response(200, text="<html>Amazon</html>"))

        with caplog.at_level(logging.INFO):
            result = client.fetch(target_url)

        assert result["status_code"] == 200
        assert result["url_finale"] == final_url
        assert "Fetch réussi" in caplog.text

    @respx.mock
    def test_fetch_handling_404(self, client, caplog):
        """Vérifie que les erreurs 404 sont remontées sans crash."""
        url = "https://www.marchand.fr/produit-mort"
        respx.get(url).mock(return_value=httpx.Response(404))

        result = client.fetch(url)
        assert result["status_code"] == 404
        assert result["error"] is None # httpx ne lève pas d'exception pour 404 par défaut

    @respx.mock
    def test_fetch_timeout_exception(self, client, caplog):
        """Vérifie la capture des timeouts de connexion."""
        url = "https://site-lent.com"
        respx.get(url).mock(side_effect=httpx.ConnectTimeout)

        with caplog.at_level(logging.WARNING):
            result = client.fetch(url)

        assert result["status_code"] == 0
        assert "Timeout de connexion" in result["error"]
        assert "Timeout de connexion atteint" in caplog.text

    def test_user_agent_rotation(self, client):
        """Vérifie qu'un User-Agent est bien présent dans les headers."""
        # On ne peut pas facilement tester l'aléatoire, mais on vérifie la présence
        with respx.mock:
            respx.get("https://t.com").mock(return_value=httpx.Response(200))
            client.fetch("https://t.com")
            
            last_request = respx.calls.last.request
            assert "User-Agent" in last_request.headers
            assert "Mozilla/5.0" in last_request.headers["User-Agent"]