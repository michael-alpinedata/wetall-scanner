"""
debug_scan.py - Sonde de diagnostic profond pour Wetall-Scanner
"""

import logging
import sys

import httpx
from bs4 import BeautifulSoup

# Import de tes modules locaux
from legacy.src.scanner.http_client import build_headers
from legacy.src.scanner.parser import get_buy_link_from_wetall

# --- CONFIGURATION DU LOGGING MAXIMAL ---
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("debug_execution.log", mode="w", encoding="utf-8"),
    ],
)
logger = logging.getLogger("DeepDebug")

# On rend httpx plus verbeux pour voir les headers réellement envoyés
logging.getLogger("httpx").setLevel(logging.DEBUG)


def run_diagnostic(url_wetall: str):
    logger.info(f"--- DÉBUT DU DIAGNOSTIC SUR : {url_wetall} ---")

    headers = build_headers()
    logger.debug(f"Headers générés : {headers}")

    try:
        with httpx.Client(follow_redirects=True, timeout=30.0) as client:
            logger.info("Étape 1 : Requête HTTP vers Wetall...")
            resp = client.get(url_wetall, headers=headers)

            logger.info(f"Statut HTTP : {resp.status_code}")
            logger.info(f"Headers de réponse : {resp.headers}")
            logger.info(f"Encodage détecté par httpx : {resp.encoding}")

            # Sauvegarde du contenu brut pour inspection manuelle
            with open("dump_raw_content.html", "wb") as f:
                f.write(resp.content)
            logger.info("Contenu brut sauvegardé dans 'dump_raw_content.html'")

            # --- VÉRIFICATION DU DÉCODAGE ---
            logger.info("Étape 2 : Vérification du décodage du texte...")
            html_text = resp.text
            if not html_text or len(html_text.strip()) == 0:
                logger.error(
                    "ALERTE : Le texte décodé est VIDE. Problème d'encodage probable (Brotli/Gzip) !"
                )
                return

            logger.debug(
                f"Aperçu du HTML décodé (100 premiers chars) : {html_text[:100]}"
            )

            # --- VÉRIFICATION DU PARSER ---
            logger.info("Étape 3 : Analyse par BeautifulSoup...")
            soup = BeautifulSoup(html_text, "html.parser")

            # Diagnostic spécifique du bouton "Stratégie A"
            logger.info("Recherche du bouton 'single_add_to_cart_button'...")
            btn = soup.find("button", class_="single_add_to_cart_button")

            if btn:
                logger.info(f"✅ BOUTON TROUVÉ : {btn}")
                form = btn.find_parent("form")
                if form:
                    logger.info(
                        f"✅ FORMULAIRE PARENT TROUVÉ. Action : {form.get('action')}"
                    )
                else:
                    logger.warning("❌ Bouton trouvé mais SANS formulaire parent.")
            else:
                logger.error(
                    "❌ BOUTON NON TROUVÉ avec la classe 'single_add_to_cart_button'"
                )
                # On cherche tous les boutons pour voir si la classe a changé
                all_btns = soup.find_all("button")
                logger.debug(
                    f"Liste des classes de tous les boutons trouvés : {[b.get('class') for b in all_btns]}"
                )

            # Exécution de la fonction officielle
            link, msg = get_buy_link_from_wetall(soup)
            logger.info(f"Résultat final du parser : Lien={link} | Message={msg}")

    except Exception as e:
        logger.exception(f"Échec critique durant le diagnostic : {e}")


if __name__ == "__main__":
    # Remplace par une URL de produit qui pose problème
    TEST_URL = "https://www.wetall.fr/produit/manteau-habille-ceinture-a-chevrons-grande-taille-jusquau-48-tall/"

    if "URL" in TEST_URL:
        print("⚠️ Modifie TEST_URL dans le script avant de lancer.")
    else:
        run_diagnostic(TEST_URL)
