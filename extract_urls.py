import logging
import os
import sys
from bs4 import BeautifulSoup
import httpx
import psycopg2
from dotenv import load_dotenv

# 1. CONFIGURATION DU LOGGING
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

load_dotenv()

# URL du sitemap dédié aux produits
PRODUCT_SITEMAP_URL = "https://www.wetall.fr/product-sitemap.xml"


def clean_url_to_name(url):
    """Transforme le slug de l'URL en nom de produit lisible."""
    # Exemple: https://www.wetall.fr/produit/chaussures-geantes/ -> Chaussures Geantes
    slug = url.strip("/").split("/")[-1]
    name = slug.replace("-", " ").title()
    return name


def sync_sitemap_to_db():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        logger.error("DATABASE_URL manquante dans l'environnement.")
        return

    logger.info(f"Téléchargement du sitemap : {PRODUCT_SITEMAP_URL}")

    try:
        with httpx.Client(timeout=30.0) as client:
            # On récupère le XML
            response = client.get(PRODUCT_SITEMAP_URL)
            if response.status_code != 200:
                logger.error(
                    f"Erreur lors de la récupération du sitemap : {response.status_code}"
                )
                return

            # Utilisation de lxml (ou html.parser si lxml n'est pas installé)
            try:
                soup = BeautifulSoup(response.text, "xml")
            except:
                logger.warning("Parseur 'xml' non trouvé, repli sur 'html.parser'")
                soup = BeautifulSoup(response.text, "html.parser")

            # Extraction et filtrage strict des URLs
            # On ne garde que ce qui contient '/produit/' pour ignorer les images et autres bruits
            all_locs = [loc.text for loc in soup.find_all("loc")]
            product_urls = [url for url in all_locs if "/produit/" in url]

            if not product_urls:
                logger.warning("Aucune URL de type '/produit/' trouvée.")
                return

            logger.info(
                f"{len(product_urls)} produits réels identifiés sur {len(all_locs)} entrées au total."
            )

            # Connexion à Neon
            conn = psycopg2.connect(db_url)
            conn.autocommit = True
            cur = conn.cursor()

            new_count = 0
            for url in product_urls:
                nom_produit = clean_url_to_name(url)

                # UPSERT : On insère, si l'URL existe déjà, on ne fait rien
                cur.execute(
                    """
                    INSERT INTO dim_produit (url_wetall, nom_produit)
                    VALUES (%s, %s)
                    ON CONFLICT (url_wetall) DO NOTHING;
                """,
                    (url, nom_produit),
                )

                if cur.rowcount > 0:
                    new_count += 1

            cur.close()
            conn.close()

            logger.info(
                f"Synchronisation terminée : {new_count} nouveaux produits ajoutés en base."
            )

    except Exception as e:
        logger.error(f"Erreur durant la synchronisation : {e}")


if __name__ == "__main__":
    sync_sitemap_to_db()
