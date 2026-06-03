"""
Synchronisation des URLs du sitemap vers la base de données.

Responsabilité unique : orchestrer la récupération des URLs (via sitemap.py)
et leur persistance en base (UPSERT dans dim_produit).
"""

import json
import logging
import os
from datetime import datetime, timezone

import psycopg2
from psycopg2.extras import DictCursor

from .sitemap import fetch_product_urls

logger = logging.getLogger(__name__)

# Requête pour récupérer les produits existants (ID, URL, état actif, historique)
_FETCH_EXISTING_PRODUCTS_SQL = """
    SELECT produit_id, url_wetall, is_active, status_history
    FROM dim_produit;
"""

# Insertion d'un nouveau produit avec initialisation de l'historique de statut
_INSERT_NEW_PRODUCT_SQL = """
    INSERT INTO dim_produit (url_wetall, nom_produit, is_active, status_history)
    VALUES (%s, %s, TRUE, %s::jsonb);
"""

# Mise à jour d'un produit existant (réactivation ou désactivation)
# et append d'un nouvel événement au status_history
_UPDATE_PRODUCT_CDC_SQL = """
    UPDATE dim_produit
    SET
        is_active = %s,
        deactivated_at = %s,
        status_history = status_history || %s::jsonb
    WHERE
        produit_id = %s;
"""


def _url_to_product_name(url: str) -> str:
    """
    Transforme le slug d'une URL en nom de produit lisible.

    Exemple:
        "https://www.wetall.fr/produit/chaussures-geantes/"
        → "Chaussures Geantes"
    """
    slug = url.strip("/").split("/")[-1]
    return slug.replace("-", " ").title()


def _upsert_products(
    cur: psycopg2.extensions.cursor, sitemap_urls: list[str]
) -> tuple[int, int, int]:
    """
    Synchronise les URLs du sitemap avec la table dim_produit, en gérant le CDC.

    Identifie les nouveaux produits à insérer, les produits à réactiver, et les produits
    à désactiver (ceux qui étaient actifs mais ne sont plus dans le sitemap).

    Returns:
        Tuple (newly_inserted_count, reactivated_count, deactivated_count).
    """
    now_utc = datetime.now(timezone.utc).isoformat(timespec="seconds") + "Z"

    # 1. Récupérer l'état actuel de tous les produits en base
    cur.execute(_FETCH_EXISTING_PRODUCTS_SQL)
    db_products = {row["url_wetall"]: row for row in cur.fetchall()}
    db_urls = set(db_products.keys())
    sitemap_urls_set = set(sitemap_urls)

    new_products_to_insert = []
    products_to_reactivate = []
    products_to_deactivate = []

    # 2. Identifier les nouveaux produits et les produits à réactiver
    for url in sitemap_urls_set:
        if url not in db_urls:
            # Nouveau produit
            nom_produit = _url_to_product_name(url)
            initial_history = json.dumps([{"status": "active", "timestamp": now_utc}])
            new_products_to_insert.append((url, nom_produit, initial_history))
        elif not db_products[url]["is_active"]:
            # Produit existant mais inactif, à réactiver
            products_to_reactivate.append(
                (
                    db_products[url]["produit_id"],
                    json.dumps({"status": "active", "timestamp": now_utc}),
                )
            )

    # 3. Identifier les produits à désactiver
    for url in db_urls:
        if url not in sitemap_urls_set and db_products[url]["is_active"]:
            # Produit existant, actif, mais plus dans le sitemap => désactiver
            products_to_deactivate.append(
                (
                    db_products[url]["produit_id"],
                    json.dumps({"status": "inactive", "timestamp": now_utc}),
                )
            )

    # 4. Exécuter les opérations batch
    newly_inserted_count = 0
    reactivated_count = 0
    deactivated_count = 0

    if new_products_to_insert:
        cur.executemany(_INSERT_NEW_PRODUCT_SQL, new_products_to_insert)
        newly_inserted_count = len(new_products_to_insert)

    if products_to_reactivate:
        # (is_active, deactivated_at, new_history_entry, produit_id)
        reactivation_data = [(True, None, history_entry, prod_id) for prod_id, history_entry in products_to_reactivate]
        cur.executemany(_UPDATE_PRODUCT_CDC_SQL, reactivation_data)
        reactivated_count = cur.rowcount

    if products_to_deactivate:
        # (is_active, deactivated_at, new_history_entry, produit_id)
        deactivation_data = [
            (False, now_utc, history_entry, prod_id) for prod_id, history_entry in products_to_deactivate
        ]
        cur.executemany(_UPDATE_PRODUCT_CDC_SQL, deactivation_data)
        deactivated_count = cur.rowcount

    return newly_inserted_count, reactivated_count, deactivated_count


def sync_sitemap_to_db() -> None:
    """
    Point d'entrée principal : synchronise le sitemap Wetall avec la DB.

    Étapes :
    1. Récupération et parsing du sitemap via `fetch_product_urls`.
    2. UPSERT de chaque URL dans `dim_produit`.
    3. Log du résumé (nouvelles insertions vs. existantes ignorées).
    """
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        logger.error("DATABASE_URL manquante dans l'environnement.")
        return

    product_urls = fetch_product_urls()
    if not product_urls:
        return  # Les erreurs sont déjà loggées dans fetch_product_urls

    try:
        conn = psycopg2.connect(
            db_url, cursor_factory=DictCursor
        )  # Use DictCursor for easier row access
        conn.autocommit = True
        cur = conn.cursor()

        new_count, reactivated_count, deactivated_count = _upsert_products(
            cur, product_urls
        )

        cur.close()
        conn.close()

        logger.info(
            "Synchronisation terminée : %d nouveaux produits, %d réactivés,"
            " %d désactivés. %d produits du sitemap étaient déjà actifs.",
            new_count,
            reactivated_count,
            deactivated_count,
            len(product_urls) - (new_count + reactivated_count),
        )

    except Exception as exc:
        logger.error("Erreur durant la synchronisation DB : %s", exc, exc_info=True)
