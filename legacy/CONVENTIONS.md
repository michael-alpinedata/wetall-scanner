# 🛠️ CONVENTIONS.md - Manifeste "Artisan Data" (Version Alignée)

Ce fichier définit les standards de qualité, les choix architecturaux et les règles de codage stricts pour le projet `wetall-scanner`. Tout agent de codage doit s'y conformer avant de soumettre une modification.

## 1. Philosophie de Développement & Clean Code
- **Artisan Data** : Prioriser la valeur métier, la simplicité et la robustesse sur la complexité technique inutile.
- **Fonctions Atomiques** : Chaque fonction doit avoir une responsabilité unique et ne doit pas dépasser **25 lignes** de code (hors docstrings).
- **Typage Statique** : L'utilisation des Type Hints Python est obligatoire pour tous les arguments et retours de fonctions.
- **Principe de Moindre Surprise** : Pas d'effet de bord caché. Les fonctions de scraping doivent être pures et isolées de la logique d'écriture en base de données.

## 2. Logique de Scraping & Gestion des Blocages
- **Moteur de Scraping** : Le scraping du marchand final s'appuie exclusivement sur la librairie `curl_cffi` pour imiter un comportement de navigateur réaliste et contourner les protections standards (TLS/Headers).
- **User-Agent & Fingerprints** : Utiliser les capacités natives de `curl_cffi` pour injecter des empreintes de navigateurs valides.
- **Gestion des Échecs** : Un code HTTP `401`, `403` ou `503` sur le site marchand ne doit pas faire crasher le script. Il doit être intercepté proprement pour déclencher le pipeline d'Auto-Healing (IA) et l'alerte par email.
- **Pas de validation silencieuse** : Si une URL marchande est impossible à extraire ou à résoudre (ex: lien brisé ou boucle infinie sur Wetall), le script doit lever une exception explicite `Lien Marchand Invalide` et passer au produit suivant.

## 3. Gestion de l'Environnement & Dépendances
- **Gestionnaire `uv`** : Le projet utilise exclusivement `uv` d'Astral pour la gestion des paquets et de l'environnement virtuel.
- **Ajout de paquets** : Si une nouvelle librairie est nécessaire (ex: `pygithub`), elle doit obligatoirement être ajoutée via la commande `uv add <paquet>` pour mettre à jour le fichier `uv.lock`. Ne jamais modifier directement le fichier des dépendances à la main.
- **Variables d'environnement** : Les secrets et configurations (`DATABASE_URL`, `GH_TOKEN`, `SMTP_PASSWORD`, etc.) sont injectés par Render. Utiliser exclusivement `os.environ.get()` sans jamais coder de valeur sensible en dur.

## 4. Tests, Fiabilité & CI/CD
- **Validation Locale Obligatoire** : Avant chaque push ou demande de déploiement, la suite de tests locaux (`pytest`) doit être exécutée et passer à 100%.
- **Utilisation de Mocks** : Pour les tests unitaires de la logique métier (dans `src/scanner/analyzer.py`), utiliser des mocks (`unittest.mock`) pour simuler les réponses réseau et les appels à la base PostgreSQL (Neon.tech). Les tests ne doivent pas dépendre d'une connexion internet ou d'une base active.
- **Sécurité d'Écriture** : La structure des tables SQL sur Neon.tech est sanctuarisée. Aucune logique d'Auto-Healing automatique ne doit modifier la structure de la base de données. Everything transite par une Pull Request (PR) pour validation humaine.