-- ============================================================
-- 1. TABLE DE DIMENSION : Référentiel des produits Wetall
-- ============================================================
CREATE TABLE IF NOT EXISTS dim_produit (
    produit_id SERIAL PRIMARY KEY,
    url_wetall VARCHAR(512) UNIQUE NOT NULL, -- Clé fonctionnelle indexée
    nom_produit VARCHAR(255) NOT NULL,
    date_creation TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Index pour accélérer la recherche par URL lors des phases de synchronisation
CREATE INDEX IF NOT EXISTS idx_dim_produit_url ON dim_produit(url_wetall);


-- ============================================================
-- 2. TABLE DE FAIT : Historique chronologique des états de stock (Snapshots)
-- ============================================================
CREATE TABLE IF NOT EXISTS fact_stock_status (
    status_id BIGSERIAL PRIMARY KEY,
    produit_id INT REFERENCES dim_produit(produit_id) ON DELETE CASCADE,
    date_scan TIMESTAMP WITH TIME ZONE NOT NULL,
    status_code VARCHAR(50) NOT NULL,            -- 'OK', 'Rupture de stock', 'Vérification bloquée (403)'
    http_code_marchand INT,                       -- 200, 403, 404
    url_marchand_finale TEXT                      -- Utile pour tracer les redirections d'affiliation changeantes
);

-- Index composites pour optimiser les Window Functions (partitionnement par produit et tri chronologique)
CREATE INDEX IF NOT EXISTS idx_fact_stock_produit_date ON fact_stock_status(produit_id, date_scan DESC);