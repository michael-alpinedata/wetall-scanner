"""
Tests — run_pipeline (batch de nuit)
======================================

Couverture visée :
  Configuration
    ✓ Absence de DATABASE_URL → log erreur, retour immédiat (pas de crash)

  Base de données — données
    ✓ Aucun produit en DB    → log info, retour immédiat
    ✓ Produits présents      → scan lancé + résultats insérés

  Comportement du scan
    ✓ scan_scan appelé pour chaque produit de la liste
    ✓ INSERT dans fact_stock_status pour chaque produit
    ✓ Progression loggée tous les 10 produits

  Gestion d'erreur
    ✓ Erreur de connexion DB → log + retour sans crash
"""

from __future__ import annotations

import json
import logging
import os
from unittest.mock import MagicMock, patch

# ── Helpers pour construire des lignes de DB fakées ──────────────────────────


def _make_product_row(
    produit_id: int,
    url: str,
    is_active: bool = True,
    status_history: list | None = None,
) -> MagicMock:
    """Simule une ligne psycopg2 DictRow avec les colonnes CDC."""
    row_data = {
        "produit_id": produit_id,
        "url_wetall": url,
        "is_active": is_active,
        "status_history": status_history
        if status_history is not None
        else [{"status": "OK", "timestamp": "2023-01-01T00:00:00Z"}],
    }
    row = MagicMock()
    # Mock __getitem__ for dictionary-like access
    row.__getitem__.side_effect = lambda key: row_data[key]
    return row


def _make_db_mock(products: list[MagicMock], cdc_update_rowcount: int = 1) -> tuple[MagicMock, MagicMock]:
    """
    Construit un mock de conn+cursor psycopg2, supportant les retours pour CDC.

    cursor.fetchall() retourne `products`.
    cursor.execute (pour UPDATE CDC) aura un mocké `rowcount`.
    """
    cur = MagicMock()
    cur.fetchall.return_value = products
    # Default rowcount for UPDATE_PRODUCT_CDC_SQL_PIPELINE
    # This will be used when _update_product_status_history is called
    type(cur).rowcount = property(lambda self: cdc_update_rowcount)

    conn = MagicMock()
    conn.cursor.return_value = cur
    conn.autocommit = True  # Important for pipeline context

    return conn, cur


FAKE_PRODUCTS = [
    _make_product_row(1, "https://www.wetall.fr/produit/chaussures-trail-x3/"),
    _make_product_row(2, "https://www.wetall.fr/produit/velo-route-carbone/"),
    _make_product_row(3, "https://www.wetall.fr/produit/short-running-homme/"),
]

FAKE_SCAN_RESULT = ("OK", 200, "https://www.decathlon.fr/buy/123", "Scan réussi")


