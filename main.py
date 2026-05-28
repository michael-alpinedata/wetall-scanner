import os
from fastapi import FastAPI, BackgroundTasks, Header, HTTPException
from scanner import run_pipeline
from dotenv import load_dotenv

load_dotenv()
app = FastAPI()

# Sécurité : définis une clé dans les variables d'env de Render
API_SECRET = os.environ.get("SCAN_SECRET_KEY", "change_moi_vite")


@app.get("/")
async def root():
    return {"status": "Service de scan opérationnel"}


@app.post("/trigger-scan")
async def trigger_scan(
    background_tasks: BackgroundTasks, x_secret_key: str = Header(None)
):
    if x_secret_key != API_SECRET:
        raise HTTPException(status_code=403, detail="Clé secrète invalide")

    # On lance le scan en tâche de fond (Background Task)
    background_tasks.add_task(run_pipeline)

    return {"message": "Scan lancé en arrière-plan"}
