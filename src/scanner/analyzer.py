"""
Analyse du statut de stock par marchand.
"""

import re
from bs4 import BeautifulSoup

ScanResult = tuple[str, str]

_NIKE_OUT_OF_STOCK_MARKERS = ("plus disponible", "indisponible", "rupture")
_DECATHLON_OUT_OF_STOCK_MARKERS = ("indisponible", "rupture", "en rupture", "épuisé")
_AMAZON_DEAD_LINK_MARKERS = ("n'est pas une page fonctionnelle",)
_AMAZON_OUT_OF_STOCK_MARKERS = ("actuellement indisponible", "nouveau approvisionné")
_ALLTRICKS_OUT_OF_STOCK_MARKERS = ("épuisé", "plus en stock", "indisponible")
_ASOS_OUT_OF_STOCK_MARKERS = ("épuisé", "plus disponible", "out of stock")


def _check_nike(url: str, html: str) -> ScanResult | None:
    html_lower = html.lower()
    if "nike" not in url and "nike" not in html_lower: return None
    if any(marker in html_lower for marker in _NIKE_OUT_OF_STOCK_MARKERS):
        return "Rupture de stock", "Nike : Rupture détectée"
    return None


def _check_decathlon(url: str, html: str) -> ScanResult | None:
    html_lower = html.lower()
    if "decathlon" not in url and "decathlon" not in html_lower: return None
    if any(marker in html_lower for marker in _DECATHLON_OUT_OF_STOCK_MARKERS):
        return "Rupture de stock", "Decathlon : Rupture détectée"
    return None


def _check_amazon(url: str, html: str) -> ScanResult | None:
    html_lower = html.lower()
    if "amazon" not in url and "amazon" not in html_lower: return None
    
    # 1. Vérification immédiate des liens morts 404
    if any(marker in html_lower for marker in _AMAZON_DEAD_LINK_MARKERS):
        return "Lien Mort (404 déguisé)", "Amazon : 404 déguisée"
    
    # 2. Si le marqueur "indisponible" est détecté, on investigue les variantes
    if any(marker in html_lower for marker in _AMAZON_OUT_OF_STOCK_MARKERS):
        soup = BeautifulSoup(html, "html.parser")
        
        # --- Cas A : Sélecteur de taille de type Dropdown (<select>) ---
        dropdown = soup.find("select", id="native_dropdown_selected_size_name")
        if dropdown:
            options = dropdown.find_all("option")
            for option in options:
                val = option.get("value", "")
                txt = option.text.lower()
                # Si une option possède une vraie valeur et ne contient pas "indisponible"
                if val and val != "-1" and "indisponible" not in txt and "choisir" not in txt:
                    return None  # Une taille est disponible ! On ignore la rupture globale -> Statut OK

        # --- Cas B : Sélecteur de taille en ligne (Boutons / Swatches) ---
        # Amazon regroupe ces boutons dans un conteneur spécifique
        twister = soup.find("div", id=re.compile(r"(inline-twister-dim-size_name|variation_size_name)"))
        if twister:
            # Les boutons de tailles disponibles ont la classe 'swatchAvailable' dans le HTML statique
            if soup.find("li", class_="swatchAvailable"):
                return None  # Au moins une taille est en stock ! On ignore la rupture globale -> Statut OK

        # Si aucun sélecteur n'existe ou si toutes les déclinaisons sont confirmées absentes : vraie rupture.
        return "Rupture de stock", "Amazon : Rupture détectée"
        
    return None


def _check_alltricks(url: str, html: str) -> ScanResult | None:
    html_lower = html.lower()
    if "alltricks" not in url and "alltricks" not in html_lower: return None
    if any(marker in html_lower for marker in _ALLTRICKS_OUT_OF_STOCK_MARKERS):
        return "Rupture de stock", "Alltricks : Rupture détectée"
    return None


def _check_asos(url: str, html: str) -> ScanResult | None:
    """Règles de détection ASOS."""
    html_lower = html.lower()
    if "asos" not in url and "asos" not in html_lower: return None
    if any(marker in html_lower for marker in _ASOS_OUT_OF_STOCK_MARKERS):
        return "Rupture de stock", "ASOS : Rupture détectée"
    return None


# Extension du registre des règles métiers
_MERCHANT_RULES = [_check_nike, _check_decathlon, _check_amazon, _check_alltricks, _check_asos]
_DEFAULT_RESULT: ScanResult = ("OK", "Scan réussi")


def analyze_merchant_status(url: str, html: str) -> ScanResult:
    url_lower = url.lower()
    # On transmet le HTML brut aux règles pour que BeautifulSoup conserve la casse des balises
    for rule in _MERCHANT_RULES:
        result = rule(url_lower, html)
        if result is not None:
            return result
    return _DEFAULT_RESULT
