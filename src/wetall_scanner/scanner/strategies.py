import logging
from bs4 import BeautifulSoup
import abc

# Configuration du logger pour le module des stratégies
logger = logging.getLogger(__name__)

# Dans ton fichier scanner/strategies.py ou un fichier de config
STATUS_EN_STOCK = "EN_STOCK"
STATUS_HORS_STOCK = "HORS_STOCK"
STATUS_ERREUR = "ERREUR_TECHNIQUE"

class BaseScanner(abc.ABC):
    """
    Interface de base pour tous les moteurs de scan marchands.
    Chaque nouveau marchand (Cdiscount, Fnac, etc.) doit hériter de cette classe
    et implémenter la méthode 'analyze'.
    """

    @abc.abstractmethod
    def analyze(self, html_content: str) -> tuple[str, str]:
        """
        Analyse le contenu HTML brut pour déterminer la disponibilité du produit.
        
        Args:
            html_content (str): Le code source HTML de la page produit.
            
        Returns:
            tuple[str, str]: 
                - status_code: Le statut normalisé ('OK', 'Hors Stock', 'Bloqué/Grisé', etc.)
                - debug_info: Un message court expliquant la décision (ex: "Bouton détecté").
        """
        pass

class AmazonScanner(BaseScanner):
    """
    Scanner Amazon.fr avec gestion d'états granulaire pour le monitoring.
    """

    def analyze(self, html_content: str) -> tuple[str, str]:
        # 1. Validation technique de la page
        if not html_content or len(html_content) < 1000:
            return STATUS_ERREUR, "Page vide ou trop courte (BLOCAGE POTENTIEL)"
            
        soup = BeautifulSoup(html_content, 'html.parser')

        # 2. Détection de page inexistante (404 / Supprimé)
        # Amazon affiche souvent un message spécifique sur les pages 404
        # Exemple : "Désolé, nous ne trouvons pas cette page"
        title = soup.select_one("title")
        if title and ("404" in title.text or "non trouvée" in title.text.lower()):
            return STATUS_ERREUR, "Page 404 détectée"
            
        # Si on ne trouve pas le titre du produit (marqueur critique d'une fich,e produit)
        if not soup.select_one("#productTitle"):
            return STATUS_ERREUR, "Le titre du produit est absent de la page"

        # 3. Détection "EN STOCK"
        # Priorité absolue : le bouton d'achat.
        if soup.select_one("#add-to-cart-button") or soup.select_one("#buy-now-button"):
            return STATUS_EN_STOCK, "Produit commandable immédiatement"

        # 4. Détection "HORS STOCK" (Rupture temporaire)
        # On cherche des marqueurs de rupture dans la BuyBox
        availability_block = soup.select_one("#availability")
        if availability_block:
            text = availability_block.get_text().lower()
            if any(word in text for word in ["indisponible", "rupture", "unavailable", "currently"]):
                return STATUS_HORS_STOCK, f"Rupture confirmée : {text.strip()[:30]}"
        
        # 5. Cas par défaut (Indéterminé)
        # Si on est sur une fiche produit valide (titre présent), mais sans bouton ni message de rupture,
        # c'est souvent un produit en "précommande" ou un bug d'affichage.
        return "INDETERMINE", "Produit identifié mais statut d'achat inconnu"

class DecathlonScanner(BaseScanner):
    """
    Implémentation pour Decathlon.fr.
    Note : Souvent sujet aux blocages IP (403).
    """

    def analyze(self, html_content: str) -> tuple[str, str]:
        # TODO: Implémenter la détection spécifique (souvent basée sur les classes de boutons)
        # Actuellement en attente de résolution des blocages IP.
        logger.warning("DecathlonScanner: Tentative d'analyse sur une stratégie non implémentée (en attente de résolution IP).")
        return "Bloqué/Grisé", "Moteur de scan Decathlon en attente d'implémentation"

class GenericScanner(BaseScanner):
    """
    Scanner de secours utilisé lorsqu'un marchand n'a pas encore de stratégie propre.
    Tente une détection basique basée sur des termes génériques.
    """

    def analyze(self, html_content: str) -> tuple[str, str]:
        # Logique très simple de repli
        logger.info("GenericScanner: Utilisation du scanner de secours pour un marchand non supporté.")
        return "À vérifier", "Marchand non supporté spécifiquement"
