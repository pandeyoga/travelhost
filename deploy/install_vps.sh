#!/usr/bin/env bash
# Pasang RahazaTrans (Travel ERP) di VPS Ubuntu/Debian bersih: Docker + MongoDB 7 + Caddy.
#
#   Tanpa domain (akses via IP, HTTP):
#     OWNER_EMAIL=admin@anda.com OWNER_PASSWORD='RahasiaKuat123' bash deploy/install_vps.sh
#
#   Dengan domain (HTTPS otomatis) + ERP di subdomain:
#     DOMAIN=rahazatrans.com ERP_DOMAIN=erp.rahazatrans.com ACME_EMAIL=email@anda.com \
#     OWNER_EMAIL=admin@anda.com OWNER_PASSWORD='RahasiaKuat123' bash deploy/install_vps.sh
#
#   Tambah SEED_DEMO=true untuk mengisi data demo (owner/ops/marketing/driver @demo.local, pass demo12345).
#
#   VPS yang sudah ada project lain (port 80/443 terpakai, mis. SIPRO) terdeteksi otomatis ->
#   PROXY_MODE=behind, situs jalan di HTTP_PORT (default 8080) dan TLS diserahkan ke proxy yang ada.
#   Paksa: PROXY_MODE=own|behind HTTP_PORT=8080. Matikan WhatsApp: WA_ENABLED=false.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEPLOY_DIR="$REPO_DIR/deploy"
ENV_FILE="$DEPLOY_DIR/.env"

say() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
die() { printf '\n\033[1;31mGAGAL: %s\033[0m\n' "$*" >&2; exit 1; }

[ "$(id -u)" = "0" ] || die "jalankan sebagai root (sudo -i)"

say "Paket dasar & Docker"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq ca-certificates curl git ufw dnsutils openssl
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sh
fi
docker compose version >/dev/null 2>&1 || die "docker compose plugin tidak tersedia"

say "Firewall (22/80/443)"
ufw allow 22/tcp >/dev/null; ufw allow 80/tcp >/dev/null; ufw allow 443/tcp >/dev/null
ufw --force enable >/dev/null

# Deteksi project lain (mis. SIPRO) yang sudah memegang port 80/443 di VPS ini.
port_busy() { ss -ltnH 2>/dev/null | awk '{print $4}' | grep -Eq "[:.]$1\$"; }
if [ -z "${PROXY_MODE:-}" ]; then
  if port_busy 80 || port_busy 443; then PROXY_MODE=behind; else PROXY_MODE=own; fi
fi
if [ "$PROXY_MODE" = "behind" ]; then
  HTTP_PORT="${HTTP_PORT:-8080}"
  port_busy "$HTTP_PORT" && die "port $HTTP_PORT juga terpakai — set HTTP_PORT=<port bebas>"
  ufw allow "$HTTP_PORT"/tcp >/dev/null
  echo "Port 80/443 sudah dipakai project lain -> mode BEHIND: situs ini di port $HTTP_PORT (HTTP), TLS oleh proxy yang ada."
else
  HTTP_PORT="${HTTP_PORT:-80}"
fi

if [ ! -f "$ENV_FILE" ]; then
  DOMAIN="${DOMAIN:-}"; ERP_DOMAIN="${ERP_DOMAIN:-}"
  ip_vps="$(curl -fsS https://api.ipify.org || hostname -I | awk '{print $1}')"
  if [ -n "$DOMAIN" ]; then
    say "Cek DNS"
    for d in $DOMAIN $ERP_DOMAIN; do
      ip_dns="$(dig +short "$d" | tail -1 || true)"
      [ -n "$ip_dns" ] || die "A record $d belum ada (arahkan ke $ip_vps)"
      [ "$ip_dns" = "$ip_vps" ] || echo "PERINGATAN: DNS $d = $ip_dns, IP VPS = $ip_vps (matikan proxy Cloudflare saat pertama kali)"
    done
    PUBLIC_SITE_URL="https://$DOMAIN"
    CORS_ORIGINS="https://$DOMAIN${ERP_DOMAIN:+,https://$ERP_DOMAIN}"
  else
    PUBLIC_SITE_URL="http://$ip_vps$([ "$HTTP_PORT" = 80 ] || echo ":$HTTP_PORT")"
    CORS_ORIGINS="*"
  fi
  COMPOSE_FILE="docker-compose.yml"; [ "$PROXY_MODE" = "own" ] && COMPOSE_FILE="docker-compose.yml:docker-compose.tls.yml"
  WA_PROFILE="wa"; [ "${WA_ENABLED:-true}" = "true" ] || WA_PROFILE=""

  say "Membuat deploy/.env"
  umask 077
  cat > "$ENV_FILE" <<EOF
