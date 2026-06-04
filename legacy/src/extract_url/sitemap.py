"""
Téléchargement et parsing du sitemap Wetall.

Responsabilité unique : récupérer le fichier XML du sitemap et
retourner la liste filtrée des URLs de produits réels.
"""

import logging

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

PRODUCT_SITEMAP_URL = "https://www.wetall.fr/product-sitemap.xml"
_PRODUCT_URL_FILTER = "/produit/"


def _parse_sitemap_xml(xml_text: str) -> list[str]:
    """
    Parse le contenu XML du sitemap et retourne toutes les <loc>.

    Utilise le parseur 'xml' (lxml) en priorité, avec repli sur 'html.parser'.
    """
    try:
        soup = BeautifulSoup(xml_text, "xml")
    except Exception:
        logger.warning("Parseur 'xml' indisponible — repli sur 'html.parser'.")
        soup = BeautifulSoup(xml_text, "html.parser")

    return [loc.text for loc in soup.find_all("loc")]


def _filter_product_urls(all_urls: list[str]) -> list[str]:
    """
    Filtre les URLs pour ne conserver que les fiches produit.

    Exclut les images, tags et autres entrées du sitemap global.
    """
    return [url for url in all_urls if _PRODUCT_URL_FILTER in url]


def fetch_product_urls(
    sitemap_url: str = PRODUCT_SITEMAP_URL,
) -> list[str]:
    """
    Télécharge le sitemap et retourne la liste des URLs de produits.

    Args:
        sitemap_url: URL du sitemap XML (paramétrable pour les tests).

    Returns:
        Liste d'URLs de type '/produit/' ou liste vide en cas d'erreur.
    """
    logger.info("Téléchargement du sitemap : %s", sitemap_url)

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(sitemap_url)

        if response.status_code != 200:
            logger.error(
                "Erreur lors de la récupération du sitemap : %s",
                response.status_code,
            )
            return []

        all_urls = _parse_sitemap_xml(response.text)
        product_urls = _filter_product_urls(all_urls)

        if not product_urls:
            logger.warning(
                "Aucune URL de type '%s' trouvée parmi %d entrées.",
                _PRODUCT_URL_FILTER,
                len(all_urls),
            )
            return []

        logger.info(
            "%d produits réels identifiés sur %d entrées au total.",
            len(product_urls),
            len(all_urls),
        )
        return product_urls

    except Exception as exc:
        logger.error("Erreur lors du téléchargement du sitemap : %s", exc)
        return []
