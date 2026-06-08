import logging
from .database import DatabaseManager
from .http_client import HTTPClient
from .strategies import AmazonScanner, DecathlonScanner, GenericScanner
from .extractor import WetallExtractor

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

    def __init__(self, db: DatabaseManager, http: HTTPClient, extractor:WetallExtractor):
        self.db = db              
        self.http = http
        self.extractor = extractor
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

    def run_link_discovery(self, limit: int = 10, product_id: int | None = None):
        """
        Phase 1 : Enrichissement. 
        Trouve l'URL finale marchande pour les produits qui ne l'ont pas encore.
        Possibilité de cibler un `product_id` précis (ex: pour les smoke tests).
        """
        products = self.db.get_products_to_discover(limit=limit, product_id=product_id)
        logger.info(f"Début discovery pour {len(products)} produit(s).")

        for p in products:
            p_id = p['produit_id']
            fetch_data = self.http.fetch(p['url_wetall'])
            
            if fetch_data['status_code'] != 200:
                logger.error(
                    f"Échec discovery pour {p_id} : impossible de joindre l'URL Wetall "
                    f"(Status: {fetch_data['status_code']})"
                )
                continue

            final_url = fetch_data['url_finale']
            
            # L'orchestrateur délègue le travail de parsing à l'extracteur
            if "wetall.fr" in final_url:
                html_content = fetch_data.get('text') or fetch_data.get('content') or ""
                extracted_url = self.extractor.extract_buy_link(html_content)
                
                if extracted_url:
                    if "wetall.fr/go/" in extracted_url or "wetall.fr/out/" in extracted_url:
                        go_fetch = self.http.fetch(extracted_url)
                        if go_fetch['status_code'] == 200:
                            final_url = go_fetch['url_finale']
                    else:
                        final_url = extracted_url

            if "wetall.fr" not in final_url:
                logger.info(f"Lien découvert pour {p_id} : {final_url}")
                self.db.update_product_merchant_url(p_id, final_url)
            else:
                logger.warning(f"Échec discovery pour {p_id}")

    def run_stock_monitoring(self, vendor: str | None = None, limit: int = 10, product_id: int | None = None):
        """
        Phase 2 : Surveillance.
        Vérifie le stock sur les URLs marchandes déjà connues.
        Possibilité de cibler un `product_id` précis.
        """
        # Note : Pense à ajouter `product_id: int | None = None` dans la signature 
        # de db.get_products_to_monitor si tu veux aussi pouvoir cibler le monitoring.
        products = self.db.get_products_to_monitor(vendor=vendor, limit=limit, product_id=product_id)
        logger.info(f"Début monitoring pour {len(products)} produit(s).")

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