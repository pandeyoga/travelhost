#!/usr/bin/env bash
###############################################################################
# seed_reset.sh — seed bersih + INTEGRITY GATE
# Verifikasi WAJIB di DB clean-seed — DB kotor menutupi drift.
###############################################################################
set -uo pipefail
CYAN='\033[96m'; GREEN='\033[92m'; RED='\033[91m'; YELLOW='\033[93m'; BOLD='\033[1m'; RESET='\033[0m'
cd "$(dirname "$0")/.." || exit 1

echo -e "${CYAN}${BOLD}\n=============================================================="
echo "  SEED RESET + INTEGRITY GATE"
echo -e "==============================================================${RESET}\n"

echo -e "${CYAN}[1/4] Seeding data...${RESET}"
python scripts/seed_data.py
SEED_RC=$?
if [ $SEED_RC -ne 0 ]; then echo -e "${RED}${BOLD}SEED GAGAL (rc=$SEED_RC).${RESET}"; exit $SEED_RC; fi

echo -e "\n${CYAN}[1b/4] Normalisasi uang -> integer rupiah (RC-11)...${RESET}"
python scripts/migrate_money_to_int.py || true

echo -e "\n${CYAN}[2/4] [GATE] Contract verifier...${RESET}"
python scripts/verify_contract.py --all; CONTRACT_RC=$?

echo -e "\n${CYAN}[3/4] [GATE] FE↔BE API contract...${RESET}"
python scripts/verify_api_contract.py; APIC_RC=$?

echo -e "\n${CYAN}[4/4] [GATE] Data-integrity (clean seed)...${RESET}"
python scripts/verify_data_integrity.py; INTEG_RC=$?

echo -e "\n${CYAN}${BOLD}==============================================================${RESET}"
if [ $CONTRACT_RC -eq 0 ] && [ $INTEG_RC -eq 0 ] && [ $APIC_RC -eq 0 ]; then
  echo -e "  ${GREEN}${BOLD}✓ SEED + GATE LULUS.${RESET}"; RC=0
else
  echo -e "  ${RED}${BOLD}✗ GATE GAGAL — contract=$CONTRACT_RC api_contract=$APIC_RC integrity=$INTEG_RC${RESET}"; RC=1
fi
echo -e "${CYAN}${BOLD}==============================================================${RESET}\n"
echo -e "Audit lanjutan: ${CYAN}python scripts/health_check.py${RESET} | ${CYAN}python scripts/audit_endpoint_sweep.py${RESET} | ${CYAN}python scripts/ux_audit.py${RESET}"
exit $RC
