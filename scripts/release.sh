#!/usr/bin/env bash
# Push de imágenes prod al registry definido en $REGISTRY (.env).
# Uso: ./scripts/release.sh <tag>
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
    echo "falta .env. cp .env.example .env y rellenar REGISTRY."
    exit 1
fi
# shellcheck disable=SC1091
set -a; source .env; set +a

if [ -z "${REGISTRY:-}" ]; then
    echo "REGISTRY no definido en .env. Ej: REGISTRY=ghcr.io/usuario"
    exit 1
fi

tag="${1:-$(git rev-parse --short HEAD 2>/dev/null || echo latest)}"

echo "→ build prod..."
make build

for img in matos-backend matos-frontend; do
    for t in "$tag" latest; do
        docker tag "$img:$tag" "$REGISTRY/$img:$t"
        echo "→ push $REGISTRY/$img:$t"
        docker push "$REGISTRY/$img:$t"
    done
done

echo "✓ release $tag publicado en $REGISTRY"
