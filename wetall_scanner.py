import datetime
import os
import sys
import logging
from bs4 import BeautifulSoup
import httpx
import psycopg2
from dotenv import load_dotenv

# 1. CONFIGURATION DU LOGGING
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

load_dotenv()

TARGETS = [
    {
        "nom": "Vélo de Biking",
        "url_wetall": "https://www.wetall.fr/produit/velo-de-biking-grande-taille/",
    }
]

def analyze_stock():
    scrapeops_api_key = os.environ.get("SCRAPING_API_KEY")
    db_url = os.environ.get("DATABASE_URL")

    if not scrapeops_api_key or not db_url:
        logger.error("Variables d'environnement manquantes (SCRAPING_API_KEY ou DATABASE_URL)")
        sys.exit(1)

    results = []
    proxy_url = "https://proxy.scrapeops.io/v1/"

    for item in TARGETS:
        logger.info(f"Démarrage analyse : {item['nom']}")
        try:
            # Étape A : Appel ScrapeOps sans JS Rendering
            params = {
                "api_key": scrapeops_api_key,
                "url": item["url_wetall"],
                "render_js": "false"
            }

            logger.info(f"Requête ScrapeOps pour: {item['url_wetall']}")
            with httpx.Client(timeout=45.0) as client:
                r_wetall = client.get(proxy_url, params=params)
                
                if r_wetall.status_code != 200:
                    logger.warning(f"Échec Proxy: Code {r_wetall.status_code} - Contenu: {r_wetall.text[:100]}...")
                    results.append({
                        "nom": item["nom"], "url_wetall": item["url_wetall"],
                        "status": f"Erreur Proxy ({r_wetall.status_code})", "emoji": "❌"
                    })
                    continue

                logger.info("Page Wetall récupérée avec succès. Analyse du DOM...")
                soup = BeautifulSoup(r_wetall.text, "html.parser")

                # Étape B : Extraction du lien
                ## DEBUG
                links = [a['href'] for a in soup.find_all('a', href=True)]
                logger.info(f"Liens extraits : {links[:5]}...") # Affiche les 5 premiers liens
                ## END DEBUG

                # Recherche robuste du bouton et de son formulaire
                btn = soup.find('button', class_='single_add_to_cart_button')
                buy_link = None

                if btn:
                    # On cherche le formulaire qui contient ce bouton
                    form = btn.find_parent('form')
                    if form and form.get('action'):
                        buy_link = form.get('action')
                        logger.info(f"Lien marchand trouvé dans l'action du formulaire : {buy_link}")
                else:
                    # Fallback sur l'ancienne méthode au cas où certains produits utilisent encore des liens simples
                    for a in soup.find_all('a', href=True):
                        if "/out/" in a['href']:
                            buy_link = a['href']
                            break

                # Étape C : Scan Marchand via Proxy
                logger.info(f"Suivi du lien marchand via Proxy: {buy_link}")
                params_marchand = {
                    "api_key": scrapeops_api_key,
                    "url": buy_link,
                    "render_js": "false"
                }
                r_marchand = client.get(proxy_url, params=params_marchand, follow_redirects=True)
                logger.info(f"Réponse proxy marchand atteinte (Code: {r_marchand.status_code})")

                # Étape D : Diagnostic
                status, emoji = "OK", "✅"
                if r_marchand.status_code == 404:
                    status, emoji = "Lien Brisé (404)", "❌"
                elif r_marchand.status_code != 200:
                    status, emoji = "Vérification bloquée", "🛡️"
                elif any(x in r_marchand.text.lower() for x in ["indisponible", "rupture"]):
                    status, emoji = "Rupture de stock", "🟠"

                results.append({"nom": item["nom"], "url_wetall": item["url_wetall"], "status": status, "emoji": emoji})
                logger.info(f"Résultat pour {item['nom']}: {status} {emoji}")

        except Exception as e:
            logger.exception(f"Erreur inattendue sur {item['nom']}")
            results.append({
                "nom": item["nom"], "url_wetall": item.get("url_wetall", ""),
                "status": f"Erreur technique: {str(e)}", "emoji": "❗"
            })

    # 3. INSERTION DB
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
                (res["nom"], res["url_wetall"], res["status"], res["emoji"], scan_date)
            )
        
        cur.close()
        conn.close()
        logger.info("Données synchronisées avec Neon avec succès.")

    except Exception as db_e:
        logger.error(f"Échec de l'écriture en base de données: {db_e}")

if __name__ == "__main__":
    analyze_stock()