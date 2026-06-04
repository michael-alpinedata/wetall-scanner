import logging
from .database import DatabaseManager
from .http_client import HTTPClient
from .strategies import AmazonScanner, DecathlonScanner, GenericScanner

# Configuration du logger pour le module orchestrator
logger = logging.getLogger(__name__)

class ScannerOrchestrator:
    """
    Chef d'orchestre du processus de scan.
    Lie la base de données, le client HTTP et les stratégies d'analyse.
    """

    # Mapping entre le nom du vendeur en DB et la classe de stratégie
    STRATEGY_MAP = {
        "amazon": AmazonScanner(),
        "decathlon": DecathlonScanner(),
    }

    def __init__(self):
        self.db = DatabaseManager()
        self.http = HTTPClient()
        self.default_strategy = GenericScanner()
        logger.debug("ScannerOrchestrator initialisé avec ses sous-composants.")

    def _get_strategy(self, vendor_name: str):
        """Récupère la stratégie correspondante ou le scanner générique."""
        if not vendor_name:
            logger.debug("Nom de vendeur absent, utilisation de la stratégie par défaut.")
            return self.default_strategy
        
        strategy = self.STRATEGY_MAP.get(vendor_name.lower())
        if strategy:
            return strategy
        
        logger.debug(f"Aucune stratégie spécifique trouvée pour '{vendor_name}', passage au GenericScanner.")
        return self.default_strategy

    def run_scan(self, vendor: str | None = None, limit: int = 10):
        """
        Exécute un cycle complet de scan pour un lot de produits.
        
        Args:
            vendor (str | None): Filtrer par vendeur si spécifié.
            limit (int): Nombre de produits à traiter dans ce lot.
        """
        # 1. Récupération des cibles
        products = self.db.get_products_to_scan(vendor=vendor, limit=limit)
        logger.info(f"Début du cycle de scan pour {len(products)} produits.")

        for product in products:
            p_id = product['produit_id']
            # On privilégie l'URL Wetall car elle gère la redirection vers le marchand
            url_to_fetch = product['url_wetall']
            vendor_name = product['nom_vendeur']

            logger.info(f"Traitement du produit {p_id} ({vendor_name})...")

            # 2. Récupération du contenu (Le "Bras")
            fetch_data = self.http.fetch(url_to_fetch)
            
            # 3. Choix et exécution de l'analyse (Le "Cerveau")
            strategy = self._get_strategy(vendor_name)
            
            # Si le client HTTP a échoué (ex: 404), on adapte le statut
            if fetch_data['status_code'] == 404:
                status_code, debug_info = "Lien Brisé", "Page non trouvée (404)"
                logger.warning(f"Produit {p_id} : Lien marchand brisé (404).")
            elif fetch_data['error']:
                status_code, debug_info = "Erreur technique", fetch_data['error']
                logger.error(f"Produit {p_id} : Échec de récupération - {fetch_data['error']}")
            else:
                # Analyse du HTML par la stratégie dédiée
                status_code, debug_info = strategy.analyze(fetch_data['html'])

            # 4. Persistance des résultats (La "Mémoire")
            try:
                self.db.save_scan_result(
                    product_id=p_id,
                    status_code=status_code,
                    http_code=fetch_data['status_code'],
                    url_finale=fetch_data['url_finale'],
                    debug_info=debug_info
                )
                logger.info(f"Produit {p_id} terminé. Statut: {status_code} | Info: {debug_info}")
            except Exception:
                logger.exception(f"Erreur critique lors de la sauvegarde du produit {p_id}.")

        logger.info(f"Cycle de scan terminé. {len(products)} produits traités.")