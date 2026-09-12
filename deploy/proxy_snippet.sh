#!/usr/bin/env bash
# Cetak blok konfigurasi untuk reverse proxy yang SUDAH ADA di VPS (mode behind).
set -euo pipefail
DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$DEPLOY_DIR/.env"
getv() { grep -E "^$1=" "$ENV_FILE" | tail -1 | cut -d= -f2- || true; }
DOMAIN="$(getv DOMAIN)"; ERP_DOMAIN="$(getv ERP_DOMAIN)"; PORT="$(getv HTTP_PORT)"
[ -n "$DOMAIN" ] || { echo "DOMAIN belum diisi (jalankan set_domain.sh dulu)"; exit 0; }
IP="$(curl -fsS https://api.ipify.org 2>/dev/null || hostname -I | awk '{print $1}')"
cat <<EOF

================= LANGKAH TAMBAHAN (mode behind) =================
Port 80/443 dipegang proxy project lain. Tambahkan blok ini ke Caddyfile proxy tersebut
(untuk SIPRO: /opt/sipro/deploy/Caddyfile — simpan juga ke repo-nya agar tidak hilang saat update):

$DOMAIN${ERP_DOMAIN:+, $ERP_DOMAIN} {
	reverse_proxy $IP:$PORT
}

lalu muat ulang proxy itu, mis.: cd /opt/sipro/deploy && docker compose restart caddy
(Untuk nginx: server_name $DOMAIN $ERP_DOMAIN; proxy_pass http://$IP:$PORT; proxy_set_header Host \$host;)
===================================================================
EOF
