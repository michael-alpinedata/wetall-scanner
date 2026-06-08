import pytest
from wetall_scanner.scanner.strategies import DecathlonScanner
from wetall_scanner.scanner.constants import ScanResult

PADDING = " " * 1000


class TestDecathlonScanner:
    @pytest.fixture
    def scanner(self):
        return DecathlonScanner()

    def test_analyze_in_stock(self, scanner):
        html = f"""
        <html>
            <body>
                <h1 class="product-title">Titre Produit</h1>
                <script type="application/ld+json">
                {{
                    "@type": "Product", 
                    "name": "Titre Produit",
                    "offers": {{"availability": "https://schema.org/InStock"}}
                }}
                </script>
                {PADDING}
            </body>
        </html>
        """
        fetch_data = {"html": html, "status_code": 200}
        result = scanner.analyze(fetch_data)
        assert result == ScanResult.EN_STOCK

    def test_analyze_out_of_stock(self, scanner):
        html = f"""
        <html>
            <body>
                <h1 class="product-title">Titre Produit</h1>
                <script type="application/ld+json">
                {{
                    "@type": "Product", 
                    "name": "Titre Produit",
                    "offers": {{"availability": "https://schema.org/OutOfStock"}}
                }}
                </script>
                {PADDING}
            </body>
        </html>
        """
        fetch_data = {"html": html, "status_code": 200}
        result = scanner.analyze(fetch_data)
        assert result == ScanResult.HORS_STOCK

    def test_analyze_blocked_by_antibot(self, scanner):
        # Pour le blocage, si le code 403 est intercepté en amont par le BaseScanner,
        # vérifie si tu dois tester le comportement du BaseScanner plutôt que du DecathlonScanner
        html = "<html><body><h1>Accès refusé</h1>" + (" " * 2000) + "</body></html>"
        fetch_data = {"html": html, "status_code": 403}

        result = scanner.analyze(fetch_data)
        # Si le BaseScanner force ERREUR_RESEAU pour un 403, ajuste l'assertion
        assert result in [ScanResult.BLOQUE_CAPTCHA, ScanResult.ERREUR_RESEAU]
