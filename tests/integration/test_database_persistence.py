import pytest
import psycopg2
from wetall_scanner.scanner.database import DatabaseManager

# Fixture pour nettoyer la base après les tests
@pytest.fixture(scope="module")
def db_manager():
    manager = DatabaseManager()
    yield manager
    # Optionnel : Nettoyage ici si besoin

def test_integration_save_scan_result(db_manager):
    """
    Test d'intégration réel : 
    1. Insère un produit test dans dim_produit.
    2. Utilise save_scan_result pour mettre à jour ce produit.
    3. Vérifie l'insertion dans fact_stock_status et la MAJ du JSONB dans dim_produit.
    """
    conn = psycopg2.connect(db_manager.db_url)
    cur = conn.cursor()
    
    # 1. Setup : Insertion d'un produit de test
    test_url = "https://wetall.fr/go/test-product"
    #delete precedent test deja présent
    cur.execute("DELETE FROM dim_produit WHERE url_wetall = %s", (test_url,))
    conn.commit()

    cur.execute(
        "INSERT INTO dim_produit (url_wetall, nom_produit, nom_vendeur) VALUES (%s, %s, %s) RETURNING produit_id;",
        (test_url, "Produit Test", "amazon")
    )
    result = cur.fetchone()
    # Debug utile : si result est None, le test échoue proprement avec un message clair
    assert result is not None, "L'insertion n'a retourné aucun ID"
    product_id = result[0]
    conn.commit()

    # 2. Action : Utilisation du vrai manager
    db_manager.save_scan_result(
        product_id=product_id,
        status_code="OK",
        http_code=200,
        url_finale="https://amazon.fr/test",
        debug_info="Test intégration"
    )

    # 3. Vérification : fact_stock_status
    cur.execute("SELECT status_code FROM fact_stock_status WHERE produit_id = %s", (product_id,))
    row = cur.fetchone()
    
    # On vérifie explicitement que row n'est pas None avant d'y accéder
    assert row is not None, "La requête a retourné None"
    assert row[0] == "OK"

# 4. Vérification : Mise à jour JSONB dans dim_produit
    cur.execute("SELECT status_history FROM dim_produit WHERE produit_id = %s", (product_id,))
    row = cur.fetchone()
    
    assert row is not None, "La requête a retourné None"
    
    # Récupération de la donnée
    history = row[0]
    
    # Si psycopg2 retourne une chaîne (str) au lieu d'un dict/list, on la parse
    if isinstance(history, str):
        import json
        history = json.loads(history)
    
    # Maintenant, 'history' est obligatoirement une liste Python
    assert isinstance(history, list), f"On attendait une liste, reçu : {type(history)}"
    assert len(history) > 0, "La liste d'historique est vide"
    
    # Accès sécurisé au premier élément
    first_entry = history[0]
    assert isinstance(first_entry, dict), "L'élément dans la liste n'est pas un dictionnaire"
    assert first_entry.get("status") == "OK"