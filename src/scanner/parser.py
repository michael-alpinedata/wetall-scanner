"""
Parsing des pages Wetall & normalisation des URLs marchands.

Responsabilité unique : transformer du HTML brut en données structurées
(lien d'achat) et corriger les URLs mal formées (Amazon relatif/tronqué).
"""

from bs4 import BeautifulSoup


def get_buy_link_from_wetall(soup: BeautifulSoup) -> tuple[str | None, str | None]:
    """
    Extrait le lien marchand depuis le HTML d'une page produit Wetall.

    Stratégies appliquées dans l'ordre de priorité :
    A — Bouton "Ajouter au panier" → action du formulaire parent.
    B — Fallback : premier lien contenant '/out/' dans l'attribut href.
    C — Fallback : lien direct vers un domaine marchand connu (amazon, decathlon, etc).

    Returns:
        (url, message_debug) ou (None, None) si aucun lien trouvé.
    """
    # --- Stratégie A : formulaire d'achat ---
    btn = soup.find("button", class_="single_add_to_cart_button")
    if btn:
        form = btn.find_parent("form")
        if form and form.get("action"):
            return form.get("action"), "Lien via formulaire"

    # --- Stratégie B : liens /out/ ---
    out_links = [
        a["href"] for a in soup.find_all("a", href=True) if "/out/" in a["href"]
    ]
    if out_links:
        return out_links[0], "Lien via fallback /out/"

    # --- Stratégie C : liens marchands directs ---
    merchant_domains = ["amazon.fr", "decathlon.fr", "alltricks.fr", "nike.com", "asos.com"]
    for a in soup.find_all("a", href=True):
        if any(domain in a["href"] for domain in merchant_domains):
            return a["href"], "Lien via détection domaine marchand"

    # --- Stratégie D : Motifs spécifiques Amazon (relatifs) ---
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith(("/dp/", "dp/", "/gp/")):
            return href, "Lien via motif relatif Amazon"

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
