### 💡 Synthèse du Projet : Système de Monitoring "Wetall"

#### 1. Objectif Principal

Sécuriser les revenus d'affiliation en garantissant que chaque produit sur Wetall mène vers une page marchande valide et en stock.

#### 2. Réalisations Techniques & Robustesse

* **Scanner "Chirurgical" :** Script intelligent capable d'analyser dynamiquement la structure des pages.
* Détection des boutons d'achat standards et liens `/out/`.
* **Fallback Anti-Blocage :** Système de repli automatique en cas d'erreur 403 (pare-feu). Utilisation de techniques d'usurpation d'empreinte TLS (`curl_cffi`) pour les cibles difficiles (Decathlon, Alltricks), garantissant une continuité de service sans intervention manuelle.


* **Intelligence Marchande :** Algorithmes dédiés par enseigne (Nike, Amazon, Decathlon) pour détecter les ruptures de stock "silencieuses" et les liens morts.

#### 3. Infrastructure & Qualité du Code

* **Stack Data (PostgreSQL/Neon) :** Modèle en étoile robuste avec historisation des scans.
* **Dashboard (Streamlit) :** Interface de pilotage pour visualiser les anomalies en temps réel.
* **Standard Qualité :** Migration vers **Ruff** pour le linting et le formatage. Mise en place de règles strictes (`pre-commit`) garantissant un code maintenable, sécurisé et performant.

#### 4. Évolution & Synchronisation (SCD)

* **Sync Hebdo (GitHub Actions) :** Mise à jour automatique du catalogue avec gestion des `soft deletes` pour préserver l'historique de scan.
* **Propreté Analytics :** Identification claire des flux via un bot dédié (`Wetall-Data-Bot`), permettant d'isoler le trafic de monitoring et de conserver des statistiques business "pures" pour Yoann.

