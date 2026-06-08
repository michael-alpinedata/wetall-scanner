import pytest
import respx
import httpx
import uuid
from wetall_scanner.scanner.constants import ScanResult


@pytest.mark.smoke
@pytest.mark.parametrize(
    "scenario, url_marchande, fichier_fixture, vendeur, statut_attendu",
    [
        (
            "Amazon_En_Stock",
            "https://www.amazon.fr/dp/2959790502",
            "amazon_en_stock.html",
            "Amazon",
            ScanResult.EN_STOCK.code,
        ),
        (
            "Amazon_Hors_Stock",
            "https://www.amazon.fr/Drop-Avery-Square-Heeled-Sandal/dp/B09JZY3GGH",
            "amazon_hors_stock.html",
            "Amazon",
            ScanResult.HORS_STOCK.code,
        ),
        (
            "Decathlon_Antibot",
            "https://www.decathlon.fr/p/chaussures-de-basketball-homme-femme-ss500-noir/144026/m8790079",
            "decathlon_bloque.html",
            "Decathlon",
            ScanResult.BLOQUE_CAPTCHA.code,
        ),
    ],
)
@respx.mock
def test_smoke_stock_monitoring_scenarios(
    components,
    load_fixture,
    scenario,
    url_marchande,
    fichier_fixture,
    vendeur,
    statut_attendu,
):
    db, _, orchestrator = components
    html_content = load_fixture(fichier_fixture)

    respx.get(url_marchande).mock(return_value=httpx.Response(200, text=html_content))

    p_id = db.insert_product(
        {
            "nom_produit": f"SMOKE - {scenario}",
            "url_wetall": f"https://www.wetall.fr/{uuid.uuid4()}",
            "nom_vendeur": vendeur,
            "url_marchand_finale": url_marchande,
        }
    )

    try:
        results = orchestrator.run_stock_monitoring(limit=1, product_id=p_id)
        assert len(results) == 1
        assert results[0]["status"] == statut_attendu
    finally:
        db.delete_product(p_id)
