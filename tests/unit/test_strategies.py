import pytest
import logging
from wetall_scanner.scanner.strategies import AmazonScanner

# Constante pour garantir que le HTML dépasse le seuil de 1000 caractères
PADDING = " " * 1000

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
        html = f'<html><body><div id="add-to-cart-button">Ajouter au panier</div>{PADDING}</body></html>'
        with caplog.at_level(logging.DEBUG):
            status, info = scanner.analyze(html)
        assert status == "EN_STOCK"
        assert "Bouton d'achat" in info
        assert "Produit en stock" in caplog.text

    def test_analyze_buy_now_present(self, scanner, caplog):
        """Vérifie la détection via le bouton d'achat immédiat."""
        html = f'<html><body><input id="buy-now-button" value="Acheter"/>{PADDING}</body></html>'
        with caplog.at_level(logging.DEBUG):
            status, info = scanner.analyze(html)
        assert status == "EN_STOCK"
        assert "Bouton d'achat" in info
        assert "buy-now" in caplog.text

    def test_analyze_out_of_stock(self, scanner, caplog):
        """Vérifie la détection explicite de rupture de stock via l'ID outOfStock."""
        html = f'<html><body><div id="availability">Actuellement indisponible</div>{PADDING}</body></html>'
        with caplog.at_level(logging.DEBUG):
            status, info = scanner.analyze(html)
        assert status == "HORS_STOCK"
        assert "Rupture" in info
        assert "rupture" in caplog.text.lower()

    def test_analyze_empty_html(self, scanner, caplog):
        """Vérifie le comportement face à un contenu vide (Erreur technique)."""
        # Ici, pas de padding volontairement pour tester la sécurité
        with caplog.at_level(logging.ERROR):
            status, info = scanner.analyze("")
        assert status == "ERREUR_TECHNIQUE"
        assert "vide" in info
        assert "Contenu" in caplog.text

    def test_analyze_fallback_indisponible(self, scanner, caplog):
        """
        Vérifie la règle de sécurité (Logique 3) : si aucun ID connu n'est trouvé, 
        le produit est considéré Hors Stock par défaut.
        """
        html = f'<html><body><div>Page produit sans boutons</div>{PADDING}</body></html>'
        with caplog.at_level(logging.INFO):
            status, info = scanner.analyze(html)
        assert status == "HORS_STOCK"
        assert "Aucun bouton" in info
        assert "règle de sécurité" in caplog.text
