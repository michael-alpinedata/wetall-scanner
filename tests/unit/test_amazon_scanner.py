import pytest
from wetall_scanner.scanner.strategies import AmazonScanner
from wetall_scanner.scanner.constants import ScanResult

PADDING = " " * 1000


class TestAmazonScanner:
    """
    Suite de tests unitaires pour valider la logique de détection Amazon via le Template Method.
    """

    @pytest.fixture
    def scanner(self):
        return AmazonScanner()

    def test_analyze_in_stock(self, scanner):
        """Vérifie la détection positive quand le bouton d'achat standard est présent."""
        html = f'<html><body><h1 id="productTitle">Produit Test</h1><div id="add-to-cart-button">Ajouter au panier</div>{PADDING}</body></html>'
        fetch_data = {"html": html, "status_code": 200}

        result = scanner.analyze(fetch_data)

        # On vérifie directement l'objet Enum retourné
        assert result == ScanResult.EN_STOCK
        assert result.code == "EN_STOCK"

    def test_analyze_buy_now_present(self, scanner):
        html = f'<html><body><h1 id="productTitle">Test</h1><input id="buy-now-button" value="Acheter"/>{PADDING}</body></html>'
        fetch_data = {"html": html, "status_code": 200}

        result = scanner.analyze(fetch_data)

        assert result == ScanResult.EN_STOCK

    def test_analyze_out_of_stock(self, scanner):
        """Vérifie la détection explicite de rupture de stock via l'ID availability."""
        html = f'<html><body><h1 id="productTitle">Test</h1><div id="availability">Actuellement indisponible</div>{PADDING}</body></html>'
        fetch_data = {"html": html, "status_code": 200}

        result = scanner.analyze(fetch_data)

        assert result == ScanResult.HORS_STOCK

    def test_analyze_empty_html(self, scanner):
        """Vérifie le comportement face à un contenu vide (Erreur technique globale gérée par BaseScanner)."""
        fetch_data = {"html": "", "status_code": 200}

        result = scanner.analyze(fetch_data)

        assert result == ScanResult.HTML_EMPTY

    def test_analyze_fallback_indisponible(self, scanner):
        html = (
            f"<html><body>"
            f"<h1 id='productTitle'>Mon Produit de Test Fallback</h1>"
            f"<div id='availability'>Actuellement indisponible</div>"
            f"<div>Page produit sans boutons</div>"
            f"{PADDING}"
            f"</body></html>"
        )
        fetch_data = {"html": html, "status_code": 200}
        result = scanner.analyze(fetch_data)

        assert result == ScanResult.HORS_STOCK
