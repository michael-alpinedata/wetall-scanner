import httpx
import random
import logging
from typing import TypedDict, Optional

# Configuration du logger pour le module réseau
logger = logging.getLogger(__name__)

class FetchResult(TypedDict):
    """Structure de données retournée par le client HTTP."""
    html: str
    status_code: int
    url_finale: str
    error: Optional[str]

class HTTPClient:
    """
    Client HTTP optimisé pour le scraping de fiches produits.
    Gère la simulation de navigateur (User-Agents), les timeouts et les redirections.
    """

    # Liste de User-Agents modernes pour simuler différents navigateurs et systèmes
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edge/119.0.0.0",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
    ]

    def __init__(self, timeout: int = 15):
        """
        Args:
            timeout (int): Temps maximum en secondes pour chaque requête.
        """
        self.timeout = timeout
        logger.debug(f"HTTPClient initialisé avec un timeout de {timeout}s.")

    def fetch(self, url: str) -> FetchResult:
        """
        Récupère le contenu d'une URL en suivant les redirections.
        
        Args:
            url (str): L'URL cible à scanner (Wetall ou Marchand).
            
        Returns:
            FetchResult: Un dictionnaire contenant le HTML, le code HTTP, 
                         l'URL finale (après redirection) et les erreurs éventuelles.
        """
        # Choix d'un User-Agent aléatoire pour chaque requête
        ua = random.choice(self.USER_AGENTS)
        headers = {
            "User-Agent": ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": "https://www.google.com/",
            "Upgrade-Insecure-Requests": "1"
        }

        logger.debug(f"Tentative de fetch : {url} | UA: {ua[:50]}...")

        try:
            # follow_redirects=True est crucial pour obtenir l'URL finale marchande depuis Wetall
            with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
                response = client.get(url, headers=headers)
                
                logger.info(f"Fetch réussi: {url} | Status: {response.status_code} | Redirect vers: {response.url}")
                
                return {
                    "html": response.text,
                    "status_code": response.status_code,
                    "url_finale": str(response.url),
                    "error": None
                }

        except httpx.ConnectTimeout:
            logger.warning(f"Timeout de connexion atteint pour l'URL: {url}")
            return {"html": "", "status_code": 0, "url_finale": url, "error": "Timeout de connexion"}
        except httpx.HTTPStatusError as e:
            logger.error(f"Erreur de statut HTTP pour {url}: {str(e)}")
            return {"html": "", "status_code": e.response.status_code, "url_finale": url, "error": f"Erreur HTTP: {str(e)}"}
        except Exception as e:
            # Capture générique pour éviter de faire planter l'orchestrateur
            # logger.exception permet d'enregistrer la stacktrace complète dans les logs
            logger.exception(f"Erreur non gérée lors du fetch de {url}")
            return {"html": "", "status_code": 0, "url_finale": url, "error": f"Exception: {str(e)[:50]}"}