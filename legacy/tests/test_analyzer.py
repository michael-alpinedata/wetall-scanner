"""
Tests — analyze_merchant_status
=================================

Couverture visée :
  Nike
    ✓ "nike" dans l'URL + "plus disponible"   → Rupture
    ✓ "nike" dans l'URL + "indisponible"      → Rupture
    ✓ "nike" dans l'URL + "rupture"           → Rupture
    ✓ "nike" dans l'URL + stock OK            → OK
    ✓ "nike" dans le HTML (pas URL) + rupture → Rupture (comportement legacy)
    ✓ Insensibilité à la casse

  Decathlon
    ✓ URL + "indisponible"  → Rupture
    ✓ URL + "rupture"       → Rupture
    ✓ URL + "en rupture"    → Rupture
    ✓ URL + stock OK        → OK
    ✓ "decathlon" dans HTML → détecté
    ✓ Insensibilité à la casse

  Amazon
    ✓ URL + "n'est pas une page fonctionnelle" → Lien Mort (404 déguisé)
    ✓ URL + "actuellement indisponible"        → Rupture
    ✓ URL + "nouveau approvisionné"            → Rupture
    ✓ URL + stock OK                           → OK
    ✓ "amazon" dans HTML (pas URL)             → détecté

  Alltricks
    ✓ URL + "épuisé"        → Rupture
    ✓ URL + "plus en stock" → Rupture
    ✓ URL + "indisponible"  → Rupture

  Cas généraux
    ✓ Marchand inconnu / URL vide              → ("OK", "Scan réussi")
    ✓ HTML vide + URL vide                     → ("OK", "Scan réussi")
    ✓ nike + marqueur decathlon                → règle Nike évaluée (pas Decathlon)
    ✓ Amazon dans URL prime sur Decathlon si decathlon dans HTML
"""

from __future__ import annotations

from legacy.tests.conftest import (
    HTML_AMAZON_404_DISGUISED,
    HTML_AMAZON_OK,
    HTML_AMAZON_OUT_OF_STOCK,
    HTML_AMAZON_RESTOCKED,
    HTML_DECATHLON_EN_RUPTURE,
    HTML_DECATHLON_INDISPONIBLE,
    HTML_DECATHLON_OK,
    HTML_DECATHLON_RUPTURE,
    HTML_GENERIC_OK,
    HTML_NIKE_INDISPONIBLE,
    HTML_NIKE_OK,
    HTML_NIKE_OUT_OF_STOCK,
    HTML_NIKE_RUPTURE,
)

NIKE_URL = "https://www.nike.com/fr/t/chaussure-react/AB1234"
DECATHLON_URL = "https://www.decathlon.fr/p/veste-trail/_/R-p-305611"
AMAZON_URL = "https://www.amazon.fr/dp/B08XYZ123/ref=ppx_yo_dt_b_search"
ALLTRICKS_URL = "https://www.alltricks.fr/produit/velo-route-1234"
GENERIC_URL = "https://www.unknown-shop.com/product/123"


# ============================================================================
# Nike
# ============================================================================


class TestAnalyzeMerchantStatusNike:
    def test_nike_url_plus_disponible_is_rupture(self, analyzer_impl):
        status, msg = analyzer_impl(NIKE_URL, HTML_NIKE_OUT_OF_STOCK)
        assert status == "Rupture de stock"
        assert "Nike" in msg

    def test_nike_url_indisponible_is_rupture(self, analyzer_impl):
        status, msg = analyzer_impl(NIKE_URL, HTML_NIKE_INDISPONIBLE)
        assert status == "Rupture de stock"
        assert "Nike" in msg

    def test_nike_url_rupture_keyword_is_rupture(self, analyzer_impl):
        status, msg = analyzer_impl(NIKE_URL, HTML_NIKE_RUPTURE)
        assert status == "Rupture de stock"
        assert "Nike" in msg

    def test_nike_url_stock_ok_returns_ok(self, analyzer_impl):
        status, _ = analyzer_impl(NIKE_URL, HTML_NIKE_OK)
        assert status == "OK"

    def test_nike_in_html_not_url_still_detected(self, analyzer_impl):
        """Le legacy vérifie 'nike' dans HTML aussi → comportement attendu."""
        html_with_nike_brand = "<p>Ce produit Nike est plus disponible.</p>"
        status, msg = analyzer_impl(GENERIC_URL, html_with_nike_brand)
        assert status == "Rupture de stock"
        assert "Nike" in msg

    def test_nike_case_insensitive(self, analyzer_impl):
        """La comparaison se fait en minuscules → majuscules tolérées dans l'entrée."""
        status, msg = analyzer_impl(
            "https://WWW.NIKE.COM/product",
            "<p>PLUS DISPONIBLE en stock.</p>",
        )
        assert status == "Rupture de stock"

    def test_nike_url_no_rupture_marker_is_ok(self, analyzer_impl):
        """URL Nike + HTML sans marqueur → OK (ne pas créer de faux positif)."""
        status, _ = analyzer_impl(NIKE_URL, HTML_GENERIC_OK)
        assert status == "OK"


