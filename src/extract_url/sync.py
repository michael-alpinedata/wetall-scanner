"""
Synchronisation des URLs du sitemap vers la base de données.

Responsabilité unique : orchestrer la récupération des URLs (via sitemap.py)
et leur persistance en base (UPSERT dans dim_produit).
"""

import logging
import os

import psycopg2

from .sitemap import fetch_product_urls

logger = logging.getLogger(__name__)

_UPSERT_PRODUCT_SQL = """
    INSERT INTO dim_produit (url_wetall, nom_produit)
    VALUES (%s, %s)
    ON CONFLICT (url_wetall) DO NOTHING;
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


def _upsert_products(cur: psycopg2.extensions.cursor, urls: list[str]) -> int:
    """
    Insère les URLs en base (sans écraser les existantes).

    Returns:
        Nombre de nouvelles lignes insérées.
    """
    new_count = 0
    for url in urls:
        nom_produit = _url_to_product_name(url)
        cur.execute(_UPSERT_PRODUCT_SQL, (url, nom_produit))
        if cur.rowcount > 0:
            new_count += 1
    return new_count


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
        conn = psycopg2.connect(db_url)
        conn.autocommit = True
        cur = conn.cursor()

        new_count = _upsert_products(cur, product_urls)

        cur.close()
        conn.close()

        logger.info(
            "Synchronisation terminée : %d nouveaux produits ajoutés en base"
            " (%d ignorés car déjà présents).",
            new_count,
            len(product_urls) - new_count,
        )

    except Exception as exc:
        logger.error("Erreur durant la synchronisation DB : %s", exc)
