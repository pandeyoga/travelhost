#!/usr/bin/env bash
###############################################################################
# run_coverage.sh — Round 6A white-box coverage harness (READ-ONLY audit)
# Stops supervisor backend, runs an instrumented uvicorn under coverage.py,
# executes every RUNTIME guardrail + comprehensive multi-role sweep, then
# combines + reports coverage. Restarts supervisor backend at the end.
###############################################################################
set -uo pipefail
cd /app
RC="/app/scripts/audit_r6/audit.coveragerc"
export COVERAGE_RCFILE="$RC"

echo "== [1/7] stop supervisor backend =="
sudo supervisorctl stop backend >/dev/null 2>&1 || true
sleep 2

echo "== [2/7] clear old coverage data =="
rm -rf /app/scripts/audit_r6/covdata 2>/dev/null || true
mkdir -p /app/scripts/audit_r6/covdata

echo "== [3/7] launch instrumented uvicorn (coverage) on :8001 =="
cd /app/backend
COVERAGE_RCFILE="$RC" coverage run -p --rcfile="$RC" -m uvicorn server:app --host 0.0.0.0 --port 8001 > /app/scripts/audit_r6/uvicorn.log 2>&1 &
UV=$!
cd /app
# wait for readiness
for i in $(seq 1 30); do
  code=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/api/ 2>/dev/null)
  if echo "$code" | grep -qE "^[2-4]"; then echo "  backend ready (HTTP $code)"; break; fi
  sleep 1
done

echo "== [4/7] seed fresh data =="
python scripts/seed_data.py > /app/scripts/audit_r6/seed.log 2>&1 && echo "  seeded" || echo "  seed WARN"

echo "== [5/7] run runtime guardrails + sweeps (driving coverage) =="
run() { echo "  -> $1"; eval "$2" > "/app/scripts/audit_r6/log_$1.txt" 2>&1 || echo "     ($1 rc=$?)"; }
run health_check           "python scripts/health_check.py"
run audit_endpoint_sweep   "python scripts/audit_endpoint_sweep.py"
run mutation_smoke         "python scripts/mutation_smoke.py"
run verify_state_machine   "python scripts/verify_state_machine.py"
run verify_concurrency     "python scripts/verify_concurrency.py"
run verify_cross_entity    "python scripts/verify_cross_entity.py"
run forensic_repro         "python scripts/forensic_repro.py || true"
run full_sweep             "python scripts/audit_r6/full_sweep.py"

echo "== [6/7] stop instrumented server (SIGINT so coverage writes) =="
kill -INT $UV 2>/dev/null || true
for i in $(seq 1 15); do
  if ! kill -0 $UV 2>/dev/null; then break; fi
  sleep 1
done
kill -TERM $UV 2>/dev/null || true
sleep 1

echo "== [7/7] combine + report coverage =="
cd /app
coverage combine --rcfile="$RC" 2>/dev/null || true
coverage json --rcfile="$RC" -o /app/scripts/audit_r6/coverage.json 2>/dev/null || true
coverage report --rcfile="$RC" > /app/scripts/audit_r6/coverage_report.txt 2>&1 || true
echo "  wrote coverage.json + coverage_report.txt"

echo "== restart supervisor backend =="
sudo supervisorctl start backend >/dev/null 2>&1 || true
sleep 3
curl -s -o /dev/null -w "supervisor backend HTTP %{http_code}\n" http://localhost:8001/api/ 2>/dev/null || true
echo "== DONE =="
