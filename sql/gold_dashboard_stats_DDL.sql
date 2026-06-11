DROP VIEW gold_dashboard_stats;

CREATE OR REPLACE VIEW gold_dashboard_stats AS
SELECT DISTINCT ON (f.produit_id) 
  f.produit_id,
  f.date_scan,
  p.nom_produit,
  p.nom_vendeur,
  f.status_code, -- On garde le code brut, c'est ta source de vérité
  f.http_code_marchand,
  p.url_marchand_finale
FROM fact_stock_status f
JOIN dim_produit p ON f.produit_id = p.produit_id
ORDER BY f.produit_id, f.date_scan DESC;