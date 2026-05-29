-- Ajout des colonnes pour le Change Data Capture (CDC) à dim_produit

ALTER TABLE dim_produit
ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE,
ADD COLUMN IF NOT EXISTS deactivated_at TIMESTAMP WITH TIME ZONE DEFAULT NULL,
ADD COLUMN IF NOT EXISTS status_history JSONB NOT NULL DEFAULT '[{"status": "active", "timestamp": "1970-01-01T00:00:00Z"}]'::jsonb;

-- Mettre à jour les entrées existantes avec une valeur par défaut cohérente
-- (Si status_history est à sa valeur par défaut '1970-01-01T00:00:00Z', on le met à jour)
UPDATE dim_produit
SET
    status_history = jsonb_set(status_history, '{0,timestamp}', to_jsonb(NOW() AT TIME ZONE 'UTC'), true)
WHERE
    status_history = '[{"status": "active", "timestamp": "1970-01-01T00:00:00Z"}]'::jsonb;
