import sqlite3
from unittest.mock import MagicMock

import pytest
from legacy.src.scanner.rescan_utility import update_product_status  # Adapte l'import


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
    # 1. On crée un mock de curseur qui supporte le 'with' (context manager)
    mock_cursor = MagicMock()
    mock_cursor.__enter__.return_value = mock_cursor
    mock_cursor.__exit__.return_value = None

    # 2. On force la connexion à utiliser ce curseur mocké
    db_conn.cursor.return_value = mock_cursor

    # 3. On mocke l'accès à la variable d'environnement
    monkeypatch.setattr("psycopg2.connect", lambda _: db_conn)

    # Appel de la fonction
    update_product_status(10, "OK", 200, "Scan réussi", "https://amazon.fr/dp/123")

    # Vérification que le cursor a bien été fermé
    mock_cursor.close.assert_called_once()
