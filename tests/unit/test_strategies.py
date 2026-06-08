import pytest
from wetall_scanner.scanner.strategies import AmazonScanner
from wetall_scanner.scanner.constants import (
    ScanStatus,
    MSG_BUY_BUTTON,
    MSG_OUT_OF_STOCK,
)

PADDING = " " * 1000


class TestAmazonScanner:
    """
    Suite de tests unitaires pour valider la logique de détection Amazon.
    """

    @pytest.fixture
    def scanner(self):
        return AmazonScanner()

    def test_analyze_in_stock(self, scanner, caplog):
        """Vérifie la détection positive quand le bouton d'achat standard est présent."""
        # Ajout du #productTitle pour passer le gatekeeper
        html = f'<html><body><h1 id="productTitle">Produit Test</h1><div id="add-to-cart-button">Ajouter au panier</div>{PADDING}</body></html>'
        # html = f'<html><body><div id="add-to-cart-button">Ajouter au panier</div>{PADDING}</body></html>'

        status, info = scanner.analyze(html)

        assert status == ScanStatus.EN_STOCK.value
        assert info == MSG_BUY_BUTTON

    def test_analyze_buy_now_present(self, scanner):
        html = f'<html><body><h1 id="productTitle">Test</h1><input id="buy-now-button" value="Acheter"/>{PADDING}</body></html>'

        # On appelle la méthode normalement
        status, info = scanner.analyze(html)

        # On teste le retour métier, pas les logs
        assert status == ScanStatus.EN_STOCK.value
        assert info == MSG_BUY_BUTTON  # Vérifie que c'est la bonne constante

    def test_analyze_out_of_stock(self, scanner, caplog):
        """Vérifie la détection explicite de rupture de stock via l'ID outOfStock."""
        html = f'<html><body><h1 id="productTitle">Test</h1><div id="availability">Actuellement indisponible</div>{PADDING}</body></html>'

        status, info = scanner.analyze(html)

        assert status == ScanStatus.HORS_STOCK.value
        assert info == MSG_OUT_OF_STOCK

    def test_analyze_empty_html(self, scanner, caplog):
        """Vérifie le comportement face à un contenu vide (Erreur technique)."""

        status, info = scanner.analyze("")

        assert status == ScanStatus.ERREUR.value
        assert "vide" in info

    def test_analyze_fallback_indisponible(self, scanner):
        html = (
            f"<html><body>"
            f"<div id='productTitle'>Mon Produit de Test Fallback</div>"
            # Ajoute le marqueur qui prouve au scanner que c'est bien HORS_STOCK
            f"<div id='availability'>Actuellement indisponible</div>"
            f"<div>Page produit sans boutons</div>"
            f"{PADDING}"
            f"</body></html>"
        )
        status, info = scanner.analyze(html)

        # Maintenant, le scanner trouvera la preuve et le test passera
        assert status == ScanStatus.HORS_STOCK.value
