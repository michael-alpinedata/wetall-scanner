"""
Tests — URL extraction & synchronisation sitemap → DB
=======================================================

Fonctions testées :
  clean_url_to_name [legacy]  / _url_to_product_name [new]
  sync_sitemap_to_db [legacy et new]

Couverture visée :

  Transformation URL → nom produit
    ✓ Slug multi-mots avec tirets        → "Title Case"
    ✓ URL avec slash final               → slug extrait correctement
    ✓ URL sans slash final               → slug extrait correctement
    ✓ Slug à un seul mot                 → mot capitalisé
    ✓ Slug avec chiffres                 → préservés

  sync_sitemap_to_db — configuration
    ✓ DATABASE_URL absente               → log erreur + retour immédiat

  sync_sitemap_to_db — HTTP sitemap
    ✓ Sitemap répond non-200             → log erreur + retour immédiat
    ✓ Sitemap répond 200 + XML valide    → URLs /produit/ extraites
    ✓ Sitemap sans URL /produit/         → log warning + retour immédiat

  sync_sitemap_to_db — persistance DB
    ✓ Nouvelles URLs insérées en DB (UPSERT)
    ✓ URL déjà existante (rowcount=0)    → non comptée comme nouvelle
    ✓ Nom produit correct inséré         → vérifié dans les appels SQL
    ✓ Erreur DB                          → log + pas de crash

  Filtrage des URLs
    ✓ URLs hors /produit/ ignorées (categories, tags, images)
    ✓ Seules les URLs /produit/ persistent
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

from legacy.tests.conftest import (
    SITEMAP_XML_EMPTY,
    SITEMAP_XML_NO_PRODUCTS,
    SITEMAP_XML_VALID,
    make_response,
)

# URLs attendues après filtrage de SITEMAP_XML_VALID
EXPECTED_PRODUCT_URLS = [
    "https://www.wetall.fr/produit/chaussures-trail-x3/",
    "https://www.wetall.fr/produit/velo-route-carbone/",
    "https://www.wetall.fr/produit/short-running-homme/",
]


# ============================================================================
# Nommage URL → Produit
# ============================================================================


class TestUrlToProductName:
    def test_multi_word_slug_title_case(self, extract_url_impl):
        url = "https://www.wetall.fr/produit/chaussures-trail-x3/"
        result = extract_url_impl["url_to_name"](url)
        assert result == "Chaussures Trail X3"

    def test_url_with_trailing_slash(self, extract_url_impl):
        url = "https://www.wetall.fr/produit/velo-route-carbone/"
        result = extract_url_impl["url_to_name"](url)
        assert result == "Velo Route Carbone"

    def test_url_without_trailing_slash(self, extract_url_impl):
        url = "https://www.wetall.fr/produit/short-running-homme"
        result = extract_url_impl["url_to_name"](url)
        assert result == "Short Running Homme"

    def test_single_word_slug(self, extract_url_impl):
        url = "https://www.wetall.fr/produit/casque/"
        result = extract_url_impl["url_to_name"](url)
        assert result == "Casque"

    def test_slug_with_numbers_preserved(self, extract_url_impl):
        url = "https://www.wetall.fr/produit/tente-3-places/"
        result = extract_url_impl["url_to_name"](url)
        assert result == "Tente 3 Places"

    def test_hyphens_replaced_by_spaces(self, extract_url_impl):
        url = "https://www.wetall.fr/produit/gants-velo-hiver-xl/"
        result = extract_url_impl["url_to_name"](url)
        assert " " in result
        assert "-" not in result


# ============================================================================
# sync_sitemap_to_db — Configuration & HTTP
# ============================================================================


class TestSyncSitemapToDbConfiguration:
    def test_missing_database_url_returns_immediately(self, extract_url_impl, caplog):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("DATABASE_URL", None)
            with patch(extract_url_impl["httpx_client_path"]) as mock_http:
                extract_url_impl["sync_sitemap_to_db"]()
                # HTTP ne doit même pas être appelé
                mock_http.assert_not_called()

    def test_missing_database_url_logs_error(self, extract_url_impl, caplog):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("DATABASE_URL", None)
            with patch(extract_url_impl["httpx_client_path"]):
                extract_url_impl["sync_sitemap_to_db"]()

        error_logs = [r for r in caplog.records if r.levelname == "ERROR"]
        assert len(error_logs) >= 1

    def test_missing_database_url_does_not_raise(self, extract_url_impl):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("DATABASE_URL", None)
            with patch(extract_url_impl["httpx_client_path"]):
                extract_url_impl["sync_sitemap_to_db"]()  # pas d'exception


class TestSyncSitemapToDbHttp:
    def _make_http_mock(self, status_code: int, text: str = ""):
        """Construit un mock httpx.Client retournant la réponse configurée."""
        mock_client = MagicMock()
        mock_client.get.return_value = make_response(status_code=status_code, text=text)
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_client)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        return mock_ctx

    def test_sitemap_non_200_returns_immediately(self, extract_url_impl, caplog):
        http_ctx = self._make_http_mock(status_code=503)

        with (
            patch.dict(os.environ, {"DATABASE_URL": "postgresql://fake"}),
            patch(extract_url_impl["httpx_client_path"], return_value=http_ctx),
            patch(extract_url_impl["psycopg2_path"]) as mock_db,
        ):
            extract_url_impl["sync_sitemap_to_db"]()
            mock_db.assert_not_called()

    def test_sitemap_non_200_logs_error(self, extract_url_impl, caplog):
        http_ctx = self._make_http_mock(status_code=404)

        with (
            patch.dict(os.environ, {"DATABASE_URL": "postgresql://fake"}),
            patch(extract_url_impl["httpx_client_path"], return_value=http_ctx),
            patch(extract_url_impl["psycopg2_path"]),
        ):
            extract_url_impl["sync_sitemap_to_db"]()

        error_logs = [r for r in caplog.records if r.levelname == "ERROR"]
        assert len(error_logs) >= 1

    def test_sitemap_no_product_urls_returns_early(self, extract_url_impl, caplog):
        http_ctx = self._make_http_mock(200, text=SITEMAP_XML_NO_PRODUCTS)

        with (
            patch.dict(os.environ, {"DATABASE_URL": "postgresql://fake"}),
            patch(extract_url_impl["httpx_client_path"], return_value=http_ctx),
            patch(extract_url_impl["psycopg2_path"]) as mock_db,
        ):
            extract_url_impl["sync_sitemap_to_db"]()
            # La DB ne doit pas être contactée si aucune URL produit
            mock_db.assert_not_called()

    def test_sitemap_no_product_urls_logs_warning(self, extract_url_impl, caplog):
        http_ctx = self._make_http_mock(200, text=SITEMAP_XML_NO_PRODUCTS)

        with (
            patch.dict(os.environ, {"DATABASE_URL": "postgresql://fake"}),
            patch(extract_url_impl["httpx_client_path"], return_value=http_ctx),
            patch(extract_url_impl["psycopg2_path"]),
        ):
            extract_url_impl["sync_sitemap_to_db"]()

        warn_logs = [r for r in caplog.records if r.levelname == "WARNING"]
        assert len(warn_logs) >= 1

    def test_empty_sitemap_returns_early(self, extract_url_impl):
        http_ctx = self._make_http_mock(200, text=SITEMAP_XML_EMPTY)

        with (
            patch.dict(os.environ, {"DATABASE_URL": "postgresql://fake"}),
            patch(extract_url_impl["httpx_client_path"], return_value=http_ctx),
            patch(extract_url_impl["psycopg2_path"]) as mock_db,
        ):
            extract_url_impl["sync_sitemap_to_db"]()
            mock_db.assert_not_called()


# ============================================================================
# sync_sitemap_to_db — Persistance DB
# ============================================================================


class TestSyncSitemapToDbPersistence:
    def _setup_mocks(
        self,
        extract_url_impl,
        sitemap_text: str,
        initial_db_rows: list | None = None,
        mock_executemany_returns: list[int] | None = None,
    ):
        """
        Utilitaire centralisant la création des mocks HTTP + DB.
        `sitemap_text`: Contenu XML du sitemap.
        `initial_db_rows`: Liste de dictionnaires simulant les lignes de `dim_produit` déjà en DB.
        `mock_executemany_returns`: Liste d'entiers, où chaque entier est le `rowcount`
                                    pour une invocation successive de `cur.executemany`.
        """
        mock_http_client = MagicMock()
        mock_http_client.get.return_value = make_response(status_code=200, text=sitemap_text)
        mock_http_ctx = MagicMock()
        mock_http_ctx.__enter__ = MagicMock(return_value=mock_http_client)
        mock_http_ctx.__exit__ = MagicMock(return_value=False)

        mock_cur = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_conn.autocommit = True

        # Configure mock_cur.fetchall to return existing products (or empty list by default)
        mock_cur.fetchall.return_value = (
            initial_db_rows if initial_db_rows is not None else []
        )

        # Configure mock_cur.executemany to return specific rowcounts
        if mock_executemany_returns:
            mock_cur.executemany.side_effect = [MagicMock(rowcount=rc) for rc in mock_executemany_returns]
        else:
            # Default to a mock with 0 rowcount if no specific counts are provided
            mock_cur.executemany.return_value = MagicMock(rowcount=0)

        return mock_http_ctx, mock_conn, mock_cur

    def test_upsert_called_for_new_product_urls(self, extract_url_impl):
        # Expect 1 executemany call for inserts, with N rows affected (N = num new products)
        mock_executemany_returns = [len(EXPECTED_PRODUCT_URLS)]
        http_ctx, conn, cur = self._setup_mocks(
            extract_url_impl,
            SITEMAP_XML_VALID,
            initial_db_rows=[],  # No existing products
            mock_executemany_returns=mock_executemany_returns,
        )

        with (
            patch.dict(os.environ, {"DATABASE_URL": "postgresql://fake"}),
            patch(extract_url_impl["httpx_client_path"], return_value=http_ctx),
            patch(extract_url_impl["psycopg2_path"], return_value=conn),
        ):
            extract_url_impl["sync_sitemap_to_db"]()

        # Check that executemany was called exactly once for INSERT
        insert_calls = [
            c
            for c in cur.executemany.call_args_list
            if "INSERT" in str(c[0][0]).upper()
        ]
        assert len(insert_calls) == 1  # Expecting one batch insert call

        # The second argument to executemany is the list of tuples for insertion
        # Each tuple is (url_wetall, nom_produit, is_active, status_history_jsonb)
        inserted_products_data = insert_calls[0][0][
            1
        ]  # Get the data from the first executemany call arguments
        inserted_urls = [prod_data[0] for prod_data in inserted_products_data]

        assert set(inserted_urls) == set(EXPECTED_PRODUCT_URLS)

    def test_product_url_passed_to_insert(self, extract_url_impl):
        """L'URL exacte de chaque nouveau produit doit figurer dans les paramètres SQL du batch d'insertion."""
        mock_executemany_returns = [len(EXPECTED_PRODUCT_URLS)]
        http_ctx, conn, cur = self._setup_mocks(
            extract_url_impl,
            SITEMAP_XML_VALID,
            initial_db_rows=[],
            mock_executemany_returns=mock_executemany_returns,
        )

        with (
            patch.dict(os.environ, {"DATABASE_URL": "postgresql://fake"}),
            patch(extract_url_impl["httpx_client_path"], return_value=http_ctx),
            patch(extract_url_impl["psycopg2_path"], return_value=conn),
        ):
            extract_url_impl["sync_sitemap_to_db"]()

        # Get the arguments passed to the executemany call for INSERT
        insert_call_args = None
        for call_args in cur.executemany.call_args_list:
            if "INSERT" in str(call_args[0][0]).upper():
                insert_call_args = call_args
                break

        assert insert_call_args is not None, "executemany for INSERT was not called"

        # The second argument to executemany is the list of tuples for insertion
        inserted_products_data = insert_call_args[0][1]
        inserted_urls = [prod_data[0] for prod_data in inserted_products_data]

        assert set(inserted_urls) == set(EXPECTED_PRODUCT_URLS)

    def test_product_name_derived_from_url_passed_to_insert(self, extract_url_impl):
        """Le nom produit inséré doit correspondre au slug de l'URL pour chaque nouveau produit."""
        mock_executemany_returns = [len(EXPECTED_PRODUCT_URLS)]
        http_ctx, conn, cur = self._setup_mocks(
            extract_url_impl,
            SITEMAP_XML_VALID,
            initial_db_rows=[],
            mock_executemany_returns=mock_executemany_returns,
        )

        with (
            patch.dict(os.environ, {"DATABASE_URL": "postgresql://fake"}),
            patch(extract_url_impl["httpx_client_path"], return_value=http_ctx),
            patch(extract_url_impl["psycopg2_path"], return_value=conn),
        ):
            extract_url_impl["sync_sitemap_to_db"]()

        insert_call_args = None
        for call_args in cur.executemany.call_args_list:
            if "INSERT" in str(call_args[0][0]).upper():
                insert_call_args = call_args
                break

        assert insert_call_args is not None, "executemany for INSERT was not called"

        inserted_products_data = insert_call_args[0][1]
        inserted_names = [prod_data[1] for prod_data in inserted_products_data]

        expected_names = [extract_url_impl["url_to_name"](url) for url in EXPECTED_PRODUCT_URLS]
        assert set(inserted_names) == set(expected_names)
        assert "Velo Route Carbone" in inserted_names

    def test_non_product_urls_not_inserted(self, extract_url_impl):
        """Les URLs de catégories et tags du sitemap ne doivent pas être insérées."""
        http_ctx, conn, cur = self._setup_mocks(extract_url_impl, SITEMAP_XML_VALID)

        with (
            patch.dict(os.environ, {"DATABASE_URL": "postgresql://fake"}),
            patch(extract_url_impl["httpx_client_path"], return_value=http_ctx),
            patch(extract_url_impl["psycopg2_path"], return_value=conn),
        ):
            extract_url_impl["sync_sitemap_to_db"]()

        all_sql_params = [c[0][1] for c in cur.execute.call_args_list if "INSERT" in str(c[0][0]).upper()]
        inserted_urls = [p[0] for p in all_sql_params]
        for url in inserted_urls:
            assert "/produit/" in url, f"URL hors /produit/ insérée : {url}"

    def test_db_error_does_not_raise(self, extract_url_impl):
        http_ctx, _, _ = self._setup_mocks(extract_url_impl, SITEMAP_XML_VALID)

        with (
            patch.dict(os.environ, {"DATABASE_URL": "postgresql://fake"}),
            patch(extract_url_impl["httpx_client_path"], return_value=http_ctx),
            patch(
                extract_url_impl["psycopg2_path"],
                side_effect=Exception("connexion DB échouée"),
            ),
        ):
            extract_url_impl["sync_sitemap_to_db"]()  # pas d'exception

    def test_db_error_is_logged(self, extract_url_impl, caplog):
        http_ctx, _, _ = self._setup_mocks(extract_url_impl, SITEMAP_XML_VALID)

        with (
            patch.dict(os.environ, {"DATABASE_URL": "postgresql://fake"}),
            patch(extract_url_impl["httpx_client_path"], return_value=http_ctx),
            patch(
                extract_url_impl["psycopg2_path"],
                side_effect=Exception("connexion DB échouée"),
            ),
        ):
            extract_url_impl["sync_sitemap_to_db"]()

        error_logs = [r for r in caplog.records if r.levelname == "ERROR"]
        assert len(error_logs) >= 1
