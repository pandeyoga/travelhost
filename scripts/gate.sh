#!/usr/bin/env bash
###############################################################################
# gate.sh — ORKESTRATOR GATE TUNGGAL (Layer 3 / VERIFY)
# Menjalankan SEMUA gate berurutan, lalu menulis memory/GATE_RECEIPT.md.
# Aturan: "Selesai" hanya sah bila receipt HIJAU. Klaim tanpa receipt = void.
#
# Gate STATIK selalu jalan. Gate RUNTIME (butuh backend) di-SKIP rapi bila
# backend belum berjalan (Phase 0) — bukan dianggap gagal.
#
# Usage: bash scripts/gate.sh
###############################################################################
set -uo pipefail
CYAN='\033[96m'; GREEN='\033[92m'; RED='\033[91m'; YEL='\033[93m'; BOLD='\033[1m'; RST='\033[0m'
cd "$(dirname "$0")/.." || exit 1
RECEIPT="memory/GATE_RECEIPT.md"
TS="$(date '+%Y-%m-%d %H:%M:%S')"
declare -a NAMES RESULTS
OVERALL=0

run_gate () {  # $1=label  $2=command
  local label="$1"; shift
  echo -e "\n${CYAN}${BOLD}▶ ${label}${RST}"
  bash -c "$*"
  local rc=$?
  if [ $rc -eq 0 ]; then
    echo -e "  ${GREEN}✓ ${label} PASS${RST}"; NAMES+=("$label"); RESULTS+=("PASS")
  else
    echo -e "  ${RED}✗ ${label} FAIL (rc=$rc)${RST}"; NAMES+=("$label"); RESULTS+=("FAIL"); OVERALL=1
  fi
}

skip_gate () { # $1=label $2=reason
  echo -e "\n${YEL}▶ $1 — SKIP ($2)${RST}"
  NAMES+=("$1"); RESULTS+=("SKIP")
}

echo -e "${CYAN}${BOLD}\n=============================================================="
echo "  GATE ORCHESTRATOR  —  $TS"
echo -e "==============================================================${RST}"

# --- Deteksi backend & kesiapan auth (semua gate runtime butuh login) ---
# Deteksi ROBUST (retry + timeout): blip transien TIDAK boleh menyebabkan runtime-gate
# ter-SKIP diam-diam → itu "hijau-palsu" (hijau tapi sebenarnya tak teruji).
BACKEND_UP=0
AUTH_READY=0
for _try in 1 2 3 4 5 6; do
  HTTP=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 http://localhost:8001/api/ 2>/dev/null)
  if echo "$HTTP" | grep -qE "^[2-4]"; then BACKEND_UP=1; break; fi
  sleep 2
done
if [ $BACKEND_UP -eq 1 ]; then
  echo -e "${GREEN}  Backend terdeteksi RUNNING${RST}"
  for _try in 1 2 3 4 5; do
    AUTH_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 8 -X POST http://localhost:8001/api/auth/login -H "Content-Type: application/json" -d '{}' 2>/dev/null)
    if [ "$AUTH_CODE" != "404" ] && [ "$AUTH_CODE" != "000" ]; then AUTH_READY=1; break; fi
    sleep 2
  done
  if [ $AUTH_READY -eq 1 ]; then
    echo -e "${GREEN}  Endpoint auth tersedia (HTTP $AUTH_CODE) — gate runtime AKAN dijalankan${RST}"
  else
    echo -e "${YEL}  /api/auth/login belum siap (HTTP $AUTH_CODE) setelah retry — gate runtime di-SKIP (Phase 0).${RST}"
  fi
else
  echo -e "${YEL}  Backend tidak merespons setelah retry — gate runtime akan di-SKIP (Phase 0).${RST}"
fi

