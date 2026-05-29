# Manifeste "Artisan Data" - wetall-links-checker

Ce fichier définit les standards de qualité et les choix architecturaux pour le projet.

## 1. Philosophie de Développement
- **Artisan Data** : Prioriser la valeur métier et la robustesse sur la complexité technique.
- **Clean Code** : Fonctions atomiques (< 25 lignes), typage statique Python (Type Hints), et docstrings claires.
- **Principe de Moindre Surprise** : Pas d'effet de bord caché dans les fonctions de scraping.

## 2. Phase 2 : Data Modeling & CDC (Change Data Capture)
- **Light CDC** : Avant chaque écriture en base (Neon.tech), comparer l'état extrait (Scraping) avec l'état actuel en DB.
- **Optimisation I/O** : Si l'état (stock, prix, statut) n'a pas changé, NE PAS effectuer de UPDATE ou d'insertion.
- **PostgreSQL JSONB** : Utiliser la colonne `status_history` pour historiser les changements.
    - Format : `[{"status": "active", "timestamp": "2026-05-29T23:00:00Z"}, ...]`
    - Toujours ajouter la nouvelle entrée en fin de liste (append).
- **SCD (Slowly Changing Dimensions)** : 
    - `is_active` : Mise à jour en place (SCD Type 1).
    - `deactivated_at` : Timestamp ISO mis à jour uniquement lors du passage à `is_active = False`.

## 3. Logique de Scraping & Réconciliation
- **Sitemap vs DB** : 
    - URL présente dans le Sitemap -> `is_active = True`.
    - URL absente du Sitemap MAIS présente en DB -> Marquer comme `is_active = False`.
- **User-Agent** : Toujours utiliser un User-Agent réaliste pour éviter le blocage.

## 4. Tests & Fiabilité
- **TDD (Test Driven Development)** : Chaque nouvelle logique de CDC doit être couverte par un test unitaire simulant un changement d'état et un état identique.
- **Mocks** : Utiliser des mocks pour les appels Neon.tech (psycopg2/asyncpg) afin de tester la logique sans dépendance réseau.