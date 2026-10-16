#!/usr/bin/env bash
###############################################################################
# run_coverage_r11.sh — Round 11 white-box coverage harness (READ-ONLY audit)
# Same idea as run_coverage.sh but adds the comprehensive MUTATION sweep so that
# POST/PUT/PATCH/DELETE code paths are exercised (the Round-6 blind spot).
# Uses `python -m coverage` (coverage binary not on PATH in this env).
# Restarts supervisor backend at the end.
###############################################################################
set -uo pipefail
cd /app
RC="/app/scripts/audit_r11/audit_r11.coveragerc"
export COVERAGE_RCFILE="$RC"
# Ephemeral audit-only env (NOT written to backend/.env): lets the GPS webhook ingest
# path (services/gps.py) be exercised by the instrumented server during coverage run.
export GPS_WEBHOOK_SECRET="r11audit-secret"
PY=python

echo "== [1/8] stop supervisor backend =="
sudo supervisorctl stop backend >/dev/null 2>&1 || true
sleep 2

echo "== [2/8] clear old coverage data =="
rm -rf /app/scripts/audit_r11/covdata 2>/dev/null || true
mkdir -p /app/scripts/audit_r11/covdata

echo "== [3/8] launch instrumented uvicorn (coverage) on :8001 =="
cd /app/backend
COVERAGE_RCFILE="$RC" $PY -m coverage run -p --rcfile="$RC" -m uvicorn server:app --host 0.0.0.0 --port 8001 > /app/scripts/audit_r11/uvicorn.log 2>&1 &
UV=$!
cd /app
for i in $(seq 1 40); do
  code=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/api/ 2>/dev/null)
  if echo "$code" | grep -qE "^[2-4]"; then echo "  backend ready (HTTP $code)"; break; fi
  sleep 1
done

echo "== [4/8] seed fresh data =="
$PY scripts/seed_data.py > /app/scripts/audit_r11/seed.log 2>&1 && echo "  seeded" || echo "  seed WARN"

echo "== [5/8] runtime guardrails + GET sweep (baseline coverage) =="
run() { echo "  -> $1"; eval "$2" > "/app/scripts/audit_r11/log_$1.txt" 2>&1 || echo "     ($1 rc=$?)"; }
run health_check           "$PY scripts/health_check.py"
run audit_endpoint_sweep   "$PY scripts/audit_endpoint_sweep.py"
run mutation_smoke         "$PY scripts/mutation_smoke.py"
run verify_state_machine   "$PY scripts/verify_state_machine.py"
run verify_concurrency     "$PY scripts/verify_concurrency.py"
run verify_cross_entity    "$PY scripts/verify_cross_entity.py"
run forensic_repro         "$PY scripts/forensic_repro.py || true"
run full_sweep_GET         "$PY scripts/audit_r6/full_sweep.py"

echo "== [6/8] COMPREHENSIVE MUTATION sweep (Round 11 — write paths) =="
run mutation_sweep_r11     "$PY scripts/audit_r11/mutation_sweep.py"

echo "== [6b/8] wait for background scheduler tick (process_due / process_scheduled) =="
# scheduler loop runs at boot+8s then every 120s; the mutation sweep planted due
# enrollments + a past-scheduled campaign, so one more tick exercises sequences/campaigns svc.
sleep 125

echo "== [7/8] stop instrumented server (SIGINT so coverage writes) =="
kill -INT $UV 2>/dev/null || true
for i in $(seq 1 15); do
  if ! kill -0 $UV 2>/dev/null; then break; fi
  sleep 1
done
kill -TERM $UV 2>/dev/null || true
sleep 1

echo "== [8/8] combine + report coverage =="
cd /app
$PY -m coverage combine --rcfile="$RC" 2>/dev/null || true
$PY -m coverage json --rcfile="$RC" -o /app/scripts/audit_r11/coverage_r11.json 2>/dev/null || true
$PY -m coverage report --rcfile="$RC" > /app/scripts/audit_r11/coverage_report_r11.txt 2>&1 || true
echo "  wrote coverage_r11.json + coverage_report_r11.txt"
tail -n 3 /app/scripts/audit_r11/coverage_report_r11.txt

echo "== restart supervisor backend =="
sudo supervisorctl start backend >/dev/null 2>&1 || true
sleep 3
curl -s -o /dev/null -w "supervisor backend HTTP %{http_code}\n" http://localhost:8001/api/ 2>/dev/null || true
echo "== DONE =="
