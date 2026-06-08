import logging
import re
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


def dump_suspicious_html(url: str, html_content: str, reason: str) -> Path | None:
    """
    Sauvegarde le HTML brut dans un dossier local pour inspection visuelle.
    Utile pour identifier la nature exacte d'un blocage (Captcha Amazon, DataDome Decathlon...)
    """
    if not html_content:
        return None

    try:
        # Création du dossier de dump (ignoré par git idéalement)
        dump_dir = Path("debug_dumps")
        dump_dir.mkdir(exist_ok=True)

        # Nettoyage du nom de domaine pour le nom de fichier
        domain = url.split("//")[-1].split("/")[0].replace("www.", "").replace(".", "_")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        clean_reason = re.sub(r"[^a-zA-Z0-9_-]", "_", reason).lower()[:20]

        filename = dump_dir / f"{timestamp}_{domain}_{clean_reason}.html"
        filename.write_text(html_content, encoding="utf-8")

        logger.info(f"📸 Dump HTML sauvegardé pour analyse : {filename}")
        return filename
    except Exception as e:
        logger.error(f"Impossible de dumper le HTML pour {url}: {e}")
        return None
