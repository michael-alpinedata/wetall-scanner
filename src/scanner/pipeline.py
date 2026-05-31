"""
Pipeline de traitement par batch (nuit).
"""

import json
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

# Nombre de produits traités par exécution
DEFAULT_NB_PRODUCT_SCANNED: int = int(os.environ.get("NB_PRODUCT_SCANNED", 50))

_FETCH_PRODUCTS_SQL = """
    SELECT p.produit_id, p.url_wetall, p.is_active, p.status_history
    FROM dim_produit p
    LEFT JOIN (
        SELECT produit_id, MAX(date_scan) AS last_scan_date
        FROM fact_stock_status
        GROUP BY produit_id
    ) f ON p.produit_id = f.produit_id
    WHERE p.is_active = TRUE
    ORDER BY f.last_scan_date ASC NULLS FIRST
    LIMIT %s;
"""

_INSERT_SCAN_SQL = """
    INSERT INTO fact_stock_status
        (produit_id, date_scan, status_code, http_code_marchand,
         url_marchand_finale, debug_info)
    VALUES (%s, %s, %s, %s, %s, %s);
"""

_UPDATE_PRODUCT_CDC_SQL_PIPELINE = """
    UPDATE dim_produit
    SET
        is_active = %s,
        deactivated_at = %s,
        status_history = status_history || %s::jsonb
    WHERE
        produit_id = %s;
"""

_LOG_PROGRESS_EVERY = 10


def _get_db_connection(db_url: str) -> psycopg2.extensions.connection:
    conn = psycopg2.connect(db_url, cursor_factory=DictCursor)
    conn.autocommit = True
    return conn


def _fetch_products(cur: psycopg2.extensions.cursor, limit: int) -> list:
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


def _update_product_status_history(
    cur: psycopg2.extensions.cursor,
    produit_id: int,
    is_active: bool,
    deactivated_at: datetime | None,
    new_history_entry_jsonb: str,
) -> None:
    cur.execute(
        _UPDATE_PRODUCT_CDC_SQL_PIPELINE,
        (
            is_active,
            deactivated_at,
            new_history_entry_jsonb,
            produit_id,
        ),
    )


def run_pipeline(limit: int | None = None) -> None:
    if limit is None:
        limit = DEFAULT_NB_PRODUCT_SCANNED

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        logger.error("La variable d'environnement DATABASE_URL est manquante.")
        return

    try:
        conn = _get_db_connection(db_url)
        cur = conn.cursor()
        products = _fetch_products(cur, limit)

        if not products:
            cur.close()
            conn.close()
            return

        nb_status_changes = 0
        nb_errors = 0

        with httpx.Client(follow_redirects=True, timeout=60.0) as client:
            for i, row in enumerate(products, start=1):
                produit_id = row["produit_id"]
                url_wetall = row["url_wetall"]
                current_is_active_in_db = row["is_active"]
                status_history_in_db = row["status_history"]

                if i % _LOG_PROGRESS_EVERY == 0:
                    logger.info("Progression : %s/%s fiches traitées.", i, len(products))

                status, code, final_url, debug_msg = smart_scan(client, url_wetall)

                if status in ("Erreur technique", "Fail Wetall") or "Erreur" in status:
                    nb_errors += 1
                    logger.warning("Smart scan a renvoyé un statut d'erreur : '%s'", status)

                # CDC Logic
                now_utc = datetime.now(timezone.utc)
                new_status_entry = {"status": status, "timestamp": now_utc.isoformat()}
                new_status_entry_jsonb = json.dumps(new_status_entry)

                last_known_status_from_history = None
                if status_history_in_db and isinstance(status_history_in_db, list):
                    last_known_status_from_history = status_history_in_db[-1].get(
                        "status"
                    )

                new_is_active_for_dim_produit = status == "OK"
                new_deactivated_at_for_dim_produit = (
                    None if new_is_active_for_dim_produit else now_utc
                )

                if (status != last_known_status_from_history) or (
                    new_is_active_for_dim_produit != current_is_active_in_db
                ):
                    nb_status_changes += 1
                    _update_product_status_history(
                        cur,
                        produit_id,
                        new_is_active_for_dim_produit,
                        new_deactivated_at_for_dim_produit,
                        new_status_entry_jsonb,
                    )

                _insert_scan_result(cur, produit_id, status, code, final_url, debug_msg)
                time.sleep(random.uniform(5, 12))

        cur.close()
        conn.close()
        logger.info(
            "RÉSUMÉ BATCH DE NUIT : %s produits traités, %s changements de statut, %s erreurs de scan.",
            len(products),
            nb_status_changes,
            nb_errors,
        )
        logger.info("Batch terminé avec succès.")

    except Exception as exc:
        logger.error("Échec critique du pipeline : %s", exc, exc_info=True)