# ============ SEED + STATIC GATES (selalu) ============
run_gate "seed_reset (seed + contract + api_contract + integrity)" "bash scripts/seed_reset.sh"
run_gate "verify_schema (field + FK + id-prefix)" "python scripts/verify_schema.py"
run_gate "verify_architecture (performa/tech-debt)" "python scripts/verify_architecture.py"
run_gate "verify_delivery (anti under-deliver)" "python scripts/verify_delivery.py"
run_gate "ux_audit --strict (baseline UX)" "python scripts/ux_audit.py --strict"
run_gate "validate_compliance (file/naming/docs/api/env)" "python scripts/validate_compliance.py"
run_gate "check_nav_map (navigasi vs SSOT)" "python scripts/check_nav_map.py"

# ============ GUARDRAIL v2 — STATIK (preventif lintas-kelas-bug; lihat memory/INVARIANTS.md) ============
run_gate "guard:numeric_bounds (INV-NUM-01)" "python scripts/guardrails/verify_numeric_bounds.py"
run_gate "guard:reservation_locks (INV-RACE-01)" "python scripts/guardrails/verify_reservation_locks.py"
run_gate "guard:rbac (INV-RBAC-01/02/03/04/05)" "python scripts/guardrails/verify_rbac_guards.py"
run_gate "guard:registry (INV-META-01)" "python scripts/guardrails/verify_guardrail_registry.py"
run_gate "guard:auth_coverage (INV-AUTH-01)" "python scripts/guardrails/verify_auth_coverage.py"
run_gate "guard:effort_quality (INV-QUALITY-01)" "python scripts/guardrails/verify_effort_quality.py"
# ---- FASE F3-F7 (Marketing & Ads): rantai konversi, belanja iklan, audiens, kerahasiaan ----
run_gate "guard:conversion_hooks (INV-CONV-01)" "python scripts/guardrails/verify_conversion_hooks.py"
run_gate "guard:ads_write_safety (INV-ADS-01)" "python scripts/guardrails/verify_ads_write_safety.py"
run_gate "guard:audience_consent (INV-AUD-01)" "python scripts/guardrails/verify_audience_consent.py"
run_gate "guard:secret_exposure (INV-SEC-02)" "python scripts/guardrails/verify_secret_exposure.py"

# ---- FASE F8 (Landing Page Builder): kontrak blok & keamanan media ----
run_gate "guard:landing_contract (INV-LP-02)" "python scripts/guardrails/verify_landing_contract.py"
run_gate "guard:media_safety (INV-MEDIA-02)" "python scripts/guardrails/verify_media_safety.py"

# ---- FASE 3 (Media Library SATU): anti "dua dunia media", folder aman, cache sadar-versi ----
# Penjaga + SELF-TEST-nya sengaja dua gate terpisah: yang pertama menjaga KODE, yang kedua menjaga
# PENJAGANYA (membuktikan lewat 23 mutasi bahwa penjaga masih MERAH saat bug disuntikkan). Penjaga
# yang tak pernah terbukti menggigit tak bisa dibedakan dari `return 0`.
run_gate "guard:media_unified (INV-MEDIA-03)" "python scripts/guardrails/verify_media_unified.py"
run_gate "guard:price_master (INV-PRICE-02)" "python scripts/guardrails/verify_price_master.py"
run_gate "selftest:media_unified (INV-MEDIA-03 — uji mutasi)" "python scripts/guardrails/selftest_media_unified.py"
run_gate "selftest:media_runtime (INV-MEDIA-04 — anti hijau-palsu)" "python scripts/guardrails/selftest_media_runtime.py"

# ---- KONTRAS & PEWARISAN TEMA (keluhan readability user 2026-08-12) ----
# Kelas bug yang dijaga TIDAK menghasilkan error apa pun di konsol — halaman cuma "terlihat
# rusak": gradient dengan token triplet HSL dibuang browser (panel CTA blog jadi kosong),
# permukaan kaca dipaku putih untuk semua mode (dialog putih + teks putih di mode gelap),
# konten Radix yang di-portal ke <body> tidak mewarisi token tema, dan offset elemen
# mengapung yang hardcode membuat panel chat menembus header. Statik + self-test mutasi.
run_gate "guard:theme_contrast (INV-THEME-01)" "python scripts/guardrails/verify_theme_contrast.py"
run_gate "selftest:theme_contrast (INV-THEME-01 — uji mutasi)" "python scripts/guardrails/selftest_theme_contrast.py"

