from fastapi import FastAPI
from wetall_scanner.scanner.orchestrator import ScannerOrchestrator

app = FastAPI()

@app.get("/health")
def health_check():
    return {"status": "ok"}