import os
import json
import logging
from datetime import datetime, timezone
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Configuration du logger pour ce module
logger = logging.getLogger(__name__)

# Chargement des variables d'environnement (DATABASE_URL, etc.)
load_dotenv()


class DatabaseManager:
    """
    Gestionnaire de persistance pour le scanner.
    Responsable de la communication avec la base de données Neon (PostgreSQL).
    Encapsule la logique SQL pour isoler le reste de l'application des détails de la base.
    """

    def __init__(self):
        """Initialise le manager et vérifie la présence de la configuration."""
        self.db_url = os.getenv("DATABASE_URL")
        if not self.db_url:
            logger.critical("Variable d'environnement DATABASE_URL absente.")
            raise ValueError(
                "Erreur critique : La variable d'environnement DATABASE_URL est absente."
            )
        logger.debug("DatabaseManager initialisé avec succès.")

    def _get_connection(self):
        """
        Crée une nouvelle connexion à la base de données.
        Note : En environnement serverless (Neon), on ouvre une connexion par transaction
        pour éviter les coupures liées à l'inactivité (timeouts).
        """
        try:
            conn = psycopg2.connect(self.db_url)
            # L'autocommit évite de gérer manuellement les transactions (BEGIN/COMMIT)
            # pour des opérations simples d'insertion ou de mise à jour.
            conn.autocommit = True
            logger.debug("Nouvelle connexion établie avec Neon.")
            return conn
        except Exception:
            logger.exception("Impossible d'établir une connexion à la base de données.")
            raise

    def get_products_to_discover(
        self, limit: int = 10, product_id: int | None = None
    ) -> list[dict]:
        """Récupère les produits à découvrir, avec possibilité de cibler un ID précis."""
        query = """
            SELECT produit_id, url_wetall, nom_vendeur 
            FROM dim_produit 
            WHERE is_active = True 
            AND url_marchand_finale IS NULL
        """
        params = []

        if product_id:
            query += " AND produit_id = %s"
            params.append(product_id)

        query += " LIMIT %s;"
        params.append(limit)

        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, tuple(params))
                return [dict(row) for row in cur.fetchall()]
        finally:
            conn.close()

    def update_product_discovery_results(
        self, product_id: int, final_url: str, vendor_name: str | None = None
    ):
        """Enregistre l'URL finale et le nom du vendeur découverts pour le produit."""
        query = """
            UPDATE dim_produit 
            SET url_marchand_finale = %s,
                nom_vendeur = COALESCE(%s, nom_vendeur)
            WHERE produit_id = %s;
        """
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(query, (final_url, vendor_name, product_id))
            logger.info(
                f"Discovery : URL et vendeur mis à jour pour le produit {product_id}"
            )
        finally:
            conn.close()

    # --- WORKFLOW 2 : MONITORING (Vérifier le Stock) ---

    def get_products_to_monitor(
        self, limit: int = 50, vendor: str | None = None, prioritize_errors: bool = True
    ) -> list[dict]:
        """
        Récupère un lot de produits à scanner en priorité :
        1. Les produits avec des codes erreur récents (403, 404, etc.)
        2. Les produits scannés il y a le plus longtemps
        """

        # Base de la requête
        query = """
            SELECT p.produit_id, p.url_marchand_finale, p.nom_vendeur, s.status_code, s.date_scan
            FROM dim_produit p
            LEFT JOIN (
                SELECT produit_id, status_code, date_scan
                FROM fact_stock_status
                WHERE (produit_id, date_scan) IN (
                    SELECT produit_id, MAX(date_scan)
                    FROM fact_stock_status
                    GROUP BY produit_id
                )
            ) s ON p.produit_id = s.produit_id
            WHERE p.is_active = True 
            AND p.url_marchand_finale IS NOT NULL
        """

        params = []

        # Filtre optionnel par vendeur
        if vendor:
            query += " AND p.nom_vendeur = %s"
            params.append(vendor)

        # Logique de tri complexe
        if prioritize_errors:
            # On met en haut les produits dont le dernier code erreur est dans une liste "critique"
            query += """ 
                ORDER BY 
                    (s.status_code IN ('403', '404', '500', 'ERREUR_RESEAU', 'BLOQUE_BOT')) DESC,
                    s.date_scan ASC NULLS FIRST
            """
        else:
            query += " ORDER BY s.date_scan ASC NULLS FIRST"

        query += " LIMIT %s;"
        params.append(limit)

        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, tuple(params))
                return [dict(row) for row in cur.fetchall()]
        finally:
            conn.close()

    def save_scan_result(
        self,
        product_id: int,
        status_code: str,
        http_code: int,
        url_finale: str,
        debug_info: str,
    ):
        """Historise le résultat du scan de stock (Monitoring)."""
        now_utc = datetime.now(timezone.utc)
        new_entry_dict = {"status": status_code, "timestamp": now_utc.isoformat()}

        # On insère dans la table de faits pour l'historique
        query_fact = """
            INSERT INTO fact_stock_status 
            (produit_id, date_scan, status_code, http_code_marchand, url_marchand_finale, debug_info) 
            VALUES (%s, %s, %s, %s, %s, %s);
        """
        # On met à jour la dimension (SCD Type 1 + historique JSONB)
        query_dim = """
            UPDATE dim_produit 
            SET status_changed_at = %s,
                status_history = COALESCE(status_history, '[]'::jsonb) || jsonb_build_array(%s::jsonb)
            WHERE produit_id = %s;
        """

        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    query_fact,
                    (
                        product_id,
                        now_utc,
                        status_code,
                        http_code,
                        url_finale,
                        debug_info,
                    ),
                )
                cur.execute(
                    query_dim, (now_utc, json.dumps(new_entry_dict), product_id)
                )
            logger.info(
                f"Monitoring : Statut {status_code} sauvegardé pour {product_id}"
            )
        finally:
            conn.close()

    def get_product_by_id(self, product_id: int) -> dict | None:
        """Récupère un produit spécifique par son ID (Principalement pour les vérifications de test)."""
        query = """
            SELECT produit_id, url_wetall, url_marchand_finale, nom_vendeur, is_active 
            FROM public.dim_produit 
            WHERE produit_id = %s;
        """
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, (product_id,))
                row = cur.fetchone()
                return dict(row) if row else None
        finally:
            conn.close()

    def insert_product(self, product_data: dict) -> int:
        """
        Insère un nouveau produit dans dim_produit et retourne son produit_id.
        Utile pour les scripts d'import et l'isolation des tests.
        """
        query = """
            INSERT INTO public.dim_produit (url_wetall, nom_produit, nom_vendeur, url_marchand_finale)
            VALUES (%(url_wetall)s, %(nom_produit)s, %(nom_vendeur)s, %(url_marchand_finale)s)
            RETURNING produit_id;
        """
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(query, product_data)
                # Récupère l'ID généré par le SERIAL
                res = cur.fetchone()
                return res[0] if res else None
        finally:
            conn.close()

    def delete_product(self, product_id: int):
        """Supprime définitivement un produit de la base via son ID."""
        query = "DELETE FROM public.dim_produit WHERE produit_id = %s;"
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(query, (product_id,))
            logger.info(f"Produit de test {product_id} supprimé avec succès.")
        finally:
            conn.close()
