# syntax=docker/dockerfile:1.7

# ─────────────────────────────────────────────────────────────────────────────
# base — runtime común con uv
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

# uv (instalador oficial — binario único)
COPY --from=ghcr.io/astral-sh/uv:0.4.20 /uv /uvx /usr/local/bin/

WORKDIR /app

# ─────────────────────────────────────────────────────────────────────────────
# deps — instala dependencias en .venv (sin el proyecto en sí)
# ─────────────────────────────────────────────────────────────────────────────
FROM base AS deps

# pyproject.toml siempre. uv.lock* permite ausencia (primera vez antes de `make lock`).
COPY backend/pyproject.toml backend/uv.lock* ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-install-project

# ─────────────────────────────────────────────────────────────────────────────
# dev — hereda deps (incluye dev); código vendrá por bind mount del override
# ─────────────────────────────────────────────────────────────────────────────
FROM deps AS dev

EXPOSE 8000
# matos package se monta en /app/matos vía volumen del compose dev
CMD ["uv", "run", "uvicorn", "matos.main:app", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--reload", "--reload-dir", "/app/matos"]

# ─────────────────────────────────────────────────────────────────────────────
# prod — copia código y lo instala como paquete
# ─────────────────────────────────────────────────────────────────────────────
FROM base AS prod

# repetimos sync sin grupo dev para una imagen mínima
COPY backend/pyproject.toml backend/uv.lock* ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-install-project --no-dev

COPY backend/matos ./matos

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev

EXPOSE 8000
CMD ["uv", "run", "uvicorn", "matos.main:app", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "4"]
