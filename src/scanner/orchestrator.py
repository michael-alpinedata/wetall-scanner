"""
Orchestrateur du scan d'un produit Wetall.

Responsabilité unique : coordonner les étapes du scan en séquence
(Wetall → extraction du lien → marchand final → analyse) sans
contenir aucune logique métier propre.
"""

import logging
import random
import time

import httpx
from bs4 import BeautifulSoup

from .analyzer import analyze_merchant_status
from .http_client import build_headers, fetch_with_fallback
from .parser import get_buy_link_from_wetall, normalize_amazon_url

logger = logging.getLogger(__name__)

# Type alias
ScanOutput = tuple[str, int, str | None, str]
# (statut_lisible, http_code_marchand, url_finale, message_debug)


def _fetch_wetall_page(
    client: httpx.Client, url_wetall: str, headers: dict
) -> httpx.Response | ScanOutput:
    """
    Télécharge la page Wetall.

    Retourne la réponse HTTP ou un ScanOutput d'erreur directement.
    """
    time.sleep(random.uniform(4, 7))
    resp = client.get(url_wetall, headers=headers)
    if resp.status_code != 200:
        return (
            f"Erreur Wetall {resp.status_code}",
            resp.status_code,
            None,
            "Fail Wetall",
        )
    return resp


def _extract_buy_link(resp_wetall: httpx.Response) -> str | ScanOutput:
    """
    Parse la page Wetall et extrait le lien marchand.

    Retourne l'URL du lien ou un ScanOutput décrivant le cas particulier
    (variations, rupture Wetall, bouton absent).
    """
    soup = BeautifulSoup(resp_wetall.text, "html.parser")
    buy_link, _ = get_buy_link_from_wetall(soup)

    if not buy_link:
        if soup.find("form", class_="variations_form"):
            return "Variations (Taille/Couleur)", 200, None, "Structure variations"
        if "en rupture" in resp_wetall.text.lower():
            return "Rupture de stock", 200, None, "Marqueur rupture Wetall"
        return "Bouton non trouvé", 200, None, "Aucun lien extrait"

    return buy_link


def _scan_merchant(client: httpx.Client, buy_link: str, headers: dict) -> ScanOutput:
    """
    Scanne la page du marchand final et retourne le statut de stock.

    Gère les codes d'erreur HTTP (403, 401, 404) avant l'analyse métier.
    """
    buy_link = normalize_amazon_url(buy_link)
    logger.info("Scan marchand : %s...", buy_link[:40])
    time.sleep(random.uniform(12, 22))

    resp_m = fetch_with_fallback(client, buy_link, headers)

    if resp_m.status_code in (401, 403):
        return (
            "Vérification bloquée (403)",
            resp_m.status_code,
            str(resp_m.url),
            "Pare-feu marchand",
        )
    if resp_m.status_code == 404:
        return "Lien Brisé (404)", 404, str(resp_m.url), "Erreur 404 serveur"

    status, msg = analyze_merchant_status(str(resp_m.url), resp_m.text)
    return status, resp_m.status_code, str(resp_m.url), msg


def smart_scan(client: httpx.Client, url_wetall: str) -> ScanOutput:
    """
    Orchestre le scan complet d'un produit Wetall en trois étapes :

    1. Téléchargement de la fiche produit Wetall.
    2. Extraction et normalisation du lien marchand.
    3. Scan de la page marchand et analyse du statut de stock.

    Args:
        client:      Client httpx partagé (connexions réutilisées).
        url_wetall:  URL de la fiche produit sur wetall.fr.

    Returns:
        (statut_lisible, http_code, url_finale, message_debug)
    """
    headers = build_headers()

    try:
        # Étape 1 — Page Wetall
        wetall_result = _fetch_wetall_page(client, url_wetall, headers)
        if isinstance(wetall_result, tuple):
            return wetall_result  # Early-exit : erreur HTTP Wetall
        resp_wetall = wetall_result

        # Étape 2 — Extraction du lien
        link_result = _extract_buy_link(resp_wetall)
        if isinstance(link_result, tuple):
            return link_result  # Early-exit : cas particulier Wetall
        buy_link = link_result

        # Étape 3 — Scan marchand
        return _scan_merchant(client, buy_link, headers)

    except Exception as exc:
        return "Erreur technique", 0, None, f"Exception: {str(exc)[:50]}"
