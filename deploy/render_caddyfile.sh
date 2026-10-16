#!/usr/bin/env bash
# Membuat deploy/Caddyfile.generated dari deploy/.env
#   DOMAIN kosong      -> mode IP: HTTP :80 (situs publik + ERP di /app)
#   DOMAIN terisi      -> HTTPS otomatis (Let's Encrypt)
#   ERP_DOMAIN terisi  -> ERP hanya lewat subdomain; /app di domain publik dialihkan ke sana
set -euo pipefail
DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$DEPLOY_DIR/.env"
OUT="$DEPLOY_DIR/Caddyfile.generated"
[ -f "$ENV_FILE" ] || { echo "GAGAL: $ENV_FILE tidak ada"; exit 1; }

getv() { grep -E "^$1=" "$ENV_FILE" | tail -1 | cut -d= -f2- | tr -d '"' || true; }
DOMAIN="$(getv DOMAIN)"; ERP_DOMAIN="$(getv ERP_DOMAIN)"; ACME_EMAIL="$(getv ACME_EMAIL)"
PROXY_MODE="$(getv PROXY_MODE)"; PROXY_MODE="${PROXY_MODE:-own}"
# behind = ada reverse proxy lain (mis. Caddy project SIPRO) yang memegang 80/443 & TLS;
# Caddy kita hanya HTTP di port internal, cocokkan Host, dan redirect memakai https://.
BEHIND=0; [ "$PROXY_MODE" = "behind" ] && BEHIND=1
SCHEME="https"

COMMON='	encode zstd gzip
	header {
		X-Content-Type-Options nosniff
		Referrer-Policy strict-origin-when-cross-origin
		-Server
	}'

if [ -z "$DOMAIN" ]; then
  cat > "$OUT" <<EOF
{
	auto_https off
}

:80 {
$COMMON
	handle /api/* {
		reverse_proxy backend:8001
	}
	handle {
		reverse_proxy frontend:80
	}
}
EOF
  echo "Caddyfile: mode IP (HTTP port $(getv HTTP_PORT), ERP di /app/login)"
  exit 0
fi

{
  if [ "$BEHIND" = 1 ]; then
    cat <<EOF
{
	auto_https off
}

http://$DOMAIN {
EOF
  else
    cat <<EOF
{
	email ${ACME_EMAIL:-admin@$DOMAIN}
}

$DOMAIN {
EOF
  fi
  cat <<EOF
$COMMON
	handle /api/* {
		reverse_proxy backend:8001
	}
EOF
  if [ -n "$ERP_DOMAIN" ]; then
    cat <<EOF
	# ERP hanya lewat subdomain: /app di situs publik dialihkan.
	redir /app https://$ERP_DOMAIN/app/login
	redir /app/* https://$ERP_DOMAIN{uri}
EOF
  fi
  cat <<EOF
	handle {
		reverse_proxy frontend:80
	}
	log {
		output file /data/access.log {
			roll_size 20mb
			roll_keep 5
		}
	}
}
EOF
  if [ -n "$ERP_DOMAIN" ]; then
    ERP_ADDR="$ERP_DOMAIN"; [ "$BEHIND" = 1 ] && ERP_ADDR="http://$ERP_DOMAIN"
    cat <<EOF

$ERP_ADDR {
$COMMON
	redir / /app/login
	handle /api/* {
		reverse_proxy backend:8001
	}
	@erp path /app /app/* /static/* /favicon.ico /manifest.json /robots.txt /asset-manifest.json /*.png /*.svg /*.ico /*.webp
	handle @erp {
		reverse_proxy frontend:80
	}
	# Halaman publik tidak dilayani dari subdomain ERP.
	handle {
		redir https://$DOMAIN{uri}
	}
}
EOF
  fi
} > "$OUT"
MODE_LABEL="HTTPS otomatis"; [ "$BEHIND" = 1 ] && MODE_LABEL="di belakang proxy lain (HTTP internal port $(getv HTTP_PORT))"
echo "Caddyfile: $DOMAIN${ERP_DOMAIN:+ + ERP $ERP_DOMAIN} — $MODE_LABEL"
