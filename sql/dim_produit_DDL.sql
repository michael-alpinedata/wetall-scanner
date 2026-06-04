CREATE TABLE IF NOT EXISTS public.dim_produit (
    produit_id SERIAL PRIMARY KEY,
    url_wetall VARCHAR(512) NOT NULL UNIQUE,
    nom_produit VARCHAR(255) NOT NULL,
    date_creation TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT true,
    status_changed_at TIMESTAMP WITH TIME ZONE,
    status_history JSONB DEFAULT '[]',
    nom_vendeur VARCHAR(50),
    url_marchand_finale TEXT,
    
    -- Contrainte explicite (déjà couverte par UNIQUE/PRIMARY KEY mais spécifiée dans votre demande)
    CONSTRAINT dim_produit_url_wetall_key UNIQUE(url_wetall)
);

-- Index additionnels pour la performance
CREATE INDEX idx_dim_produit_url ON public.dim_produit USING BTREE (url_wetall);
CREATE INDEX idx_dim_produit_url_marchand ON public.dim_produit USING BTREE (url_marchand_finale);
CREATE INDEX idx_dim_produit_vendeur ON public.dim_produit USING BTREE (nom_vendeur);