import pytest
from wetall_scanner.scanner.database import DatabaseManager
from wetall_scanner.scanner.http_client import HTTPClient
from wetall_scanner.scanner.orchestrator import ScannerOrchestrator

@pytest.mark.smoke
def test_full_workflow_smoke():
    """
    Smoke Test : Validation de la chaîne complète (E2E).
    """
    db = DatabaseManager()
    http = HTTPClient()
    orchestrator = ScannerOrchestrator(db, http)
    
    # 1. Récupération
    products = db.get_products_to_scan(limit=1)
    
    if not products:
        pytest.skip("Aucun produit actif en base pour le smoke test.")
        
    product = products[0]
    
    # 2. Exécution du cycle complet
    # On s'assure que results est traité comme une liste
    results = orchestrator.run_scan(vendor=product['nom_vendeur'])
    
    # 3. Assertions robustes pour Pylance
    assert results is not None, "Le scan a retourné None"
    assert isinstance(results, list), "Le résultat devrait être une liste"
    assert len(results) > 0, "Le scan n'a retourné aucun résultat"
    assert 'status' in results[0], "Le résultat ne contient pas de statut"
    
    print(f"Smoke test réussi pour le produit {product['produit_id']}")