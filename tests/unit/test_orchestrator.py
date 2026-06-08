import pytest
import logging
from unittest.mock import MagicMock, patch
from wetall_scanner.scanner.orchestrator import ScannerOrchestrator
from wetall_scanner.scanner.database import DatabaseManager
from wetall_scanner.scanner.http_client import HTTPClient


class TestScannerOrchestrator:
    """
    Tests unitaires de l'orchestrateur.
    Valide la logique métier sans aucune connexion réseau ou base de données.
    """

    @pytest.fixture
    def orch(self):
        # Utilisation de 'spec' pour s'assurer qu'on n'appelle que des méthodes existantes
        mock_db = MagicMock(spec=DatabaseManager)
        mock_http = MagicMock(spec=HTTPClient)

        # Le patch évite que psycopg2 ne tente de se connecter pendant l'init
        with patch("wetall_scanner.scanner.database.psycopg2.connect"):
            return ScannerOrchestrator(db=mock_db, http=mock_http)

    def test_strategy_selection_logic(self, orch):
        """Vérifie que le bon scanner est choisi selon le nom du vendeur."""
        from wetall_scanner.scanner.strategies import AmazonScanner, GenericScanner

        assert isinstance(orch._get_strategy("Amazon"), AmazonScanner)
        assert isinstance(
            orch._get_strategy("amazon"), AmazonScanner
        )  # Test de la casse
        assert isinstance(orch._get_strategy("Inconnu"), GenericScanner)
        assert isinstance(orch._get_strategy(None), GenericScanner)

    # --- TESTS DU WORKFLOW 1 : DISCOVERY ---

    def test_run_link_discovery_success(self, orch):
        """
        Vérifie que la découverte d'un lien Wetall entraîne
        bien la mise à jour de l'URL finale en base.
        """
        # Simulation d'un produit à découvrir
        orch.db.get_products_to_discover.return_value = [
            {"produit_id": 10, "url_wetall": "https://wetall.fr/p/10"}
        ]

        # Simulation d'une redirection réussie
        orch.http.fetch.return_value = {
            "status_code": 200,
            "url_finale": "https://www.amazon.fr/dp/B000XYZ",
            "html": "<html>...</html>",
            "error": None,
        }

        orch.run_link_discovery(limit=1)

        # On vérifie que la DB a bien reçu l'ordre d'update avec l'URL finale
        orch.db.update_product_merchant_url.assert_called_once_with(
            10, "https://www.amazon.fr/dp/B000XYZ"
        )

    def test_run_link_discovery_failure_stays_on_wetall(self, orch):
        """Vérifie qu'on n'update pas la DB si le lien n'a pas été redirigé (reste sur Wetall)."""
        orch.db.get_products_to_discover.return_value = [
            {"produit_id": 11, "url_wetall": "https://wetall.fr/p/11"}
        ]

        # La redirection échoue ou renvoie sur Wetall
        orch.http.fetch.return_value = {
            "status_code": 200,
            "url_finale": "https://wetall.fr/p/11",
            "html": "<html>...</html>",
            "error": None,
        }

        orch.run_link_discovery(limit=1)

        # L'update ne doit PAS être appelé
        orch.db.update_product_merchant_url.assert_not_called()

    # --- TESTS DU WORKFLOW 2 : MONITORING ---

    def test_run_stock_monitoring_handles_404(self, orch):
        """Vérifie que les 404 sur l'URL marchande sont gérées correctement."""
        orch.db.get_products_to_monitor.return_value = [
            {
                "produit_id": 1,
                "url_marchand_finale": "http://amazon.fr/p1",
                "nom_vendeur": "amazon",
            }
        ]

        orch.http.fetch.return_value = {
            "html": "",
            "status_code": 404,
            "url_finale": "http://amazon.fr/p1",
            "error": None,
        }

        orch.run_stock_monitoring(limit=1)

        # Vérification de l'enregistrement du résultat "Lien Brisé"
        _, kwargs = orch.db.save_scan_result.call_args
        assert kwargs["status_code"] == "Lien Brisé"
        assert "404" in kwargs["debug_info"]

    def test_run_stock_monitoring_full_flow_success(self, orch, caplog):
        """Test du chemin nominal (Happy Path) pour le monitoring de stock."""
        orch.db.get_products_to_monitor.return_value = [
            {
                "produit_id": 99,
                "url_marchand_finale": "http://amazon.fr/99",
                "nom_vendeur": "amazon",
            }
        ]

        padding = " " * 1100
        orch.http.fetch.return_value = {
            "html": f'<div id="add-to-cart-button"></div>{padding}',
            "status_code": 200,
            "url_finale": "http://amazon.fr/99",
            "error": None,
        }

        with caplog.at_level(logging.INFO):
            orch.run_stock_monitoring(limit=1)

        # Assertion corrigée : on cherche ce que le code loggue vraiment
        assert "Produit 99 terminé" in caplog.text
        orch.db.save_scan_result.assert_called_once()
        _, kwargs = orch.db.save_scan_result.call_args
        assert kwargs["status_code"] == "EN_STOCK"
