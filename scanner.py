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

def smart_scan(url_wetall):
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": "https://www.google.com/",
    }
    
    time.sleep(random.uniform(3, 7))
    
    try:
        with httpx.Client(headers=headers, follow_redirects=True, timeout=45.0) as client:
            # --- ÉTAPE A : REQUÊTE WETALL ---
            resp_wetall = client.get(url_wetall)
            if resp_wetall.status_code != 200:
                return f"Erreur Wetall {resp_wetall.status_code}", resp_wetall.status_code, None

            soup = BeautifulSoup(resp_wetall.text, 'html.parser')
            buy_link = None

            # --- ÉTAPE B : TA LOGIQUE D'EXTRACTION (FORM ACTION) ---
            # On cherche le bouton WooCommerce
            btn = soup.find("button", class_="single_add_to_cart_button")
            if btn:
                form = btn.find_parent("form")
                if form and form.get("action"):
                    buy_link = form.get("action")
            
            # Fallback 1 : Si pas de form, on cherche le lien direct avec /out/
            if not buy_link:
                for a in soup.find_all("a", href=True):
                    if "/out/" in a["href"]:
                        buy_link = a["href"]
                        break
            
            # Fallback 2 : Bouton externe classique
            if not buy_link:
                btn_alt = soup.find('a', class_='single_add_to_cart_button')
                if btn_alt:
                    buy_link = btn_alt.get('href')

            if not buy_link:
                status = "Rupture de stock" if "rupture" in resp_wetall.text.lower() else "Bouton non trouvé"
                return status, 200, None

            logger.info(f"Lien marchand identifié : {buy_link[:60]}...")

            # --- ÉTAPE C : SUIVI DU LIEN MARCHAND ---
            time.sleep(random.uniform(2, 4))
            # On suit les redirections pour arriver sur Decathlon/Amazon/etc.
            resp_marchand = client.get(buy_link)
            
            final_url = str(resp_marchand.url).lower()
            page_content = resp_marchand.text.lower()
            
            # --- ÉTAPE D : TA LOGIQUE MÉTIER (DECATHLON / AMAZON) ---
            status, code = "OK", resp_marchand.status_code

            if code in [403, 401]:
                status = "Vérification bloquée (403)"
            elif code == 404:
                status = "Lien Brisé (404)"
            
            # Analyse spécifique par marchand (comme dans ton script)
            elif "decathlon" in final_url or "decathlon" in page_content:
                if any(x in page_content for x in ["indisponible", "rupture de stock", "en rupture"]):
                    status = "Rupture de stock"
            
            elif "amazon" in final_url or "amazon" in page_content:
                markers_amazon = ["actuellement indisponible", "ne sais pas quand cet article sera de nouveau approvisionné"]
                if any(m in page_content for m in markers_amazon):
                    status = "Rupture de stock"

            return status, code, final_url

    except Exception as e:
        logger.error(f"Erreur technique sur {url_wetall} : {e}")
        return f"Erreur: {str(e)[:15]}", 0, None