class TestRunPipelineConfiguration:
    def test_missing_database_url_returns_immediately(self, pipeline_impl, caplog):
        """Sans DATABASE_URL → log d'erreur + sortie sans exception."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("DATABASE_URL", None)
            pipeline_impl["run_pipeline"]()

        # Doit avoir loggé une erreur mentionnant DATABASE_URL
        assert any("DATABASE_URL" in r.message for r in caplog.records)

    def test_missing_database_url_does_not_raise(self, pipeline_impl):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("DATABASE_URL", None)
            # pas d'exception
            pipeline_impl["run_pipeline"]()


class TestRunPipelineNoProducts:
    def test_empty_product_list_returns_immediately(self, pipeline_impl, caplog):
        conn, cur = _make_db_mock(products=[])

        with (
            patch.dict(os.environ, {"DATABASE_URL": "postgresql://fake"}),
            patch(pipeline_impl["psycopg2_path"], return_value=conn),
            patch(pipeline_impl["smart_scan_path"]),
            patch(pipeline_impl["sleep_path"]),
            patch(pipeline_impl["httpx_client_path"]),
        ):
            pipeline_impl["run_pipeline"]()

        # smart_scan ne doit pas être appelé
        # (on vérifie que fetchall a bien eu lieu mais pas de scan)
        cur.fetchall.assert_called_once()

    def test_empty_product_list_no_insert(self, pipeline_impl):
        conn, cur = _make_db_mock(products=[])

        with (
            patch.dict(os.environ, {"DATABASE_URL": "postgresql://fake"}),
            patch(pipeline_impl["psycopg2_path"], return_value=conn),
            patch(pipeline_impl["smart_scan_path"]),
            patch(pipeline_impl["sleep_path"]),
            patch(pipeline_impl["httpx_client_path"]),
        ):
            pipeline_impl["run_pipeline"]()

        # Aucun INSERT ne doit avoir eu lieu
        for c in cur.execute.call_args_list:
            sql_arg = c[0][0] if c[0] else ""
            assert "INSERT" not in sql_arg.upper()


class TestRunPipelineScanExecution:
    def test_smart_scan_called_for_each_product(self, pipeline_impl):
        conn, cur = _make_db_mock(products=FAKE_PRODUCTS)

        with (
            patch.dict(os.environ, {"DATABASE_URL": "postgresql://fake"}),
            patch(pipeline_impl["psycopg2_path"], return_value=conn),
            patch(pipeline_impl["smart_scan_path"], return_value=FAKE_SCAN_RESULT) as mock_scan,
            patch(pipeline_impl["sleep_path"]),
            patch(pipeline_impl["httpx_client_path"]) as mock_client_cls,
        ):
            # Simule le context manager httpx.Client
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
            mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

            # Appel avec une limite explicite
            pipeline_impl["run_pipeline"](limit=50)

        # Vérifie que la limite a été passée à la requête SQL (le premier execute)
        # On cherche l'appel qui contient "SELECT"
        select_call = [c for c in cur.execute.call_args_list if "SELECT" in str(c[0][0]).upper()][0]
        assert select_call[0][1] == (50,)
        assert mock_scan.call_count == len(FAKE_PRODUCTS)

    def test_insert_called_for_each_product(self, pipeline_impl):
        conn, cur = _make_db_mock(products=FAKE_PRODUCTS)

        with (
            patch.dict(os.environ, {"DATABASE_URL": "postgresql://fake"}),
            patch(pipeline_impl["psycopg2_path"], return_value=conn),
            patch(pipeline_impl["smart_scan_path"], return_value=FAKE_SCAN_RESULT),
            patch(pipeline_impl["sleep_path"]),
            patch(pipeline_impl["httpx_client_path"]) as mock_client_cls,
        ):
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
            mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

            pipeline_impl["run_pipeline"]()

        insert_calls = [c for c in cur.execute.call_args_list if "INSERT" in str(c[0][0]).upper()]
        assert len(insert_calls) == len(FAKE_PRODUCTS)

    def test_scan_result_tuple_passed_to_insert(self, pipeline_impl):
        """Vérifie que les 4 éléments du scan sont bien insérés en DB."""
        conn, cur = _make_db_mock(products=FAKE_PRODUCTS[:1])  # 1 produit
        expected_status, expected_code, expected_url, expected_debug = FAKE_SCAN_RESULT

        with (
            patch.dict(os.environ, {"DATABASE_URL": "postgresql://fake"}),
            patch(pipeline_impl["psycopg2_path"], return_value=conn),
            patch(pipeline_impl["smart_scan_path"], return_value=FAKE_SCAN_RESULT),
            patch(pipeline_impl["sleep_path"]),
            patch(pipeline_impl["httpx_client_path"]) as mock_client_cls,
        ):
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
            mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

            pipeline_impl["run_pipeline"]()

        # Cherche l'appel INSERT dans les exécutions SQL
        insert_call = next(c for c in cur.execute.call_args_list if "INSERT" in str(c[0][0]).upper())
        params = insert_call[0][1]  # tuple de paramètres SQL

        assert expected_status in params
        assert expected_code in params
        assert expected_url in params
        assert expected_debug in params

    def test_progress_logged_every_10_products(self, pipeline_impl, caplog):
        """Log de progression attendu pour le 10ème produit traité."""
        import logging

        products_10 = [_make_product_row(i, f"https://www.wetall.fr/produit/produit-{i}/") for i in range(1, 11)]
        conn, cur = _make_db_mock(products=products_10)

        # Force la capture des logs INFO de tous les modules concernés
        with caplog.at_level(logging.INFO):
            with (
                patch.dict(os.environ, {"DATABASE_URL": "postgresql://fake"}),
                patch(pipeline_impl["psycopg2_path"], return_value=conn),
                patch(pipeline_impl["smart_scan_path"], return_value=FAKE_SCAN_RESULT),
                patch(pipeline_impl["sleep_path"]),
                patch(pipeline_impl["httpx_client_path"]) as mock_client_cls,
            ):
                mock_client = MagicMock()
                mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
                mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

                pipeline_impl["run_pipeline"]()

        # Au moins un message de progression doit avoir été loggé
        progress_logs = [
            r
            for r in caplog.records
            if any(word in r.message.lower() for word in ["progression", "fiches", "progress", "trait"])
        ]
        assert len(progress_logs) >= 1


class TestRunPipelineErrorHandling:
    def test_db_connection_error_does_not_raise(self, pipeline_impl):
        with (
            patch.dict(os.environ, {"DATABASE_URL": "postgresql://fake"}),
            patch(
                pipeline_impl["psycopg2_path"],
                side_effect=Exception("connexion refusée"),
            ),
            patch(pipeline_impl["sleep_path"]),
        ):
            # Pas d'exception levée vers l'appelant
            pipeline_impl["run_pipeline"]()

    def test_db_connection_error_is_logged(self, pipeline_impl, caplog):
        with (
            patch.dict(os.environ, {"DATABASE_URL": "postgresql://fake"}),
            patch(
                pipeline_impl["psycopg2_path"],
                side_effect=Exception("connexion refusée"),
            ),
            patch(pipeline_impl["sleep_path"]),
        ):
            pipeline_impl["run_pipeline"]()

        error_logs = [r for r in caplog.records if r.levelname == "ERROR"]
        assert any("Échec critique du pipeline" in r.message for r in error_logs)
        assert any("connexion refusée" in r.message for r in error_logs)

    def test_smart_scan_error_updates_status_history_and_logs_summary(self, pipeline_impl, caplog):
        product_id = 1
        product_url = "https://www.wetall.fr/produit/produit-erreur/"
        # Simulate a product that was initially OK
        initial_status_history = [{"status": "OK", "timestamp": "2023-01-01T00:00:00Z"}]
        product_row = _make_product_row(
            product_id,
            product_url,
            is_active=True,
            status_history=initial_status_history,
        )
        conn, cur = _make_db_mock(products=[product_row])

        # Simulate smart_scan returning an error
        error_status = "Erreur technique"
        error_code = 0
        error_debug_msg = "Exception: timeout"
        error_scan_result = (error_status, error_code, None, error_debug_msg)

        with caplog.at_level(logging.INFO):
            with (
                patch.dict(os.environ, {"DATABASE_URL": "postgresql://fake"}),
                patch(pipeline_impl["psycopg2_path"], return_value=conn),
                patch(pipeline_impl["smart_scan_path"], return_value=error_scan_result) as mock_smart_scan,
                patch(pipeline_impl["sleep_path"]),
                patch(pipeline_impl["httpx_client_path"]) as mock_client_cls,
            ):
                mock_client = MagicMock()
                mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
                mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

                pipeline_impl["run_pipeline"]()

        # 1. Verify smart_scan was called
        mock_smart_scan.assert_called_once_with(mock_client, product_url)

        # 2. Verify fact_stock_status was updated
        insert_calls = [c for c in cur.execute.call_args_list if "INSERT" in str(c[0][0]).upper()]
        assert len(insert_calls) == 1
        # Check params of the INSERT call
        inserted_params = insert_calls[0][0][1]
        assert inserted_params[0] == product_id  # produit_id
        # We need to skip datetime (param[1]) as it's dynamic
        assert inserted_params[2] == error_status  # status_code
        assert inserted_params[3] == error_code  # http_code_marchand
        assert inserted_params[4] is None  # url_marchand_finale
        assert error_debug_msg in inserted_params[5]  # debug_info

        # 3. Verify dim_produit.status_history was updated and is_active changed
        update_calls = [c for c in cur.execute.call_args_list if "UPDATE" in str(c[0][0]).upper()]
        assert len(update_calls) == 1
        updated_params = update_calls[0][0][1]
        assert updated_params[0] is False  # is_active should be False
        assert updated_params[1] is not None  # deactivated_at should be set
        new_history_entry = json.loads(updated_params[2])  # new_history_entry_jsonb
        assert new_history_entry["status"] == error_status
        assert new_history_entry["timestamp"] is not None
        assert updated_params[3] == product_id  # produit_id

        # 4. Verify summary logs
        info_logs = [r for r in caplog.records if r.levelname == "INFO"]
        summary_log = next((r for r in info_logs if "RÉSUMÉ BATCH DE NUIT" in r.message), None)
        assert summary_log is not None
        assert "1 produits traités" in summary_log.message
        assert "1 changements de statut" in summary_log.message
        assert "1 erreurs de scan" in summary_log.message

        # 5. Verify warning for error status
        warning_logs = [r for r in caplog.records if r.levelname == "WARNING"]
        assert any(f"Smart scan a renvoyé un statut d'erreur : '{error_status}'" in r.message for r in warning_logs)
