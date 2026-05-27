import httpx
from bs4 import BeautifulSoup
import datetime
import os
import psycopg2

# CONFIGURATION : On commence par ton lien de test
TARGETS = [
    {"nom": "Vélo de Biking", "url_wetall": "https://www.wetall.fr/produit/velo-de-biking-grande-taille/"}
]

def analyze_stock():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    results = []
    
    for item in TARGETS:
        print(f"Analyse de : {item['nom']}...")
        try:
            # 1. Aller sur la page Wetall
            with httpx.Client(follow_redirects=True, headers=headers, timeout=20.0) as client:
                r_wetall = client.get(item['url_wetall'])
                
                if r_wetall.status_code != 200:
                    results.append({"nom": item['nom'], "url_wetall": item['url_wetall'], "status": f"Erreur Wetall ({r_wetall.status_code})", "emoji": "❌"})
                    continue
                
                soup = BeautifulSoup(r_wetall.text, 'html.parser')
                
                # 2. Trouver le lien de redirection (bouton "Commander")
                # On cherche le lien qui contient "out" ou qui est lié au bouton d'achat
                buy_link = None
                for a in soup.find_all('a', href=True):
                    if "/out/" in a['href'] or "commander" in a.text.lower():
                        buy_link = a['href']
                        break
                
                if not buy_link:
                    results.append({"nom": item['nom'], "url_wetall": item['url_wetall'], "status": "Bouton 'Commander' non trouvé", "emoji": "⚠️"})
                    continue

                # 3. Suivre le lien pour voir où il mène (Decathlon, etc.)
                r_marchand = client.get(buy_link)
                final_url = str(r_marchand.url)
                
                # 4. Diagnostic de l'état (basé sur ton retour : il est brisé/404)
                status = "OK"
                emoji = "✅"
                
                if r_marchand.status_code == 404:
                    status = "Lien Brisé (404 chez le marchand)"
                    emoji = "❌"
                elif "decathlon" in final_url and ("indisponible" in r_marchand.text.lower() or "rupture" in r_marchand.text.lower()):
                    status = "Rupture de stock"
                    emoji = "🟠"
                
                results.append({"nom": item['nom'], "url_wetall": item['url_wetall'], "status": status, "emoji": emoji})
                
        except Exception as e:
            results.append({"nom": item['nom'], "url_wetall": item.get('url_wetall', ''), "status": f"Erreur technique : {str(e)}", "emoji": "❗"})

    # INSERTION DANS POSTGRESQL
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("Erreur : la variable d'environnement DATABASE_URL n'est pas définie.")
        return

    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        scan_date = datetime.datetime.now()
        
        for res in results:
            cur.execute(
                "INSERT INTO wetall_link_history (nom_produit, url_wetall, statut, code_etat, date_scan) "
                "VALUES (%s, %s, %s, %s, %s)",
                (res['nom'], res['url_wetall'], res['status'], res['emoji'], scan_date)
            )
            
        conn.commit()
        cur.close()
        conn.close()
        print("Résultats insérés dans la base de données avec succès.")
    except Exception as db_e:
        print(f"Erreur lors de l'insertion dans la base de données : {db_e}")

if __name__ == "__main__":
    analyze_stock()
