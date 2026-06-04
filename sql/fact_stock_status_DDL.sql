CREATE TABLE IF NOT EXISTS public.fact_stock_status (
    status_id BIGSERIAL PRIMARY KEY,
    produit_id INTEGER NOT NULL,
    date_scan TIMESTAMP WITH TIME ZONE NOT NULL,
    status_code VARCHAR(50) NOT NULL,
    http_code_marchand INTEGER,
    url_marchand_finale TEXT,
    debug_info TEXT,

    -- Clé étrangère avec suppression en cascade
    CONSTRAINT fact_stock_status_produit_id_fkey 
        FOREIGN KEY (produit_id) 
        REFERENCES public.dim_produit(produit_id) 
        ON DELETE CASCADE
);

-- Index pour optimiser les jointures et les tris par date
CREATE INDEX idx_fact_stock_produit_date ON public.fact_stock_status USING BTREE (produit_id, date_scan DESC);