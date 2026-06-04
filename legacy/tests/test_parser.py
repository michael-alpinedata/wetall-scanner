"""
Tests — get_buy_link_from_wetall & normalize_amazon_url
=========================================================

Couverture visée :
  get_buy_link_from_wetall
    ✓ Stratégie A  : bouton + formulaire avec action         → (action, label)
    ✓ Stratégie A  : bouton + formulaire avec action + /out/ → A gagne
    ✓ Fallback B   : bouton sans parent form                 → /out/
    ✓ Fallback B   : bouton + form sans attribut action      → /out/
    ✓ Fallback B   : pas de bouton, /out/ présent            → premier /out/
    ✓ Fallback B   : plusieurs /out/ → premier retourné
    ✓ Fallback C   : lien direct marchand (Amazon/Decathlon) → lien direct
    ✓ Aucun lien   : (None, None)
    ✓ HTML vide    : (None, None)
    ✓ Labels retournés corrects par stratégie

  normalize_amazon_url
    ✓ URL relative commençant par '/'     → https://www.amazon.fr + url
    ✓ URL partielle commençant par 'dp/'  → https://www.amazon.fr/ + url
    ✓ URL absolue complète               → inchangée
    ✓ URL non-Amazon                     → inchangée
    ✓ Espaces en début/fin               → strippés
    ✓ URL absolue avec espaces           → strippée, inchangée
    ✓ dp/ avec espaces                   → strippé puis préfixé
"""

from __future__ import annotations

from legacy.tests.conftest import (
    HTML_BUTTON_AND_OUT_LINK,
    HTML_BUTTON_FORM_NO_ACTION,
    HTML_BUTTON_NO_PARENT_FORM,
    HTML_BUTTON_WITH_FORM_ACTION,
    HTML_NO_BUY_LINK,
    HTML_OUT_LINK_ONLY,
    make_soup,
)

# ============================================================================
# get_buy_link_from_wetall
# ============================================================================


class TestGetBuyLinkFromWetall:
    # ── Stratégie A : Formulaire avec action ─────────────────────────────────

    def test_button_with_form_action_returns_action_url(self, parser_impl):
        soup = make_soup(HTML_BUTTON_WITH_FORM_ACTION)
        url, label = parser_impl["get_buy_link"](soup)
        assert url == "https://www.decathlon.fr/buy/product/123"

    def test_button_with_form_action_returns_correct_label(self, parser_impl):
        soup = make_soup(HTML_BUTTON_WITH_FORM_ACTION)
        url, label = parser_impl["get_buy_link"](soup)
        assert label == "Lien via formulaire"

    def test_strategy_a_wins_over_out_link(self, parser_impl):
        """Lorsque le bouton + formulaire ET un /out/ sont présents, A gagne."""
        soup = make_soup(HTML_BUTTON_AND_OUT_LINK)
        url, label = parser_impl["get_buy_link"](soup)
        assert url == "https://form-target.com/buy/product"
        assert label == "Lien via formulaire"

    # ── Fallback B : Lien /out/ ────────────────────────────────────────────

    def test_out_link_is_returned_when_no_button(self, parser_impl):
        soup = make_soup(HTML_OUT_LINK_ONLY)
        url, label = parser_impl["get_buy_link"](soup)
        assert url == "https://www.amazon.fr/out/product/123"

    def test_out_link_returns_first_when_multiple(self, parser_impl):
        """Plusieurs /out/ → le premier dans le DOM est retourné."""
        soup = make_soup(HTML_OUT_LINK_ONLY)
        url, _ = parser_impl["get_buy_link"](soup)
        assert "product/123" in url  # premier, pas /456

    def test_out_link_label_correct(self, parser_impl):
        soup = make_soup(HTML_OUT_LINK_ONLY)
        _, label = parser_impl["get_buy_link"](soup)
        assert label == "Lien via fallback /out/"

    def test_button_without_parent_form_falls_back_to_out(self, parser_impl):
        """Bouton sans <form> parent → stratégie B (/out/)."""
        soup = make_soup(HTML_BUTTON_NO_PARENT_FORM)
        url, label = parser_impl["get_buy_link"](soup)
        assert "/out/" in url
        assert label == "Lien via fallback /out/"

    def test_button_form_without_action_falls_back_to_out(self, parser_impl):
        """Bouton avec <form> mais sans attribut action → stratégie B."""
        soup = make_soup(HTML_BUTTON_FORM_NO_ACTION)
        url, label = parser_impl["get_buy_link"](soup)
        assert "/out/" in url
        assert label == "Lien via fallback /out/"

    # ── Fallback C : Lien direct marchand ──────────────────────────────────

    def test_direct_merchant_link_detected_as_fallback(self, parser_impl):
        """Si pas de bouton ni /out/, on détecte un lien direct vers un marchand."""
        html = """
        <html><body>
          <a href="https://www.amazon.fr/dp/B0123456">Acheter sur Amazon</a>
        </body></html>
        """
        soup = make_soup(html)
        url, label = parser_impl["get_buy_link"](soup)
        assert url == "https://www.amazon.fr/dp/B0123456"
        assert label == "Lien via détection domaine marchand"

    # ── Aucun lien disponible ─────────────────────────────────────────────

    def test_no_buy_link_returns_none_tuple(self, parser_impl):
        soup = make_soup(HTML_NO_BUY_LINK)
        url, label = parser_impl["get_buy_link"](soup)
        assert url is None
        assert label is None

    def test_empty_html_returns_none_tuple(self, parser_impl):
        soup = make_soup("")
        url, label = parser_impl["get_buy_link"](soup)
        assert url is None
        assert label is None

    def test_only_non_out_links_returns_none(self, parser_impl):
        """Des liens présents, mais aucun ne contient /out/ ou domaine marchand → (None, None)."""
        html = """
        <html><body>
          <a href="https://www.wetall.fr/produit/shoes/">Voir produit</a>
          <a href="/wp-login.php">Login</a>
        </body></html>
        """
        soup = make_soup(html)
        url, label = parser_impl["get_buy_link"](soup)
        assert url is None


