import sqlite3
import pytest
from src.scanner.rescan_utility import update_product_status  # Adapte l'import


@pytest.fixture
def db_conn():
    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE fact_stock_status (
            produit_id INTEGER, 
            status_code TEXT, 
            http_code_marchand INTEGER, 
            debug_info TEXT, 
            url_marchand_finale TEXT,
            date_scan TIMESTAMP
        )
    """)
    yield conn
    conn.close()


def test_integration_update_db(db_conn, monkeypatch):
    # On mocke l'accès à la variable d'environnement DATABASE_URL
    monkeypatch.setattr("psycopg2.connect", lambda _: db_conn)

    # Appel de la fonction
    update_product_status(10, "OK", 200, "Scan réussi", "https://amazon.fr/dp/123")

    # Vérification du résultat dans la table
    cur = db_conn.cursor()
    cur.execute(
        "SELECT status_code, http_code_marchand FROM fact_stock_status WHERE produit_id = 10"
    )
    row = cur.fetchone()

    assert row[0] == "OK"
    assert row[1] == 200
