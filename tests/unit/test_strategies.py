import pytest
import logging
from wetall_scanner.scanner.strategies import AmazonScanner
from wetall_scanner.scanner.constants import ScanStatus, MSG_BUY_BUTTON, MSG_OUT_OF_STOCK
from wetall_scanner.scanner.config import MERCHANT_CONFIGS

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
        html = f'<html><body><div id="add-to-cart-button">Ajouter au panier</div>{PADDING}</body></html>'
        with caplog.at_level(logging.INFO):
            status, info = scanner.analyze(html)
        assert status == ScanStatus.EN_STOCK.value
        assert info == MSG_BUY_BUTTON
        assert MSG_BUY_BUTTON in caplog.text

    def test_analyze_buy_now_present(self, scanner, caplog):
        """Vérifie la détection via le bouton d'achat immédiat."""
        html = f'<html><body><input id="buy-now-button" value="Acheter"/>{PADDING}</body></html>'
        with caplog.at_level(logging.INFO):
            status, info = scanner.analyze(html)
        assert status == ScanStatus.EN_STOCK.value
        assert info == MSG_BUY_BUTTON
        assert MSG_BUY_BUTTON in caplog.text

    def test_analyze_out_of_stock(self, scanner, caplog):
        """Vérifie la détection explicite de rupture de stock via l'ID outOfStock."""
        html = f'<html><body><div id="availability">Actuellement indisponible</div>{PADDING}</body></html>'
        with caplog.at_level(logging.INFO):
            status, info = scanner.analyze(html)
        assert status == ScanStatus.HORS_STOCK.value
        assert info == MSG_OUT_OF_STOCK
        assert MSG_OUT_OF_STOCK in caplog.text

    def test_analyze_empty_html(self, scanner, caplog):
        """Vérifie le comportement face à un contenu vide (Erreur technique)."""
        with caplog.at_level(logging.ERROR):
            status, info = scanner.analyze("")
        assert status == ScanStatus.ERREUR.value
        assert "vide" in info
        assert "Contenu HTML reçu vide" in caplog.text

    def test_analyze_fallback_indisponible(self, scanner, caplog):
        """
        Vérifie la règle de sécurité (Logique 3) : si aucun ID connu n'est trouvé, 
        le produit est considéré Hors Stock par défaut.
        """
        html = f'<html><body><div>Page produit sans boutons</div>{PADDING}</body></html>'
        with caplog.at_level(logging.WARNING):
            status, info = scanner.analyze(html)
            
        expected_fallback = MERCHANT_CONFIGS["amazon"]["fallback_message"]
        assert status == ScanStatus.HORS_STOCK.value
        assert info == expected_fallback
        assert expected_fallback in caplog.text