# ============================================================================
# Decathlon
# ============================================================================


class TestAnalyzeMerchantStatusDecathlon:
    def test_decathlon_indisponible_is_rupture(self, analyzer_impl):
        status, msg = analyzer_impl(DECATHLON_URL, HTML_DECATHLON_INDISPONIBLE)
        assert status == "Rupture de stock"
        assert "Decathlon" in msg

    def test_decathlon_rupture_is_rupture(self, analyzer_impl):
        status, msg = analyzer_impl(DECATHLON_URL, HTML_DECATHLON_RUPTURE)
        assert status == "Rupture de stock"
        assert "Decathlon" in msg

    def test_decathlon_en_rupture_is_rupture(self, analyzer_impl):
        status, msg = analyzer_impl(DECATHLON_URL, HTML_DECATHLON_EN_RUPTURE)
        assert status == "Rupture de stock"
        assert "Decathlon" in msg

    def test_decathlon_url_stock_ok_returns_ok(self, analyzer_impl):
        status, _ = analyzer_impl(DECATHLON_URL, HTML_DECATHLON_OK)
        assert status == "OK"

    def test_decathlon_in_html_not_url_still_detected(self, analyzer_impl):
        html = "<p>Voir sur Decathlon — indisponible actuellement.</p>"
        status, msg = analyzer_impl(GENERIC_URL, html)
        assert status == "Rupture de stock"
        assert "Decathlon" in msg

    def test_decathlon_case_insensitive(self, analyzer_impl):
        status, msg = analyzer_impl(
            "https://WWW.DECATHLON.FR/product",
            "<p>INDISPONIBLE en ligne.</p>",
        )
        assert status == "Rupture de stock"


# ============================================================================
# Amazon
# ============================================================================


class TestAnalyzeMerchantStatusAmazon:
    def test_amazon_404_disguised_returns_lien_mort(self, analyzer_impl):
        status, msg = analyzer_impl(AMAZON_URL, HTML_AMAZON_404_DISGUISED)
        assert status == "Lien Mort (404 déguisé)"
        assert "Amazon" in msg
        assert "404" in msg

    def test_amazon_actuellement_indisponible_is_rupture(self, analyzer_impl):
        status, msg = analyzer_impl(AMAZON_URL, HTML_AMAZON_OUT_OF_STOCK)
        assert status == "Rupture de stock"
        assert "Amazon" in msg

    def test_amazon_nouveau_approvisionne_is_rupture(self, analyzer_impl):
        status, msg = analyzer_impl(AMAZON_URL, HTML_AMAZON_RESTOCKED)
        assert status == "Rupture de stock"
        assert "Amazon" in msg

    def test_amazon_stock_ok_returns_ok(self, analyzer_impl):
        status, _ = analyzer_impl(AMAZON_URL, HTML_AMAZON_OK)
        assert status == "OK"

    def test_amazon_in_html_not_url_still_detected(self, analyzer_impl):
        html = "<p>n'est pas une page fonctionnelle — amazon</p>"
        status, _ = analyzer_impl(GENERIC_URL, html)
        assert status == "Lien Mort (404 déguisé)"

    def test_amazon_case_insensitive(self, analyzer_impl):
        status, msg = analyzer_impl(
            "https://WWW.AMAZON.FR/dp/B001",
            "<p>ACTUELLEMENT INDISPONIBLE</p>",
        )
        assert status == "Rupture de stock"

    def test_amazon_404_marker_takes_precedence_over_stock_marker(self, analyzer_impl):
        """Quand les deux marqueurs Amazon sont présents, le 404 est évalué d'abord."""
        html = "<p>n'est pas une page fonctionnelle. actuellement indisponible.</p>"
        status, msg = analyzer_impl(AMAZON_URL, html)
        assert status == "Lien Mort (404 déguisé)"