COMPOSE_PROJECT_NAME=travel
COMPOSE_FILE=$COMPOSE_FILE
COMPOSE_PROFILES=$WA_PROFILE
PROXY_MODE=$PROXY_MODE
HTTP_PORT=$HTTP_PORT
HTTPS_PORT=443
DOMAIN=$DOMAIN
ERP_DOMAIN=$ERP_DOMAIN
ACME_EMAIL=${ACME_EMAIL:-}
DB_NAME=${DB_NAME:-travel}
PUBLIC_SITE_URL=$PUBLIC_SITE_URL
CORS_ORIGINS=$CORS_ORIGINS
OWNER_EMAIL=${OWNER_EMAIL:-owner@rahazatrans.id}
OWNER_PASSWORD=${OWNER_PASSWORD:-$(openssl rand -base64 12 | tr -d '/+=' | cut -c1-16)}
OWNER_NAME=${OWNER_NAME:-Pemilik}
GPS_WEBHOOK_SECRET=$(openssl rand -hex 24)
OPENWA_API_KEY=$(openssl rand -hex 24)
OPENWA_EXTRA_ARGS=
GOOGLE_MAPS_API_KEY=
MAP_PROVIDER=
EMERGENT_LLM_KEY=
MEDIA_BACKEND=local
EOF
else
  say "deploy/.env sudah ada — dipakai apa adanya"
fi

say "Susun Caddyfile"
bash "$DEPLOY_DIR/render_caddyfile.sh"

say "Build & jalankan"
mkdir -p "$DEPLOY_DIR/backups"
cd "$DEPLOY_DIR"
docker compose build --pull
docker compose up -d --remove-orphans

say "Tunggu backend sehat"
for i in $(seq 1 72); do
  status="$(docker compose ps --format '{{.Service}} {{.Health}}' 2>/dev/null | awk '$1=="backend"{print $2}')"
  [ "$status" = "healthy" ] && break
  sleep 5
  [ "$i" = "72" ] && { docker compose logs --tail=80 backend; die "backend tidak sehat"; }
done

say "Akun owner"
docker compose exec -T backend python /app/deploy/create_owner.py
if [ "${SEED_DEMO:-false}" = "true" ]; then
  say "Isi data demo"
  docker compose exec -T backend python /app/scripts/seed_data.py
fi

say "Cron backup harian 02:00"
CRON_LINE="0 2 * * * bash $DEPLOY_DIR/backup.sh >> /var/log/travel-backup.log 2>&1"
( crontab -l 2>/dev/null | grep -v 'deploy/backup.sh' ; echo "$CRON_LINE" ) | crontab -

DOMAIN_VAL="$(grep '^DOMAIN=' "$ENV_FILE" | cut -d= -f2-)"
ERP_VAL="$(grep '^ERP_DOMAIN=' "$ENV_FILE" | cut -d= -f2-)"
MODE_VAL="$(grep '^PROXY_MODE=' "$ENV_FILE" | cut -d= -f2-)"
PORT_VAL="$(grep '^HTTP_PORT=' "$ENV_FILE" | cut -d= -f2-)"
docker compose ps
echo
if [ -n "$DOMAIN_VAL" ]; then
  echo "Situs   ->  https://$DOMAIN_VAL"
  echo "ERP     ->  https://${ERP_VAL:-$DOMAIN_VAL}/app/login"
  [ "$MODE_VAL" = "behind" ] && bash "$DEPLOY_DIR/proxy_snippet.sh"
else
  ip_vps="$(curl -fsS https://api.ipify.org || hostname -I | awk '{print $1}')"
  SUFFIX=""; [ "$PORT_VAL" = "80" ] || SUFFIX=":$PORT_VAL"
  echo "Situs   ->  http://$ip_vps$SUFFIX"
  echo "ERP     ->  http://$ip_vps$SUFFIX/app/login"
fi
echo "Login   ->  $(grep '^OWNER_EMAIL=' "$ENV_FILE" | cut -d= -f2-) / $(grep '^OWNER_PASSWORD=' "$ENV_FILE" | cut -d= -f2-)"
echo "WA      ->  ERP > Sistem > Integrasi API > WhatsApp: provider OpenWA, lalu scan QR"
echo "Update  ->  cd $REPO_DIR && bash deploy/update.sh"
echo "Domain  ->  bash deploy/set_domain.sh rahazatrans.com erp.rahazatrans.com email@anda.com"
