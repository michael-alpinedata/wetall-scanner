import re
from bs4 import BeautifulSoup

class WetallExtractor:
    """Responsabilité unique : Extraire et normaliser les données du HTML brut de Wetall."""
    
    def extract_buy_link(self, html_content: str) -> str | None:
        if not html_content:
            return None
            
        soup = BeautifulSoup(html_content, "html.parser")
        found_url = None

        # 1. WooCommerce
        btn_cart = soup.find("button", class_="single_add_to_cart_button")
        if btn_cart:
            form = btn_cart.find_parent("form")
            if form and form.get("action"):
                found_url = form.get("action")

        # 2. Gutenberg
        if not found_url:
            btn_g = soup.select_one('a[class*="wp-block-button__link"]')
            if btn_g and btn_g.get("href"):
                found_url = btn_g["href"]

        # 3. Redirection /go/
        if not found_url:
            link_go = soup.find("a", href=re.compile(r"/go/|/out/"))
            if link_go:
                found_url = link_go["href"]

        # 4. Amazon & co
        if not found_url:
            merchant_domains = ["amazon.fr", "decathlon.fr", "alltricks.fr"]
            for a in soup.find_all("a", href=True):
                if any(d in a["href"] for d in merchant_domains):
                    found_url = a["href"]
                    break

        return self._normalize_url(found_url) if found_url else None

    def _normalize_url(self, url: str) -> str:
        clean_url = url.strip()
        if clean_url.startswith("//"):
            return f"https:{clean_url}"
        if clean_url.startswith(("/go/", "/out/")):
            return f"https://www.wetall.fr{clean_url}"
        if clean_url.startswith(("/dp/", "/gp/")):
            return f"https://www.amazon.fr{clean_url}"
        if clean_url.startswith("dp/"):
            return f"https://www.amazon.fr/{clean_url}"
        return clean_url