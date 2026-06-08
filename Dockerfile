# Stage 1: Builder
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

WORKDIR /app
COPY pyproject.toml uv.lock ./

# Installe les dépendances dans le venv
RUN uv sync --no-install-project --no-dev

# Stage 2: Runtime
FROM python:3.12-slim AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
    libssl-dev \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
ENV PYTHONUNBUFFERED=1
# Ajoute le dossier 'src' au PYTHONPATH pour que 'wetall_scanner' soit détectable
ENV PYTHONPATH="/app/src"
ENV PATH="/app/.venv/bin:$PATH"

COPY --from=builder /app/.venv /app/.venv
COPY . .

EXPOSE 10000

# Lance ton script directement en utilisant le chemin absolu
CMD ["python", "src/wetall_scanner/api.py"]