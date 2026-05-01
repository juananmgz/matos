#!/usr/bin/env bash
# Restaura backup: extrae archivo/ y opcionalmente recarga índice.
# Uso: ./scripts/restore.sh backups/matos-YYYY-MM-DD-HHMMSS.tar.gz
set -euo pipefail

if [ $# -ne 1 ]; then
    echo "uso: $0 <fichero.tar.gz>"
    exit 1
fi

backup="$1"
cd "$(dirname "$0")/.."

if [ ! -f "$backup" ]; then
    echo "no existe: $backup"
    exit 1
fi

echo "⚠ esto sobreescribe archivo/ y el índice. Ctrl-C para abortar."
read -p "continuar? [y/N] " r
[[ "$r" == "y" ]] || exit 1

echo "→ extrayendo..."
tar -xzf "$backup" -C .

if [ -f matos.db.bak ]; then
    echo "→ restaurando índice..."
    docker compose exec -T backend sh -c "cat > /data/index/matos.db" < matos.db.bak
    rm -f matos.db.bak
fi

echo "✓ restaurado. Considera ejecutar: make reindex"
