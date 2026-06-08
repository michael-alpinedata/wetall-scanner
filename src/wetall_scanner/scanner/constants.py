from enum import Enum


class ScanResult(Enum):
    # Format : NOM = (Code_Status, Message_Par_Defaut, is_error, requires_action)

    # --- Succès ---
    EN_STOCK = ("EN_STOCK", "Bouton d'achat détecté", False, False)
    HORS_STOCK = ("HORS_STOCK", "Rupture de stock", False, False)
    NO_BUTTON = ("NO_BUTTON", "Aucun bouton trouvé", False, False)

    # --- Infrastructure / Blocage ---
    BLOQUE_CAPTCHA = ("BLOQUE_BOT", "Blocage Amazon détecté (CAPTCHA)", True, True)
    BLOCK_IP = ("BLOQUE_IP", "Blocage IP suspecté (Rate limiting)", True, True)
    TIMEOUT = ("TIMEOUT", "Le délai d'attente a été dépassé", True, True)
    ERREUR_RESEAU = ("ERREUR_RESEAU", "Erreur de connexion réseau", True, True)

    # --- Structure & Maintenance ---
    STRUCT_CHANGEE = (
        "STRUCTURE_CHANGEE",
        "Structure CSS modifiée (sélecteur introuvable)",
        True,
        False,
    )
    PAGE_404 = ("PAGE_404", "Page introuvable (404)", True, False)
    STRUCT_TITLE_MISSING = ("A_VERIFIER", "Titre du produit absent", True, False)

    # --- Technique ---
    HTML_EMPTY = (
        "HTML_TROP_COURT",
        "Contenu HTML reçu vide ou trop court",
        True,
        False,
    )

    # --- Cas indéterminés & Configuration ---
    A_VERIFIER = (
        "A_VERIFIER",
        "Statut ambigu : produit détecté mais paramètres inconnus",
        True,
        False,
    )
    VENDEUR_NON_GERE = (
        "ERREUR_CONFIG",
        "Vendeur non supporté par la plateforme",
        True,
        False,
    )

    def __init__(self, code, message, is_error, requires_action):
        self._code = code
        self._message = message
        self._is_error = is_error
        self._requires_action = requires_action

    @property
    def code(self):
        return self._code

    @property
    def message(self):
        return self._message

    @property
    def is_error(self):
        return self._is_error

    @property
    def requires_action(self):
        return self._requires_action
