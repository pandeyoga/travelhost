#!/usr/bin/env bash
# Update di VPS: tarik kode terbaru -> rebuild -> ganti container.
# Data (mongo_data, uploads), sertifikat (caddy_data) dan deploy/.env TIDAK disentuh.
#   bash deploy/update.sh            # update penuh
#   bash deploy/update.sh --no-pull  # rebuild tanpa git pull
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEPLOY_DIR="$REPO_DIR/deploy"
ENV_FILE="$DEPLOY_DIR/.env"

say() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
die() { printf '\n\033[1;31mGAGAL: %s\033[0m\n' "$*" >&2; exit 1; }

[ -f "$ENV_FILE" ] || die "$ENV_FILE tidak ada. Jalankan deploy/install_vps.sh dulu."
grep -q '^COMPOSE_PROJECT_NAME=' "$ENV_FILE" || printf '\nCOMPOSE_PROJECT_NAME=travel\n' >> "$ENV_FILE"
grep -q '^OPENWA_API_KEY=.\+' "$ENV_FILE" || { echo "OPENWA_API_KEY=$(openssl rand -hex 24)" >> "$ENV_FILE"; }

if [ "${1:-}" != "--no-pull" ]; then
  say "Backup cepat sebelum update"
  bash "$DEPLOY_DIR/backup.sh" || echo "PERINGATAN: backup gagal (lanjut)"

  say "Tarik kode terbaru dari GitHub"
  cd "$REPO_DIR"
  git fetch --all --prune
  BRANCH="$(git rev-parse --abbrev-ref HEAD)"
  git reset --hard "origin/$BRANCH"
  git log --oneline -1
fi

say "Susun Caddyfile"
bash "$DEPLOY_DIR/render_caddyfile.sh"

say "Build image (backend & frontend)"
cd "$DEPLOY_DIR"
docker compose build --pull

say "Ganti container"
docker compose up -d --remove-orphans

say "Tunggu backend sehat"
for i in $(seq 1 60); do
  status="$(docker compose ps --format '{{.Service}} {{.Health}}' 2>/dev/null | awk '$1=="backend"{print $2}')"
  [ "$status" = "healthy" ] && break
  sleep 5
  [ "$i" = "60" ] && { docker compose logs --tail=60 backend; die "backend tidak sehat setelah 5 menit"; }
done

say "Status akhir"
docker compose ps
docker image prune -f >/dev/null 2>&1 || true
say "Selesai."
