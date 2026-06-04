import pytest
import logging
from wetall_scanner.scanner.database import DatabaseManager
from wetall_scanner.scanner.http_client import HTTPClient
from wetall_scanner.scanner.orchestrator import ScannerOrchestrator

@pytest.fixture
def components():
    db = DatabaseManager()
    http = HTTPClient()
    orchestrator = ScannerOrchestrator(db, http)
    return db, http, orchestrator

@pytest.mark.smoke
def test_smoke_link_discovery(components):
    """Vérifie que le système peut transformer un lien Wetall en lien Marchand."""
    db, _, orchestrator = components
    
    # 1. On cherche un produit qui n'a pas encore d'URL finale
    products = db.get_products_to_discover(limit=1)
    if not products:
        pytest.skip("Aucun produit à découvrir en base.")
    
    p_id = products[0]['produit_id']
    old_url = products[0].get('url_marchand_finale')
    
    # 2. Exécution du discovery
    orchestrator.run_link_discovery(limit=1)
    
    # 3. Vérification : l'URL finale doit maintenant être remplie en base
    # On recharge le produit depuis la base pour vérifier l'update
    updated_products = db.get_products_to_monitor(limit=100) # On cherche notre ID dedans
    updated_p = next((p for p in updated_products if p['produit_id'] == p_id), None)
    
    assert updated_p is not None, f"Le produit {p_id} devrait maintenant avoir une URL marchande"
    assert updated_p['url_marchand_finale'].startswith("http")
    assert "wetall.fr" not in updated_p['url_marchand_finale']

@pytest.mark.smoke
def test_smoke_stock_monitoring(components):
    """Vérifie que le système peut scanner le stock sur une URL marchande connue."""
    db, _, orchestrator = components
    
    # 1. On cherche un produit déjà prêt (URL marchande présente)
    products = db.get_products_to_monitor(limit=1)
    if not products:
        pytest.skip("Aucun produit prêt pour le monitoring en base.")
    
    # 2. Exécution du scan de stock
    results = orchestrator.run_stock_monitoring(limit=1)
    
    # 3. Assertions
    assert len(results) > 0
    # Dans test_smoke_stock_monitoring
    assert results[0]['status'] in ["EN_STOCK", "HORS_STOCK", "ERREUR_TECHNIQUE", "A_VERIFIER"]