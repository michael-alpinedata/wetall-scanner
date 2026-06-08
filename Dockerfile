# Utilise une image légère de Python
FROM python:3.12-slim

# Empêche Python d'écrire des fichiers .pyc et de bufferiser les logs
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Installation des dépendances système nécessaires pour le scraping et curl
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Installation de uv pour gérer les dépendances rapidement
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uv

WORKDIR /app

# Copie des fichiers de dépendances
COPY pyproject.toml uv.lock ./

# Installation des dépendances
RUN uv sync --frozen

# Copie du reste du code source
COPY . .

# Expose le port par défaut de Render
EXPOSE 10000

# Commande de lancement (en mode production avec Uvicorn)
CMD ["uv", "run", "python", "src/wetall_scanner/api.py"]