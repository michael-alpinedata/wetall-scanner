import os
import httpx

# Configuration des URLs à mocker
FIXTURES = {
    "amazon_en_stock.html": "https://www.amazon.fr/dp/2959790502",
    "amazon_hors_stock.html": "https://www.amazon.fr/Drop-Avery-Square-Heeled-Sandal/dp/B09JZY3GGH",
    "decathlon_bloque.html": "https://www.decathlon.fr/p/chaussures-de-basketball-homme-femme-ss500-noir/144026/m8790079",
    "wetall_discovery.html": "https://www.wetall.fr/produit/nike-homme-precision-vii-grande-taille-jusqua-pointure-525/",
}


def save_all_fixtures():
    output_dir = "tests/fixtures"
    os.makedirs(output_dir, exist_ok=True)

    # Utilisation d'un client unique pour toute la session de sauvegarde
    with httpx.Client(follow_redirects=True) as client:
        for filename, url in FIXTURES.items():
            print(f"Récupération de {url}...")
            # On simule un User-Agent pour éviter d'être bloqué pendant le script
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }

            try:
                response = client.get(url, headers=headers)
                path = os.path.join(output_dir, filename)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(response.text)
                print(f"-> Sauvegardé dans {path} ({response.status_code})")
            except Exception as e:
                print(f"-> Erreur sur {url}: {e}")


if __name__ == "__main__":
    save_all_fixtures()
