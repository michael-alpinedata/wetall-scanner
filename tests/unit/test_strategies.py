import pytest
import logging
from src.scanner.strategies import AmazonScanner

class TestAmazonScanner:
    """
    Suite de tests unitaires pour valider la logique de détection Amazon.
    Vérifie la non-régression sur les sélecteurs CSS critiques et le logging.
    """

    @pytest.fixture
    def scanner(self):
        return AmazonScanner()

    def test_analyze_in_stock(self, scanner, caplog):
        """Vérifie la détection positive quand le bouton d'achat standard est présent."""
        html = '<html><body><div id="add-to-cart-button">Ajouter au panier</div></body></html>'
        with caplog.at_level(logging.DEBUG):
            status, info = scanner.analyze(html)
        assert status == "OK"
        assert "Bouton d'achat" in info
        assert "Produit en stock" in caplog.text

    def test_analyze_buy_now_present(self, scanner, caplog):
        """Vérifie la détection via le bouton d'achat immédiat."""
        html = '<html><body><input id="buy-now-button" value="Acheter"/></body></html>'
        with caplog.at_level(logging.DEBUG):
            status, info = scanner.analyze(html)
        assert status == "OK"
        assert "Bouton d'achat" in info
        assert "buy-now" in caplog.text

    def test_analyze_out_of_stock(self, scanner, caplog):
        """Vérifie la détection explicite de rupture de stock via l'ID outOfStock."""
        html = '<html><body><div id="outOfStock">Actuellement indisponible</div></body></html>'
        with caplog.at_level(logging.DEBUG):
            status, info = scanner.analyze(html)
        assert status == "Hors Stock"
        assert "outOfStock" in info
        assert "hors stock confirmé" in caplog.text.lower()

    def test_analyze_empty_html(self, scanner, caplog):
        """Vérifie le comportement face à un contenu vide (Erreur technique)."""
        with caplog.at_level(logging.ERROR):
            status, info = scanner.analyze("")
        assert status == "Erreur technique"
        assert "vide" in info
        assert "Contenu HTML reçu vide" in caplog.text

    def test_analyze_fallback_indisponible(self, scanner, caplog):
        """
        Vérifie la règle de sécurité (Logique 3) : si aucun ID connu n'est trouvé, 
        le produit est considéré Hors Stock par défaut.
        """
        html = '<html><body><div>Page produit sans boutons</div></body></html>'
        with caplog.at_level(logging.INFO):
            status, info = scanner.analyze(html)
        assert status == "Hors Stock"
        assert "Aucun indicateur" in info
        assert "Application de la règle de sécurité" in caplog.text