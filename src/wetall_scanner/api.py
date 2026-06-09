import argparse
import logging
import os
import sys
from typing import Literal

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, Header, HTTPException

# Import de tes classes métier
from wetall_scanner.scanner.orchestrator import ScannerOrchestrator
from wetall_scanner.scanner.database import DatabaseManager
from wetall_scanner.scanner.http_client import HTTPClient
from wetall_scanner.scanner.extractor import WetallExtractor

load_dotenv()

# --- MODIFICATION 1 : Double destination pour les logs (Console + Fichier) ---
logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("app.log", encoding="utf-8"),  # Sauvegarde pour Streamlit
        logging.StreamHandler(sys.stdout)                  # Conserve l'affichage sur Render
    ]
)
logger = logging.getLogger(__name__)

# Initialisation des composants (Injection de dépendances au démarrage)
db = DatabaseManager()
http = HTTPClient()
extractor = WetallExtractor()
orchestrator = ScannerOrchestrator(db=db, http=http, extractor=extractor)

app = FastAPI(
    title="Wetall Links Checker",
    description="API de déclenchement du pipeline de scan des liens affiliés.",
    version="2.0.0",
)

API_SECRET = os.environ.get("SCAN_SECRET_KEY")


def run_pipeline(limit: int, mode: str):
    """Bridge entre l'ancienne logique et le nouvel orchestrateur."""
    logger.info(f"Démarrage du pipeline : mode={mode}, limit={limit}")
    try:
        if mode == "discover":
            orchestrator.run_link_discovery(limit=limit)
        elif mode == "rescan":
            # Appel de la méthode fusionnée get_products_to_monitor
            orchestrator.run_stock_monitoring(limit=limit, vendor="amazon")
        logger.info(f"Fin du pipeline : mode={mode}")
    except Exception as e:
        logger.exception(f"Erreur fatale lors du pipeline {mode} : {e}")


@app.api_route("/", methods=["GET", "HEAD"])
async def healthcheck():
    return {"status": "ok"}


@app.post("/trigger-scan")
async def trigger_scan(
    background_tasks: BackgroundTasks,
    x_secret_key: str = Header(..., alias="X-Secret-Key"),
    mode: Literal["discover", "rescan"] = "rescan",
    limit: int = 50,
):
    if x_secret_key != API_SECRET:
        raise HTTPException(status_code=401, detail="Clé invalide")

    logger.info(f"Scan déclenché par API : mode={mode}, limit={limit}")

    # Exécution asynchrone
    background_tasks.add_task(run_pipeline, limit=limit, mode=mode)

    return {"message": f"Scan '{mode}' lancé avec succès", "limit": limit}


# --- MODIFICATION 2 : Le nouvel endpoint sécurisé pour extraire les logs ---
@app.get("/logs")
async def get_logs(x_secret_key: str = Header(..., alias="X-Secret-Key")):
    # Même niveau de sécurité que pour le lancement du scan
    if x_secret_key != API_SECRET:
        raise HTTPException(status_code=401, detail="Clé invalide")
    
    log_file = "app.log"
    if not os.path.exists(log_file):
        return {"logs": "Aucun log disponible pour le moment. Lancez un scan !"}
    
    try:
        with open(log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
            # On extrait les 150 dernières lignes pour un affichage léger et rapide
            dernieres_lignes = "".join(lines[-150:])
            return {"logs": dernieres_lignes}
    except Exception as e:
        logger.error(f"Erreur lors de la lecture du fichier de logs : {e}")
        raise HTTPException(status_code=500, detail="Impossible de lire les logs du serveur.")


if __name__ == "__main__":
    # Logique CLI pour test local
    if len(sys.argv) > 1:
        parser = argparse.ArgumentParser(description="Wetall Scanner CLI")
        parser.add_argument("--limit", type=int, default=50, help="Nombre de produits")
        parser.add_argument(
            "--mode",
            choices=["discover", "rescan"],
            default="rescan",
            help="Mode de scan",
        )
        args = parser.parse_args()

        logger.info(f"Exécution CLI : mode={args.mode}, limit={args.limit}")
        run_pipeline(limit=args.limit, mode=args.mode)
    else:
        # Lancement API
        import uvicorn

        port = int(os.environ.get("PORT", 10000))
        uvicorn.run(app, host="0.0.0.0", port=port, log_config=None)
