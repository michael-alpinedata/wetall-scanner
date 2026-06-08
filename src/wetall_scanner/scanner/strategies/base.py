from abc import ABC, abstractmethod
import logging
from bs4 import BeautifulSoup

from ..constants import ScanResult

logger = logging.getLogger(__name__)


class BaseScanner(ABC):
    """Interface de base avec le pattern Template Method."""

    def analyze(self, fetch_data: dict, url: str = "") -> ScanResult:
        """Le flux standard d'analyse. Prend le dict entier du fetch."""
        html_content = fetch_data.get("html", "")
        status_code = fetch_data.get("status_code", 0)

        # 1. Erreur 404 (Priorité absolue, même si le HTML reçu est vide)
        if status_code == 404 or self.is_404(html_content):
            return ScanResult.PAGE_404

        # 2. Validation technique de base
        if not html_content or len(html_content) < 100:
            return ScanResult.HTML_EMPTY

        soup = BeautifulSoup(html_content, "html.parser")

        # 3. Validation Sécurité / Blocages
        # (Se fait ICI, car un blocage antibot renvoie souvent un code 403 ou 429)
        if self.is_blocked(soup, html_content):
            return ScanResult.BLOQUE_CAPTCHA

        # 4. Gestion des autres erreurs réseaux (500, 502, 503...)
        if status_code != 200:
            return ScanResult.ERREUR_RESEAU

        # 5. Détection Rupture
        if self.is_out_of_stock(soup):
            return ScanResult.HORS_STOCK

        # 6. Vérification de la structure (Le Gardien)
        if not self.has_valid_structure(soup):
            logger.warning(f"Structure suspecte pour {url}.")
            self._dump_if_suspicious(
                url, html_content, reason="missing_title_structural_check"
            )
            return ScanResult.STRUCT_TITLE_MISSING

        # 7. Validation de stock positif
        if self.is_in_stock(soup):
            return ScanResult.EN_STOCK

        return ScanResult.A_VERIFIER

    def _dump_if_suspicious(self, url: str, html: str, reason: str):
        try:
            from wetall_scanner.scanner.utils.html_inspector import dump_suspicious_html

            dump_suspicious_html(url, html, reason=reason)
        except ImportError:
            pass

    # --- Hooks que les enfants doivent implémenter ---
    def is_404(self, html: str) -> bool:
        return False  # Optionnel, par défaut False

    @abstractmethod
    def is_blocked(self, soup: BeautifulSoup, html: str) -> bool:
        pass

    @abstractmethod
    def is_out_of_stock(self, soup: BeautifulSoup) -> bool:
        pass

    @abstractmethod
    def is_in_stock(self, soup: BeautifulSoup) -> bool:
        pass

    @abstractmethod
    def has_valid_structure(self, soup: BeautifulSoup) -> bool:
        pass
