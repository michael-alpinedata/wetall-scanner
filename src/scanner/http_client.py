import httpx
import random
import logging
from typing import TypedDict, Optional

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
        headers = {
            "User-Agent": random.choice(self.USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": "https://www.google.com/",
            "Upgrade-Insecure-Requests": "1"
        }

        try:
            # follow_redirects=True est crucial pour obtenir l'URL finale marchande depuis Wetall
            with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
                response = client.get(url, headers=headers)
                
                return {
                    "html": response.text,
                    "status_code": response.status_code,
                    "url_finale": str(response.url),
                    "error": None
                }

        except httpx.ConnectTimeout:
            return {"html": "", "status_code": 0, "url_finale": url, "error": "Timeout de connexion"}
        except httpx.HTTPStatusError as e:
            return {"html": "", "status_code": e.response.status_code, "url_finale": url, "error": f"Erreur HTTP: {str(e)}"}
        except Exception as e:
            # Capture générique pour éviter de faire planter l'orchestrateur
            return {"html": "", "status_code": 0, "url_finale": url, "error": f"Exception: {str(e)[:50]}"}