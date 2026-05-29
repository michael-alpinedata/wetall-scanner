"""
Tests — smart_scan (orchestrateur principal)
==============================================

Couverture visée :
  Erreurs côté Wetall
    ✓ Page Wetall en 404                    → "Erreur Wetall 404"
    ✓ Page Wetall en 500                    → "Erreur Wetall 500"

  Cas particuliers Wetall (sans lien marchand)
    ✓ Pas de lien + formulaire variations   → "Variations (Taille/Couleur)"
    ✓ Pas de lien + "en rupture" dans page  → "Rupture de stock" (marqueur Wetall)
    ✓ Pas de lien + aucun cas particulier   → "Bouton non trouvé"

  Scan marchand — codes HTTP
    ✓ Marchand en 403                       → "Vérification bloquée (403)"
    ✓ Marchand en 401                       → "Vérification bloquée (403)" (même msg)
    ✓ Marchand en 404                       → "Lien Brisé (404)"

  Scan marchand — analyse de stock
    ✓ Marchand OK (200)                     → ("OK", 200, url, "Scan réussi")
    ✓ Amazon avec rupture                   → "Rupture de stock"

  Normalisation d'URL
    ✓ Lien Amazon relatif (/dp/...)         → normalisé avant appel marchand

  Gestion d'exception
    ✓ Exception inattendue                  → "Erreur technique"

  Valeurs de retour
    ✓ Tuple 4-éléments dans tous les cas
    ✓ url_finale None quand Wetall échoue
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from tests.conftest import (
    HTML_NO_BUY_LINK,
    HTML_RUPTURE_WETALL,
    HTML_VARIATIONS_FORM,
    make_response,
)

WETALL_URL = "https://www.wetall.fr/produit/chaussures-trail-x3/"

# HTML Wetall valide avec lien de formulaire vers Amazon relatif
HTML_WETALL_VALID_REL = """
<html><body>
  <form action="/dp/B08XYZ123/ref=ppx">
    <button class="single_add_to_cart_button">Acheter</button>
  </form>
</body></html>
"""

# HTML Wetall valide avec lien absolu vers Decathlon
HTML_WETALL_VALID_ABS = """
<html><body>
  <form action="https://www.decathlon.fr/buy/product/123">
    <button class="single_add_to_cart_button">Acheter</button>
  </form>
</body></html>
"""

# HTML Wetall avec lien /out/ Amazon
HTML_WETALL_OUT_LINK = """
<html><body>
  <a href="https://www.amazon.fr/out/product/B001">Voir sur Amazon</a>
</body></html>
"""


def _make_smart_scan_client(
    wetall_status: int = 200,
    wetall_html: str = HTML_WETALL_VALID_ABS,
) -> MagicMock:
    """Crée un client mock retournant une réponse Wetall configurable."""
    client = MagicMock()
    wetall_resp = make_response(
        status_code=wetall_status,
        text=wetall_html,
        url=WETALL_URL,
    )
    client.get.return_value = wetall_resp
    return client


class TestSmartScanWetallErrors:
    """Cas d'échec au niveau de la récupération de la page Wetall."""

    def test_wetall_404_returns_error_tuple(self, smart_scan_impl):
        client = _make_smart_scan_client(wetall_status=404)
        with patch(smart_scan_impl["sleep_path"]):
            status, code, url_finale, msg = smart_scan_impl["smart_scan"](
                client, WETALL_URL
            )

        assert status == "Erreur Wetall 404"
        assert code == 404
        assert url_finale is None
        assert msg == "Fail Wetall"

    def test_wetall_500_returns_error_tuple(self, smart_scan_impl):
        client = _make_smart_scan_client(wetall_status=500)
        with patch(smart_scan_impl["sleep_path"]):
            status, code, url_finale, _ = smart_scan_impl["smart_scan"](
                client, WETALL_URL
            )

        assert status == "Erreur Wetall 500"
        assert code == 500
        assert url_finale is None

    def test_wetall_error_returns_4_tuple(self, smart_scan_impl):
        client = _make_smart_scan_client(wetall_status=403)
        with patch(smart_scan_impl["sleep_path"]):
            result = smart_scan_impl["smart_scan"](client, WETALL_URL)
        assert len(result) == 4


class TestSmartScanWetallSpecialCases:
    """Cas particuliers détectés sur la page Wetall elle-même."""

    def test_variations_form_returns_variations_status(self, smart_scan_impl):
        client = _make_smart_scan_client(wetall_html=HTML_VARIATIONS_FORM)
        with patch(smart_scan_impl["sleep_path"]):
            status, code, url_finale, msg = smart_scan_impl["smart_scan"](
                client, WETALL_URL
            )

        assert status == "Variations (Taille/Couleur)"
        assert code == 200
        assert url_finale is None
        assert msg == "Structure variations"

    def test_en_rupture_in_wetall_page_returns_rupture(self, smart_scan_impl):
        client = _make_smart_scan_client(wetall_html=HTML_RUPTURE_WETALL)
        with patch(smart_scan_impl["sleep_path"]):
            status, code, url_finale, msg = smart_scan_impl["smart_scan"](
                client, WETALL_URL
            )

        assert status == "Rupture de stock"
        assert code == 200
        assert url_finale is None
        assert msg == "Marqueur rupture Wetall"

    def test_no_buy_link_no_special_case_returns_bouton_non_trouve(
        self, smart_scan_impl
    ):
        client = _make_smart_scan_client(wetall_html=HTML_NO_BUY_LINK)
        with patch(smart_scan_impl["sleep_path"]):
            status, code, url_finale, msg = smart_scan_impl["smart_scan"](
                client, WETALL_URL
            )

        assert status == "Bouton non trouvé"
        assert code == 200
        assert url_finale is None
        assert msg == "Aucun lien extrait"


