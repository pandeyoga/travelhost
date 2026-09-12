#!/usr/bin/env bash
# Pasang / ganti domain setelah instalasi (tanpa rebuild frontend).
#   bash deploy/set_domain.sh rahazatrans.com erp.rahazatrans.com email@anda.com
#   bash deploy/set_domain.sh rahazatrans.com "" email@anda.com     # ERP tetap di /app/login domain utama
set -euo pipefail
DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$DEPLOY_DIR/.env"
DOMAIN="${1:?pakai: set_domain.sh DOMAIN [ERP_DOMAIN] [ACME_EMAIL]}"
ERP_DOMAIN="${2:-}"
ACME_EMAIL="${3:-admin@$DOMAIN}"
[ -f "$ENV_FILE" ] || { echo "GAGAL: $ENV_FILE tidak ada"; exit 1; }

setv() { if grep -q "^$1=" "$ENV_FILE"; then sed -i "s|^$1=.*|$1=$2|" "$ENV_FILE"; else echo "$1=$2" >> "$ENV_FILE"; fi; }
setv DOMAIN "$DOMAIN"
setv ERP_DOMAIN "$ERP_DOMAIN"
setv ACME_EMAIL "$ACME_EMAIL"
setv PUBLIC_SITE_URL "https://$DOMAIN"
setv CORS_ORIGINS "https://$DOMAIN${ERP_DOMAIN:+,https://$ERP_DOMAIN}"

bash "$DEPLOY_DIR/render_caddyfile.sh"
cd "$DEPLOY_DIR"
docker compose up -d --force-recreate backend caddy
echo
echo "Situs -> https://$DOMAIN"
echo "ERP   -> https://${ERP_DOMAIN:-$DOMAIN}/app/login"
if [ "$(grep '^PROXY_MODE=' "$ENV_FILE" | cut -d= -f2-)" = "behind" ]; then
  bash "$DEPLOY_DIR/proxy_snippet.sh"
else
  echo "Sertifikat HTTPS diterbitkan otomatis dalam ±1 menit (pastikan A record sudah mengarah ke VPS)."
fi
