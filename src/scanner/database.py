import os
import json
from datetime import datetime, timezone
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

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
            raise ValueError("Erreur critique : La variable d'environnement DATABASE_URL est absente.")

    def _get_connection(self):
        """
        Crée une nouvelle connexion à la base de données.
        Note : En environnement serverless (Neon), on ouvre une connexion par transaction
        pour éviter les coupures liées à l'inactivité (timeouts).
        """
        conn = psycopg2.connect(self.db_url)
        # L'autocommit évite de gérer manuellement les transactions (BEGIN/COMMIT)
        # pour des opérations simples d'insertion ou de mise à jour.
        conn.autocommit = True
        return conn

    def get_products_to_scan(self, vendor: str | None = None, limit: int = 10) -> list[dict]:
        """
        Récupère une liste de produits actifs à analyser.

        Args:
            vendor (str | None): Nom du vendeur (ex: 'amazon') pour filtrer le scan. 
                                 Si None, récupère tous les vendeurs actifs.
            limit (int): Nombre maximum de produits à récupérer.

        Returns:
            list[dict]: Liste de dictionnaires représentant les lignes de dim_produit.
        """
        # Base de la requête SQL
        base_query = """
            SELECT produit_id, url_wetall, url_marchand_finale, status_history, nom_vendeur 
            FROM dim_produit 
            WHERE is_active = True
        """
        
        conn = self._get_connection()
        try:
            # RealDictCursor permet d'accéder aux colonnes par leur nom (ex: row['produit_id'])
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                if vendor:
                    # Filtrage spécifique par marchand
                    query = base_query + " AND nom_vendeur = %s LIMIT %s;"
                    cur.execute(query, (vendor, limit))
                else:
                    # Scan global
                    query = base_query + " LIMIT %s;"
                    cur.execute(query, (limit,))
                
                return cur.fetchall()
        finally:
            # Fermeture systématique pour libérer les ressources Neon
            conn.close()

    def save_scan_result(self, product_id: int, status_code: str, http_code: int, url_finale: str, debug_info: str):
        """
        Enregistre les résultats d'un scan de manière atomique.
        
        Effectue deux opérations :
        1. Insertion dans 'fact_stock_status' : Historique complet pour le dashboard.
        2. Mise à jour de 'dim_produit' : État actuel et journal d'historique JSONB.

        Args:
            product_id (int): Identifiant unique du produit.
            status_code (str): Libellé du statut (ex: 'OK', 'Hors Stock').
            http_code (int): Code de retour HTTP du marchand.
            url_finale (str): URL de destination après redirections.
            debug_info (str): Message technique pour le diagnostic.
        """
        now_utc = datetime.now(timezone.utc)
        
        # Préparation du nouvel élément pour le journal d'historique (JSONB)
        new_history_entry = json.dumps([{
            "status": status_code,
            "timestamp": now_utc.isoformat()
        }])

        # Requête 1 : Table de faits (Données temporelles brutes)
        query_fact = """
            INSERT INTO fact_stock_status 
            (produit_id, date_scan, status_code, http_code_marchand, url_marchand_finale, debug_info) 
            VALUES (%s, %s, %s, %s, %s, %s);
        """
        
        # Requête 2 : Table de dimension (État actuel de l'objet)
        # COALESCE est utilisé pour :
        # - Ne pas écraser l'URL finale si elle est nulle lors de ce scan.
        # - Initialiser 'status_history' avec une liste vide '[]' si la colonne est NULL.
        # L'opérateur '||' permet la concaténation de tableaux JSONB.
        query_dim = """
            UPDATE dim_produit 
            SET url_marchand_finale = COALESCE(%s, url_marchand_finale),
                status_changed_at = %s,
                status_history = COALESCE(status_history, '[]'::jsonb) || %s::jsonb
            WHERE produit_id = %s;
        """

        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                # Enregistrement du fait
                cur.execute(query_fact, (product_id, now_utc, status_code, http_code, url_finale, debug_info))
                # Mise à jour de la dimension
                cur.execute(query_dim, (url_finale, now_utc, new_history_entry, product_id))
        finally:
            # Fermeture garantie de la connexion serverless
            conn.close()