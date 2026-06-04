from bs4 import BeautifulSoup
import abc

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
    Implémentation spécifique pour Amazon.fr.
    Priorise la détection d'éléments DOM structurels (IDs) plutôt que le texte,
    car les IDs sont plus stables face aux changements de langue ou de design.
    """

    def analyze(self, html_content: str) -> tuple[str, str]:
        if not html_content:
            return "Erreur technique", "Contenu HTML vide ou non reçu"
            
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # LOGIQUE 1 : Recherche des boutons d'action d'achat.
        # Sur Amazon, la présence de ces IDs garantit que le produit est commandable.
        # 'add-to-cart-button' est le standard, 'buy-now-button' est le bouton d'achat immédiat.
        add_to_cart = soup.find(id="add-to-cart-button")
        buy_now = soup.find(id="buy-now-button")
        
        if add_to_cart or buy_now:
            return "OK", "Bouton d'achat identifié dans le DOM"
            
        # LOGIQUE 2 : Détection explicite de rupture.
        # Si les boutons manquent, on cherche le conteneur de message d'indisponibilité.
        if soup.find(id="outOfStock"):
            return "Hors Stock", "ID 'outOfStock' présent sur la page"

        # LOGIQUE 3 : Cas de sécurité.
        # Si aucun indicateur de stock ou de rupture n'est trouvé, on considère par défaut
        # que le produit est indisponible pour éviter d'envoyer des utilisateurs vers des pages mortes.
        return "Hors Stock", "Aucun indicateur de stock détecté (Bouton/ID absent)"

class DecathlonScanner(BaseScanner):
    """
    Implémentation pour Decathlon.fr.
    Note : Souvent sujet aux blocages IP (403).
    """

    def analyze(self, html_content: str) -> tuple[str, str]:
        # TODO: Implémenter la détection spécifique (souvent basée sur les classes de boutons)
        # Actuellement en attente de résolution des blocages IP.
        return "Bloqué/Grisé", "Moteur de scan Decathlon en attente d'implémentation"

class GenericScanner(BaseScanner):
    """
    Scanner de secours utilisé lorsqu'un marchand n'a pas encore de stratégie propre.
    Tente une détection basique basée sur des termes génériques.
    """

    def analyze(self, html_content: str) -> tuple[str, str]:
        # Logique très simple de repli
        return "À vérifier", "Marchand non supporté spécifiquement"