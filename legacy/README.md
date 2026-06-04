# Wetall Scanner

`wetall-scanner` est un outil de Data Engineering conçu pour orchestrer l'extraction, l'analyse et la synchronisation de données via le web. Il s'appuie sur une architecture robuste et modulaire pour garantir la qualité et la fiabilité des données extraites.

---

## 🚀 Vue d'ensemble

Ce projet a pour objectif d'automatiser le scan de sites web via des sitemaps et des outils d'extraction, et d'analyser ces données pour les stocker dans une base de données (ex: Neon). Il est conçu pour être "Agent-Ready", facilitant la maintenance et l'évolution par des assistants IA.

### 🏗️ Architecture du Projet

Le projet est structuré pour maximiser la modularité et la séparation des responsabilités :

```text
src/
├── scanner/           # Logique cœur : orchestration, analyse et parsing
├── extract_url/       # Outils pour la gestion des sitemaps et extraction
└── main.py            # Point d'entrée de l'application
tests/                 # Tests unitaires et d'intégration

```

---

## 🛠️ Installation

1. **Cloner le repository :**
```bash
git clone <votre-repo-url>
cd wetall-scanner

```


2. **Configuration :**
Assurez-vous d'avoir Docker installé si vous utilisez les environnements conteneurisés. Référez-vous aux fichiers `CONTEXT.md` et `CONVENTIONS.md` pour configurer vos variables d'environnement.
3. **Dépendances :**
Le projet utilise `pyproject.toml` pour la gestion des dépendances.
```bash
pip install .
# ou via poetry/uv selon votre workflow

```



---

## 📖 Méthodologie et Conventions

Le projet suit des directives strictes pour garantir la qualité du code, notamment documentées dans :

* **`CONTEXT.md`** : Définit la "Source Unique de Vérité" (SSOT) pour l'agent IA et les développeurs.
* **`CONVENTIONS.md`** : Règles de nommage, structure de commit, et standards de code.

*Note : Ces fichiers sont cruciaux pour permettre aux agents IA d'interagir efficacement avec le code sans hallucination.*

---

## 🧪 Tests

Le projet utilise `pytest` pour valider les flux de données et le comportement du scanner.

Pour lancer les tests :

```bash
python run_test.py
# ou directement :
pytest tests/

```

Les tests sont divisés en deux catégories principales :

* `tests/smoke/` : Tests de validation rapide.
* `tests/integration/` : Tests de flux complets (database, scan, orchestration).

---

## ⚙️ Développement

Si vous souhaitez contribuer ou modifier le comportement de l'agent :

1. Modifiez `CONTEXT.md` pour refléter les changements d'infrastructure.
2. Assurez-vous que les tests d'intégration dans `tests/integration/` passent après chaque modification majeure.

---

## 📄 Licence

Propriétaire - Wetall.
"""

with open("README.md", "w", encoding="utf-8") as f:
f.write(content)
