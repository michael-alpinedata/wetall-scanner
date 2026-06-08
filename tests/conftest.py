import pytest
from wetall_scanner.scanner.database import DatabaseManager
from wetall_scanner.scanner.http_client import HTTPClient
from wetall_scanner.scanner.orchestrator import ScannerOrchestrator
from wetall_scanner.scanner.extractor import WetallExtractor


@pytest.fixture
def load_fixture():
    def _load(filename):
        with open(f"tests/fixtures/{filename}", "r", encoding="utf-8") as f:
            return f.read()

    return _load


@pytest.fixture
def components():
    db = DatabaseManager()
    http = HTTPClient()
    extractor = WetallExtractor()
    orchestrator = ScannerOrchestrator(db, http, extractor)
    return db, http, orchestrator
