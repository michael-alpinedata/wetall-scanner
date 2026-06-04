import os
import urllib.request
import urllib.error
import psycopg2
from wetall_scanner.scanner.database import DatabaseManager

OUTPUT_DIR = "tests/fixtures/html"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
}

def fetch_and_save(url, filename, category):
    path = os.path.join(OUTPUT_DIR, category)
    os.makedirs(path, exist_ok=True)
    
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status == 200:
                content = response.read().decode('utf-8', errors='ignore')
                with open(os.path.join(path, filename), "w", encoding="utf-8") as f:
                    f.write(content)
                return True
            else:
                print(f" -> ÉCHEC (Status {response.status})")
                return False
    except Exception as e:
        print(f" -> ERREUR : {e}")
        return False

def main():
    db = DatabaseManager()
    conn = psycopg2.connect(db.db_url)
    cur = conn.cursor()

    for status in ["OK", "Hors Stock"]:
        cat_folder = "ok" if status == "OK" else "ko"
        print(f"\n--- Analyse des produits : {status} ---")
        
        # On sélectionne plus de colonnes pour voir l'état de la donnée en base
        query = """
            SELECT s.produit_id, s.status_code, s.url_marchand_finale, s.date_scan, s.debug_info
            FROM fact_stock_status s
            JOIN dim_produit p ON s.produit_id = p.produit_id
            WHERE p.nom_vendeur = 'amazon' AND s.status_code = %s
            ORDER BY s.date_scan DESC
            LIMIT 5;
        """
        cur.execute(query, (status,))
        rows = cur.fetchall()

        for i, row in enumerate(rows):
            produit_id, db_status, url, date_scan, debug = row
            
            # Affichage des infos de la base pour vérification
            print(f"\n[Ligne DB] Prod ID: {produit_id} | Statut: {db_status}")
            print(f"URL: {url}")
            print(f"Date: {date_scan} | Debug: {debug}")
            
            filename = f"amazon_{cat_folder}_{i}.html"
            success = fetch_and_save(url, filename, cat_folder)
            
            if success:
                print(f" -> HTML récupéré avec succès : {filename}")
            else:
                print(f" -> FAILED pour {filename}")

    cur.close()
    conn.close()

if __name__ == "__main__":
    main()