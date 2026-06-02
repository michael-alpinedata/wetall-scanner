"""
Couche transport HTTP.

Responsabilité unique : exécuter les requêtes GET avec rotation de User-Agent,
résolution des liens d'affiliation (Link Synergy) et gestion du client curl_cffi 
pour les cibles anti-bot (Decathlon, Alltricks, ASOS, Nike).
"""

import logging
import random
import httpx

logger = logging.getLogger(__name__)

USER_AGENTS: list[str] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
]

# Marchands éligibles au traitement d'usurpation TLS Chrome préventif
HARD_TARGETS: set[str] = {
    "decathlon.fr", "alltricks.fr", "nike.com", "asos.com", 
    "onelink.me", "linksynergy.com" # On ajoute les redirecteurs ici
}


def build_headers() -> dict[str, str]:
    """Construit des headers humains complets pour éviter la détection comportementale."""
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Referer": "https://www.google.com/",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1"
    }


def _is_hard_target(url: str) -> bool:
    """Vérifie si l'URL appartient à un domaine nécessitant curl_cffi en priorité."""
    url_lower = url.lower()
    return any(target in url_lower for target in HARD_TARGETS)


def resolve_affiliation_link(url: str) -> str:
    """
    Suit les redirections des plateformes comme Link Synergy (Rakuten) via des requêtes 
    HEAD légères pour extraire l'URL finale du marchand avant le scan de contenu.
    """
    if "linksynergy" not in url.lower():
        return url
        
    logger.info("Détection d'un lien d'affiliation Link Synergy. Résolution de la trajectoire...")
    try:
        from curl_cffi import requests as curl_requests
        headers = build_headers()
        
        # On remonte la chaîne sans autoriser le redirect automatique pour éviter le tracking anti-bot
        res = curl_requests.head(url, headers=headers, impersonate="chrome", allow_redirects=False, timeout=15)
        while res.status_code in (301, 302):
            next_url = res.headers.get("Location")
            if not next_url:
                break
            url = next_url
            res = curl_requests.head(url, headers=headers, impersonate="chrome", allow_redirects=False, timeout=15)
        
        logger.info("Lien d'affiliation résolu vers : %s", url[:50])
        return url
    except Exception as exc:
        logger.error("Échec de la résolution du lien d'affiliation : %s", exc)
        return url


def fetch_with_fallback(client: httpx.Client, url: str, headers: dict[str, str]) -> httpx.Response:
    """
    Exécute la requête de scraping. Utilise directement curl_cffi pour les cibles sensibles
    afin de protéger l'IP, sinon utilise httpx avec un fallback curl_cffi en cas d'erreur.
    """
    if _is_hard_target(url):
        logger.info(f"Cible sensible détectée ({url[:40]}). Utilisation directe de curl_cffi.")
        try:
            return _fetch_with_curl(url, headers)
        except Exception as e:
            logger.warning(f"Échec curl_cffi sur cible sensible {url[:40]}. Fallback vers httpx. Erreur: {e}")
            return client.get(url, headers=headers)

    resp = client.get(url, headers=headers)
    if resp.status_code in (401, 403):
        logger.warning(f"Blocage {resp.status_code} sur {url[:40]}. Tentative de fallback curl_cffi.")
        return _fetch_with_curl(url, headers, fallback_resp=resp)
    return resp


def _fetch_with_curl(url: str, headers: dict, fallback_resp: httpx.Response | None = None) -> httpx.Response:
    """Encapsulation de l'appel curl_cffi avec reconstruction d'objet httpx.Response."""
    try:
        from curl_cffi import requests as curl_requests
        # Pour Decathlon, on remplace le UA aléatoire par un UA compatible Chrome stable
        if "decathlon" in url:
            headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        
        r = curl_requests.get(url, headers=headers, impersonate="chrome", timeout=30)
        return httpx.Response(
            status_code=r.status_code,
            content=r.content,
            headers=httpx.Headers(dict(r.headers)),
            request=httpx.Request("GET", url)
        )
    except Exception as e:
        logger.error(f"Échec curl_cffi sur {url[:40]} : {e}")
        if fallback_resp:
            return fallback_resp
        raise
