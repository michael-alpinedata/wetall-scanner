from enum import Enum

class ScanResult(Enum):
    # Format : NOM = (Code_Status, Message_Par_Defaut, is_error, requires_action)
    
    # --- Succès & État ---
    EN_STOCK = ("EN_STOCK", "Bouton d'achat détecté", False, False)
    HORS_STOCK = ("HORS_STOCK", "Rupture de stock", False, False)
    
    # --- Infrastructure / Blocage ---
    BLOQUE_BOT = ("BLOQUE_BOT", "Blocage antibot détecté", True, True)
    ERREUR_RESEAU = ("ERREUR_RESEAU", "Erreur de connexion réseau", True, True)
    
    # --- Structure & Maintenance ---
    PAGE_404 = ("PAGE_404", "Page introuvable (404)", True, False)
    
    # --- Cas indéterminés & Configuration ---
    A_VERIFIER = ("A_VERIFIER", "Produit détecté mais ambigu", True, False)
    ERREUR_CONFIG = ("ERREUR_CONFIG", "Vendeur non supporté", True, False)

    def __init__(self, code, message, is_error, requires_action):
        self._code = code
        self._message = message
        self._is_error = is_error
        self._requires_action = requires_action

    @property
    def code(self): return self._code
    @property
    def message(self): return self._message
    @property
    def is_error(self): return self._is_error
    @property
    def requires_action(self): return self._requires_action

# Enum pour la validation API restreint aux valeurs réelles
FilterStatus = Enum("FilterStatus", {item.code: item.code for item in ScanResult})