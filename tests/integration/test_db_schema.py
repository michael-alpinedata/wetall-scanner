import pytest
from wetall_scanner.scanner.database import DatabaseManager

@pytest.fixture(scope="module")
def db():
    # Instanciation du manager pointant sur ta BDD de test
    manager = DatabaseManager()
    return manager

def test_insert_product_and_status(db):
    # 1. Nettoyage préventif (Optionnel)
    # 2. Insertion réelle d'un produit
    # 3. Insertion réelle d'un scan
    # 4. Vérification via SELECT count(*)
    pass