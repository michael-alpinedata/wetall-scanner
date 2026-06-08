import re
from bs4 import BeautifulSoup


class WetallExtractor:
    """Responsabilité unique : Extraire et normaliser les données du HTML brut de Wetall."""

    def extract_from_fetch_data(self, fetch_data: dict) -> str | None:
        """
        Extrait le lien marchand depuis le dictionnaire retourné par le HTTPClient.
        Gère la tolérance aux différentes clés de contenu ('html', 'text', 'content').
        """
        html_content = (
            fetch_data.get("html")
            or fetch_data.get("text")
            or fetch_data.get("content")
            or ""
        )
        if not html_content:
            return None
        return self.extract_buy_link(html_content)

    def is_internal_redirect(self, url: str) -> bool:
        """
        Détermine si l'URL extraite est un lien de redirection interne Wetall (/go/ ou /out/)
        qui nécessite un second appel réseau pour découvrir le marchand final.
        """
        return any(path in url for path in ["wetall.fr/go/", "wetall.fr/out/"])

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

    def extract_merchant_name(self, url: str) -> str:
        """Déduit le nom propre du vendeur à partir de l'URL marchande finale."""
        url_lower = url.lower()
        if "amazon" in url_lower or "amzn" in url_lower:
            return "Amazon"
        if "decathlon" in url_lower:
            return "Decathlon"
        if "alltricks" in url_lower:
            return "Alltricks"

        # Fallback dynamique si le domaine est inconnu (ex: https://www.boutique.fr/... -> Boutique)
        from urllib.parse import urlparse

        try:
            domain = urlparse(url).netloc or urlparse(url).path
            clean_domain = domain.replace("www.", "").split(".")[0]
            return clean_domain.capitalize() if clean_domain else "Marchand"
        except Exception:
            return "Marchand"

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