# ============================================================================
# normalize_amazon_url
# ============================================================================


class TestNormalizeAmazonUrl:
    def test_relative_url_starting_with_slash_is_prefixed(self, parser_impl):
        result = parser_impl["normalize_amazon_url"]("/dp/B08XYZ123/ref=ppx")
        assert result == "https://www.amazon.fr/dp/B08XYZ123/ref=ppx"

    def test_partial_url_starting_with_dp_is_prefixed(self, parser_impl):
        result = parser_impl["normalize_amazon_url"]("dp/B08XYZ123/ref=ppx")
        assert result == "https://www.amazon.fr/dp/B08XYZ123/ref=ppx"

    def test_full_absolute_url_is_unchanged(self, parser_impl):
        url = "https://www.amazon.fr/dp/B08XYZ123/ref=ppx"
        result = parser_impl["normalize_amazon_url"](url)
        assert result == url

    def test_non_amazon_absolute_url_is_unchanged(self, parser_impl):
        url = "https://www.decathlon.fr/buy/product/123"
        result = parser_impl["normalize_amazon_url"](url)
        assert result == url

    def test_leading_trailing_spaces_are_stripped(self, parser_impl):
        result = parser_impl["normalize_amazon_url"]("  /dp/B08XYZ  ")
        # strip → "/dp/B08XYZ" → starts with "/" → préfixé
        assert result == "https://www.amazon.fr/dp/B08XYZ"

    def test_absolute_url_with_spaces_is_stripped_and_unchanged(self, parser_impl):
        url = "  https://www.amazon.fr/dp/B00001  "
        result = parser_impl["normalize_amazon_url"](url)
        assert result == "https://www.amazon.fr/dp/B00001"

    def test_dp_url_with_leading_spaces_is_stripped_then_prefixed(self, parser_impl):
        result = parser_impl["normalize_amazon_url"]("  dp/B08ABC")
        assert result == "https://www.amazon.fr/dp/B08ABC"

    def test_empty_string_startswith_slash_check(self, parser_impl):
        """Chaîne vide → ne commence ni par '/' ni par 'dp/' → retournée vide."""
        result = parser_impl["normalize_amazon_url"]("")
        assert result == ""

    def test_http_non_ssl_absolute_url_unchanged(self, parser_impl):
        url = "http://www.amazon.fr/gp/product/B001"
        result = parser_impl["normalize_amazon_url"](url)
        assert result == url
