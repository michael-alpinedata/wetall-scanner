"""
Parsing des pages Wetall & normalisation des URLs marchands.

Responsabilité unique : transformer du HTML brut en données structurées
(lien d'achat) et corriger les URLs mal formées (Amazon relatif/tronqué).
"""

import re
from bs4 import BeautifulSoup


def get_buy_link_from_wetall(soup: BeautifulSoup) -> tuple[str | None, str | None]:
    found_url = None
    strategy = "Aucune"

    # 1. WooCommerce
    btn_cart = soup.find("button", class_="single_add_to_cart_button")
    if btn_cart:
        form = btn_cart.find_parent("form")
        if form and form.get("action"):
            found_url = form.get("action")
            strategy = "WooCommerce"

    # 2. Gutenberg (ID 7)
    if not found_url:
        btn_g = soup.select_one('a[class*="wp-block-button__link"]')
        if btn_g and btn_g.get("href"):
            found_url = btn_g["href"]
            strategy = "Gutenberg"

    # 3. Redirection /go/
    if not found_url:
        link_go = soup.find("a", href=re.compile(r"/go/|/out/"))
        if link_go:
            found_url = link_go["href"]
            strategy = "Redirection"

    # 4. Amazon & co
    if not found_url:
        merchant_domains = ["amazon.fr", "decathlon.fr", "alltricks.fr"]
        for a in soup.find_all("a", href=True):
            if any(d in a["href"] for d in merchant_domains):
                found_url = a["href"]
                strategy = "Marchand Direct"
                break

    # --- BLINDAGE FINAL : Gestion des URLs relatives et protocoles manquants ---
    if found_url:
        clean_url = found_url.strip()

        # 1. Gestion du protocole relatif (le cas de l'ID 7 !)
        if clean_url.startswith("//"):
            clean_url = f"https:{clean_url}"

        # 2. Gestion des redirections Wetall relatives
        elif clean_url.startswith(("/go/", "/out/")):
            clean_url = f"https://www.wetall.fr{clean_url}"

        # 3. Gestion des URLs Amazon relatives
        elif clean_url.startswith(("/dp/", "/gp/")):
            clean_url = f"https://www.amazon.fr{clean_url}"
        elif clean_url.startswith("dp/"):
            clean_url = f"https://www.amazon.fr/{clean_url}"

        return clean_url, f"Stratégie: {strategy} | URL: {clean_url}"

    return None, None


def normalize_amazon_url(url: str) -> str:
    """
    Corrige les URLs Amazon relatives ou tronquées.

    Cas gérés :
    - URL relative commençant par '/'  → préfixe amazon.fr
    - URL partielle commençant par 'dp/' → préfixe amazon.fr/
    - URL déjà absolue                 → retournée telle quelle.
    """
    url = url.strip()
    if url.startswith("/"):
        return f"https://www.amazon.fr{url}"
    if url.startswith("dp/"):
        return f"https://www.amazon.fr/{url}"
    return url
