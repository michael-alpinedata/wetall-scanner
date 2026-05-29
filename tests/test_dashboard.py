"""
Tests — dashboard (smoke tests uniquement)
==========================================

Le dashboard est du code UI pur Streamlit. Les tests unitaires classiques
ont un ROI quasi-nul sur des appels `st.metric()` / `px.pie()`.

Ce fichier couvre uniquement :
  ✓ Le module est importable sans erreur de syntaxe
  ✓ load_data() renvoie un DataFrame vide si la DB est indisponible
  ✓ load_data() ne lève pas d'exception vers l'appelant (gestion silencieuse)

Streamlit et psycopg2 sont mockés pour éviter toute dépendance réseau.
"""

from __future__ import annotations

import importlib
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

# ── Helpers ──────────────────────────────────────────────────────────────────


def _import_dashboard():
    """
    Importe dashboard.dashboard en mockant streamlit pour éviter l'initialisation
    des composants UI (st.set_page_config lève une erreur hors contexte Streamlit).
    """
    import sys

    # Mock streamlit avant l'import pour neutraliser les appels UI
    mock_st = MagicMock()
    mock_st.error = MagicMock()  # utilisé dans load_data pour afficher les erreurs

    with patch.dict(sys.modules, {"streamlit": mock_st}):
        # Force le rechargement pour éviter les effets de bord entre tests
        if "dashboard.dashboard" in sys.modules:
            del sys.modules["dashboard.dashboard"]
        mod = importlib.import_module("dashboard.dashboard")

    return mod, mock_st


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestDashboardSmoke:
    def test_module_imports_without_error(self):
        """Le module s'importe sans SyntaxError ni ImportError."""
        mod, _ = _import_dashboard()
        assert mod is not None

    def test_load_data_returns_dataframe_when_db_unavailable(self):
        """Sans DATABASE_URL valide, load_data ne doit pas lever d'exception."""
        mod, mock_st = _import_dashboard()

        with patch("psycopg2.connect", side_effect=Exception("connexion refusée")):
            result = mod.load_data()

        # Doit retourner un DataFrame (vide ou non) — jamais None
        assert isinstance(result, pd.DataFrame)

    def test_load_data_does_not_raise_on_db_error(self):
        """load_data absorbe toutes les exceptions DB sans les propager."""
        mod, _ = _import_dashboard()

        with patch("psycopg2.connect", side_effect=RuntimeError("timeout réseau")):
            try:
                mod.load_data()
            except Exception as exc:
                pytest.fail(f"load_data a levé une exception : {exc}")

    def test_load_data_returns_empty_dataframe_on_db_error(self):
        """En cas d'erreur DB, le DataFrame retourné doit être vide."""
        mod, _ = _import_dashboard()

        with patch("psycopg2.connect", side_effect=Exception("DB down")):
            result = mod.load_data()

        assert result.empty
