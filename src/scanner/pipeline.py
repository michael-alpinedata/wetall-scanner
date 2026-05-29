"""
Pipeline de traitement par batch (nuit).

Responsabilité unique : gérer la boucle principale (connexion DB,
récupération des produits, appel du scanner, écriture des résultats).
Aucune logique métier ici — délégation totale à `smart_scan`.
"""

import logging
import os
import random
import time
from datetime import datetime, timezone

import httpx
import psycopg2
from psycopg2.extras import DictCursor

from .orchestrator import smart_scan

logger = logging.getLogger(__name__)

# Nombre de produits traités par exécution (configurable via env)
NB_PRODUCT_SCANNED: int = int(os.environ.get("NB_PRODUCT_SCANNED", 1000))

# Requête SQL : produits les plus anciennement scannés (ou jamais scannés)
_FETCH_PRODUCTS_SQL = """
    SELECT p.produit_id, p.url_wetall
    FROM dim_produit p
    LEFT JOIN (
        SELECT produit_id, MAX(date_scan) AS dernier_scan
        FROM fact_stock_status
        GROUP BY produit_id
    ) f ON p.produit_id = f.produit_id
    ORDER BY f.dernier_scan ASC NULLS FIRST
    LIMIT %s;
"""

_INSERT_SCAN_SQL = """
    INSERT INTO fact_stock_status
        (produit_id, date_scan, status_code, http_code_marchand,
         url_marchand_finale, debug_info)
    VALUES (%s, %s, %s, %s, %s, %s);
"""

_LOG_PROGRESS_EVERY = 10  # Log tous les N produits


def _get_db_connection(db_url: str) -> psycopg2.extensions.connection:
    """Ouvre et retourne une connexion PostgreSQL en mode autocommit."""
    conn = psycopg2.connect(db_url, cursor_factory=DictCursor)
    conn.autocommit = True
    return conn


def _fetch_products(cur: psycopg2.extensions.cursor, limit: int) -> list:
    """Récupère la liste des produits à scanner depuis la DB."""
    cur.execute(_FETCH_PRODUCTS_SQL, (limit,))
    return cur.fetchall()


def _insert_scan_result(
    cur: psycopg2.extensions.cursor,
    produit_id: int,
    status: str,
    http_code: int,
    url_finale: str | None,
    debug_msg: str,
) -> None:
    """Insère le résultat d'un scan dans la table de faits."""
    cur.execute(
        _INSERT_SCAN_SQL,
        (
            produit_id,
            datetime.now(timezone.utc),
            status,
            http_code,
            url_finale,
            debug_msg,
        ),
    )


def run_pipeline() -> None:
    """
    Point d'entrée du batch de nuit.

    Récupère les N produits les plus anciennement scannés,
    les scanne un à un et persiste les résultats en base.
    """
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        logger.error("La variable d'environnement DATABASE_URL est manquante.")
        return

    try:
        conn = _get_db_connection(db_url)
        cur = conn.cursor()

        products = _fetch_products(cur, NB_PRODUCT_SCANNED)
        if not products:
            logger.info("Aucun produit en attente de traitement.")
            cur.close()
            conn.close()
            return

        logger.info("DÉMARRAGE DU BATCH DE NUIT : %d produits ciblés.", len(products))

        with httpx.Client(follow_redirects=True, timeout=60.0) as client:
            for i, row in enumerate(products, start=1):
                status, code, final_url, debug_msg = smart_scan(
                    client, row["url_wetall"]
                )

                _insert_scan_result(
                    cur, row["produit_id"], status, code, final_url, debug_msg
                )

                if i % _LOG_PROGRESS_EVERY == 0:
                    logger.info(
                        "Progression : %d/%d fiches traitées.", i, len(products)
                    )

                # Pause de sécurité entre chaque produit
                time.sleep(random.uniform(5, 12))

        cur.close()
        conn.close()
        logger.info("FIN DU BATCH DE NUIT. Données disponibles pour le Dashboard.")

    except Exception as exc:
        logger.error("Échec critique du pipeline : %s", exc)
