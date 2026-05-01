#!/usr/bin/env bash
# Genera lock files (uv.lock + pnpm-lock.yaml) en contenedores efímeros.
# Ejecutar 1ª vez tras clonar el repo, y cuando se cambien dependencias.
set -euo pipefail

cd "$(dirname "$0")/.."

# ── backend: uv.lock ─────────────────────────────────────────────────────────
echo "→ generando backend/uv.lock..."
docker run --rm \
    -v "$PWD/backend:/app" \
    -w /app \
    ghcr.io/astral-sh/uv:0.4.20-python3.12-bookworm-slim \
    uv lock

# ── frontend: pnpm-lock.yaml ─────────────────────────────────────────────────
# No usamos pipe (corepack contamina stdout). Creamos el contenedor, lo
# arrancamos en modo attached para ver el progreso, luego docker cp extrae
# el lock desde el FS interno del contenedor (evita EISDIR en macOS bind mounts).
echo "→ generando frontend/pnpm-lock.yaml..."

tmp=$(docker create \
    -e COREPACK_ENABLE_STRICT=0 \
    -v "$PWD/frontend/package.json:/app/package.json:ro" \
    -w /app \
    node:20-alpine \
    sh -c "corepack enable && \
           corepack prepare pnpm@9.7.0 --activate && \
           pnpm install --lockfile-only")

cleanup() { docker rm -f "$tmp" >/dev/null 2>&1 || true; }
trap cleanup EXIT

docker start --attach "$tmp"
docker cp "$tmp:/app/pnpm-lock.yaml" "$PWD/frontend/pnpm-lock.yaml"

echo ""
echo "✓ lock files generados."
echo "  - backend/uv.lock"
echo "  - frontend/pnpm-lock.yaml"
echo ""
echo "Comitear ambos al repo. Siguiente: make up"
