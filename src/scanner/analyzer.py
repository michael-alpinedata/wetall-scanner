"""
Analyse du statut de stock par marchand.

Responsabilité unique : appliquer les règles métier de détection de rupture
ou de lien mort pour chaque marchand connu. Chaque règle est isolée dans
sa propre fonction privée pour faciliter les tests unitaires et l'extension.
"""

# Type alias pour la clarté
ScanResult = tuple[str, str]  # (statut_lisible, message_debug)

# ---------------------------------------------------------------------------
# Marqueurs textuels par marchand  (en minuscules — la comparaison est normalisée)
# ---------------------------------------------------------------------------
_NIKE_OUT_OF_STOCK_MARKERS = ("plus disponible", "indisponible", "rupture")
_DECATHLON_OUT_OF_STOCK_MARKERS = ("indisponible", "rupture", "en rupture")
_AMAZON_DEAD_LINK_MARKERS = ("n'est pas une page fonctionnelle",)
_AMAZON_OUT_OF_STOCK_MARKERS = ("actuellement indisponible", "nouveau approvisionné")
_ALLTRICKS_OUT_OF_STOCK_MARKERS = ("épuisé", "plus en stock", "indisponible")


def _check_nike(url: str, html: str) -> ScanResult | None:
    """Règles de détection Nike. Retourne un résultat ou None (non-applicable)."""
    if "nike" not in url and "nike" not in html:
        return None
    if any(marker in html for marker in _NIKE_OUT_OF_STOCK_MARKERS):
        return "Rupture de stock", "Nike : Rupture détectée"
    return None


def _check_decathlon(url: str, html: str) -> ScanResult | None:
    """Règles de détection Decathlon."""
    if "decathlon" not in url and "decathlon" not in html:
        return None
    if any(marker in html for marker in _DECATHLON_OUT_OF_STOCK_MARKERS):
        return "Rupture de stock", "Decathlon : Rupture détectée"
    return None


def _check_amazon(url: str, html: str) -> ScanResult | None:
    """Règles de détection Amazon (404 déguisée + rupture de stock)."""
    if "amazon" not in url and "amazon" not in html:
        return None
    if any(marker in html for marker in _AMAZON_DEAD_LINK_MARKERS):
        return "Lien Mort (404 déguisé)", "Amazon : 404 déguisée"
    if any(marker in html for marker in _AMAZON_OUT_OF_STOCK_MARKERS):
        return "Rupture de stock", "Amazon : Rupture détectée"
    return None


def _check_alltricks(url: str, html: str) -> ScanResult | None:
    """Règles de détection Alltricks."""
    if "alltricks" not in url and "alltricks" not in html:
        return None
    if any(marker in html for marker in _ALLTRICKS_OUT_OF_STOCK_MARKERS):
        return "Rupture de stock", "Alltricks : Rupture détectée"
    return None


# Pipeline de règles : ordre d'évaluation explicite et extensible
_MERCHANT_RULES = [_check_nike, _check_decathlon, _check_amazon, _check_alltricks]

_DEFAULT_RESULT: ScanResult = ("OK", "Scan réussi")


def analyze_merchant_status(url: str, html: str) -> ScanResult:
    """
    Applique les règles métier de détection de stock par marchand.

    Les comparaisons sont effectuées en minuscules pour éviter les faux négatifs
    liés à la casse. Le premier résultat non-None est retourné immédiatement.

    Args:
        url:  URL finale du marchand (après redirections).
        html: Corps de la réponse HTTP du marchand.

    Returns:
        Exemple : ("Rupture de stock", "Nike : Rupture détectée")
    """
    url_lower, html_lower = url.lower(), html.lower()

    for rule in _MERCHANT_RULES:
        result = rule(url_lower, html_lower)
        if result is not None:
            return result

    return _DEFAULT_RESULT
