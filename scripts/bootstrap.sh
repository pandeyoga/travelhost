#!/usr/bin/env bash
# scripts/bootstrap.sh — SETUP CEPAT setelah clone repo.
#
# Kenapa perlu ini?
#   - `git clone` sendiri CEPAT (repo ~6 MB; node_modules & .git di-.gitignore).
#   - Yang lama HANYA `yarn install` PERTAMA (cold): membangun node_modules ~1.1 GB
#     (CRA + ~78 dependency) + build wheel pip pertama. Reinstall "warm" hanya ~1-2 detik.
#
# Optimasi di script ini:
#   1) Install backend (pip) & frontend (yarn) PARALEL (keduanya independen).
#   2) yarn `--prefer-offline` (pakai cache global dulu) + network-timeout besar.
#   3) pip `--prefer-binary` (pakai wheel, hindari build dari source).
#   4) Restart services + health check otomatis.
#
# Pakai:
#   bash scripts/bootstrap.sh            # install + restart + health check
#   bash scripts/bootstrap.sh --seed     # + isi data demo
#   bash scripts/bootstrap.sh --gate     # + jalankan guardrail gate.sh
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "=================================================="
echo "  RAHAZA TRAVEL — BOOTSTRAP (setup cepat)"
echo "=================================================="

# 0) .env disediakan oleh platform Emergent — JANGAN dibuat/di-overwrite di sini.
[ -f backend/.env ]  || echo "  WARN backend/.env tidak ada (MONGO_URL/DB_NAME) — pastikan platform menyediakannya."
[ -f frontend/.env ] || echo "  WARN frontend/.env tidak ada (REACT_APP_BACKEND_URL) — pastikan platform menyediakannya."

t0=$(date +%s)

# 1) Install deps FE & BE PARALEL
echo "> Install backend deps (pip, prefer-binary)..."
( cd backend && pip install --prefer-binary --disable-pip-version-check -q -r requirements.txt ) &
BE=$!
echo "> Install frontend deps (yarn, prefer-offline)..."
( cd frontend && yarn install --prefer-offline --network-timeout 600000 --silent ) &
FE=$!

FAIL=0
wait $BE || { echo "  x backend deps GAGAL"; FAIL=1; }
wait $FE || { echo "  x frontend deps GAGAL"; FAIL=1; }
[ $FAIL -eq 0 ] || { echo "x Bootstrap gagal pada install deps."; exit 1; }
echo "  OK deps FE+BE siap dalam $(( $(date +%s) - t0 ))s"

# 2) Restart services (hot-reload aktif; restart utk deps/.env baru)
echo "> Restart services (supervisor)..."
sudo supervisorctl restart backend frontend >/dev/null 2>&1 || true
sleep 4

# 3) Health check backend
echo "> Health check backend..."
if curl -fsS http://localhost:8001/api/ >/dev/null 2>&1; then
  echo "  OK backend merespons di http://localhost:8001/api/"
else
  echo "  WARN backend belum merespons — cek: tail -n 50 /var/log/supervisor/backend.err.log"
fi

# 4) Opsi tambahan
case "${1:-}" in
  --seed) echo "> Seed data demo..."; python scripts/seed_data.py | tail -2 ;;
  --gate) echo "> Jalankan gate.sh..."; bash scripts/gate.sh ;;
esac

echo "=================================================="
echo "  OK BOOTSTRAP SELESAI dalam $(( $(date +%s) - t0 ))s"
echo "  Lanjut: bash scripts/gate.sh   (atau: bash scripts/bootstrap.sh --seed)"
echo "=================================================="
