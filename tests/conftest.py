"""
Fixtures et helpers partagés par l'ensemble de la suite de tests.

Architecture
------------
Les fichiers legacy (scanner.py, extract_urls.py, main.py racine) ont été
supprimés après validation de la non-régression (202/202 legacy + new).
Les fixtures importent directement depuis src/ — une seule implémentation.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from bs4 import BeautifulSoup

# ============================================================================
# Helpers
# ============================================================================


def make_soup(html: str) -> BeautifulSoup:
    """Parse un fragment HTML en BeautifulSoup (html.parser)."""
    return BeautifulSoup(html, "html.parser")


def make_response(
    status_code: int = 200,
    text: str = "",
    url: str = "https://example.com",
) -> MagicMock:
    """Crée un mock de réponse httpx minimaliste."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    resp.url = url
    return resp


# ============================================================================
# Constantes HTML — scénarios de pages Wetall
# ============================================================================

HTML_BUTTON_WITH_FORM_ACTION = """
<html><body>
  <form action="https://www.decathlon.fr/buy/product/123">
    <button class="single_add_to_cart_button">Acheter</button>
  </form>
</body></html>
"""

HTML_OUT_LINK_ONLY = """
<html><body>
  <a href="https://www.amazon.fr/out/product/123">Voir sur Amazon</a>
  <a href="https://www.amazon.fr/out/product/456">Autre lien</a>
</body></html>
"""

HTML_BUTTON_FORM_NO_ACTION = """
<html><body>
  <form>
    <button class="single_add_to_cart_button">Acheter</button>
  </form>
  <a href="https://www.nike.fr/out/product/789">Fallback</a>
</body></html>
"""

HTML_BUTTON_NO_PARENT_FORM = """
<html><body>
  <div>
    <button class="single_add_to_cart_button">Acheter</button>
  </div>
  <a href="https://www.nike.fr/out/product/789">Fallback</a>
</body></html>
"""

HTML_BUTTON_AND_OUT_LINK = """
<html><body>
  <form action="https://form-target.com/buy/product">
    <button class="single_add_to_cart_button">Acheter</button>
  </form>
  <a href="https://www.amazon.fr/out/product/456">Amazon fallback</a>
</body></html>
"""

HTML_NO_BUY_LINK = """
<html><body>
  <p>Produit sans lien d'achat.</p>
</body></html>
"""

HTML_VARIATIONS_FORM = """
<html><body>
  <form class="variations_form">
    <select name="taille">
      <option value="S">S</option>
      <option value="M">M</option>
    </select>
  </form>
</body></html>
"""

HTML_RUPTURE_WETALL = """
<html><body>
  <p>Ce produit est actuellement <strong>en rupture</strong> de stock.</p>
</body></html>
"""

HTML_WETALL_AMAZON_RELATIVE = """
<html><body>
  <form action="/dp/B08XYZ123/ref=ppx_yo_dt_b_search">
    <button class="single_add_to_cart_button">Acheter</button>
  </form>
</body></html>
"""

HTML_AMAZON_OK = "<html><body><p>En stock. Livraison rapide.</p></body></html>"
HTML_AMAZON_404_DISGUISED = "<html><body><p>n'est pas une page fonctionnelle</p></body></html>"
HTML_AMAZON_OUT_OF_STOCK = "<html><body><p>actuellement indisponible</p></body></html>"
HTML_AMAZON_RESTOCKED = "<html><body><p>nouveau approvisionné prochainement</p></body></html>"
HTML_NIKE_OUT_OF_STOCK = "<html><body><p>Ce produit est plus disponible.</p></body></html>"
HTML_NIKE_INDISPONIBLE = "<html><body><p>Article indisponible.</p></body></html>"
HTML_NIKE_RUPTURE = "<html><body><p>En rupture temporaire.</p></body></html>"
HTML_NIKE_OK = "<html><body><p>Ajouter au panier.</p></body></html>"
HTML_DECATHLON_INDISPONIBLE = "<html><body><p>Article indisponible en ligne.</p></body></html>"
HTML_DECATHLON_RUPTURE = "<html><body><p>En rupture.</p></body></html>"
HTML_DECATHLON_EN_RUPTURE = "<html><body><p>En rupture de stock.</p></body></html>"
HTML_DECATHLON_OK = "<html><body><p>Disponible en ligne.</p></body></html>"
HTML_GENERIC_OK = "<html><body><p>Disponible.</p></body></html>"

# ============================================================================
# Sitemap XML fixtures
# ============================================================================

SITEMAP_XML_VALID = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://www.wetall.fr/produit/chaussures-trail-x3/</loc></url>
  <url><loc>https://www.wetall.fr/produit/velo-route-carbone/</loc></url>
  <url>
    <loc>https://www.wetall.fr/produit/short-running-homme/</loc>
    <image:image>
      <image:loc>https://img.wetall.fr/img1.jpg</image:loc>
    </image:image>
  </url>
  <url><loc>https://www.wetall.fr/categorie/running/</loc></url>
  <url><loc>https://www.wetall.fr/tag/promo/</loc></url>
</urlset>"""

SITEMAP_XML_NO_PRODUCTS = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://www.wetall.fr/categorie/running/</loc></url>
  <url><loc>https://www.wetall.fr/tag/promo/</loc></url>
</urlset>"""

SITEMAP_XML_EMPTY = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
</urlset>"""


# ============================================================================
# Fixtures — importent directement depuis src/
# ============================================================================


@pytest.fixture
def parser_impl():
    from src.scanner.parser import get_buy_link_from_wetall, normalize_amazon_url

    return {
        "get_buy_link": get_buy_link_from_wetall,
        "normalize_amazon_url": normalize_amazon_url,
    }


@pytest.fixture
def analyzer_impl():
    from src.scanner.analyzer import analyze_merchant_status

    return analyze_merchant_status


@pytest.fixture
def http_client_impl():
    from src.scanner.http_client import fetch_with_fallback

    return {
        "fetch_with_fallback": fetch_with_fallback,
        "curl_get_path": "curl_cffi.requests.get",
    }


@pytest.fixture
def smart_scan_impl():
    from src.scanner.orchestrator import smart_scan

    return {
        "smart_scan": smart_scan,
        "sleep_path": "src.scanner.orchestrator.time.sleep",
        "fetch_fallback_path": "src.scanner.orchestrator.fetch_with_fallback",
    }


@pytest.fixture
def pipeline_impl():
    from src.scanner.pipeline import run_pipeline

    return {
        "run_pipeline": run_pipeline,
        "sleep_path": "src.scanner.pipeline.time.sleep",
        "smart_scan_path": "src.scanner.pipeline.smart_scan",
        "psycopg2_path": "src.scanner.pipeline.psycopg2.connect",
        "httpx_client_path": "src.scanner.pipeline.httpx.Client",
    }


@pytest.fixture
def extract_url_impl():
    from src.extract_url.sync import _url_to_product_name, sync_sitemap_to_db

    return {
        "sync_sitemap_to_db": sync_sitemap_to_db,
        "url_to_name": _url_to_product_name,
        "httpx_client_path": "src.extract_url.sitemap.httpx.Client",
        "psycopg2_path": "src.extract_url.sync.psycopg2.connect",
    }
