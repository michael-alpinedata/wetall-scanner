import pytest
from unittest.mock import MagicMock, patch
from wetall_scanner.scanner.orchestrator import ScannerOrchestrator
from wetall_scanner.scanner.database import DatabaseManager
from wetall_scanner.scanner.http_client import HTTPClient
from wetall_scanner.scanner.extractor import WetallExtractor

# Nouveaux imports propres
from wetall_scanner.scanner.constants import ScanResult
from wetall_scanner.scanner.strategies.factory import ScannerFactory
from wetall_scanner.scanner.strategies.amazon import AmazonScanner
from wetall_scanner.scanner.strategies.generic import GenericScanner


class TestScannerOrchestrator:
    """
    Tests unitaires de l'orchestrateur.
    Valide la logique métier sans aucune connexion réseau ou base de données.
    """

    @pytest.fixture
    def orch(self):
        mock_db = MagicMock(spec=DatabaseManager)
        mock_http = MagicMock(spec=HTTPClient)
        mock_extractor = MagicMock(spec=WetallExtractor)

        with patch("wetall_scanner.scanner.database.psycopg2.connect"):
            return ScannerOrchestrator(
                db=mock_db, http=mock_http, extractor=mock_extractor
            )

    def test_factory_selection_logic(self):
        """Vérifie que la Factory distribue le bon scanner selon le nom du vendeur."""
        assert isinstance(ScannerFactory.get_scanner("Amazon"), AmazonScanner)
        assert isinstance(ScannerFactory.get_scanner("amazon"), AmazonScanner)
        assert isinstance(ScannerFactory.get_scanner("Inconnu"), GenericScanner)
        assert isinstance(ScannerFactory.get_scanner(None), GenericScanner)

    # --- TESTS DU WORKFLOW 1 : DISCOVERY ---

    def test_run_link_discovery_success(self, orch):
        target_id = 10
        orch.db.get_products_to_discover.return_value = [
            {"produit_id": target_id, "url_wetall": "https://wetall.fr/p/10"}
        ]

        orch.http.fetch.return_value = {
            "status_code": 200,
            "url_finale": "https://www.amazon.fr/dp/B000XYZ",
            "html": "<html>...</html>",
            "error": None,
        }

        orch.extractor.extract_merchant_name.return_value = "amazon"

        orch.run_link_discovery(limit=1, product_id=target_id)

        orch.db.update_product_discovery_results.assert_called_once_with(
            target_id, "https://www.amazon.fr/dp/B000XYZ", "amazon"
        )
        orch.db.get_products_to_discover.assert_called_once_with(
            limit=1, product_id=target_id
        )

    def test_run_link_discovery_failure_stays_on_wetall(self, orch):
        orch.db.get_products_to_discover.return_value = [
            {"produit_id": 11, "url_wetall": "https://wetall.fr/p/11"}
        ]

        orch.http.fetch.return_value = {
            "status_code": 200,
            "url_finale": "https://wetall.fr/p/11",
            "html": "<html>...</html>",
            "error": None,
        }

        orch.run_link_discovery(limit=1)
        orch.db.update_product_discovery_results.assert_not_called()

    # --- TESTS DU WORKFLOW 2 : MONITORING ---

    def test_run_stock_monitoring_handles_404(self, orch):
        orch.db.get_products_to_monitor.return_value = [
            {
                "produit_id": 1,
                "url_marchand_finale": "http://amazon.fr/p1",
                "nom_vendeur": "amazon",
            }
        ]

        orch.http.fetch_stealth.return_value = {
            "html": "",
            "status_code": 404,
            "url_finale": "http://amazon.fr/p1",
            "error": None,
        }

        orch.run_stock_monitoring(limit=1)

        _, kwargs = orch.db.save_scan_result.call_args

        # Mise à jour de l'assertion pour matcher l'objet Enum et sa propriété "code"
        assert kwargs["status_code"] == ScanResult.PAGE_404.code
        assert ScanResult.PAGE_404.message in kwargs["debug_info"]

    def test_run_stock_monitoring_full_flow_success(self, orch):
        orch.db.get_products_to_monitor.return_value = [
            {
                "produit_id": 99,
                "url_marchand_finale": "http://amazon.fr/99",
                "nom_vendeur": "amazon",
            }
        ]

        padding = " " * 1100
        html_content = f'<html><body><h1 id="productTitle">Mon Produit</h1><div id="add-to-cart-button"></div>{padding}</body></html>'

        orch.http.fetch_stealth.return_value = {
            "html": html_content,
            "status_code": 200,
            "url_finale": "http://amazon.fr/99",
            "error": None,
        }

        orch.run_stock_monitoring(limit=1)

        orch.db.save_scan_result.assert_called_once()
        _, kwargs = orch.db.save_scan_result.call_args

        assert kwargs["product_id"] == 99
        # Mise à jour ici aussi pour utiliser .code au lieu de .value (qui retournait un tuple complet)
        assert kwargs["status_code"] == ScanResult.EN_STOCK.code
