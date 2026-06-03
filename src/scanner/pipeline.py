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
        status_changed_at = %s,
        status_history = status_history || %s::jsonb
    WHERE
        produit_id = %s;
"""
#         -- is_active = %s,

_LOG_PROGRESS_EVERY = 10


def _get_db_connection(db_url: str) -> psycopg2.extensions.connection:
    conn = psycopg2.connect(db_url, cursor_factory=DictCursor)
    conn.autocommit = True
    return conn


# Dans src/scanner/pipeline.py
def _fetch_products(cur, limit, mode="standard"):
    if mode == "discovery":
        # Priorité absolue aux URLs manquantes
        sql = """SELECT produit_id, url_wetall FROM dim_produit 
                 WHERE url_marchand_finale IS NULL OR url_marchand_finale = '' 
                 LIMIT %s;"""
    else:
        # Ton SQL actuel de batch de nuit
        sql = _FETCH_PRODUCTS_SQL
    cur.execute(sql, (limit,))
    return cur.fetchall()


def _insert_fact_scan_result(
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


def _update_dim_product_status_history(
    cur: psycopg2.extensions.cursor,
    produit_id: int,
    # is_active: bool,
    status_changed_at: datetime | None,
    new_history_entry_jsonb: str,
) -> None:
    cur.execute(
        _UPDATE_PRODUCT_CDC_SQL_PIPELINE,
        (
            # is_active,
            status_changed_at,
            new_history_entry_jsonb,
            produit_id,
        ),
    )


def _update_dim_product_fields(cur, produit_id, final_url, http_code):
    """Met à jour l'url_marchand_finale."""
    sql = """
        UPDATE dim_produit
        SET url_marchand_finale = %s
        WHERE produit_id = %s;
    """
    cur.execute(sql, (final_url, produit_id))


def run_pipeline(limit: int = None, mode: str = "standard"):
    if limit is None:
        limit = DEFAULT_NB_PRODUCT_SCANNED

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        logger.error("La variable d'environnement DATABASE_URL est manquante.")
        return

    try:
        conn = _get_db_connection(db_url)
        cur = conn.cursor()
        products = _fetch_products(cur, limit, mode=mode)

        if not products:
            logger.info("Aucun produit à scanner.")
            cur.close()
            conn.close()
            return

        nb_status_changes = 0
        nb_errors = 0

        # TODO - pour l'instant, un scan de wetall ne doit pas desactiver le produit
        # dans le catalogue, seul un scan de la sitemap le peut (avec extract_url)
        # on pourrait faire des statuts dans la dim_produits 
        # 'is_link_broken', 'is_out_of_stock' 
        # (en SCD 2, avec suivi des dates de changement de statut)
        STATUS_CRITIQUES_DESACTIVATION = (
            # "Lien Brisé (404)",
            # "Erreur Wetall 404",
            # "Bouton non trouvé",
        )

        with httpx.Client(follow_redirects=True, timeout=60.0) as client:
            for i, row in enumerate(products, start=1):
                produit_id = row["produit_id"]
                url_wetall = row["url_wetall"]
                current_is_active_in_db = row["is_active"]
                status_history_in_db = row["status_history"]

                if i % _LOG_PROGRESS_EVERY == 0:
                    logger.info(
                        "Progression : %s/%s fiches traitées.", i, len(products)
                    )

                # 1. Scan
                status, code, final_url, debug_msg = smart_scan(client, url_wetall)

                # 1. Insertion systématique (Trace d'audit pour le debug)
                _insert_fact_scan_result(cur, produit_id, status, code, final_url, debug_msg)

                # 2. Gestion des erreurs techniques (Pas de mise à jour produit)
                if status in ("Erreur technique", "Fail Wetall") or "Erreur" in status:
                    nb_errors += 1
                    logger.warning("Smart scan a renvoyé un statut d'erreur : '%s'", status)

                # 2. Mise à jour TECHNIQUE (URL et Code HTTP) - NE TOUCHE PAS À IS_ACTIVE
                if final_url:
                    _update_dim_product_fields(cur, produit_id, final_url, code)

                # 3. CDC Logic (Gestion du statut is_active)
                now_utc = datetime.now(timezone.utc)
                new_status_entry = {"status": status, "timestamp": now_utc.isoformat()}
                new_status_entry_jsonb = json.dumps(new_status_entry)

                last_known_status = None
                if status_history_in_db and isinstance(status_history_in_db, list):
                    last_known_status = status_history_in_db[-1].get("status")

                #  on ne touche pas à is_active
                new_is_active = status not in STATUS_CRITIQUES_DESACTIVATION

                if new_is_active:
                    new_status_at = None
                else:
                    new_status_at = (
                        now_utc
                        if current_is_active_in_db
                        else row.get("status_changed_at")
                    )

                # TODO: Mise à jour si changement réel
                # A réécrire pour MAJ d'autre chose que is_active (is_link_broken,
                # is out_of_stock)
                # ID : pour l'instant met juste à jour le status_entry
                if (status != last_known_status) or (
                    new_is_active != current_is_active_in_db
                ):
                    nb_status_changes += 1
                    _update_dim_product_status_history(
                        cur,
                        produit_id,
                        new_status_at,
                        new_status_entry_jsonb,
                    )

                time.sleep(random.uniform(5, 12))

        cur.close()
        conn.close()
        logger.info(
            "RÉSUMÉ BATCH : %s traités, %s changements, %s erreurs.",
            len(products),
            nb_status_changes,
            nb_errors,
        )

    except Exception as exc:
        logger.error("Échec critique du pipeline : %s", exc, exc_info=True)
