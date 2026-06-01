# 📄 CONTEXT_COMMANDS.md (Version Alignée sur la Réalité)

## 1. Contexte du Projet & Objectif Métier
* **Nom du Projet** : wetall-scanner
* **Objectif** : Vérifier la disponibilité des produits et la validité des liens marchands du catalogue Wetall.
* **Stack Technique** : Python 3.12, managé par `uv` (Astral). Utilisation intensive de `curl_cffi` pour le scraping.
* **Base de Données** : PostgreSQL serverless hébergée sur Neon.tech.
* **Infrastructure** : Le service tourne en continu en tant que Background Worker sur Render (déploiement via Docker multi-stage).

## 2. Architecture & Flux Nominal
1. Lecture des produits un par un dans la base PostgreSQL (Neon).
2. Chargement de la page produit Wetall pour extraire le bouton d'achat (lien d'affiliation).
3. Résolution des redirections pour obtenir l'URL finale du marchand (ex: Décathlon, Nike, Amazon). Amazon est le partenaire principal et ne bloque pas.
4. Scraping de la page finale via `curl_cffi`.
5. Application des règles de `src/scanner/analyzer.py` pour déterminer le stock et le prix.
6. Mise à jour de la base PostgreSQL (Neon) avec le statut et l'URL réelle.

## 3. Objectif de la Feature : Moteur d'Auto-Healing
* **Détection** : Si le marchand final renvoie un code de blocage (401, 403, 503).
* **IA (Gemini)** : Appeler l'API Gemini (gemini-1.5-flash) via `httpx`. Le LLM doit tenter de générer une fonction Python corrective à injecter à la fin de `src/scanner/analyzer.py`.
* **Cas d'Échec de l'IA** : Si le blocage est impossible à contourner par du code, le LLM doit générer un "Rapport de Blocage Spécifique" avec des suggestions alternatives (proxies, API, etc.).
* **Workflow Git Sécurisé** : L'IA ne pousse JAMAIS sur `main`. Elle utilise `PyGithub` pour créer une branche `feature/auto-fix-<marchand>-<timestamp>` et ouvre une Pull Request.
* **Alerte SMTP** : Envoi d'un email (Gmail SMTP) avec l'URL bloquée, le diagnostic de l'IA et le lien vers la PR ou le rapport.

## 4. Contraintes Strictes ("Red Lines")
* **PAS de Faux Positifs** : Si le lien marchand ne peut pas être résolu, lever une erreur explicite (Lien Marchand Invalide). Pas de validation silencieuse.
* **PAS de corruption SQL** : La logique d'écriture dans Neon est sanctuarisée.
* **Sécurité de Syntaxe** : Utiliser impérativement des triples guillemets f"""...""" pour les blocs de texte multilignes (prompts et corps de PR) pour éviter les SyntaxError.
* **Qualité** : Fonctions atomiques (< 25 lignes), Type Hints, et validation locale via `pytest` obligatoire avant tout push.