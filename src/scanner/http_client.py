"""
Couche transport HTTP.

Responsabilité unique : exécuter les requêtes GET avec rotation de User-Agent
et gestion du fallback curl_cffi pour les cibles anti-bot (Decathlon, Alltricks).
"""

import logging
import random

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pool de User-Agents représentatifs de navigateurs desktop courants
# ---------------------------------------------------------------------------
USER_AGENTS: list[str] = [
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
]

# Marchands connus pour bloquer les scrapers — éligibles au fallback curl_cffi
_HARD_TARGETS: tuple[str, ...] = ("decathlon", "alltricks", "nike")


def build_headers() -> dict[str, str]:
    """Construit des headers HTTP avec un User-Agent aléatoire."""
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": "https://www.google.com/",
    }


def _is_hard_target(url: str) -> bool:
    """Retourne True si l'URL correspond à un marchand anti-bot connu."""
    url_lower = url.lower()
    return any(target in url_lower for target in _HARD_TARGETS)


def _fallback_curl(url: str, headers: dict[str, str]) -> httpx.Response | None:
    """
    Tente une requête via curl_cffi en mode impersonation Chrome.

    Retourne la réponse curl_cffi ou None en cas d'échec.
    curl_cffi n'est pas obligatoire : l'import est lazy pour éviter
    une dépendance bloquante si le paquet n'est pas installé.
    """
    try:
        from curl_cffi import requests as curl_requests  # noqa: PLC0415

        resp = curl_requests.get(url, headers=headers, impersonate="chrome", timeout=30)
        logger.info("Fallback curl_cffi réussi pour %s", url[:40])
        return resp  # type: ignore[return-value]
    except Exception as exc:
        logger.error("Fallback curl_cffi échoué : %s", exc)
        return None


def fetch_with_fallback(
    client: httpx.Client, url: str, headers: dict[str, str]
) -> httpx.Response:
    """
    Effectue une requête GET avec fallback curl_cffi sur les cibles dures.

    Stratégie :
    1. Requête standard via le client httpx partagé.
    2. Si la réponse est 401/403 ET que l'URL est un hard-target,
       on retente avec curl_cffi (impersonation navigateur).
    3. Si le fallback échoue, on retourne la réponse originale.
    """
    resp = client.get(url, headers=headers)

    if resp.status_code in (401, 403) and _is_hard_target(url):
        logger.warning(
            "Réponse %s reçue depuis %s — tentative fallback curl_cffi.",
            resp.status_code,
            url[:40],
        )
        fallback_resp = _fallback_curl(url, headers)
        if fallback_resp is not None:
            return fallback_resp  # type: ignore[return-value]

    return resp
