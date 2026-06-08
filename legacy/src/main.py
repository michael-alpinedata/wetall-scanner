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
from typing import Literal  # À ajouter en haut de ton fichier

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, Header, HTTPException
from legacy.src.scanner import run_pipeline

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
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


# Dans src/scanner/main.py


@app.post("/trigger-scan")
async def trigger_scan(
    background_tasks: BackgroundTasks,
    x_secret_key: str = Header(...),  # Utilise Header(...) pour rendre le header obligatoire
    mode: Literal["discover", "rescan"] = "rescan",  # Valeurs autorisées uniquement
    limit: int = 50,
):
    if x_secret_key != API_SECRET:
        raise HTTPException(status_code=401, detail="Clé invalide")

    # Log pour tracer le déclenchement
    logger.info(f"Scan déclenché par API : mode={mode}, limit={limit}")

    # Appel du pipeline
    background_tasks.add_task(run_pipeline, limit=limit, mode=mode)

    return {"message": f"Scan '{mode}' lancé avec succès", "limit": limit}


if __name__ == "__main__":
    if len(sys.argv) > 1:
        parser = argparse.ArgumentParser(description="Wetall Scanner CLI")
        parser.add_argument("--limit", type=int, default=50, help="Nombre de produits")
        # On définit les choix possibles ici aussi
        parser.add_argument("--mode", choices=["discover", "rescan"], default="rescan", help="Mode de scan")
        args = parser.parse_args()

        logger.info(f"Exécution CLI : mode={args.mode}, limit={args.limit}")
        run_pipeline(limit=args.limit, mode=args.mode)
    else:
        # Sinon, on lance le serveur API
        import uvicorn

        port = int(os.environ.get("PORT", 10000))
        uvicorn.run(app, host="0.0.0.0", port=port)
