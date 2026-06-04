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

    def __init__(self, db: DatabaseManager, http: HTTPClient):
        self.db = db              
        self.http = http
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

    def run_link_discovery(self, limit: int = 10):
        """
        Phase 1 : Enrichissement. 
        Trouve l'URL finale marchande pour les produits qui ne l'ont pas encore.
        """
        # On suppose une méthode en DB qui filtre : WHERE url_marchand_finale IS NULL
        products = self.db.get_products_to_discover(limit=limit)
        logger.info(f"Début discovery pour {len(products)} produits.")

        for p in products:
            p_id = p['produit_id']
            # On appelle l'URL Wetall qui va nous rediriger
            fetch_data = self.http.fetch(p['url_wetall'])
            
            final_url = fetch_data['url_finale']
            
            # Vérification : est-ce qu'on a bien atterri chez un marchand ?
            if "wetall.fr" not in final_url and fetch_data['status_code'] == 200:
                logger.info(f"Lien découvert pour {p_id} : {final_url}")
                # On met à jour uniquement l'URL dans la dimension produit
                self.db.update_product_merchant_url(p_id, final_url)
            else:
                logger.warning(f"Échec discovery pour {p_id} (toujours sur Wetall ou erreur {fetch_data['status_code']})")

    def run_stock_monitoring(self, vendor: str | None = None, limit: int = 10):
        """
        Phase 2 : Surveillance.
        Vérifie le stock sur les URLs marchandes déjà connues.
        """
        # On filtre : WHERE url_marchand_finale IS NOT NULL
        products = self.db.get_products_to_monitor(vendor=vendor, limit=limit)
        logger.info(f"Début monitoring pour {len(products)} produits.")

        results = []
        for p in products:
            p_id = p['produit_id']
            # ICI : On utilise l'URL finale, plus l'URL Wetall
            url_to_scan = p['url_marchand_finale']
            
            fetch_data = self.http.fetch(url_to_scan)
            strategy = self._get_strategy(p['nom_vendeur'])

            if fetch_data['status_code'] == 404:
                status_code, debug_info = "Lien Brisé", "Page 404"
            elif fetch_data['error']:
                status_code, debug_info = "Erreur", fetch_data['error']
            else:
                status_code, debug_info = strategy.analyze(fetch_data['html'])

            # Sauvegarde du résultat (Historisation)
            self.db.save_scan_result(
                product_id=p_id,
                status_code=status_code,
                http_code=fetch_data['status_code'],
                url_finale=url_to_scan,
                debug_info=debug_info
            )
            results.append({"produit_id": p_id, "status": status_code})

            logger.info(f"Produit {p_id} terminé")
        return results