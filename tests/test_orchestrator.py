import pytest
from unittest.mock import MagicMock, patch
from src.scanner.orchestrator import ScannerOrchestrator

class TestScannerOrchestrator:
    @pytest.fixture
    def orch(self):
        with patch("src.scanner.database.psycopg2.connect"):
            return ScannerOrchestrator()

    def test_strategy_selection_logic(self, orch):
        """Vérifie que l'orchestrateur choisit le bon 'cerveau' selon le marchand."""
        from src.scanner.strategies import AmazonScanner, GenericScanner
        
        assert isinstance(orch._get_strategy("Amazon"), AmazonScanner)
        assert isinstance(orch._get_strategy("Inconnu"), GenericScanner)
        assert isinstance(orch._get_strategy(None), GenericScanner)

    def test_run_scan_handles_404_explicitly(self, orch):
        """Vérifie que les 404 sont transformés en statut 'Lien Brisé'."""
        # Simulation d'un produit en attente
        orch.db.get_products_to_scan = MagicMock(return_value=[
            {'produit_id': 1, 'url_wetall': 'http://w', 'nom_vendeur': 'amazon'}
        ])
        
        # Simulation d'une 404 côté HTTP
        orch.http.fetch = MagicMock(return_value={
            'html': '', 'status_code': 404, 'url_finale': 'http://w', 'error': None
        })
        
        orch.db.save_scan_result = MagicMock()
        orch.run_scan(limit=1)

        # Vérification de la décision finale
        args, kwargs = orch.db.save_scan_result.call_args
        assert kwargs['status_code'] == "Lien Brisé"
        assert "404" in kwargs['debug_info']

    def test_run_scan_full_flow_success(self, orch, caplog):
        """Test du chemin nominal (Happy Path)."""
        orch.db.get_products_to_scan = MagicMock(return_value=[
            {'produit_id': 99, 'url_wetall': 'http://w', 'nom_vendeur': 'amazon'}
        ])
        
        # Le HTML contient le bouton Amazon
        orch.http.fetch = MagicMock(return_value={
            'html': '<div id="add-to-cart-button"></div>', 
            'status_code': 200, 
            'url_finale': 'http://amazon.fr/99', 
            'error': None
        })
        
        orch.db.save_scan_result = MagicMock()
        
        import logging
        with caplog.at_level(logging.INFO):
            orch.run_scan(limit=1)

        # On vérifie que tout s'est enchaîné
        assert "Traitement du produit 99" in caplog.text
        orch.db.save_scan_result.assert_called_once()
        _, kwargs = orch.db.save_scan_result.call_args
        assert kwargs['status_code'] == "OK"