FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# Installation des outils de compilation nécessaires
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    build-essential \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./

# On installe les dépendances. 
# Si une compilation est nécessaire, build-essential la gérera.
RUN uv sync --frozen --no-dev

# Ajout du venv au PATH
ENV PATH="/app/.venv/bin:$PATH"

COPY . .

EXPOSE 10000
CMD ["python", "src/wetall_scanner/api.py"]