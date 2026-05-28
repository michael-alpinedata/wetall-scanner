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
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
]


def smart_scan(client, url_wetall):
    """
    Scrapeur chirurgical avec diagnostic intégré (debug_info)
    """
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "fr,fr-FR;q=0.8,en-US;q=0.5,en;q=0.3",
        "Referer": "https://www.google.com/",
    }

    debug_msg = "Début du scan"

    try:
        # --- ÉTAPE 1 : WETALL ---
        time.sleep(random.uniform(4, 7))
        resp_wetall = client.get(url_wetall, headers=headers)

        if resp_wetall.status_code != 200:
            return (
                f"Erreur Wetall {resp_wetall.status_code}",
                resp_wetall.status_code,
                None,
                f"Code HTTP Wetall: {resp_wetall.status_code}",
            )

        soup = BeautifulSoup(resp_wetall.text, "html.parser")
        buy_link = None

        # Stratégie A : Bouton d'achat standard WooCommerce
        btn = soup.find("button", class_="single_add_to_cart_button")
        if btn:
            form = btn.find_parent("form")
            if form and form.get("action"):
                buy_link = form.get("action")
                debug_msg = "Lien extrait via formulaire bouton"

        # Stratégie B : Fallback par les liens /out/ (Très fréquent sur Wetall)
        if not buy_link:
            out_links = [
                a["href"] for a in soup.find_all("a", href=True) if "/out/" in a["href"]
            ]
            if out_links:
                buy_link = out_links[0]
                debug_msg = "Lien extrait via fallback /out/"

        # Stratégie C : Détection spécifique des produits à variations (tailles/couleurs)
        if not buy_link and soup.find("form", class_="variations_form"):
            debug_msg = "Structure à variations détectée (taille requise)"
            return "Variations (Taille/Couleur)", 200, None, debug_msg

        # Si toujours aucun lien trouvé après toutes les stratégies
        if not buy_link:
            if "en rupture" in resp_wetall.text.lower():
                return (
                    "Rupture de stock",
                    200,
                    None,
                    "Marqueur rupture trouvé sur Wetall",
                )
            else:
                return (
                    "Bouton non trouvé",
                    200,
                    None,
                    "Aucun bouton ni lien /out/ dans le HTML",
                )

        # Correction des liens relatifs Amazon
        if buy_link.startswith("/dp/"):
            buy_link = f"https://www.amazon.fr{buy_link}"

        # --- ÉTAPE 2 : MARCHAND FINAL ---
        logger.info(
            f"Redirection marchande identifiée. Simulation de lecture humaine..."
        )
        time.sleep(random.uniform(12, 22))

        resp_marchand = client.get(buy_link, headers=headers)
        final_url = str(resp_marchand.url).lower()
        page_content = resp_marchand.text.lower()

        status = "OK"
        code = resp_marchand.status_code

        # --- LOGIQUE MÉTIER PAR MARCHAND ---
        if code in [403, 401]:
            status = "Vérification bloquée (403)"
            debug_msg = f"Bloqué par le pare-feu du marchand à l'URL : {final_url[:50]}"
        elif code == 404:
            status = "Lien Brisé (404)"
            debug_msg = "Le serveur marchand renvoie une vraie erreur 404"

        # Condition spécifique Nike
        elif "nike" in final_url or "nike" in page_content:
            if "le produit recherché n'est plus disponible" in page_content:
                status = "Rupture de stock"
                debug_msg = "Nike : Message 'Produit non disponible' détecté"
            elif any(x in page_content for x in ["indisponible", "rupture de stock"]):
                status = "Rupture de stock"
                debug_msg = "Nike : Terme de rupture standard trouvé"

        # Condition spécifique Decathlon
        elif "decathlon" in final_url or "decathlon" in page_content:
            if any(
                x in page_content
                for x in ["indisponible", "rupture de stock", "en rupture"]
            ):
                status = "Rupture de stock"
                debug_msg = "Decathlon : Produit détecté hors stock"

        # Condition spécifique Amazon
        elif "amazon" in final_url or "amazon" in page_content:
            markers_amazon_rupture = [
                "actuellement indisponible",
                "ne sais pas quand cet article sera de nouveau approvisionné",
            ]
            marker_amazon_mort = (
                "l'adresse web que vous avez saisie n'est pas une page fonctionnelle"
            )

            if marker_amazon_mort in page_content:
                status = "Lien Mort (404 déguisé)"
                debug_msg = "Amazon : Page 'Vous cherchez quelque chose ?' interceptée"
            elif any(m in page_content for m in markers_amazon_rupture):
                status = "Rupture de stock"
                debug_msg = "Amazon : Bloc d'indisponibilité standard trouvé"

        else:
            debug_msg = f"Scan réussi sans détection d'anomalie sur {final_url[:30]}"

        return status, code, final_url, debug_msg

    except Exception as e:
        logger.error(f"Erreur technique rencontrée : {e}")
        # On capture les 100 premiers caractères de l'erreur Python (Timeout, Connexion refusée, etc.)
        return "Erreur technique", 0, None, f"Exception Python: {str(e)[:100]}"


def run_pipeline():
    """Fonction principale pour le traitement de nuit (250 produits)."""
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        logger.error("La variable d'environnement DATABASE_URL est manquante.")
        return

    try:
        conn = psycopg2.connect(db_url, cursor_factory=DictCursor)
        conn.autocommit = True
        cur = conn.cursor()

        # Récupération des 250 fiches les plus anciennes ou jamais scannées
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
            LIMIT 250;
        """
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
                    (produit_id, date_scan, status_code, http_code_marchand, url_marchand_finale, debug_info)
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
