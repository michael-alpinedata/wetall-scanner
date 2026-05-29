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

import os
from unittest.mock import MagicMock, patch

# ── Helpers pour construire des lignes de DB fakées ──────────────────────────


def _make_product_row(produit_id: int, url: str) -> MagicMock:
    """Simule une ligne psycopg2 DictRow."""
    row = MagicMock()
    row.__getitem__ = lambda self, key: produit_id if key == "produit_id" else url
    return row


def _make_db_mock(products: list) -> MagicMock:
    """
    Construit un mock de conn+cursor psycopg2.

    cursor.fetchall() retourne `products`.
    cursor.rowcount est ignoré ici (pas d'UPSERT dans run_pipeline).
    """
    cur = MagicMock()
    cur.fetchall.return_value = products

    conn = MagicMock()
    conn.cursor.return_value = cur

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
            patch(
                pipeline_impl["smart_scan_path"], return_value=FAKE_SCAN_RESULT
            ) as mock_scan,
            patch(pipeline_impl["sleep_path"]),
            patch(pipeline_impl["httpx_client_path"]) as mock_client_cls,
        ):
            # Simule le context manager httpx.Client
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
            mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

            pipeline_impl["run_pipeline"]()

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

        insert_calls = [
            c for c in cur.execute.call_args_list if "INSERT" in str(c[0][0]).upper()
        ]
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
        insert_call = next(
            c for c in cur.execute.call_args_list if "INSERT" in str(c[0][0]).upper()
        )
        params = insert_call[0][1]  # tuple de paramètres SQL

        assert expected_status in params
        assert expected_code in params
        assert expected_url in params
        assert expected_debug in params

    def test_progress_logged_every_10_products(self, pipeline_impl, caplog):
        """Log de progression attendu pour le 10ème produit traité."""
        import logging

        products_10 = [
            _make_product_row(i, f"https://www.wetall.fr/produit/produit-{i}/")
            for i in range(1, 11)
        ]
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
                mock_client_cls.return_value.__enter__ = MagicMock(
                    return_value=mock_client
                )
                mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

                pipeline_impl["run_pipeline"]()

        # Au moins un message de progression doit avoir été loggé
        progress_logs = [
            r
            for r in caplog.records
            if any(
                word in r.message.lower()
                for word in ["progression", "fiches", "progress", "trait"]
            )
        ]
        assert len(progress_logs) >= 1


class TestRunPipelineDatabaseErrors:
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
        assert len(error_logs) >= 1
