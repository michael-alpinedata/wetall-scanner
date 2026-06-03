import pytest
import respx
import httpx
from src.scanner.orchestrator import smart_scan
from src.scanner.parser import get_buy_link_from_wetall
from bs4 import BeautifulSoup


def test_extract_amazon_link():
    """Vérifie qu'on extrait correctement un lien Amazon depuis une page Wetall."""
    html_mock = """
    <div class="product">
        <a href="https://www.amazon.fr/dp/B0123456789/?tag=wetall-21">Acheter sur Amazon</a>
    </div>
    """
    soup = BeautifulSoup(html_mock, "html.parser")
    link, _ = get_buy_link_from_wetall(soup)
    assert "amazon.fr/dp/B0123456789" in link


def test_resolve_affiliation_link():
    """Vérifie la résolution du lien LinkSynergy."""
    from src.scanner.http_client import resolve_affiliation_link

    ls_url = "https://click.linksynergy.com/deeplink?murl=https%3A%2F%2Fwww.decathlon.fr%2Fproduit-test"
    resolved = resolve_affiliation_link(ls_url)

    assert "decathlon.fr" in resolved
    assert "https://www.decathlon.fr/produit-test" == resolved


def test_wetall_detect_buy_button():
    """Vérifie qu'on détecte correctement le bouton d'achat Wetall."""
    # HTML simulant une vraie page produit Wetall
    html_mock = """
    <div class="product">
        <a href="https://www.amazon.fr/dp/B071DH6LKT/" class="button alt">Commander</a>
    </div>
    """
    soup = BeautifulSoup(html_mock, "html.parser")
    link, _ = get_buy_link_from_wetall(soup)

    assert link == "https://www.amazon.fr/dp/B071DH6LKT/"


def test_wetall_no_buy_button():
    """Vérifie qu'on détecte bien l'absence de bouton."""
    html_mock = '<div class="product">Produit indisponible</div>'
    soup = BeautifulSoup(html_mock, "html.parser")
    link, _ = get_buy_link_from_wetall(soup)

    assert link is None


@respx.mock
def test_smart_scan_success():
    # On simule la réponse de Wetall
    respx.get("https://www.wetall.fr/produit/test").mock(
        return_value=httpx.Response(
            200, text='<a href="https://amazon.fr/dp/123" class="button">Commander</a>'
        )
    )

    # On simule la réponse d'Amazon
    respx.get("https://amazon.fr/dp/123").mock(
        return_value=httpx.Response(
            200, text="<html><body><div id='add-to-cart'>Ajouté</div></body></html>"
        )
    )

    with httpx.Client() as client:
        status, code, _, _ = smart_scan(client, "https://www.wetall.fr/produit/test")
        # Ici on vérifie que ton parser a tout bien enchaîné
        assert code == 200


# Définition des scénarios de test
@pytest.mark.parametrize(
    "html_content, expected_status",
    [
        ('<div class="out-of-stock">En rupture</div>', "Rupture de stock"),
        (
            '<form class="variations_form">Select Taille</form>',
            "Variations (Taille/Couleur)",
        ),
        (
            '<a href="https://amazon.fr/dp/123" class="button">Commander</a>',
            "https://amazon.fr/dp/123",
        ),
    ],
)
def test_parsing_scenarios(html_content, expected_status):
    soup = BeautifulSoup(html_content, "html.parser")
    result, _ = get_buy_link_from_wetall(soup)

    if expected_status == "Rupture de stock":
        assert result == "Rupture de stock"
    elif expected_status == "Variations (Taille/Couleur)":
        assert result == "Variations (Taille/Couleur)"
    else:
        assert result == expected_status
