import datetime
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

# Charger l'environnement local (.env)
load_dotenv()

# CONFIGURATION DES TARGETS
TARGETS = [
    # {
    #     "nom": "Vélo de Biking",
    #     "url_wetall": "https://www.wetall.fr/produit/velo-de-biking-grande-taille/",
    # },
    {
        "nom": "Chaussures Adidas Rugby (TEST RUPTURE)",
        "url_wetall": "https://www.wetall.fr/produit/adidas-x-crazyfast-3-laceless-grande-taille-jusquau-50/",
    }
]


def analyze_stock():
    scrapeops_api_key = os.environ.get("SCRAPING_API_KEY")
    db_url = os.environ.get("DATABASE_URL")

    if not scrapeops_api_key or not db_url:
        logger.error(
            "Variables d'environnement manquantes (SCRAPING_API_KEY ou DATABASE_URL)"
        )
        sys.exit(1)

    results = []
    proxy_url = "https://proxy.scrapeops.io/v1/"

    for item in TARGETS:
        logger.info(f"Démarrage analyse : {item['nom']}")
        try:
            # ==========================================
            # ÉTAPE A : REQUÊTE WETALL (PROXY, NO-JS)
            # ==========================================
            params_wetall = {
                "api_key": scrapeops_api_key,
                "url": item["url_wetall"],
                "render_js": "false",
            }

            logger.info(f"Requête ScrapeOps pour: {item['url_wetall']}")
            with httpx.Client(timeout=45.0) as client:
                r_wetall = client.get(proxy_url, params=params_wetall)

                if r_wetall.status_code != 200:
                    logger.warning(f"Échec Proxy Wetall: Code {r_wetall.status_code}")
                    results.append(
                        {
                            "nom": item["nom"],
                            "url_wetall": item["url_wetall"],
                            "status": f"Erreur Proxy Wetall ({r_wetall.status_code})",
                            "emoji": "❌",
                        }
                    )
                    continue

                logger.info("Page Wetall récupérée avec succès. Analyse du DOM...")
                soup = BeautifulSoup(r_wetall.text, "html.parser")

                # ==========================================
                # ÉTAPE B : EXTRACTION DU FORMULAIRE WOOCOMMERCE
                # ==========================================
                btn = soup.find("button", class_="single_add_to_cart_button")
                buy_link = None

                if btn:
                    form = btn.find_parent("form")
                    if form and form.get("action"):
                        buy_link = form.get("action")
                        logger.info(
                            f"Lien marchand trouvé dans l'action du formulaire : {buy_link}"
                        )
                else:
                    # Fallback historique au cas où
                    for a in soup.find_all("a", href=True):
                        if "/out/" in a["href"]:
                            buy_link = a["href"]
                            break

                if not buy_link:
                    logger.error(f"Bouton 'Commander' introuvable sur {item['nom']}")
                    results.append(
                        {
                            "nom": item["nom"],
                            "url_wetall": item["url_wetall"],
                            "status": "Bouton non trouvé",
                            "emoji": "⚠️",
                        }
                    )
                    continue

                # ==========================================
                # ÉTAPE C : REQUÊTE MARCHAND (PROXY, NO-JS)
                # ==========================================
                logger.info(f"Suivi du lien marchand via Proxy: {buy_link}")
                params_marchand = {
                    "api_key": scrapeops_api_key,
                    "url": buy_link,
                    "render_js": "false",
                }

                r_marchand = client.get(proxy_url, params=params_marchand)
                logger.info(
                    f"Réponse proxy marchand atteinte (Code: {r_marchand.status_code})"
                )

                # Log léger du HTML pour contrôle visuel
                if r_marchand.status_code == 200:
                    print(r_marchand.text[:500])

                # ==========================================
                # ÉTAPE D : EVALUATION MÉTIER DU STOCK
                # ==========================================
                final_url = str(r_marchand.url).lower()
                page_content = r_marchand.text.lower()
                status, emoji = "OK", "✅"

                if r_marchand.status_code in [401, 403]:
                    status, emoji = "Vérification bloquée (403)", "🛡️"
                elif r_marchand.status_code == 404:
                    status, emoji = "Lien Brisé (404)", "❌"

                # 1. LOGIQUE DECATHLON
                elif "decathlon" in final_url or "decathlon" in page_content:
                    if any(
                        x in page_content
                        for x in ["indisponible", "rupture de stock", "en rupture"]
                    ):
                        status, emoji = "Rupture de stock", "🟠"

                # 2. LOGIQUE AMAZON (Nouveau)
                elif "amazon" in final_url or "amazon" in page_content:
                    # Amazon utilise ces chaînes précises dans son HTML pour les produits indisponibles
                    markers_amazon = [
                        "actuellement indisponible",
                        "features-and-availability-title",  # Div qui pop souvent uniquement sur les ruptures
                        "ne sais pas quand cet article sera de nouveau approvisionné",
                    ]
                    if any(m in page_content for m in markers_amazon):
                        status, emoji = "Rupture de stock", "🟠"

                results.append(
                    {
                        "nom": item["nom"],
                        "url_wetall": item["url_wetall"],
                        "status": status,
                        "emoji": emoji,
                    }
                )
                logger.info(f"Résultat pour {item['nom']}: {status} {emoji}")

        except Exception as e:
            logger.exception(f"Erreur inattendue sur {item['nom']}")
            results.append(
                {
                    "nom": item["nom"],
                    "url_wetall": item.get("url_wetall", ""),
                    "status": f"Erreur technique: {str(e)}",
                    "emoji": "❗",
                }
            )

    # ==========================================
    # 3. PERSISTENCE DANS NEON.TECH
    # ==========================================
    if not results:
        logger.info("Aucun résultat à insérer.")
        return

    try:
        logger.info(f"Connexion à Neon pour insertion de {len(results)} ligne(s)...")
        conn = psycopg2.connect(db_url)
        conn.autocommit = True
        cur = conn.cursor()
        scan_date = datetime.datetime.now(datetime.timezone.utc)

        for res in results:
            cur.execute(
                "INSERT INTO wetall_link_history (nom_produit, url_wetall, statut, code_etat, date_scan) VALUES (%s, %s, %s, %s, %s)",
                (
                    res["nom"],
                    res["url_wetall"],
                    res["status"],
                    res["emoji"],
                    scan_date,
                ),
            )

        cur.close()
        conn.close()
        logger.info("Données synchronisées avec Neon avec succès.")

    except Exception as db_e:
        logger.error(f"Échec de l'écriture en base de données: {db_e}")


if __name__ == "__main__":
    analyze_stock()
