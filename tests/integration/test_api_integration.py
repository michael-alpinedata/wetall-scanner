import requests
import os
from dotenv import load_dotenv

load_dotenv()


def test_api_trigger():
    # 1. Configuration
    base_url = "http://localhost:10000"
    secret_key = os.getenv("SCAN_SECRET_KEY")

    # 2. Envoi du trigger
    print(f"Envoi du signal à {base_url}/trigger-scan ...")
    try:
        response = requests.post(
            f"{base_url}/trigger-scan?mode=rescan&limit=2",
            headers={"X-Secret-Key": secret_key},
        )

        # 3. Vérification immédiate de la réponse de l'API
        if response.status_code == 200:
            print(f"✅ Succès : {response.json()}")
        else:
            print(f"❌ Erreur {response.status_code} : {response.text}")

    except Exception as e:
        print(f"❌ Impossible de joindre l'API (est-elle démarrée ?) : {e}")


if __name__ == "__main__":
    test_api_trigger()
