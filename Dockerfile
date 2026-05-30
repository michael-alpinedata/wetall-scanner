FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

# On copie les fichiers de lock/pyproject pour optimiser le cache
COPY pyproject.toml uv.lock ./

# Installation des dépendances avec uv
RUN uv sync --frozen

# Copie du reste du code
COPY . .

# On expose le port 8000 par défaut
EXPOSE 8000

# Commande pour lancer l'API via uv
CMD ["uv", "run", "python", "src/main.py"]
