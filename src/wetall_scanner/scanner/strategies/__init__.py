from .base import BaseScanner
from .amazon import AmazonScanner
from .decathlon import DecathlonScanner
from .generic import GenericScanner
from .factory import ScannerFactory

# Cela permet de définir ce qui est exposé proprement à l'extérieur du dossier
__all__ = [
    "BaseScanner",
    "AmazonScanner",
    "DecathlonScanner",
    "GenericScanner",
    "ScannerFactory",
]