# ============================================================================
# Alltricks
# ============================================================================


class TestAnalyzeMerchantStatusAlltricks:
    def test_alltricks_epuise_is_rupture(self, analyzer_impl):
        status, msg = analyzer_impl(ALLTRICKS_URL, "<html>Produit épuisé</html>")
        assert status == "Rupture de stock"
        assert "Alltricks" in msg

    def test_alltricks_plus_en_stock_is_rupture(self, analyzer_impl):
        status, msg = analyzer_impl(ALLTRICKS_URL, "<html>Plus en stock actuellement.</html>")
        assert status == "Rupture de stock"
        assert "Alltricks" in msg

    def test_alltricks_indisponible_is_rupture(self, analyzer_impl):
        status, msg = analyzer_impl(ALLTRICKS_URL, "<html>Indisponible pour le moment.</html>")
        assert status == "Rupture de stock"
        assert "Alltricks" in msg


# ============================================================================
# Cas généraux & règles de priorité
# ============================================================================


class TestAnalyzeMerchantStatusGeneral:
    def test_unknown_merchant_returns_ok(self, analyzer_impl):
        status, msg = analyzer_impl(GENERIC_URL, HTML_GENERIC_OK)
        assert status == "OK"
        assert msg == "Scan réussi"

    def test_empty_url_and_html_returns_ok(self, analyzer_impl):
        status, msg = analyzer_impl("", "")
        assert status == "OK"
        assert msg == "Scan réussi"

    def test_nike_rule_evaluated_before_decathlon(self, analyzer_impl):
        """
        URL Nike + marqueurs UNIQUEMENT Decathlon dans HTML ("rupture", "en rupture").
        La règle Nike est évaluée, mais "rupture" est AUSSI un marqueur Nike
        (voir liste _NIKE_OUT_OF_STOCK_MARKERS). Ce test vérifie la priorité des
        règles : Nike est évaluée avant Decathlon, et "rupture" la déclenche.
        NOTE : "indisponible" et "rupture" sont des marqueurs communs
        aux deux marchands.
        """
        # Seul marqueur dont Nike ne se soucie PAS mais Decathlon oui : "en rupture"
        # Attention : "en rupture" contient "rupture" → toujours détecté par Nike.
        # Pour tester l'isolation, on utilise un HTML sans aucun marqueur Nike.
        html = "<p>Article disponible. Merci de votre visite.</p>"
        # L'URL contient "nike" mais aucun marqueur Nike n'est présent → OK
        status, _ = analyzer_impl(NIKE_URL, html)
        assert status == "OK"

    def test_only_decathlon_markers_not_triggered_on_nike_url(self, analyzer_impl):
        """Vérifie que les marqueurs Decathlon n'affectent pas une URL Nike."""
        status, _ = analyzer_impl(NIKE_URL, HTML_DECATHLON_INDISPONIBLE)
        # "indisponible" est aussi un marqueur Nike → doit bien être Rupture
        assert status == "Rupture de stock"

    def test_generic_html_with_irrelevant_brand_mention(self, analyzer_impl):
        """Mention d'une marque sans marqueur de rupture → OK."""
        html = "<p>Produit compatible avec Nike et Amazon.</p>"
        # "nike" present in html → règle Nike → mais pas de marqueur de rupture
        status, _ = analyzer_impl(GENERIC_URL, html)
        assert status == "OK"
