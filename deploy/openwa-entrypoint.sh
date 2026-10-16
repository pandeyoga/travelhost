#!/usr/bin/env sh
# Jalankan wa-automate Easy API. cwd=/data (volume) agar sesi (_IGNORE_rahaza, *.data.json) persisten.
set -eu
: "${OPENWA_API_KEY:?OPENWA_API_KEY wajib diisi}"
PORT="${OPENWA_PORT:-8033}"
SESSION_ID="${OPENWA_SESSION_ID:-rahaza}"
WEBHOOK="${OPENWA_WEBHOOK:-http://backend:8001/api/wa/openwa-webhook}?key=${OPENWA_API_KEY}"

cd /data
# Buang lock Chromium yatim (container restart) — kalau tidak, Chrome menolak start & QR tak muncul.
for f in SingletonLock SingletonCookie SingletonSocket; do rm -f "/data/_IGNORE_${SESSION_ID}/$f"; done

cat > /data/cli.config.json <<EOF
{
  "executablePath": "/usr/bin/chromium",
  "chromiumArgs": ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
}
EOF

exec /opt/openwa/node_modules/.bin/wa-automate \
  -p "$PORT" --api-key "$OPENWA_API_KEY" --session-id "$SESSION_ID" \
  --qr-timeout 86400 --no-dashboard --webhook "$WEBHOOK" --skip-url-check ${OPENWA_EXTRA_ARGS:-}
