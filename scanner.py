import logging
import os
import random
import time
from datetime import datetime, timezone

import httpx
import psycopg2
from bs4 import BeautifulSoup
from psycopg2.extras import DictCursor

NB_PRODUCT_SCANNED = 250

# CONFIGURATION LOGGING
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 "
    "Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
]


def get_buy_link_from_wetall(soup):
    """Extrait le lien marchand depuis la soupe HTML de Wetall."""
    # Stratégie A : Bouton d'achat
    btn = soup.find("button", class_="single_add_to_cart_button")
    if btn:
        form = btn.find_parent("form")
        if form and form.get("action"):
            return form.get("action"), "Lien via formulaire"

    # Stratégie B : Liens /out/
    out_links = [
        a["href"] for a in soup.find_all("a", href=True) if "/out/" in a["href"]
    ]
    if out_links:
        return out_links[0], "Lien via fallback /out/"

    return None, None


def normalize_amazon_url(url):
    """Corrige les URLs Amazon relatives ou tronquées."""
    url = url.strip()
    if url.startswith("/"):
        return f"https://www.amazon.fr{url}"
    if url.startswith("dp/"):
        return f"https://www.amazon.fr/{url}"
    return url


def fetch_with_fallback(client, url, headers):
    """Effectue la requête avec un fallback vers curl_cffi si bloqué."""
    # 1er essai
    resp = client.get(url, headers=headers)

    # Fallback pour les cibles dures
    if resp.status_code in [403, 401] and any(
        t in url.lower() for t in ["decathlon", "alltricks"]
    ):
        try:
            from curl_cffi import requests as curl_requests

            resp_curl = curl_requests.get(
                url, headers=headers, impersonate="chrome", timeout=30
            )
            return resp_curl
        except Exception as e:
            logger.error(f"Fallback curl_cffi échoué: {e}")

    return resp


def analyze_merchant_status(url, html):
    """Applique les règles métier de détection de stock par marchand."""
    url, html = url.lower(), html.lower()

    if "nike" in url or "nike" in html:
        if any(x in html for x in ["plus disponible", "indisponible", "rupture"]):
            return "Rupture de stock", "Nike : Rupture détectée"

    elif "decathlon" in url or "decathlon" in html:
        if any(x in html for x in ["indisponible", "rupture", "en rupture"]):
            return "Rupture de stock", "Decathlon : Rupture détectée"

    elif "amazon" in url or "amazon" in html:
        if "n'est pas une page fonctionnelle" in html:
            return "Lien Mort (404 déguisé)", "Amazon : 404 déguisée"
        if any(
            m in html for m in ["actuellement indisponible", "nouveau approvisionné"]
        ):
            return "Rupture de stock", "Amazon : Rupture détectée"

    return "OK", "Scan réussi"


# --- LA FONCTION PRINCIPALE DEVIENT UN ORCHESTRATEUR ---
def smart_scan(client, url_wetall):
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": "https://www.google.com/",
    }

    try:
        # ÉTAPE 1 : WETALL
        time.sleep(random.uniform(4, 7))
        resp_wetall = client.get(url_wetall, headers=headers)
        if resp_wetall.status_code != 200:
            return (
                f"Erreur Wetall {resp_wetall.status_code}",
                resp_wetall.status_code,
                None,
                "Fail Wetall",
            )

        soup = BeautifulSoup(resp_wetall.text, "html.parser")
        buy_link, debug_msg = get_buy_link_from_wetall(soup)

        # Cas particuliers Wetall (variations / rupture)
        if not buy_link:
            if soup.find("form", class_="variations_form"):
                return "Variations (Taille/Couleur)", 200, None, "Structure variations"
            if "en rupture" in resp_wetall.text.lower():
                return "Rupture de stock", 200, None, "Marqueur rupture Wetall"
            return "Bouton non trouvé", 200, None, "Aucun lien extrait"

        # ÉTAPE 2 : NORMALISATION & MARCHAND FINAL
        buy_link = normalize_amazon_url(buy_link)

        logger.info(f"Scan marchand : {buy_link[:40]}...")
        time.sleep(random.uniform(12, 22))

        resp_m = fetch_with_fallback(client, buy_link, headers)

        # ÉTAPE 3 : ANALYSE FINALE
        if resp_m.status_code in [403, 401]:
            return (
                "Vérification bloquée (403)",
                resp_m.status_code,
                str(resp_m.url),
                "Pare-feu marchand",
            )
        if resp_m.status_code == 404:
            return "Lien Brisé (404)", 404, str(resp_m.url), "Erreur 404 serveur"

        status, msg = analyze_merchant_status(str(resp_m.url), resp_m.text)
        return status, resp_m.status_code, str(resp_m.url), msg

    except Exception as e:
        return "Erreur technique", 0, None, f"Exception: {str(e)[:50]}"


def run_pipeline():
    """Fonction principale pour le traitement de nuit (NB_PRODUCT_SCANNED produits)."""
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        logger.error("La variable d'environnement DATABASE_URL est manquante.")
        return

    try:
        conn = psycopg2.connect(db_url, cursor_factory=DictCursor)
        conn.autocommit = True
        cur = conn.cursor()

        # Récupération des NB_PRODUCT_SCANNED fiches les plus anciennes
        # ou jamais scannées
        cur.execute(
            """
            SELECT p.produit_id, p.url_wetall 
            FROM dim_produit p
            LEFT JOIN (
                SELECT produit_id, MAX(date_scan) as dernier_scan
                FROM fact_stock_status
                GROUP BY produit_id
            ) f ON p.produit_id = f.produit_id
            ORDER BY f.dernier_scan ASC NULLS FIRST
            LIMIT %s;
        """,
            (NB_PRODUCT_SCANNED,),
        )
        products = cur.fetchall()

        if not products:
            logger.info("Aucun produit en attente de traitement.")
            return

        logger.info(f"DÉMARRAGE DU BATCH DE NUIT : {len(products)} produits ciblés.")

        with httpx.Client(follow_redirects=True, timeout=60.0) as client:
            for i, row in enumerate(products, 1):
                p_id = row["produit_id"]
                url_wetall = row["url_wetall"]

                # Exécution du scan avec récupération du diagnostic
                status, code, final_url, debug_msg = smart_scan(client, url_wetall)

                # Insertion propre dans la table de faits
                cur.execute(
                    """
                    INSERT INTO fact_stock_status 
                    (produit_id, date_scan, status_code, http_code_marchand, 
                    url_marchand_finale, debug_info)
                    VALUES (%s, %s, %s, %s, %s, %s);
                """,
                    (
                        p_id,
                        datetime.now(timezone.utc),
                        status,
                        code,
                        final_url,
                        debug_msg,
                    ),
                )

                if i % 10 == 0:
                    logger.info(f"Progression : {i}/{len(products)} fiches traitées.")

                # Temporisation de sécurité pour ne pas saturer la passerelle
                time.sleep(random.uniform(5, 12))

        cur.close()
        conn.close()
        logger.info("FIN DU BATCH DE NUIT. Données disponibles pour le Dashboard.")

    except Exception as e:
        logger.error(f"Échec critique du pipeline : {e}")


if __name__ == "__main__":
    run_pipeline()
