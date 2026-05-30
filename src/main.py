"""
Point d'entrée de l'API FastAPI.

Expose deux routes :
- GET/HEAD /          → healthcheck (utilisé par Render pour le keep-alive).
- POST /trigger-scan  → déclenche le batch de nuit en tâche de fond.
"""

import argparse
import logging
import os
import sys

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, Header, HTTPException

from src.scanner import run_pipeline

load_dotenv()

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Wetall Links Checker",
    description="API de déclenchement du pipeline de scan des liens affiliés Wetall.",
    version="1.0.0",
)

# Clé secrète à définir dans les variables d'environnement de Render
API_SECRET: str = os.environ.get("SCAN_SECRET_KEY")


@app.api_route("/", methods=["GET", "HEAD"])
async def healthcheck():
    """Healthcheck pour Render et GitHub Actions."""
    return {"status": "ok"}


@app.post("/trigger-scan")
async def trigger_scan(
    background_tasks: BackgroundTasks,
    x_secret_key: str = Header(None),
):
    """
    Déclenche le batch de nuit en arrière-plan.

    Le header `X-Secret-Key` doit correspondre à la variable SCAN_SECRET_KEY.
    """
    if not x_secret_key or x_secret_key != API_SECRET:
        logger.warning("Tentative de déclenchement avec une clé invalide ou absente.")
        raise HTTPException(status_code=401, detail="Clé secrète invalide ou absente")

    background_tasks.add_task(run_pipeline)
    logger.info("Batch de nuit déclenché via /trigger-scan.")
    return {"message": "Scan lancé en arrière-plan"}


if __name__ == "__main__":
    # Si des arguments sont passés (ex: --limit), on exécute le pipeline en CLI
    if len(sys.argv) > 1:
        parser = argparse.ArgumentParser(description="Wetall Scanner CLI")
        parser.add_argument("--limit", type=int, help="Nombre maximum de produits à scanner")
        args = parser.parse_args()

        logger.info("Exécution du pipeline via CLI (limit=%s)", args.limit)
        run_pipeline(limit=args.limit)
    else:
        # Sinon, on lance le serveur API
        import uvicorn

        uvicorn.run(app, host="0.0.0.0", port=8000)
