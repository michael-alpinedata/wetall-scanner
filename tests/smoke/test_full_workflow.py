import pytest
from wetall_scanner.scanner.database import DatabaseManager
from wetall_scanner.scanner.http_client import HTTPClient
from wetall_scanner.scanner.orchestrator import ScannerOrchestrator

@pytest.mark.smoke
def test_full_workflow_monitoring_only():
    db = DatabaseManager()
    # On force/injecte un produit qui a déjà une URL finale pour le test
    # (ou on s'assure que get_products_to_monitor en renvoie un)
    products = db.get_products_to_monitor(limit=1)
    
    if not products:
        pytest.skip("Besoin d'un produit avec url_marchand_finale pour ce test.")
        
    orchestrator = ScannerOrchestrator(db, HTTPClient())
    results = orchestrator.run_stock_monitoring(limit=1)
    
    assert results[0]['status'] in ["EN_STOCK", "HORS_STOCK"]