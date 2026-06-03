import os
import argparse
import logging
import httpx
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timezone
from dotenv import load_dotenv
from src.scanner.orchestrator import smart_scan

load_dotenv()

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

DEBUG_HTML_DIR = "debug_html_dumps"
os.makedirs(DEBUG_HTML_DIR, exist_ok=True)

# LA REQUÊTE QUE TU VOULEIS GARDER
_FETCH_FAILED_PRODUCTS_SQL = """
    SELECT p.produit_id, p.url_wetall, f.http_code_marchand
    FROM dim_produit p
    JOIN fact_stock_status f ON p.produit_id = f.produit_id
    WHERE f.http_code_marchand IN (403, 429, 500, 503, 0)
    AND p.is_active = TRUE
    ORDER BY f.date_scan ASC;
"""

_FETCH_FAILED_AMAZON_SQL = """
    SELECT p.produit_id, p.url_wetall, f.http_code_marchand
    FROM dim_produit p
    JOIN fact_stock_status f ON p.produit_id = f.produit_id
    WHERE f.http_code_marchand IN (403, 429, 500, 503)
    AND p.url_wetall LIKE '%amazon.%'
    AND p.is_active = TRUE
    ORDER BY f.date_scan ASC;
"""

def get_products_to_rescan():
    """Récupère uniquement les produits avec erreurs HTTP connues."""
    db_url = os.getenv("DATABASE_URL")
    with psycopg2.connect(db_url) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(_FETCH_FAILED_PRODUCTS_SQL)
            return cur.fetchall()

def update_product_status(pid, status_code, http_code_marchand, debug_info, url_marchand_finale):
    now_utc = datetime.now(timezone.utc)
    db_url = os.getenv("DATABASE_URL")
    query = """
        UPDATE fact_stock_status
        SET status_code = %s,
            http_code_marchand = %s,
            debug_info = %s,
            url_marchand_finale = %s,
            date_scan = %s
        WHERE produit_id = %s
    """
    with psycopg2.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(query, (status_code, http_code_marchand, debug_info, url_marchand_finale, now_utc, pid))
            conn.commit()

def main():
    # Plus besoin d'arguments start/end si on utilise la requête SQL fixe
    products = get_products_to_rescan()
    logger.info(f"🔍 {len(products)} produits en échec HTTP identifiés pour rescan.")

    with httpx.Client(timeout=30, follow_redirects=True) as client:
        for product in products:
            pid = product["produit_id"]
            url = product["url_wetall"]
            
            logger.info(f"--- Tentative de rescan ID {pid} (Erreur précédente: {product['http_code_marchand']}) ---")

            try:
                status, http_code, final_url, debug_info = smart_scan(client, url)
                update_product_status(pid, status, http_code, f"RETRY: {debug_info}", final_url)
                logger.info(f"✅ ID {pid} mis à jour : {status}")
            except Exception as e:
                logger.error(f"❌ Erreur critique sur ID {pid} : {e}")

if __name__ == "__main__":
    main()