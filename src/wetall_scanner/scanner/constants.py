from enum import Enum


class ScanStatus(Enum):
    EN_STOCK = "EN_STOCK"
    HORS_STOCK = "HORS_STOCK"
    LIEN_BRISE = "LIEN_BRISE"
    ERREUR = "ERREUR_TECHNIQUE"
    A_VERIFIER = "A_VERIFIER"


# ==========================================
# Messages de log / retour standardisés
# ==========================================

# Statuts de stock et boutons
MSG_BUY_BUTTON = "Bouton d'achat détecté"
MSG_OUT_OF_STOCK = "Rupture de stock"
MSG_NO_BUTTON = "Aucun bouton trouvé"

# Validations techniques et erreurs HTML
MSG_HTML_EMPTY = "Contenu HTML reçu vide ou trop court"
MSG_PAGE_404 = "Page 404 détectée"
MSG_PRODUCT_TITLE_MISSING = "Titre du produit absent, mais l'analyse continue"

# Statuts des moteurs spécifiques
MSG_NOT_IMPLEMENTED = "Moteur de scan Decathlon en attente d'implémentation"
MSG_UNSUPPORTED_MERCHANT = "Marchand non supporté spécifiquement"
