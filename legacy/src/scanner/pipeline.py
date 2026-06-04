"""
Pipeline de traitement par batch (nuit).
"""

import json
import logging
import os
from datetime import datetime, timezone

import httpx
import psycopg2
from psycopg2.extras import DictCursor

# Import dynamique pour éviter les dépendances circulaires
# (Laisser ces imports ici ou dans les fonctions si besoin)

logger = logging.getLogger(__name__)

# --- CONSTANTES ---
DEFAULT_NB_PRODUCT_SCANNED = int(os.environ.get("NB_PRODUCT_SCANNED", 50))
_LOG_PROGRESS_EVERY = 10
STATUS_CRITIQUES_DESACTIVATION = ("Lien Brisé (404)", "Erreur Wetall 404", "Bouton non trouvé")

# --- SQL QUERIES ---
_FETCH_PRODUCTS_SQL = """
    SELECT produit_id, url_wetall, is_active, status_history, status_changed_at, nom_vendeur 
    FROM dim_produit 
    WHERE is_active = TRUE 
    ORDER BY produit_id LIMIT %s;
"""

_INSERT_SCAN_SQL = """
    INSERT INTO fact_stock_status 
    (produit_id, date_scan, status_code, http_code_marchand, url_marchand_finale, debug_info) 
    VALUES (%s, %s, %s, %s, %s, %s);
"""

_UPDATE_PRODUCT_CDC_SQL_PIPELINE = """
    UPDATE dim_produit 
    SET status_changed_at = %s, status_history = status_history || %s::jsonb 
    WHERE produit_id = %s;
"""

# --- FONCTIONS UTILITAIRES ---


def _get_db_connection(db_url):
    return psycopg2.connect(db_url, cursor_factory=DictCursor)


def _insert_fact_scan_result(cur, produit_id, status, http_code, url_finale, debug_msg):
    cur.execute(_INSERT_SCAN_SQL, (produit_id, datetime.now(timezone.utc), status, http_code, url_finale, debug_msg))


def _update_dim_product_status_history(cur, produit_id, status_changed_at, new_history_entry_jsonb):
    cur.execute(_UPDATE_PRODUCT_CDC_SQL_PIPELINE, (status_changed_at, new_history_entry_jsonb, produit_id))


def _update_dim_product_fields(cur, produit_id, final_url, http_code):
    cur.execute("UPDATE dim_produit SET url_marchand_finale = %s WHERE produit_id = %s;", (final_url, produit_id))


def _fetch_products(cur, limit, mode="standard"):
    if mode == "discovery":
        sql = """
            SELECT produit_id, url_wetall, is_active, status_history, 
            status_changed_at, nom_vendeur 
            FROM dim_produit 
            WHERE url_marchand_finale IS NULL OR url_marchand_finale = '' 
            LIMIT %s;
        """
    elif mode == "rescan":
        sql = """
            SELECT p.produit_id, p.url_marchand_finale AS url_wetall, p.is_active, 
                   p.status_history, p.status_changed_at, p.nom_vendeur 
            FROM dim_produit p
            JOIN fact_stock_status f ON p.produit_id = f.produit_id
            WHERE p.url_marchand_finale LIKE '%%amazon.%%'
              AND f.status_code = 'Rupture de stock'
              AND (f.http_code_marchand = 200 OR f.http_code_marchand IS NULL 
              OR f.http_code_marchand = 0)
            ORDER BY f.date_scan ASC
            LIMIT %s;
        """
    else:
        sql = _FETCH_PRODUCTS_SQL

    cur.execute(sql, (limit,))
    return cur.fetchall()


def _perform_scan(client: httpx.Client, row: dict, mode: str):
    target_url = row["url_wetall"]
    merchant_name = row.get("nom_vendeur", "Inconnu")

    if mode == "rescan":
        from .orchestrator import direct_merchant_scan

        return direct_merchant_scan(client, target_url, merchant_name=merchant_name)
    else:
        from .orchestrator import smart_scan

        return smart_scan(client, target_url, merchant_name=merchant_name)


def _apply_cdc_logic(cur, row, status):
    produit_id = row["produit_id"]
    current_is_active = row["is_active"]
    status_history = row.get("status_history") or []

    now_utc = datetime.now(timezone.utc)
    new_status_entry = {"status": status, "timestamp": now_utc.isoformat()}
    last_known_status = status_history[-1].get("status") if status_history else None
    new_is_active = status not in STATUS_CRITIQUES_DESACTIVATION

    new_status_at = None if new_is_active else (now_utc if current_is_active else row.get("status_changed_at"))

    if (status != last_known_status) or (new_is_active != current_is_active):
        _update_dim_product_status_history(cur, produit_id, new_status_at, json.dumps(new_status_entry))
        return True
    return False


def _process_scan_result(cur, row, scan_output):
    status, code, final_url, debug_msg = scan_output
    produit_id = row["produit_id"]
    merchant_name = row.get("nom_vendeur", "Inconnu")

    _insert_fact_scan_result(cur, produit_id, status, code, final_url, debug_msg)

    logger.info(
        f"💾 [DB INSERT] ID {produit_id:4} ({merchant_name}) | "
        f"Statut: {status} | HTTP: {code} | Détail: {debug_msg} | URL: {str(final_url)[:40]}..."
    )

    if final_url:
        _update_dim_product_fields(cur, produit_id, final_url, code)

    _apply_cdc_logic(cur, row, status)


# --- ENTRY POINT ---
def run_pipeline(limit: int = None, mode: str = "discover"):
    limit = limit or DEFAULT_NB_PRODUCT_SCANNED
    db_url = os.environ.get("DATABASE_URL")

    if not db_url:
        logger.error("DATABASE_URL manquante.")
        return

    conn = _get_db_connection(db_url)
    conn.autocommit = True
    cur = conn.cursor()

    try:
        products = _fetch_products(cur, limit, mode=mode)
        if not products:
            logger.info("Rien à scanner.")
            return

        logger.info(f"Démarrage {mode} : {len(products)} produits.")

        with httpx.Client(follow_redirects=True, timeout=60.0) as client:
            for i, row in enumerate(products, start=1):
                try:
                    result = _perform_scan(client, row, mode)
                    _process_scan_result(cur, row, result)

                    if i % _LOG_PROGRESS_EVERY == 0:
                        logger.info("Progression : %s/%s", i, len(products))
                except Exception as e:
                    logger.error(f"❌ Erreur inattendue sur le produit {row['produit_id']} : {e}")
                    continue
    finally:
        cur.close()
        conn.close()
        logger.info("Pipeline terminé et connexions fermées.")
