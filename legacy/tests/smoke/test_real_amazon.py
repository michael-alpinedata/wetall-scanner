# tests/smoke/test_real_amazon.py
import pytest
import httpx


@pytest.mark.smoke
def test_real_amazon_connectivity():
    """Vérifie une fois par jour si Amazon nous laisse passer (Vrai scan)."""
    with httpx.Client(follow_redirects=True) as client:
        # On utilise une URL produit Amazon standard
        resp = client.get("https://www.amazon.fr/dp/B071DH6LKT/")

        # On vérifie si on est bloqué
        assert resp.status_code == 200
        assert "amazon" in resp.text.lower()
