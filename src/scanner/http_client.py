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

# Marchands éligibles au traitement d'usurpation TLS Chrome
_HARD_TARGETS: tuple[str, ...] = ("decathlon", "alltricks", "nike", "asos")


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
    url_lower = url.lower()
    return any(target in url_lower for target in _HARD_TARGETS)


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
    Exécute la requête de scraping avec usurpation de signature TLS via curl_cffi 
    si la cible fait partie des marchands protégés par Cloudflare/Akamai.
    """
    # Si c'est une cible réputée difficile, on utilise directement curl_cffi pour éviter le marquage IP
    if _is_hard_target(url):
        logger.info("Cible sensible détectée (%s). Utilisation directe de curl_cffi.", url[:40])
        try:
            from curl_cffi import requests as curl_requests
            resp_curl = curl_requests.get(url, headers=headers, impersonate="chrome", timeout=30)
            
            # Reconstruction d'un objet httpx.Response factice pour maintenir la compatibilité de l'orchestrateur
            mock_resp = httpx.Response(
                status_code=resp_curl.status_code,
                content=resp_curl.content,
                headers=httpx.Headers(dict(resp_curl.headers)),
                request=httpx.Request("GET", url)
            )
            return mock_resp
        except Exception as exc:
            logger.error("Échec curl_cffi direct sur hard target : %s. Tentative httpx standard.", exc)

    # Fallback standard pour le reste du catalogue
    resp = client.get(url, headers=headers)
    return resp
    
