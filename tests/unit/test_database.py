import pytest
import json
from unittest.mock import patch
import logging
from wetall_scanner.scanner.database import DatabaseManager


class TestDatabaseManager:
    @patch("wetall_scanner.scanner.database.psycopg2.connect")
    def test_init_raises_error_if_no_url(self, mock_connect):
        """Vérifie que le manager râle si DATABASE_URL manque."""
        with patch.dict("os.environ", {"DATABASE_URL": ""}):
            with pytest.raises(ValueError, match="DATABASE_URL est absente"):
                DatabaseManager()

    @patch("wetall_scanner.scanner.database.psycopg2.connect")
    def test_get_products_to_scan_query_build(self, mock_connect):
        # Configuration des mocks AVANT l'instanciation
        mock_conn = mock_connect.return_value
        mock_cur = mock_conn.cursor.return_value.__enter__.return_value
        mock_cur.fetchall.return_value = [{"produit_id": 1}]

        with patch.dict("os.environ", {"DATABASE_URL": "postgresql://test"}):
            db = DatabaseManager()
            db.get_products_to_monitor(vendor="amazon", limit=5)

            assert mock_cur.execute.called

    @patch("wetall_scanner.scanner.database.psycopg2.connect")
    def test_save_scan_result_atomic_operation(self, mock_connect, caplog):
        """Vérifie l'insertion simultanée dans les tables Fact et Dim."""
        mock_conn = mock_connect.return_value
        mock_cur = mock_conn.cursor.return_value.__enter__.return_value

        with patch.dict("os.environ", {"DATABASE_URL": "postgresql://test"}):
            db = DatabaseManager()
            with caplog.at_level(logging.INFO):
                db.save_scan_result(
                    product_id=10,
                    status_code="Hors Stock",
                    http_code=200,
                    url_finale="http://final.com",
                    debug_info="Test log",
                )

        # 1. Vérification des appels SQL
        assert mock_cur.execute.call_count == 2

        # 2. Vérification de la structure du log JSONB (2ème appel)
        calls = mock_cur.execute.call_args_list
        dim_query_args = calls[1][0][1]  # Arguments du UPDATE dim_produit
        history_json = dim_query_args[1]  # Le 2ème paramètre est status_history

        data = json.loads(history_json)

        assert isinstance(data, dict), (
            f"Le JSON doit être un dictionnaire, reçu : {type(data)}"
        )
        assert data["status"] == "Hors Stock", (
            f"Statut attendu 'Hors Stock', reçu : {data['status']}"
        )
        assert "timestamp" in data, "Le timestamp devrait être présent dans le JSON"
        assert "Résultat sauvegardé" in caplog.text
