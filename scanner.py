import logging
import os
import random
import time
from datetime import datetime, timezone
import httpx
import psycopg2
from psycopg2.extras import DictCursor

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
]

def get_next_batch(cur):
    query = """
        SELECT p.produit_id, p.url_wetall 
        FROM dim_produit p
        LEFT JOIN (
            SELECT produit_id, MAX(date_scan) as dernier_scan
            FROM fact_stock_status
            GROUP BY produit_id
        ) f ON p.produit_id = f.produit_id
        ORDER BY f.dernier_scan ASC NULLS FIRST
        LIMIT 30; -- 30 par run pour rester discret
    """
    cur.execute(query)
    return cur.fetchall()

def smart_scan(url):
    """Scan direct avec headers rotatifs et délais aléatoires."""
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "fr,fr-FR;q=0.8,en-US;q=0.5,en;q=0.3",
        "Referer": "https://www.google.com/",
    }
    
    # Délai aléatoire "humain" entre 3 et 7 secondes
    time.sleep(random.uniform(3, 7))
    
    try:
        with httpx.Client(headers=headers, follow_redirects=True, timeout=30.0) as client:
            resp = client.get(url)
            if resp.status_code == 200:
                # Logique simplifiée : si "rupture" est dans le texte, c'est mort
                status = "Rupture de stock" if "rupture" in resp.text.lower() else "OK"
                return status, 200, str(resp.url)
            return f"Erreur {resp.status_code}", resp.status_code, None
    except Exception as e:
        return f"Erreur: {str(e)[:15]}", 0, None

def run_pipeline():
    db_url = os.environ.get("DATABASE_URL")
    try:
        conn = psycopg2.connect(db_url, cursor_factory=DictCursor)
        conn.autocommit = True
        cur = conn.cursor()
        
        products = get_next_batch(cur)
        logger.info(f"Début du scan pour {len(products)} produits...")
        
        for row in products:
            status, code, final_url = smart_scan(row['url_wetall'])
            cur.execute("""
                INSERT INTO fact_stock_status (produit_id, date_scan, status_code, http_code_marchand, url_marchand_finale)
                VALUES (%s, %s, %s, %s, %s);
            """, (row['produit_id'], datetime.now(timezone.utc), status, code, final_url))
            logger.info(f"Produit {row['produit_id']} scanné : {status}")

        cur.close()
        conn.close()
        logger.info("Batch terminé.")
    except Exception as e:
        logger.error(f"Erreur Pipeline: {e}")