# ============ RUNTIME GATES (butuh backend + auth) ============
if [ $AUTH_READY -eq 1 ]; then
  run_gate "health_check (isi endpoint kritis)" "python scripts/health_check.py"
  run_gate "audit_endpoint_sweep (semua GET → 5xx)" "python scripts/audit_endpoint_sweep.py"
  run_gate "mutation_smoke (write-path)" "python scripts/mutation_smoke.py"
  run_gate "verify_state_machine (RC-02/03/04/05)" "python scripts/verify_state_machine.py"
  run_gate "verify_concurrency (RC-01 / INV-2)" "python scripts/verify_concurrency.py"
  run_gate "verify_cross_entity (RC-06/RC-07)" "python scripts/verify_cross_entity.py"
  run_gate "guard:adversarial_5xx (INV-5XX-01)" "python scripts/guardrails/verify_adversarial_5xx.py"
  run_gate "guard:identity_race (INV-IDENT-01)" "python scripts/guardrails/verify_identity_race.py"
  run_gate "guard:settings_bounds (INV-SET-01)" "python scripts/guardrails/verify_settings_bounds.py"
  run_gate "guard:rbac_runtime (INV-RBAC-06)" "python scripts/guardrails/verify_rbac_runtime.py"
  run_gate "guard:media_runtime (INV-MEDIA-04)" "python scripts/guardrails/verify_media_runtime.py"
  # ---- PEMESANAN ONLINE (Fase 3 plan.md): harga & reservasi tidak boleh bisa ditawar klien ----
  run_gate "guard:pricing_integrity (INV-PRICE-01)" "python scripts/guardrails/verify_pricing_integrity.py"
  run_gate "guard:booking_public (INV-BOOK-02)" "python scripts/guardrails/verify_booking_public.py"
  run_gate "guard:string_bounds (INV-STR-01)" "python scripts/guardrails/verify_string_bounds.py"
  # ---- INTEGRITAS PILIHAN & REFERENSI (audit permintaan user): dropdown boleh apa saja di FE,
  #      tapi SERVER yang wajib menolak referensi hantu & pilihan di luar daftar ----
  run_gate "guard:reference_integrity (INV-REF-01)" "python scripts/guardrails/verify_reference_integrity.py"
  run_gate "guard:ssot_relations (INV-REF-02)" "python scripts/guardrails/verify_ssot_relations.py"
  run_gate "selftest:booking_guards (INV-PRICE-01/BOOK-02/STR-01 — uji mutasi)" "python scripts/guardrails/selftest_booking_guards.py"
  # ---- SIKLUS HIDUP KONTEN CMS (fase CMS-CW3): hapus WAJIB bisa dibatalkan, penyuntingan
  #      WAJIB berjejak versi, dan perubahan slug WAJIB mengalihkan URL lama. Ketiganya
  #      pernah TERBUKA: satu klik hapus = konten hilang selamanya, salah tempel = isi lama
  #      musnah, ganti slug = peringkat pencarian & tautan pihak lain mati 404. ----
  run_gate "guard:content_lifecycle (INV-CMS-01)" "python scripts/guardrails/verify_content_lifecycle.py"
  run_gate "selftest:content_lifecycle (INV-CMS-01 — uji mutasi)" "python scripts/guardrails/selftest_content_lifecycle.py"
  # ---- KEBERSIHAN DATA (BUG-0127, keluhan user 2026-08-13): penjaga & smoke menulis lewat API
  #      sungguhan; kalau side-effect-nya (percakapan Inbox, notifikasi, event, audit, aset media)
  #      tidak dibersihkan, ERP pengguna kebanjiran data hantu — termasuk customer "AAAA…"
  #      60.000 karakter dari self-test mutasi INV-STR-01. Dijalankan PALING AKHIR supaya
  #      kebocoran penjaga mana pun langsung MEMERAHKAN gate (bukan pengguna yang menemukan). ----
  run_gate "guard:no_test_pollution (INV-CLEAN-01)" "python scripts/guardrails/verify_no_test_pollution.py"
  run_gate "selftest:no_test_pollution (INV-CLEAN-01 — uji mutasi)" "python scripts/guardrails/selftest_no_test_pollution.py"
