# 🚀 Wetall Scanner

Wetall Scanner est un moteur d'orchestration conçu pour automatiser la surveillance de la disponibilité des produits chez divers marchands. Il extrait les données, analyse le contenu des pages produits et assure la persistance des résultats pour un suivi en temps réel.

## 📋 Fonctionnalités actuelles

* **Orchestrateur intelligent** : Gère le flux complet (récupération, analyse, sauvegarde).
* **Client HTTP robuste** : Simulation de navigateur, rotation de User-Agents, gestion des redirections et des timeouts.
* **Stratégies d'analyse** : Moteur modulaire pour parser différents sites (Amazon, Decathlon, etc.).
* **Persistance** : Sauvegarde des scans dans une base de données PostgreSQL avec historique (JSONB).
* **Fiabilité** : Suite de tests unitaires complète avec `pytest` et `respx`.

## 🛠️ Stack Technique

* **Langage** : Python 3.11+
* **Gestionnaire de paquets** : [uv](https://github.com/astral-sh/uv)
* **Base de données** : PostgreSQL
* **Parsing** : BeautifulSoup4
* **Requêtes HTTP** : httpx

## 🏗️ Roadmap & Évolutions futures

Le projet est en phase d'industrialisation. Voici les prochaines étapes prévues :

1. **API Backend (FastAPI)** : Mise en place d'une interface REST pour piloter les scans à distance et consulter les résultats en temps réel.
2. **Conteneurisation (Docker)** : Création d'un `Dockerfile` et `docker-compose` pour faciliter le déploiement et la reproductibilité des environnements.
3. **Tests d'intégration & Smoke Tests** :
* Tests sur instances PostgreSQL réelles pour valider les flux de données.
* Smoke tests de bout en bout sur des URL réelles (produits en stock, hors stock, liens brisés, cas complexes multi-tailles).


4. **Déploiement Cloud** : Hébergement sur **Render** avec une stratégie de déploiement continu.

## 🚀 Installation & Démarrage

### Prérequis

* `uv` installé sur votre machine.

### Installation

```bash
# Cloner le projet
git clone <url-du-repo>
cd wetall-scanner

# Installer les dépendances
uv sync

```

### Lancer les tests

```bash
uv run pytest -v -s

```

## 📜 Licence

Projet privé - [AlpineData](https://alpinedata.fr)

