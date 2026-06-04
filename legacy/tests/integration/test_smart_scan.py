import respx
import httpx
import pytest
from legacy.src.scanner.orchestrator import smart_scan


@respx.mock
def test_integration_smart_scan_amazon_block():
    # 1. On mocke la réponse de Wetall (le point de départ)
    respx.get("https://www.wetall.fr/produit/test").mock(
        return_value=httpx.Response(
            200, text='<a href="https://amazon.fr/dp/123" class="button">Commander</a>'
        )
    )

    # 2. On mocke la réponse d'Amazon (un blocage 403)
    respx.get("https://amazon.fr/dp/123").mock(
        return_value=httpx.Response(403, text="<html><body>Bot detected</body></html>")
    )

    with httpx.Client() as client:
        # On exécute le flux complet
        status, code, final_url, debug_info = smart_scan(
            client, "https://www.wetall.fr/produit/test"
        )

        # On vérifie les assertions
        assert code == 403
        assert "Vérification bloquée" in status
        assert "ERR_HTTP_BLOCK" in debug_info
