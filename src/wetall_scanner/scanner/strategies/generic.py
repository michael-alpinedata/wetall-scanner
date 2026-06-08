import logging
from .base import BaseScanner
from ..constants import ScanResult

logger = logging.getLogger(__name__)


class GenericScanner(BaseScanner):
    """Scanner de secours pour les marchands non implémentés."""

    def analyze(self, fetch_data: dict, url: str = "") -> ScanResult:
        # On surcharge volontairement analyze pour court-circuiter le flux
        logger.info("GenericScanner: Utilisation du scanner de secours.")
        return ScanResult.VENDEUR_NON_GERE

    # Méthodes factices requises par l'interface, mais jamais appelées grâce à l'override
    def is_blocked(self, soup, html):
        return False

    def is_out_of_stock(self, soup):
        return False

    def is_in_stock(self, soup):
        return False

    def has_valid_structure(self, soup):
        return True
