import time
import random
import httpx
import logging
from typing import TypedDict, Optional

# Assumons que ces imports existent déjà dans ton projet
from curl_cffi import requests as cffi_requests

logger = logging.getLogger(__name__)


class FetchResult(TypedDict):
    """Structure de réponse unifiée pour le scraping."""

    html: str
    status_code: int
    url_finale: str
    error: Optional[str]


class HTTPClient:
    """
    Client HTTP optimisé pour le scraping de fiches produits.
    Gère la simulation de navigateur (User-Agents), les timeouts,
    le contournement anti-bot et le lissage du trafic (jitter).
    """

    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edge/119.0.0.0",
    ]

    def __init__(self, timeout: int = 30):
        """Initialise le client avec un timeout par défaut."""
        self.timeout = timeout
        logger.debug(f"HTTPClient initialisé avec un timeout de {timeout}s.")

    def _apply_jitter(self):
        """Ajoute un délai aléatoire pour simuler une navigation humaine."""
        delay = random.uniform(2.0, 5.0)
        logger.debug(
            f"Jitter appliqué : attente de {delay:.2f}s avant la prochaine action."
        )
        time.sleep(delay)

    def fetch(self, url: str) -> dict:
        """
        Récupère le contenu d'une URL via httpx.
        Retourne un dictionnaire standardisé, sans lever d'exception sur les 4xx/5xx.
        """
        ua = random.choice(self.USER_AGENTS)
        headers = {"User-Agent": ua}

        logger.info(f"Tentative fetch standard : {url}")

        try:
            with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
                response = client.get(url, headers=headers)

                # On ne lève pas d'exception ici (raise_for_status supprimé)
                # pour laisser l'Orchestrator gérer les 404 proprement.

                logger.info(f"Fetch réussi : {url} | Status: {response.status_code}")

                return {
                    "html": response.text,
                    "status_code": response.status_code,
                    "url_finale": str(response.url),
                    "error": None,
                }

        except httpx.ConnectTimeout:
            # Message corrigé pour correspondre exactement à l'attente du test
            logger.warning(f"Timeout de connexion atteint pour {url}")
            return {
                "html": "",
                "status_code": 0,
                "url_finale": url,
                "error": "Timeout de connexion",
            }

        except Exception as e:
            logger.exception(f"Erreur inattendue sur {url}")
            return {"html": "", "status_code": 500, "url_finale": url, "error": str(e)}

    def fetch_stealth(self, url: str) -> FetchResult:
        """
        Effectue une requête ultra-furtive via curl_cffi (imitation TLS Chrome).
        """
        logger.info(f"Stealth Fetch : Contournement anti-bot pour {url}")

        try:
            # impersonate="chrome124" émule le handshake TLS de Chrome
            response = cffi_requests.get(
                url, impersonate="chrome124", timeout=self.timeout
            )

            logger.info(
                f"Stealth Fetch réussi : {url} | Status: {response.status_code}"
            )

            result = {
                "html": response.text,
                "status_code": response.status_code,
                "url_finale": str(response.url),
                "error": None,
            }
        except Exception as e:
            logger.error(f"Erreur critique Stealth Fetch sur {url}: {e}")
            result = {
                "html": "",
                "status_code": 500,
                "url_finale": url,
                "error": str(e),
            }

        self._apply_jitter()
        return result
