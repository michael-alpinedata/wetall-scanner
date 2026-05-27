import logging
import os
import random
import time
from datetime import datetime, timezone
import httpx
import psycopg2
from psycopg2.extras import DictCursor
from bs4 import BeautifulSoup

# CONFIGURATION LOGGING
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0"
]

def smart_scan(client, url_wetall):
    """
    Scrapeur en 'Slow Mode' optimisé pour les gros volumes.
    """
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "fr,fr-FR;q=0.8,en-US;q=0.5,en;q=0.3",
        "Referer": "https://www.google.com/",
    }
    
    try:
        # --- ÉTAPE 1 : WETALL ---
        time.sleep(random.uniform(4, 8)) 
        resp_wetall = client.get(url_wetall, headers=headers)
        if resp_wetall.status_code != 200:
            return f"Erreur Wetall {resp_wetall.status_code}", resp_wetall.status_code, None

        soup = BeautifulSoup(resp_wetall.text, 'html.parser')
        buy_link = None

        # Extraction via formulaire (WooCommerce)
        btn = soup.find("button", class_="single_add_to_cart_button")
        if btn:
            form = btn.find_parent("form")
            if form and form.get("action"):
                buy_link = form.get("action")
        
        # Fallback lien /out/
        if not buy_link:
            for a in soup.find_all("a", href=True):
                if "/out/" in a["href"]:
                    buy_link = a["href"]
                    break

        if not buy_link:
            status = "Rupture de stock" if "en rupture" in resp_wetall.text.lower() else "Bouton non trouvé"
            return status, 200, None

        # Correction Amazon (liens relatifs)
        if buy_link.startswith('/dp/'):
            buy_link = f"https://www.amazon.fr{buy_link}"

        # --- ÉTAPE 2 : MARCHAND FINAL ---
        # On simule un temps de réflexion humain avant de cliquer
        time.sleep(random.uniform(12, 25)) 
        
        resp_marchand = client.get(buy_link, headers=headers)
        final_url = str(resp_marchand.url).lower()
        page_content = resp_marchand.text.lower()
        
        status = "OK"
        code = resp_marchand.status_code

        # Logique Marchands
        if code in [403, 401]:
            status = "Vérification bloquée (403)"
        elif code == 404:
            status = "Lien Brisé (404)"
        elif "decathlon" in final_url or "decathlon" in page_content:
            if any(x in page_content for x in ["indisponible", "rupture de stock", "en rupture"]):
                status = "Rupture de stock"
        elif "amazon" in final_url or "amazon" in page_content:
            markers_amazon = ["actuellement indisponible", "ne sais pas quand cet article sera de nouveau approvisionné"]
            if any(m in page_content for m in markers_amazon):
                status = "Rupture de stock"

        return status, code, final_url

    except Exception as e:
        logger.error(f"Erreur technique sur {url_wetall}: {e}")
        return "Erreur technique", 0, None

def run_pipeline():
    """Fonction principale gérant le batch de 250 produits."""
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        logger.error("DATABASE_URL manquante.")
        return

    try:
        conn = psycopg2.connect(db_url, cursor_factory=DictCursor)
        conn.autocommit = True
        cur = conn.cursor()

        # Récupération des 250 produits les moins récemment scannés
        cur.execute("""
            SELECT p.produit_id, p.url_wetall 
            FROM dim_produit p
            LEFT JOIN (
                SELECT produit_id, MAX(date_scan) as dernier_scan
                FROM fact_stock_status
                GROUP BY produit_id
            ) f ON p.produit_id = f.produit_id
            ORDER BY f.dernier_scan ASC NULLS FIRST
            LIMIT 250;
        """)
        products = cur.fetchall()

        if not products:
            logger.info("Aucun produit à scanner.")
            return

        logger.info(f"DÉMARRAGE BATCH NUIT : {len(products)} produits.")

        with httpx.Client(follow_redirects=True, timeout=60.0) as client:
            for i, row in enumerate(products, 1):
                p_id = row['produit_id']
                url_wetall = row['url_wetall']
                
                status, code, final_url = smart_scan(client, url_wetall)
                
                cur.execute("""
                    INSERT INTO fact_stock_status 
                    (produit_id, date_scan, status_code, http_code_marchand, url_marchand_finale)
                    VALUES (%s, %s, %s, %s, %s);
                """, (p_id, datetime.now(timezone.utc), status, code, final_url))
                
                if i % 10 == 0:
                    logger.info(f"Progression : {i}/{len(products)} produits traités.")
                
                # Petite pause entre chaque fiche produit pour la discrétion
                time.sleep(random.uniform(5, 12))

        cur.close()
        conn.close()
        logger.info("BATCH NUIT TERMINÉ.")

    except Exception as e:
        logger.error(f"Erreur run_pipeline: {e}")
