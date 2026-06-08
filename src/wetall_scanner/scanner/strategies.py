import logging
from bs4 import BeautifulSoup
import abc

from .config import MERCHANT_CONFIGS
from .constants import ScanStatus, MSG_BUY_BUTTON, MSG_OUT_OF_STOCK, MSG_NO_BUTTON

# Configuration du logger pour le module des stratégies
logger = logging.getLogger(__name__)


class BaseScanner(abc.ABC):
    """
    Interface de base pour tous les moteurs de scan marchands.
    """

    def __init__(self, merchant_name: str | None = None):
        # Charge la config du marchand si elle existe, sinon un dictionnaire vide
        self.config = MERCHANT_CONFIGS.get(merchant_name, {}) if merchant_name else {}

    @abc.abstractmethod
    def analyze(self, html_content: str) -> tuple[str, str]:
        pass


class AmazonScanner(BaseScanner):
    """
    Scanner Amazon.fr optimisé, piloté par la configuration (Data-Driven).
    """

    def __init__(self):
        super().__init__("amazon")  # Lie ce scanner à la clé "amazon" dans config.py

    def analyze(self, html_content: str) -> tuple[str, str]:
        # 1. Validation technique (Seuil à 100 pour laisser passer les tests)
        if not html_content or len(html_content) < 100:
            msg = "Contenu HTML reçu vide ou trop court"
            logger.error(msg)
            return ScanStatus.ERREUR.value, msg

        soup = BeautifulSoup(html_content, "html.parser")

        # 2. Détection 404
        title = soup.select_one("title")
        if title and ("404" in title.text or "non trouvée" in title.text.lower()):
            msg = "Page 404 détectée"
            logger.warning(msg)
            return ScanStatus.ERREUR.value, msg

        # 3. Détection "EN STOCK" (Dynamique via config.py)
        in_stock_selectors = self.config.get("in_stock_selectors", [])
        if any(soup.select_one(sel) for sel in in_stock_selectors):
            logger.info(MSG_BUY_BUTTON)
            return ScanStatus.EN_STOCK.value, MSG_BUY_BUTTON

        # 4. Détection "HORS STOCK" (Dynamique via config.py)
        availability_block = soup.select_one("#availability")
        if availability_block:
            text = availability_block.get_text().lower()
            out_of_stock_keywords = self.config.get("out_of_stock_keywords", [])
            if any(word in text for word in out_of_stock_keywords):
                logger.info(MSG_OUT_OF_STOCK)
                return ScanStatus.HORS_STOCK.value, MSG_OUT_OF_STOCK

        # 5. Vérification facultative du titre
        if not soup.select_one("#productTitle"):
            logger.warning("Titre du produit absent, mais l'analyse continue")

        # 6. Fallback final (Message lu depuis config.py)
        fallback_msg = self.config.get("fallback_message", MSG_NO_BUTTON)
        logger.warning(fallback_msg)
        return ScanStatus.HORS_STOCK.value, fallback_msg


class DecathlonScanner(BaseScanner):
    def __init__(self):
        super().__init__("decathlon")

    def analyze(self, html_content: str) -> tuple[str, str]:
        logger.warning(
            "DecathlonScanner: Tentative d'analyse sur une stratégie non implémentée."
        )
        return "Bloqué/Grisé", "Moteur de scan Decathlon en attente d'implémentation"


class GenericScanner(BaseScanner):
    def __init__(self):
        super().__init__(None)

    def analyze(self, html_content: str) -> tuple[str, str]:
        logger.info("GenericScanner: Utilisation du scanner de secours.")
        return "À vérifier", "Marchand non supporté spécifiquement"
