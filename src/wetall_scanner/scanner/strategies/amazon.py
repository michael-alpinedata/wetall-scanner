from bs4 import BeautifulSoup
from .base import BaseScanner
from ..config import MERCHANT_CONFIGS


class AmazonScanner(BaseScanner):
    """Scanner Amazon.fr optimisé, sans state (stateless)."""

    @property
    def config(self):
        return MERCHANT_CONFIGS.get("amazon", {})

    def is_404(self, html: str) -> bool:
        soup = BeautifulSoup(html, "html.parser")
        title = soup.select_one("title")
        return bool(
            title and ("404" in title.text or "non trouvée" in title.text.lower())
        )

    def is_blocked(self, soup: BeautifulSoup, html: str) -> bool:
        if soup.select_one('form[action*="captcha"]'):
            return True
        if soup.select_one('img[alt="Dogs of Amazon"]'):
            return True
        blocked_texts = [
            "Cliquez sur le bouton ci-dessous pour continuer vos achats",
            "Attention, vous avez fait trop de requêtes",
        ]
        if any(text in html for text in blocked_texts):
            return True
        return False

    def is_out_of_stock(self, soup: BeautifulSoup) -> bool:
        availability_block = soup.select_one("#availability")
        if availability_block:
            text = availability_block.get_text().lower()
            return any(
                kw in text
                for kw in ["indisponible", "rupture", "currently unavailable"]
            )
        return False

    def is_in_stock(self, soup: BeautifulSoup) -> bool:
        in_stock_selectors = self.config.get("in_stock_selectors", [])
        return any(soup.select_one(sel) for sel in in_stock_selectors)

    def has_valid_structure(self, soup: BeautifulSoup) -> bool:
        return bool(soup.select_one("#productTitle"))
