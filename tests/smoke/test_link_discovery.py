import pytest
import respx
import httpx
import uuid


@pytest.mark.smoke
@respx.mock
def test_smoke_link_discovery(components, load_fixture):
    db, _, orchestrator = components

    wetall_url = "https://www.wetall.fr/produit/nike-unique-id"
    respx.get(wetall_url).mock(
        return_value=httpx.Response(200, text=load_fixture("wetall_discovery.html"))
    )

    p_id = db.insert_product(
        {
            "url_wetall": wetall_url,
            "nom_produit": f"SMOKE - {uuid.uuid4()}",
            "nom_vendeur": "",
            "url_marchand_finale": None,
        }
    )

    try:
        orchestrator.run_link_discovery(limit=1, product_id=p_id)
        updated_p = db.get_product_by_id(p_id)

        assert updated_p["url_marchand_finale"] is not None
        assert updated_p["nom_vendeur"] != ""
    finally:
        db.delete_product(p_id)
