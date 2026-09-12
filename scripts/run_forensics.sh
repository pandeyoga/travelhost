#!/usr/bin/env bash
########################################################################
# run_forensics.sh — DEEP BUG-HUNT battery (superset gate.sh + probe adversarial).
# SOP lengkap: docs/17_BUGHUNT_SOP.md. Reseed di akhir agar DB bersih setelah probe.
# Pakai saat: audit berkala, sebelum rilis besar, atau saat curiga ada bug tersembunyi.
########################################################################
set -uo pipefail
cd "$(dirname "$0")/.."
G='\033[92m'; R='\033[91m'; Y='\033[93m'; C='\033[96m'; B='\033[1m'; X='\033[0m'
FAILED=0

run() {
  echo -e "\n${C}${B}▶ $1${X}"
  bash -c "$2"; rc=$?
  if [ $rc -ne 0 ]; then echo -e "${R}✗ $1 (rc=$rc)${X}"; FAILED=$((FAILED+1));
  else echo -e "${G}✓ $1${X}"; fi
}

echo -e "${C}${B}=================================================================${X}"
echo -e "${C}${B} RUN FORENSICS — DEEP BUG-HUNT (SOP: docs/17_BUGHUNT_SOP.md)${X}"
echo -e "${C}${B}=================================================================${X}"

# 1) Gate penuh (statik + runtime guards: auth, quality, numeric, race, rbac, 5xx, dst).
run "gate.sh (semua invariant + guardrail)" "bash scripts/gate.sh"

# 2) Probe forensik adversarial (butuh backend hidup).
run "fa_5xx_fuzz (adversarial luas, no-5xx)" "python forensic/fa_5xx_fuzz.py"
run "fa_rbac_matrix (RBAC runtime driver-forbidden)" "python forensic/fa_rbac_matrix.py"

# 3) Hygiene (report-only, TAK mem-fail).
echo -e "\n${C}${B}▶ hygiene: find_dead_services (report-only)${X}"
python scripts/find_dead_services.py || true

# 4) Reseed agar DB bersih setelah probe yang mungkin membuat data.
echo -e "\n${C}${B}▶ reseed (bersihkan sisa probe)${X}"
bash scripts/seed_reset.sh >/dev/null 2>&1 && echo -e "${G}✓ reseed selesai${X}" || echo -e "${Y}⚠ reseed dilewati${X}"

echo ""
if [ $FAILED -eq 0 ]; then
  echo -e "${G}${B}✓ FORENSICS BERSIH — tak ada temuan blocking. (Ingat: bersih ≠ zero-bug; lihat SOP §confidence.)${X}"
else
  echo -e "${R}${B}✗ FORENSICS: $FAILED area bermasalah — triage per docs/17_BUGHUNT_SOP.md → catat di BUG_REGISTRY → fix → guardrail → self-test.${X}"
fi
exit $FAILED
