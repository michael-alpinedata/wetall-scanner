from enum import Enum

class ScanStatus(Enum):
    EN_STOCK = "EN_STOCK"
    HORS_STOCK = "HORS_STOCK"
    ERREUR = "ERREUR_TECHNIQUE"

# Messages de log / retour
MSG_BUY_BUTTON = "Bouton d'achat détecté"
MSG_OUT_OF_STOCK = "Rupture de stock"
MSG_NO_BUTTON = "Aucun bouton trouvé"