class TestSmartScanMerchantHttpCodes:
    """Codes HTTP retournés par le marchand final."""

    def _run_with_merchant_response(self, smart_scan_impl, merchant_status: int):
        client = _make_smart_scan_client(wetall_html=HTML_WETALL_VALID_ABS)
        merchant_resp = make_response(
            status_code=merchant_status,
            text="<p>page marchand</p>",
            url="https://www.decathlon.fr/buy/product/123",
        )

        with (
            patch(smart_scan_impl["sleep_path"]),
            patch(
                smart_scan_impl["fetch_fallback_path"],
                return_value=merchant_resp,
            ),
        ):
            return smart_scan_impl["smart_scan"](client, WETALL_URL)

    def test_merchant_403_returns_verification_bloquee(self, smart_scan_impl):
        status, code, url_finale, msg = self._run_with_merchant_response(
            smart_scan_impl, 403
        )
        assert status == "Vérification bloquée (403)"
        assert code == 403
        assert msg == "Pare-feu marchand"

    def test_merchant_401_returns_verification_bloquee(self, smart_scan_impl):
        """401 et 403 partagent le même message de retour."""
        status, code, url_finale, msg = self._run_with_merchant_response(
            smart_scan_impl, 401
        )
        assert status == "Vérification bloquée (403)"
        assert code == 401

    def test_merchant_404_returns_lien_brise(self, smart_scan_impl):
        status, code, url_finale, msg = self._run_with_merchant_response(
            smart_scan_impl, 404
        )
        assert status == "Lien Brisé (404)"
        assert code == 404
        assert msg == "Erreur 404 serveur"

    def test_merchant_200_ok_returns_ok(self, smart_scan_impl):
        client = _make_smart_scan_client(wetall_html=HTML_WETALL_VALID_ABS)
        merchant_resp = make_response(
            status_code=200,
            text="<p>Disponible en ligne.</p>",
            url="https://www.decathlon.fr/buy/product/123",
        )

        with (
            patch(smart_scan_impl["sleep_path"]),
            patch(
                smart_scan_impl["fetch_fallback_path"],
                return_value=merchant_resp,
            ),
        ):
            status, code, url_finale, msg = smart_scan_impl["smart_scan"](
                client, WETALL_URL
            )

        assert status == "OK"
        assert code == 200
        assert msg == "Scan réussi"

    def test_merchant_200_amazon_rupture_returns_rupture(self, smart_scan_impl):
        client = _make_smart_scan_client(wetall_html=HTML_WETALL_OUT_LINK)
        merchant_resp = make_response(
            status_code=200,
            text="<p>actuellement indisponible</p>",
            url="https://www.amazon.fr/dp/B001",
        )

        with (
            patch(smart_scan_impl["sleep_path"]),
            patch(
                smart_scan_impl["fetch_fallback_path"],
                return_value=merchant_resp,
            ),
        ):
            status, code, url_finale, msg = smart_scan_impl["smart_scan"](
                client, WETALL_URL
            )

        assert status == "Rupture de stock"
        assert "Amazon" in msg


class TestSmartScanUrlNormalization:
    """Vérifie que les URLs Amazon relatives sont normalisées avant le scan."""

    def test_relative_amazon_url_is_normalized_before_merchant_call(
        self, smart_scan_impl
    ):
        """
        La page Wetall retourne un lien /dp/... relatif.
        L'URL envoyée à fetch_with_fallback doit commencer par https://www.amazon.fr.
        """
        client = _make_smart_scan_client(wetall_html=HTML_WETALL_VALID_REL)
        merchant_resp = make_response(
            status_code=200,
            text="En stock.",
            url="https://www.amazon.fr/dp/B08XYZ123/ref=ppx",
        )

        with (
            patch(smart_scan_impl["sleep_path"]),
            patch(
                smart_scan_impl["fetch_fallback_path"],
                return_value=merchant_resp,
            ) as mock_fetch,
        ):
            smart_scan_impl["smart_scan"](client, WETALL_URL)

        # Vérifier l'URL passée à fetch_with_fallback
        called_url = mock_fetch.call_args[0][1]  # 2ème argument positionnel
        assert called_url.startswith("https://www.amazon.fr")


class TestSmartScanExceptionHandling:
    """Gestion des exceptions imprévues."""

    def test_exception_during_wetall_fetch_returns_erreur_technique(
        self, smart_scan_impl
    ):
        client = MagicMock()
        client.get.side_effect = ConnectionError("réseau indisponible")

        with patch(smart_scan_impl["sleep_path"]):
            status, code, url_finale, msg = smart_scan_impl["smart_scan"](
                client, WETALL_URL
            )

        assert status == "Erreur technique"
        assert code == 0
        assert url_finale is None
        assert "Exception" in msg

    def test_exception_message_truncated_to_50_chars(self, smart_scan_impl):
        long_msg = "x" * 200
        client = MagicMock()
        client.get.side_effect = RuntimeError(long_msg)

        with patch(smart_scan_impl["sleep_path"]):
            _, _, _, msg = smart_scan_impl["smart_scan"](client, WETALL_URL)

        # Le message de debug ne dépasse pas "Exception: " + 50 chars
        assert len(msg) <= len("Exception: ") + 50

    def test_return_is_always_4_tuple(self, smart_scan_impl):
        """Quel que soit le scénario, smart_scan retourne toujours un 4-tuple."""
        client = MagicMock()
        client.get.side_effect = Exception("boom")

        with patch(smart_scan_impl["sleep_path"]):
            result = smart_scan_impl["smart_scan"](client, WETALL_URL)

        assert isinstance(result, tuple)
        assert len(result) == 4
