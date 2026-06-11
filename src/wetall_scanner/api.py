import argparse
import logging
import os
import sys
from typing import Literal, Optional
from enum import Enum

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, Header, HTTPException

# Import de tes classes métier
from wetall_scanner.scanner.orchestrator import ScannerOrchestrator
from wetall_scanner.scanner.database import DatabaseManager
from wetall_scanner.scanner.http_client import HTTPClient
from wetall_scanner.scanner.extractor import WetallExtractor

load_dotenv()

# --- ENUMS POUR LA VALIDATION API ---
class FilterStatus(str, Enum):
    """
    Enum aligné sur les codes de la base de données (fact_stock_status).
    Garantit que l'API n'accepte que des valeurs existantes en base.
    """
    EN_STOCK = "EN_STOCK"
    HORS_STOCK = "HORS_STOCK"
    NO_BUTTON = "NO_BUTTON"
    BLOQUE_BOT = "BLOQUE_BOT"
    BLOQUE_IP = "BLOQUE_IP"
    TIMEOUT = "TIMEOUT"
    ERREUR_RESEAU = "ERREUR_RESEAU"
    STRUCTURE_CHANGEE = "STRUCTURE_CHANGEE"
    PAGE_404 = "PAGE_404"
    A_VERIFIER = "A_VERIFIER"
    HTML_TROP_COURT = "HTML_TROP_COURT"
    ERREUR_CONFIG = "ERREUR_CONFIG"


# --- CONFIGURATION LOGS ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("app.log", encoding="utf-8"),  # Sauvegarde pour Streamlit
        logging.StreamHandler(sys.stdout),  # Conserve l'affichage sur Render
    ],
)
logger = logging.getLogger(__name__)

# Initialisation des composants
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


def run_pipeline(
    limit: int,
    mode: str,
    vendor: Optional[str] = None,
    product_id: Optional[int] = None,
    status_filter: Optional[str] = None, 
):
    """Bridge vers l'orchestrateur."""
    logger.info(f"Démarrage du pipeline : mode={mode}, status_filter={status_filter}")
    try:
        if mode == "discover":
            orchestrator.run_link_discovery(limit=limit, product_id=product_id)
        elif mode == "rescan":
            orchestrator.run_stock_monitoring(
                limit=limit, 
                vendor=vendor, 
                product_id=product_id,
                status_filter=status_filter 
            )

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
    vendor: Optional[str] = None, # TODO: À remplacer par un Enum VendorList plus tard
    product_id: Optional[int] = None,
    status_filter: Optional[FilterStatus] = None, # Validation stricte ici
):
    if x_secret_key != API_SECRET:
        raise HTTPException(status_code=401, detail="Clé invalide")

    # On extrait la chaîne de caractères brute de l'Enum pour le SQL
    filter_value = status_filter.value if status_filter else None

    logger.info(
        f"Scan déclenché par API : mode={mode}, limit={limit}, "
        f"vendor={vendor}, product_id={product_id}, status_filter={filter_value}"
    )

    background_tasks.add_task(
        run_pipeline, 
        limit=limit, 
        mode=mode, 
        vendor=vendor, 
        product_id=product_id,
        status_filter=filter_value 
    )

    return {"message": f"Scan '{mode}' lancé avec succès", "limit": limit}


@app.get("/logs")
async def get_logs(x_secret_key: str = Header(..., alias="X-Secret-Key")):
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
        raise HTTPException(
            status_code=500, detail="Impossible de lire les logs du serveur."
        )


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
        parser.add_argument(
            "--vendor",
            type=str,
            default=None,
            help="Vendeur à scanner",
        )
        parser.add_argument(
            "--product_id",
            type=int,
            default=None,
            help="Produit spécifique à rescanner",
        )
        parser.add_argument(
            "--status_filter",
            type=str,
            default=None,
            help="Filtrer par statut spécifique (ex: HORS_STOCK)",
        )
        args = parser.parse_args()

        logger.info(
            f"Exécution CLI : mode={args.mode}, limit={args.limit}, "
            f"vendor={args.vendor}, product_id={args.product_id}, status_filter={args.status_filter}"
        )

        run_pipeline(
            limit=args.limit,
            mode=args.mode,
            vendor=args.vendor,
            product_id=args.product_id,
            status_filter=args.status_filter
        )
    else:
        # Lancement API
        import uvicorn
        port = int(os.environ.get("PORT", 10000))
        uvicorn.run(app, host="0.0.0.0", port=port, log_config=None)