"""
Analyse du statut de stock par marchand.
"""

ScanResult = tuple[str, str]

_NIKE_OUT_OF_STOCK_MARKERS = ("plus disponible", "indisponible", "rupture")
_DECATHLON_OUT_OF_STOCK_MARKERS = ("indisponible", "rupture", "en rupture", "épuisé")
_AMAZON_DEAD_LINK_MARKERS = ("n'est pas une page fonctionnelle",)
_AMAZON_OUT_OF_STOCK_MARKERS = ("actuellement indisponible", "nouveau approvisionné")
_ALLTRICKS_OUT_OF_STOCK_MARKERS = ("épuisé", "plus en stock", "indisponible")
_ASOS_OUT_OF_STOCK_MARKERS = ("épuisé", "plus disponible", "out of stock")


def _check_nike(url: str, html: str) -> ScanResult | None:
    if "nike" not in url and "nike" not in html: return None
    if any(marker in html for marker in _NIKE_OUT_OF_STOCK_MARKERS):
        return "Rupture de stock", "Nike : Rupture détectée"
    return None


def _check_decathlon(url: str, html: str) -> ScanResult | None:
    if "decathlon" not in url and "decathlon" not in html: return None
    if any(marker in html for marker in _DECATHLON_OUT_OF_STOCK_MARKERS):
        return "Rupture de stock", "Decathlon : Rupture détectée"
    return None


def _check_amazon(url: str, html: str) -> ScanResult | None:
    if "amazon" not in url and "amazon" not in html: return None
    if any(marker in html for marker in _AMAZON_DEAD_LINK_MARKERS):
        return "Lien Mort (404 déguisé)", "Amazon : 404 déguisée"
    if any(marker in html for marker in _AMAZON_OUT_OF_STOCK_MARKERS):
        return "Rupture de stock", "Amazon : Rupture détectée"
    return None


def _check_alltricks(url: str, html: str) -> ScanResult | None:
    if "alltricks" not in url and "alltricks" not in html: return None
    if any(marker in html for marker in _ALLTRICKS_OUT_OF_STOCK_MARKERS):
        return "Rupture de stock", "Alltricks : Rupture détectée"
    return None


def _check_asos(url: str, html: str) -> ScanResult | None:
    """Règles de détection ASOS."""
    if "asos" not in url and "asos" not in html: return None
    if any(marker in html for marker in _ASOS_OUT_OF_STOCK_MARKERS):
        return "Rupture de stock", "ASOS : Rupture détectée"
    return None


# Extension du registre des règles métiers
_MERCHANT_RULES = [_check_nike, _check_decathlon, _check_amazon, _check_alltricks, _check_asos]
_DEFAULT_RESULT: ScanResult = ("OK", "Scan réussi")


def analyze_merchant_status(url: str, html: str) -> ScanResult:
    url_lower, html_lower = url.lower(), html.lower()
    for rule in _MERCHANT_RULES:
        result = rule(url_lower, html_lower)
        if result is not None:
            return result
    return _DEFAULT_RESULT
