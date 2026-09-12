#!/usr/bin/env bash
# Impor konten situs (foto + copywriting) ke deployment VPS yang sudah berjalan.
# Jalankan dari root repo: bash deploy/import_content.sh [--dry-run] [--skip-testimonials]
set -euo pipefail
cd "$(dirname "$0")"
COMPOSE=(docker compose)
[ -f docker-compose.tls.yml ] && [ -f Caddyfile.generated ] && COMPOSE+=(-f docker-compose.yml -f docker-compose.tls.yml)

echo "▶ Memastikan image backend terbaru (berisi content_import/assets)…"
"${COMPOSE[@]}" build backend >/dev/null
"${COMPOSE[@]}" up -d backend >/dev/null

echo "▶ Mengimpor konten…"
"${COMPOSE[@]}" exec -T backend python /app/scripts/import_content.py "$@"
echo "✔ Selesai. Buka situs publik dan cek Beranda, Destinasi, dan Media Library (folder 'Konten Situs')."
