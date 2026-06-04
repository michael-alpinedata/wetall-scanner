-- 1. Nettoyage
DROP VIEW IF EXISTS v_gold_dashboard_stats;

-- 2. Création avec DIM comme source de vérité pour l'URL
CREATE VIEW v_gold_dashboard_stats AS
SELECT DISTINCT ON (f.produit_id)
       f.produit_id, 
       f.date_scan, 
       p.nom_produit, 
       p.nom_vendeur, 
       f.status_code, 
       f.http_code_marchand, 
       -- Ici, on force l'URL de la table DIM
       p.url_marchand_finale as url_marchand_finale, 
       CASE 
           WHEN f.status_code = 'OK' THEN 'OK'
           WHEN f.http_code_marchand = '404' THEN 'Lien Brisé'
           WHEN f.http_code_marchand = '403' THEN 'Bloqué/Grisé'
           ELSE 'Hors Stock'
       END as gravite
FROM fact_stock_status f
JOIN dim_produit p ON f.produit_id = p.produit_id
ORDER BY f.produit_id, f.date_scan DESC;