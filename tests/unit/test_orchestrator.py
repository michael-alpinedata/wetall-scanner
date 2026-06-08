import pytest
from unittest.mock import MagicMock, patch
from wetall_scanner.scanner.orchestrator import ScannerOrchestrator
from wetall_scanner.scanner.database import DatabaseManager
from wetall_scanner.scanner.http_client import HTTPClient
from wetall_scanner.scanner.extractor import WetallExtractor

from wetall_scanner.scanner.strategies import ScanStatus, MSG_PAGE_404


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
        mock_extractor = MagicMock(spec=WetallExtractor)

        # Le patch évite que psycopg2 ne tente de se connecter pendant l'init
        with patch("wetall_scanner.scanner.database.psycopg2.connect"):
            return ScannerOrchestrator(
                db=mock_db, http=mock_http, extractor=mock_extractor
            )

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
        # 1. On injecte le ID spécifique
        target_id = 10

        # 2. On configure le mock pour ne retourner QUE ce produit
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

        # 3. On appelle le run en passant le product_id
        orch.run_link_discovery(limit=1, product_id=target_id)

        # 4. On vérifie que la DB a bien reçu la mise à jour pour CE produit
        orch.db.update_product_discovery_results.assert_called_once_with(
            target_id, "https://www.amazon.fr/dp/B000XYZ", "amazon"
        )

        # 5. On vérifie que le mock de DB a bien été appelé avec le bon filtre
        orch.db.get_products_to_discover.assert_called_once_with(
            limit=1, product_id=target_id
        )

    def test_run_link_discovery_failure_stays_on_wetall(self, orch):
        """Vérifie qu'on n'update pas la DB si le lien reste sur Wetall."""
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

        # L'appel combiné ne doit PAS être déclenché
        orch.db.update_product_discovery_results.assert_not_called()

    # --- TESTS DU WORKFLOW 2 : MONITORING ---

    def test_run_stock_monitoring_handles_404(self, orch):
        """Vérifie que les 404 sont gérées via ScanStatus.ERREUR."""
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

        orch.http.fetch_stealth.return_value = {
            "html": "",
            "status_code": 404,
            "url_finale": "http://amazon.fr/p1",
            "error": None,
        }

        orch.run_stock_monitoring(limit=1)

        # Vérification avec les constantes/Enums
        _, kwargs = orch.db.save_scan_result.call_args

        # On vérifie l'enum de statut
        assert kwargs["status_code"] == ScanStatus.ERREUR.value

        # On vérifie que le message est bien la constante MSG_PAGE_404
        # (Assure-toi que ton orchestrateur passe le message dans debug_info ou un champ similaire)
        assert MSG_PAGE_404 in kwargs["debug_info"]

    def test_run_stock_monitoring_full_flow_success(self, orch):
        orch.db.get_products_to_monitor.return_value = [
            {
                "produit_id": 99,
                "url_marchand_finale": "http://amazon.fr/99",
                "nom_vendeur": "amazon",
            }
        ]

        padding = " " * 1100
        # FIX : Ajout de <h1 id="productTitle"> pour satisfaire le validateur du scanner
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
        # Maintenant, le scanner trouvera le bouton ET le titre -> EN_STOCK
        assert kwargs["status_code"] == ScanStatus.EN_STOCK.value
