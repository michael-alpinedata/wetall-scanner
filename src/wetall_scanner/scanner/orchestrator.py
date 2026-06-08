import time
import random
import logging
from .database import DatabaseManager
from .http_client import HTTPClient
from .extractor import WetallExtractor
from .strategies import ScannerFactory

# Configuration du logger pour le module orchestrator
logger = logging.getLogger(__name__)


class ScannerOrchestrator:
    """
    Chef d'orchestre du processus de scan.
    Lie la base de données, le client HTTP et les stratégies d'analyse.
    """

    def __init__(
        self, db: DatabaseManager, http: HTTPClient, extractor: WetallExtractor
    ):
        self.db = db
        self.http = http
        self.extractor = extractor
        logger.debug("ScannerOrchestrator initialisé avec ses sous-composants.")

    def run_link_discovery(self, limit: int = 10, product_id: int | None = None):
        """
        Phase 1 : Enrichissement.
        Trouve l'URL finale marchande pour les produits qui ne l'ont pas encore.
        Possibilité de cibler un `product_id` précis (ex: pour les smoke tests).
        """
        products = self.db.get_products_to_discover(limit=limit, product_id=product_id)
        logger.info(f"Début discovery pour {len(products)} produit(s).")

        for p in products:
            p_id = p["produit_id"]
            fetch_data = self.http.fetch(p["url_wetall"])

            if fetch_data["status_code"] != 200:
                logger.error(
                    f"Échec discovery pour {p_id} : impossible de joindre l'URL Wetall (Status: {fetch_data['status_code']})"
                )
                continue

            final_url = fetch_data["url_finale"]

            if "wetall.fr" in final_url:
                # 1. L'extracteur extrait le lien de manière agnostique
                extracted_url = self.extractor.extract_from_fetch_data(fetch_data)

                if extracted_url:
                    # 2. L'extracteur valide s'il faut faire un second fetch de rebond
                    if self.extractor.is_internal_redirect(extracted_url):
                        go_fetch = self.http.fetch(extracted_url)
                        if go_fetch["status_code"] == 200:
                            final_url = go_fetch["url_finale"]
                    else:
                        final_url = extracted_url

            # Validation finale et sauvegarde
            if "wetall.fr" not in final_url:
                logger.info(f"Lien découvert pour {p_id} : {final_url}")

                # 1. Extraction dynamique du nom du vendeur
                nom_vendeur = self.extractor.extract_merchant_name(final_url)

                # 2. Sauvegarde combinée (1 seule requête SQL, 1 seule connexion Neon)
                self.db.update_product_discovery_results(p_id, final_url, nom_vendeur)
            else:
                logger.warning(f"Échec discovery pour {p_id}")

    def run_stock_monitoring(
        self, vendor: str | None = None, limit: int = 10, product_id: int | None = None
    ):
        """Phase 2 : Surveillance par lot (utilise run_single_scan)."""
        # On utilise ta méthode de sélection optimisée
        products = self.db.get_products_to_monitor(
            limit=limit, vendor=vendor, prioritize_errors=True
        )

        logger.info(f"Début monitoring pour {len(products)} produit(s).")

        results = []
        for p in products:
            # On délègue tout à la méthode unitaire
            result = self.run_single_scan(p["produit_id"])
            results.append({"produit_id": p["produit_id"], "status": result.code})

            # La pause reste ici car elle concerne la gestion du flux de batch
            time.sleep(random.uniform(2, 5))

        return results

    def run_single_scan(self, product_id: int):
        """Exécute le cycle de vie complet pour UN seul produit."""
        # 1. Récupérer les infos du produit
        product = self.db.get_product_by_id(product_id)
        if not product:
            logger.error(f"Produit {product_id} non trouvé en base.")
            return

        target_url = product["url_marchand_finale"]
        vendeur = product["nom_vendeur"]

        # 2. Fetch
        if vendeur in ["amazon", "decathlon"]:
            fetch_data = self.http.fetch_stealth(target_url)
        else:
            fetch_data = self.http.fetch(target_url)

        # 3. Analyse
        scanner = ScannerFactory.get_scanner(vendeur)
        scan_result = scanner.analyze(fetch_data, url=target_url)

        # 4. Sauvegarde
        self.db.save_scan_result(
            product_id=product_id,
            status_code=scan_result.code,
            http_code=fetch_data.get("status_code", 0),
            url_finale=fetch_data.get("url_finale", target_url),
            debug_info=scan_result.message,
        )
        return scan_result

    def run_batch(self, limit=50, vendor=None, prioritize_errors=True):
        """Boucle de batch qui utilise run_single_scan."""
        produits = self.db.get_products_to_monitor(
            limit=limit, vendor=vendor, prioritize_errors=prioritize_errors
        )

        results = []
        for p in produits:
            # Utilisation de la méthode unitaire
            res = self.run_single_scan(p["produit_id"])
            results.append(res)

            # Anti-ban
            time.sleep(random.uniform(2, 5))

        return results