else
  skip_gate "health_check" "auth belum ada / backend down"
  skip_gate "audit_endpoint_sweep" "auth belum ada / backend down"
  skip_gate "mutation_smoke" "auth belum ada / backend down"
  skip_gate "verify_state_machine" "auth belum ada / backend down"
  skip_gate "verify_concurrency" "auth belum ada / backend down"
  skip_gate "verify_cross_entity" "auth belum ada / backend down"
  skip_gate "guard:adversarial_5xx (INV-5XX-01)" "auth belum ada / backend down"
  skip_gate "guard:identity_race (INV-IDENT-01)" "auth belum ada / backend down"
  skip_gate "guard:settings_bounds (INV-SET-01)" "auth belum ada / backend down"
  skip_gate "guard:rbac_runtime (INV-RBAC-06)" "auth belum ada / backend down"
  skip_gate "guard:media_runtime (INV-MEDIA-04)" "auth belum ada / backend down"
  skip_gate "guard:pricing_integrity (INV-PRICE-01)" "auth belum ada / backend down"
  skip_gate "guard:booking_public (INV-BOOK-02)" "auth belum ada / backend down"
  skip_gate "guard:string_bounds (INV-STR-01)" "auth belum ada / backend down"
  skip_gate "guard:reference_integrity (INV-REF-01)" "auth belum ada / backend down"
  skip_gate "guard:ssot_relations (INV-REF-02)" "auth belum ada / backend down"
  skip_gate "selftest:booking_guards (uji mutasi)" "auth belum ada / backend down"
  skip_gate "guard:content_lifecycle (INV-CMS-01)" "auth belum ada / backend down"
  skip_gate "selftest:content_lifecycle (INV-CMS-01 — uji mutasi)" "auth belum ada / backend down"
  skip_gate "guard:no_test_pollution (INV-CLEAN-01)" "auth belum ada / backend down"
  skip_gate "selftest:no_test_pollution (INV-CLEAN-01 — uji mutasi)" "auth belum ada / backend down"
fi

# ============ TULIS RECEIPT ============
{
  echo "# 🧾 GATE RECEIPT"
  echo ""
  echo "> Bukti verifikasi otomatis. Dihasilkan \`scripts/gate.sh\`. JANGAN edit manual."
  echo ""
  echo "- **Waktu:** $TS"
  if [ $AUTH_READY -eq 1 ]; then echo "- **Backend:** RUNNING + auth siap (gate runtime dijalankan)"; elif [ $BACKEND_UP -eq 1 ]; then echo "- **Backend:** RUNNING tapi auth belum ada (gate runtime di-skip — wajar di Phase 0)"; else echo "- **Backend:** DOWN (gate runtime di-skip — wajar di Phase 0)"; fi
  echo ""
  echo "| Gate | Hasil |"
  echo "|------|-------|"
  for i in "${!NAMES[@]}"; do
    echo "| ${NAMES[$i]} | ${RESULTS[$i]} |"
  done
  echo ""
  if [ $OVERALL -eq 0 ]; then
    echo "## ✅ VERDICT: HIJAU — boleh lanjut / klaim selesai (untuk cakupan yang TIDAK di-skip)."
  else
    echo "## ❌ VERDICT: MERAH — ADA GATE GAGAL. DILARANG klaim selesai. Perbaiki lalu jalankan ulang."
  fi
  echo ""
  echo "_Catatan: SKIP bukan PASS. Gate runtime harus dijalankan ulang saat backend sudah hidup._"
} > "$RECEIPT"

echo -e "\n${CYAN}${BOLD}==============================================================${RST}"
if [ $OVERALL -eq 0 ]; then
  echo -e "  ${GREEN}${BOLD}✓ SEMUA GATE (non-skip) HIJAU.${RST}  Receipt: $RECEIPT"
else
  echo -e "  ${RED}${BOLD}✗ ADA GATE MERAH.${RST}  Lihat detail di atas & $RECEIPT"
fi
echo -e "${CYAN}${BOLD}==============================================================${RST}\n"
exit $OVERALL
