import logging
import os
import random
import time
from datetime import datetime, timezone
import httpx
import psycopg2
from psycopg2.extras import DictCursor
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
]

def smart_scan(client, url_wetall):
    """Logique d'extraction du lien marchand et vérification du stock."""
    try:
        # 1. Requête sur la page produit Wetall
        time.sleep(random.uniform(2, 4))
        resp_wetall = client.get(url_wetall)
        if resp_wetall.status_code != 200:
            return f"Erreur Wetall {resp_wetall.status_code}", resp_wetall.status_code, None

        soup = BeautifulSoup(resp_wetall.text, 'html.parser')
        buy_link = None

        # Extraction via le formulaire (ta logique fiable)
        btn = soup.find("button", class_="single_add_to_cart_button")
        if btn:
            form = btn.find_parent("form")
            if form and form.get("action"):
                buy_link = form.get("action")
        
        # Fallbacks
        if not buy_link:
            for a in soup.find_all("a", href=True):
                if "/out/" in a["href"]:
                    buy_link = a["href"]
                    break

        if not buy_link:
            status = "Rupture de stock" if "rupture" in resp_wetall.text.lower() else "Bouton non trouvé"
            return status, 200, None

        # 2. Suivi du lien vers le marchand
        time.sleep(random.uniform(1, 3))
        resp_marchand = client.get(buy_link)
        final_url = str(resp_marchand.url).lower()
        page_content = resp_marchand.text.lower()
        
        status = "OK"
        code = resp_marchand.status_code

        # Logique métier par marchand
        if "decathlon" in final_url or "decathlon" in page_content:
            if any(x in page_content for x in ["indisponible", "rupture de stock", "en rupture"]):
                status = "Rupture de stock"
        elif "amazon" in final_url or "amazon" in page_content:
            if any(m in page_content for m in ["actuellement indisponible", "reapprovisionne"]):
                status = "Rupture de stock"

        return status, code, final_url

    except Exception as e:
        logger.error(f"Erreur smart_scan sur {url_wetall}: {e}")
        return f"Erreur technique", 0, None

def run_pipeline():
    """Boucle principale appelée par FastAPI."""
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        logger.error("DATABASE_URL manquante")
        return

    try:
        conn = psycopg2.connect(db_url, cursor_factory=DictCursor)
        conn.autocommit = True
        cur = conn.cursor()

        # Récupération des 30 produits les plus anciens à scanner
        cur.execute("""
            SELECT p.produit_id, p.url_wetall 
            FROM dim_produit p
            LEFT JOIN (
                SELECT produit_id, MAX(date_scan) as dernier_scan
                FROM fact_stock_status
                GROUP BY produit_id
            ) f ON p.produit_id = f.produit_id
            ORDER BY f.dernier_scan ASC NULLS FIRST
            LIMIT 30;
        """)
        products = cur.fetchall()

        if not products:
            logger.info("Aucun produit à scanner.")
            return

        logger.info(f"Début du batch pour {len(products)} produits...")

        headers = {"User-Agent": random.choice(USER_AGENTS), "Referer": "https://www.google.com/"}
        
        with httpx.Client(headers=headers, follow_redirects=True, timeout=45.0) as client:
            for row in products:
                p_id = row['produit_id']
                url = row['url_wetall']
                
                status, code, final_url = smart_scan(client, url)
                
                cur.execute("""
                    INSERT INTO fact_stock_status (produit_id, date_scan, status_code, http_code_marchand, url_marchand_finale)
                    VALUES (%s, %s, %s, %s, %s);
                """, (p_id, datetime.now(timezone.utc), status, code, final_url))
                
                logger.info(f"Produit {p_id} scanné : {status}")

        cur.close()
        conn.close()
        logger.info("Fin du pipeline.")

    except Exception as e:
        logger.error(f"Erreur run_pipeline: {e}")
