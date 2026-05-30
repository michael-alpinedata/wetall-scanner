"""
Pipeline de traitement par batch (nuit).

Responsabilité unique : gérer la boucle principale (connexion DB,
récupération des produits, appel du scanner, écriture des résultats).
Aucune logique métier ici — délégation totale à `smart_scan`.
"""

import logging
import os
import json
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
    SELECT p.produit_id, p.url_wetall, p.is_active, p.status_history
    FROM dim_produit p
    LEFT JOIN (
        SELECT produit_id, MAX(date_scan) AS dernier_scan
        FROM fact_stock_status
        GROUP BY produit_id
    ) f ON p.produit_id = f.produit_id
    WHERE p.is_active = TRUE
    ORDER BY f.dernier_scan ASC NULLS FIRST
    LIMIT %s;
"""

_INSERT_SCAN_SQL = """
    INSERT INTO fact_stock_status
        (produit_id, date_scan, status_code, http_code_marchand,
         url_marchand_finale, debug_info)
    VALUES (%s, %s, %s, %s, %s, %s);
"""

# Mise à jour de dim_produit avec l'historique de statut et l'état actif/désactivé
_UPDATE_PRODUCT_CDC_SQL_PIPELINE = """
    UPDATE dim_produit
    SET
        is_active = %s,
        deactivated_at = %s,
        status_history = status_history || %s::jsonb
    WHERE
        produit_id = %s;
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


def _update_product_status_history(
    cur: psycopg2.extensions.cursor,
    produit_id: int,
    is_active: bool,
    deactivated_at: str | None,
    new_history_entry_jsonb: str,  # JSON string
) -> None:
    """
    Met à jour dim_produit avec le nouvel état is_active, deactivated_at et
    ajoute une nouvelle entrée à status_history.
    """
    cur.execute(
        _UPDATE_PRODUCT_CDC_SQL_PIPELINE,
        (
            is_active,
            deactivated_at,
            new_history_entry_jsonb,
            produit_id,
        ),
    )
    logger.debug(
        "dim_produit (ID %d) mis à jour: is_active=%s, deactivated_at=%s, nouvelle entrée status_history.",
        produit_id,
        is_active,
        deactivated_at,
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

        total_products_processed = 0
        status_changes_count = 0
        error_count = 0

        with httpx.Client(follow_redirects=True, timeout=60.0) as client:
            for i, row in enumerate(products, start=1):
                produit_id = row["produit_id"]
                url_wetall = row["url_wetall"]
                current_is_active_in_db = row["is_active"]
                status_history_in_db = row["status_history"]

                status, code, final_url, debug_msg = smart_scan(client, url_wetall)
                total_products_processed += 1

                # If smart_scan returns an error status
                if status != "OK":
                    error_count += 1
                    logger.warning(
                        "Produit ID %d (URL: %s) : Smart scan a renvoyé un statut d'erreur : '%s'",
                        produit_id,
                        url_wetall[:50],
                        status,
                    )

                # CDC Logic for dim_produit
                now_utc = datetime.now(timezone.utc).isoformat(timespec="seconds") + "Z"
                new_status_entry = {"status": status, "timestamp": now_utc}
                new_status_entry_jsonb = json.dumps(new_status_entry)

                last_known_status_from_history = None
                if (
                    status_history_in_db
                    and isinstance(status_history_in_db, list)
                    and len(status_history_in_db) > 0
                ):
                    last_known_status_from_history = status_history_in_db[-1].get(
                        "status"
                    )

                # Determine the 'is_active' and 'deactivated_at' for dim_produit based on the new scan status
                # 'OK' implies active/in-stock, other statuses imply inactive/out-of-stock or error.
                new_is_active_for_dim_produit = status == "OK"
                new_deactivated_at_for_dim_produit = (
                    None if new_is_active_for_dim_produit else now_utc
                )

                # Condition for updating dim_produit:
                # 1. The main 'status' (e.g., "OK", "Rupture") has changed.
                # 2. The derived 'is_active' status for dim_produit has changed.
                if (status != last_known_status_from_history) or (
                    new_is_active_for_dim_produit != current_is_active_in_db
                ):
                    logger.info(
                        (
                            "Produit ID %d (Wetall URL: %s) - Statut modifié (avant: '%s', après: '%s') ou état actif changé"
                            " (avant: %s, après: %s). Mise à jour de dim_produit."
                        ),
                        produit_id,
                        url_wetall[:50],
                        last_known_status_from_history,
                        status,
                        current_is_active_in_db,
                        new_is_active_for_dim_produit,
                    )
                    _update_product_status_history(
                        cur,
                        produit_id,
                        new_is_active_for_dim_produit,
                        new_deactivated_at_for_dim_produit,
                        new_status_entry_jsonb,
                    )
                    status_changes_count += 1
                else:
                    logger.debug(
                        (
                            "Produit ID %d (Wetall URL: %s) - Statut '%s' et état actif (%s) inchangés. Pas de mise à jour de dim_produit"
                            " (sauf fact_stock_status)."
                        ),
                        produit_id,
                        url_wetall[:50],
                        status,
                        new_is_active_for_dim_produit,
                    )

                # Always insert into fact_stock_status regardless of dim_produit update
                _insert_scan_result(
                    cur, produit_id, status, code, final_url, debug_msg
                )

                if i % _LOG_PROGRESS_EVERY == 0:
                    logger.info(
                        "Progression : %d/%d fiches traitées.", i, len(products)
                    )

                # Pause de sécurité entre chaque produit
                time.sleep(random.uniform(5, 12))

        cur.close()
        conn.close()
        logger.info(
            "RÉSUMÉ BATCH DE NUIT : %d produits traités, %d changements de statut (UPDATE dim_produit), %d erreurs de scan.",
            total_products_processed,
            status_changes_count,
            error_count,
        )
        logger.info("FIN DU BATCH DE NUIT. Données disponibles pour le Dashboard.")

    except Exception as exc:
        logger.error("Échec critique du pipeline : %s", exc, exc_info=True)
