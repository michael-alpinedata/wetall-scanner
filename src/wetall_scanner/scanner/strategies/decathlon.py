import json
import logging
from bs4 import BeautifulSoup
from .base import BaseScanner

logger = logging.getLogger(__name__)


class DecathlonScanner(BaseScanner):
    """Scanner Decathlon respectant le Template Method via parsing du JSON-LD."""

    def _get_product_data(self, soup: BeautifulSoup) -> dict:
        """Méthode utilitaire pour extraire et parser le JSON-LD proprement."""
        script = soup.find("script", type="application/ld+json")
        if not script or not script.string:
            return {}

        try:
            data = json.loads(script.string)
            if isinstance(data, list):
                # On isole l'objet Product s'il y a plusieurs objets dans la liste
                data = next(
                    (item for item in data if item.get("@type") == "Product"), {}
                )
            return data
        except json.JSONDecodeError as e:
            logger.warning(f"DecathlonScanner: Erreur de décodage JSON-LD : {e}")
            return {}

    def _get_availability(self, soup: BeautifulSoup) -> str:
        """Méthode utilitaire pour isoler le champ 'availability'."""
        data = self._get_product_data(soup)
        offers = data.get("offers", {})

        # Parfois 'offers' est une liste d'offres, parfois un dictionnaire unique
        if isinstance(offers, list):
            offers = offers[0] if offers else {}

        return offers.get("availability", "")

    def is_blocked(self, soup: BeautifulSoup, html: str) -> bool:
        # Implémentation basique pour Decathlon (ex: protection Datadome ou Cloudflare)
        return "datadome" in html.lower() or "cloudflare" in html.lower()

    def has_valid_structure(self, soup: BeautifulSoup) -> bool:
        """La structure est valide si on réussit à trouver le JSON du produit."""
        data = self._get_product_data(soup)
        if not data:
            logger.warning("DecathlonScanner: Aucun JSON-LD de type 'Product' trouvé.")
            return False
        return True

    def is_out_of_stock(self, soup: BeautifulSoup) -> bool:
        availability = self._get_availability(soup)
        return "OutOfStock" in availability

    def is_in_stock(self, soup: BeautifulSoup) -> bool:
        availability = self._get_availability(soup)
        return "InStock" in availability
