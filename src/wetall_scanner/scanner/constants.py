from enum import Enum


class ScanStatus(Enum):
    EN_STOCK = "EN_STOCK"
    HORS_STOCK = "HORS_STOCK"
    LIEN_BRISE = "LIEN_BRISE"
    ERREUR = "ERREUR_TECHNIQUE"
    A_VERIFIER = "A_VERIFIER"


# Messages de log / retour
MSG_BUY_BUTTON = "Bouton d'achat détecté"
MSG_OUT_OF_STOCK = "Rupture de stock"
MSG_NO_BUTTON = "Aucun bouton trouvé"
