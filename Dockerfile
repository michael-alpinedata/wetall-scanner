# Stage 1: Builder
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# Stage 2: Runtime
FROM python:3.12-slim AS runtime

WORKDIR /app
ENV PYTHONUNBUFFERED=1
ENV PATH="/app/.venv/bin:$PATH"

# Copie de l'exécutable uv depuis l'image officielle pour le CMD
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uv/bin/

COPY --from=builder /app/.venv /app/.venv
COPY . .

EXPOSE 8000

CMD ["/uv/bin/uv", "run", "python", "src/main.py"]
