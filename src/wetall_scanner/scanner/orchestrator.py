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

    def __init__(
        self, db: DatabaseManager, http: HTTPClient, extractor: WetallExtractor
    ):
        self.db = db
        self.http = http
        self.extractor = extractor
        self.default_strategy = GenericScanner()
        logger.debug("ScannerOrchestrator initialisé avec ses sous-composants.")

    def _get_strategy(self, vendor_name: str):
        """Récupère la stratégie correspondante ou le scanner générique."""
        if not vendor_name:
            logger.debug(
                "Nom de vendeur absent, utilisation de la stratégie par défaut."
            )
            return self.default_strategy

        strategy = self.STRATEGY_MAP.get(vendor_name.lower())
        if strategy:
            return strategy

        logger.debug(
            f"Aucune stratégie spécifique trouvée pour '{vendor_name}', passage au GenericScanner."
        )
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
        """
        Phase 2 : Surveillance.
        Vérifie le stock sur les URLs marchandes déjà connues.
        Possibilité de cibler un `product_id` précis.
        """
        products = self.db.get_products_to_monitor(
            vendor=vendor, limit=limit, product_id=product_id
        )
        logger.info(f"Début monitoring pour {len(products)} produit(s).")

        results = []
        for p in products:
            p_id = p["produit_id"]
            target_url = p["url_marchand_finale"]
            vendeur = p["nom_vendeur"]

            # Correction : Appel de la méthode interne _get_strategy
            strategy = self._get_strategy(vendeur)

            # 1. Tentative Standard (Rapide, via httpx)
            fetch_data = self.http.fetch(target_url)

            # 2. Détection du blocage réseau frontal (ex: Cloudflare 403 sur Decathlon)
            # Correction : Utilisation de "status_code" au lieu de "status"
            if fetch_data["status_code"] in [403, 405, 407]:
                logger.warning(
                    f"Blocage HTTP {fetch_data['status_code']} détecté sur {vendeur}. Bascule en Stealth Mode..."
                )
                fetch_data = self.http.fetch_stealth(target_url)

            # Analyse via la stratégie
            status_code, debug_info = strategy.analyze(
                fetch_data["html"], url=target_url
            )

            # 3. Détection du Soft-Block (ex: Captcha Amazon détecté par la stratégie)
            if status_code == "ERREUR_TECHNIQUE" and "Captcha" in debug_info:
                logger.warning(
                    f"Soft-Block Amazon détecté pour {p_id}. Seconde tentative en Stealth Mode..."
                )
                fetch_data = self.http.fetch_stealth(target_url)
                # On relance l'analyse sur le HTML propre (en croisant les doigts)
                status_code, debug_info = strategy.analyze(
                    fetch_data["html"], url=target_url
                )

            # Sauvegarde du résultat (Historisation)
            self.db.save_scan_result(
                product_id=p_id,
                status_code=status_code,
                http_code=fetch_data["status_code"],
                url_finale=target_url,  # Correction : Utilisation de target_url
                debug_info=debug_info,
            )
            results.append({"produit_id": p_id, "status": status_code})

            logger.info(f"Produit {p_id} terminé avec statut: {status_code}")

        return results
