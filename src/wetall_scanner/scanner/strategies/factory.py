# Imports depuis les nouveaux fichiers éclatés
from .base import BaseScanner
from .amazon import AmazonScanner
from .decathlon import DecathlonScanner
from .generic import GenericScanner


class ScannerFactory:
    """Distribue le bon scanner en fonction du nom du vendeur. Totalement Stateless."""

    _registry = {
        "amazon": AmazonScanner(),
        "decathlon": DecathlonScanner(),
        # Demain : "fnac": FnacScanner()
    }

    @classmethod
    def get_scanner(cls, vendor_name: str | None) -> BaseScanner:
        """Retourne le scanner approprié ou le scanner de secours si inconnu/absent."""
        if not vendor_name:
            return GenericScanner()
        return cls._registry.get(vendor_name.lower(), GenericScanner())
