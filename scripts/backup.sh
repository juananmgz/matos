#!/usr/bin/env bash
# Backup: tar de archivo/ + dump del SQLite de índice.
# Salida: backups/matos-YYYY-MM-DD-HHMMSS.tar.gz
set -euo pipefail

cd "$(dirname "$0")/.."

mkdir -p backups
ts="$(date +%Y-%m-%d-%H%M%S)"
out="backups/matos-${ts}.tar.gz"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

# dump del índice (si existe)
if docker compose ps -q backend >/dev/null 2>&1 && \
   docker compose exec -T backend test -f /data/index/matos.db; then
    echo "→ dumping índice SQLite..."
    docker compose exec -T backend sqlite3 /data/index/matos.db ".backup '/tmp/matos.db.bak'" \
        && docker compose exec -T backend cat /tmp/matos.db.bak > "$tmp/matos.db.bak" \
        && docker compose exec -T backend rm -f /tmp/matos.db.bak
fi

echo "→ tar..."
tar -czf "$out" \
    -C . archivo/ \
    $([ -f "$tmp/matos.db.bak" ] && echo "-C $tmp matos.db.bak")

echo "✓ backup en $out"
ls -lh "$out"
