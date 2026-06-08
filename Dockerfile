# Utilise une image légère de Python
FROM python:3.12-slim

# Empêche Python d'écrire des fichiers .pyc et de bufferiser les logs
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Variables d'environnement pour optimiser uv
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# Installation des dépendances système nécessaires 
# "build-essential" est CRUCIAL pour compiler curl-cffi
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    build-essential \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Installation de uv dans /usr/local/bin pour qu'il soit dans le PATH
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copie des fichiers de dépendances
COPY pyproject.toml uv.lock ./

# Installation des dépendances de PRODUCTION uniquement
# On utilise --no-dev pour éviter d'installer pytest/respx en prod
# On ajoute --verbose pour voir le détail de ce qu'il essaie de faire
RUN uv sync --frozen --no-dev --verbose

# Ajout du venv au PATH pour que les exécutables soient trouvés sans "uv run"
ENV PATH="/app/.venv/bin:$PATH"

# Copie du reste du code source
COPY . .

# Expose le port par défaut
EXPOSE 10000

# Commande de lancement
CMD ["python", "src/wetall_scanner/api.py"]