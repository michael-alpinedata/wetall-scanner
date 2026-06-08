import pytest
import logging
from wetall_scanner.scanner.database import DatabaseManager
from wetall_scanner.scanner.http_client import HTTPClient
from wetall_scanner.scanner.orchestrator import ScannerOrchestrator
from wetall_scanner.scanner.extractor import WetallExtractor  # Ajout de l'extracteur
from wetall_scanner.scanner.constants import ScanResult


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
@pytest.mark.parametrize(
    "scenario, url_marchande, vendeur, statut_attendu",
    [
        (
            "Amazon_En_Stock",
            "https://www.amazon.fr/dp/2959790502?__mk_fr_FR=%C3%85M%C3%85%C5%BD%C3%95%C3%91&crid=2CZ51GHHAFIFJ&dib=eyJ2IjoiMSJ9.gEt5v4BHL22XJgOqHaVWYSclichqCO0tHTNTNQp03bE.A7tqbC478Uy_2SyEpudWOM7cBy6YqSZI0QeTz6y8x7Y&dib_tag=se&keywords=yoann+Genier&qid=1759395302&sprefix=yoann+genier,aps,77&sr=8-1&linkCode=sl1&tag=spdy-21&linkId=01ca3e7b3adf1d626bf9725e2394e3dd&language=fr_FR&ref_=as_li_ss_tl",  # Un bouquin classique souvent édité/disponible
            "Amazon",
            ScanResult.EN_STOCK.code,
        ),
        (
            "Amazon_Hors_Stock",
            "https://www.amazon.fr/Drop-Avery-Square-Heeled-Sandal/dp/B09JZY3GGH?pf_rd_i=20956511031&pf_rd_m=A1X6FK5RDHNB96&pf_rd_p=093ceae9-38cc-4022-ac70-1c4144554700&pf_rd_r=F85MV9AA6WMXN3P8MS2B&pf_rd_s=merchandised-search-4&pf_rd_t=101&qid=1669277209&refinements=p_n_deal_type%3A26902975031%2Cp_n_size_browse-vebin%3A14675964031%257C14675965031%257C14675966031%257C14675967031%257C14675968031%257C14675969031%257C14675970031%257C14675971031%257C14675972031&rnid=1902697031&s=apparel&sr=1-25&th=1&linkCode=sl1&tag=wetall-21&linkId=9782fbf0c6f4cf71035ab880806bc970&language=fr_FR&ref_=as_li_ss_tl&psc=1",  # Un vieux produit obsolète ou introuvable depuis des années
            "Amazon",
            ScanResult.HORS_STOCK.code,
        ),
        (
            "Decathlon_Antibot",
            # n'est plus en stock vivisblement car fallback : https://www.decathlon.fr/tous-les-sports/basketball/chaussures-de-basket-kipsta
            # "https://www.decathlon.fr/p/chaussure-de-basketball-fast-500-grise-tige-basse-homme/_/R-p-306446?mc=8547445&c=GRIS",  # URL Decathlon standard qui va se heurter à DataDome/Cloudflare
            # n'est plus en stock vivisblement car fallback : https://www.decathlon.fr/tous-les-sports/velo-cyclisme/vtt-electrique
            # "https://www.decathlon.fr/p/velo-vtt-electrique-e-st-500-v2-noir-bleu-27-5/_/R-p-310922?mc=8561490&c=GRIS",  # URL Decathlon standard qui va se heurter à DataDome/Cloudflare
            # en stock le 08/06/2026 (mas surement bloqué antibot):
            "https://www.decathlon.fr/p/chaussures-de-basketball-homme-femme-ss500-noir/144026/m8790079",  # URL Decathlon standard qui va se heurter à DataDome/Cloudflare
            "Decathlon",
            ScanResult.BLOQUE_CAPTCHA.code,
        ),
    ],
)
def test_smoke_stock_monitoring_scenarios(
    components, scenario, url_marchande, vendeur, statut_attendu
):
    """
    Vérifie le comportement réel du monitoring face à des situations concrètes :
    Amazon disponible, Amazon épuisé, et Decathlon protégé par un dispositif anti-bot.
    """
    db, _, orchestrator = components

    # 1. Préparation de la donnée de test éphémère
    product_data = {
        "nom_produit": f"SMOKE MONITORING - {scenario}",
        "url_wetall": f"https://www.wetall.fr/smoke-test-{scenario.lower()}",
        "nom_vendeur": vendeur,
        "url_marchand_finale": url_marchande,
    }

    # Insertion en base (Savoir quel ID Neon nous a attribué)
    p_id = db.insert_product(product_data)

    try:
        # 2. Exécution ciblée du monitoring sur ce produit précis
        results = orchestrator.run_stock_monitoring(limit=1, product_id=p_id)

        # 3. Validations de base sur le retour de l'orchestrateur
        assert len(results) == 1, (
            f"Le scan n'a retourné aucun résultat pour le scénario {scenario}"
        )
        assert results[0]["produit_id"] == p_id

        # 4. Validation de la détection métier
        assert results[0]["status"] == statut_attendu, (
            f"Scénario {scenario} échoué. "
            f"Attendu: {statut_attendu}, Obtenu: {results[0]['status']}"
        )

    finally:
        # 5. Nettoyage chirurgical de la base de données Neon pour ne laisser aucune trace
        db.delete_product(p_id)
