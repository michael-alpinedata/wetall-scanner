from abc import ABC, abstractmethod
import logging
from bs4 import BeautifulSoup
import json

from .config import MERCHANT_CONFIGS
from .constants import (
    MSG_BUY_BUTTON,
    MSG_HTML_EMPTY,
    MSG_OUT_OF_STOCK,
    MSG_PAGE_404,
    MSG_UNSUPPORTED_MERCHANT,
    ScanStatus,
)


# Configuration du logger pour le module des stratégies
logger = logging.getLogger(__name__)


class BaseScanner(ABC):
    """Interface de base pour tous les moteurs de scan marchands."""

    def __init__(self, merchant_name: str | None = None):
        # Charge la config du marchand si elle existe, sinon un dictionnaire vide
        self.config = MERCHANT_CONFIGS.get(merchant_name, {}) if merchant_name else {}

    @abstractmethod
    def analyze(self, html_content: str, url: str = "") -> tuple[str, str]:
        """
        Analyse le HTML d'un marchand.
        L'URL est optionnelle et sert principalement au logging et au debug (dumps).
        """
        pass


class AmazonScanner(BaseScanner):
    """Scanner Amazon.fr optimisé, piloté par la configuration."""

    def __init__(self):
        super().__init__("amazon")

    def analyze(self, html_content: str, url: str = "") -> tuple[str, str]:
        # 1. Validation technique de base
        if not html_content or len(html_content) < 100:
            return ScanStatus.ERREUR.value, MSG_HTML_EMPTY

        soup = BeautifulSoup(html_content, "html.parser")

        # 2. Détection 404
        if self._is_404(soup):
            return ScanStatus.ERREUR.value, MSG_PAGE_404

        # 3. Détection Blocage (Anti-bot explicite) - PRIORITÉ ABSOLUE
        # Si on est ici, le serveur refuse de nous parler normalement.
        if self._is_bot_blocked(soup, url, html_content):
            return ScanStatus.ERREUR.value, "Blocage anti-bot détecté"

        # 4. Détection Hors Stock Explicite - PRIORITÉ HAUTE
        # On vérifie avant de valider la structure, car une page "Hors Stock"
        # peut avoir une structure différente d'une page produit classique.
        if self._is_explicitly_out_of_stock(soup):
            return ScanStatus.HORS_STOCK.value, MSG_OUT_OF_STOCK

        # 5. Validation structurelle (Le Gardien)
        # Si on n'a pas le titre et qu'on n'est pas "Hors Stock",
        # alors on est effectivement dans un cas inconnu (A_VERIFIER).
        if not soup.select_one("#productTitle"):
            logger.warning(f"AmazonScanner: Titre absent sur {url}.")
            self._dump_if_suspicious(
                url, html_content, reason="missing_title_structural_check"
            )
            return ScanStatus.A_VERIFIER.value, "Page invalide (titre absent)"

        # 6. Analyse métier (Page produit confirmée)
        if self._is_in_stock(soup):
            return ScanStatus.EN_STOCK.value, MSG_BUY_BUTTON

        # Si on a le titre, pas de blocage, pas de stock trouvé, et pas de "Hors Stock" détecté :
        # C'est une page produit dont le statut nous échappe.
        return ScanStatus.A_VERIFIER.value, f"Statut ambigu (Fallback) : {url}"

    # --- Méthodes de diagnostic ---

    def _is_bot_blocked(self, soup: BeautifulSoup, url: str, html: str) -> bool:
        """Détecte les signatures de blocage indiscutables."""
        if soup.select_one('img[alt="Dogs of Amazon"]'):
            return True
        if soup.select_one('form[action*="captcha"]'):
            return True
        return False

    def _is_explicitly_out_of_stock(self, soup: BeautifulSoup) -> bool:
        """
        Détecte le bloc #availability.
        C'est un marqueur fort qui valide que la page est "connue", même sans titre.
        """
        availability_block = soup.select_one("#availability")
        if availability_block:
            text = availability_block.get_text().lower()
            return any(
                kw in text
                for kw in ["indisponible", "rupture", "currently unavailable"]
            )
        return False

    def _is_in_stock(self, soup: BeautifulSoup) -> bool:
        """Détecte la présence d'un bouton d'achat."""
        in_stock_selectors = self.config.get("in_stock_selectors", [])
        return any(soup.select_one(sel) for sel in in_stock_selectors)

    def _is_404(self, soup: BeautifulSoup) -> bool:
        title = soup.select_one("title")
        return bool(
            title and ("404" in title.text or "non trouvée" in title.text.lower())
        )

    def _dump_if_suspicious(self, url: str, html: str, reason: str):
        from wetall_scanner.scanner.utils.html_inspector import dump_suspicious_html

        dump_suspicious_html(url, html, reason=reason)


class DecathlonScanner(BaseScanner):
    def __init__(self):
        super().__init__("decathlon")

    def analyze(self, html_content: str, url: str | None = None) -> tuple[str, str]:
        """
        Analyse le stock Decathlon via le JSON-LD présent dans le HTML.
        Retourne un tuple (Statut, Message).
        """
        if not html_content or len(html_content) < 500:
            logger.error("DecathlonScanner: HTML vide ou trop court.")
            return ScanStatus.ERREUR.value, "HTML_INSUFFISANT"

        try:
            soup = BeautifulSoup(html_content, "html.parser")
            script = soup.find("script", type="application/ld+json")

            if not script:
                logger.warning("DecathlonScanner: Aucun JSON-LD trouvé.")
                return ScanStatus.ERREUR.value, "JSON_LD_ABSENT"

            data = json.loads(script.string)

            # Gérer le cas où JSON-LD est une liste
            if isinstance(data, list):
                data = next(
                    (item for item in data if item.get("@type") == "Product"), {}
                )

            offers = data.get("offers", {})
            if isinstance(offers, list):
                offers = offers[0]

            availability = offers.get("availability", "")

            # Mapping du statut
            if "InStock" in availability:
                return ScanStatus.EN_STOCK.value, "En stock"
            elif "OutOfStock" in availability:
                return ScanStatus.HORS_STOCK.value, "Hors stock"
            else:
                logger.warning(
                    f"DecathlonScanner: Disponibilité inconnue ({availability})"
                )
                return ScanStatus.A_VERIFIER.value, f"Dispo: {availability}"

        except Exception as e:
            logger.exception(f"DecathlonScanner: Erreur d'analyse : {e}")
            return ScanStatus.ERREUR.value, f"Erreur: {str(e)}"


class GenericScanner(BaseScanner):
    def __init__(self):
        super().__init__(None)

    def analyze(self, html_content: str, url: str | None = None) -> tuple[str, str]:
        logger.info("GenericScanner: Utilisation du scanner de secours.")
        return ScanStatus.ERREUR.value, MSG_UNSUPPORTED_MERCHANT
