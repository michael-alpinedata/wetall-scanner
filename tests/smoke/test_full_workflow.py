import pytest
import logging
from wetall_scanner.scanner.database import DatabaseManager
from wetall_scanner.scanner.http_client import HTTPClient
from wetall_scanner.scanner.orchestrator import ScannerOrchestrator
from wetall_scanner.scanner.extractor import WetallExtractor  # Ajout de l'extracteur


@pytest.fixture
def components():
    db = DatabaseManager()
    http = HTTPClient()
    extractor = WetallExtractor()  # Initialisation de l'extracteur
    orchestrator = ScannerOrchestrator(db, http, extractor)  # Passage à l'orchestrateur
    return db, http, orchestrator


@pytest.fixture
def test_product(components):
    """Fixture Smoke Test : crée et nettoie le produit wetall temporaire via le DatabaseManager."""
    db, _, _ = components

    # Ton URL réelle de test (qui renvoie un code 200)
    vrai_url_wetall = "https://www.wetall.fr/produit/nike-homme-precision-vii-grande-taille-jusqua-pointure-525/"

    new_product_data = {
        "url_wetall": vrai_url_wetall,
        "nom_produit": "SMOKE TEST - Nike Precision VII",
        "nom_vendeur": "",  # Laissé vide, l'orchestrateur doit l'extraire et le remplir
        "url_marchand_finale": None,  # NULL pour forcer le passage dans run_link_discovery
    }

    # SETUP : Insertion propre en BDD de test via le manager
    product_id = db.insert_product(new_product_data)
    new_product_data["produit_id"] = product_id

    yield new_product_data

    # TEARDOWN : Nettoyage automatique après le test, même en cas d'échec (assert Fail)
    try:
        db.delete_product(product_id)
    except Exception as e:
        logging.error(
            f"Erreur lors de la suppression du produit de test {product_id} : {e}"
        )


@pytest.mark.smoke
def test_smoke_link_discovery(components, test_product):
    """Vérifie que l'extracteur arrive à transformer le lien Wetall Nike en lien marchand
    et extraire le nom du marchand à partir de l'url obtenue."""
    db, _, orchestrator = components
    p_id = test_product["produit_id"]

    # 1. Exécution CIBLÉE du workflow de découverte sur notre ID de test unique
    orchestrator.run_link_discovery(limit=1, product_id=p_id)

    # 2. Vérification directe du résultat par ID
    updated_p = db.get_product_by_id(p_id)

    # 3. Assertions de bout en bout
    assert updated_p is not None, (
        f"Le produit {p_id} n'a pas été trouvé en base de données."
    )
    assert updated_p["url_marchand_finale"] is not None, (
        "Le scraper n'a pas réussi à extraire l'URL marchande de la page Nike."
    )
    assert updated_p["url_marchand_finale"].startswith("http"), (
        "L'URL extraite n'est pas une URL HTTP valide."
    )
    assert "wetall.fr" not in updated_p["url_marchand_finale"], (
        "L'URL finale ne doit pas pointer vers Wetall."
    )

    # Validation de l'extraction dynamique du vendeur
    assert updated_p["nom_vendeur"] not in [None, ""], (
        "L'orchestrateur n'a pas extrait ni mis à jour le nom du vendeur."
    )


@pytest.mark.smoke
def test_smoke_stock_monitoring(components):
    """Vérifie que le système peut scanner le stock sur une URL marchande connue."""
    db, _, orchestrator = components

    # On cherche un produit déjà prêt (URL marchande présente)
    products = db.get_products_to_monitor(limit=1)
    if not products:
        pytest.skip("Aucun produit prêt pour le monitoring en base.")

    target_id = products[0]["produit_id"]

    # Exécution CIBLÉE du scan de stock sur le produit sélectionné
    results = orchestrator.run_stock_monitoring(limit=1, product_id=target_id)

    # Assertions
    assert len(results) > 0
    assert results[0]["produit_id"] == target_id

    # Statuts normalisés et nettoyés après refactoring
    assert results[0]["status"] in [
        "EN_STOCK",
        "HORS_STOCK",
        "ERREUR_TECHNIQUE",
        "A_VERIFIER",
    ]
