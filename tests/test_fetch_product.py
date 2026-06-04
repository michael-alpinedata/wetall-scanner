from unittest.mock import MagicMock

from src.scanner.pipeline import _fetch_products


def test_fetch_products_queries():
    mock_cur = MagicMock()

    # Vérifie le mode discovery
    _fetch_products(mock_cur, limit=10, mode="discovery")
    sql_discovery = mock_cur.execute.call_args[0][0]
    assert "WHERE url_marchand_finale IS NULL" in sql_discovery

    # Vérifie le mode rescan
    _fetch_products(mock_cur, limit=10, mode="rescan")
    sql_rescan = mock_cur.execute.call_args[0][0]
    assert "AS url_wetall" in sql_rescan
    assert "ORDER BY RANDOM()" in sql_rescan
