# 🧾 GATE RECEIPT

> Bukti verifikasi otomatis. Dihasilkan `scripts/gate.sh`. JANGAN edit manual.

- **Waktu:** 2026-10-28 17:27:24
- **Backend:** RUNNING + auth siap (gate runtime dijalankan)

| Gate | Hasil |
|------|-------|
| seed_reset (seed + contract + api_contract + integrity) | PASS |
| verify_schema (field + FK + id-prefix) | PASS |
| verify_architecture (performa/tech-debt) | PASS |
| verify_delivery (anti under-deliver) | PASS |
| ux_audit --strict (baseline UX) | PASS |
| validate_compliance (file/naming/docs/api/env) | PASS |
| check_nav_map (navigasi vs SSOT) | PASS |
| guard:numeric_bounds (INV-NUM-01) | PASS |
| guard:reservation_locks (INV-RACE-01) | PASS |
| guard:rbac (INV-RBAC-01/02/03/04/05) | PASS |
| guard:registry (INV-META-01) | PASS |
| guard:auth_coverage (INV-AUTH-01) | PASS |
| guard:effort_quality (INV-QUALITY-01) | PASS |
| guard:conversion_hooks (INV-CONV-01) | PASS |
| guard:ads_write_safety (INV-ADS-01) | PASS |
| guard:audience_consent (INV-AUD-01) | PASS |
| guard:secret_exposure (INV-SEC-02) | PASS |
| guard:landing_contract (INV-LP-02) | PASS |
| guard:media_safety (INV-MEDIA-02) | PASS |
| guard:media_unified (INV-MEDIA-03) | PASS |
| guard:price_master (INV-PRICE-02) | PASS |
| selftest:media_unified (INV-MEDIA-03 — uji mutasi) | PASS |
| selftest:media_runtime (INV-MEDIA-04 — anti hijau-palsu) | PASS |
| guard:theme_contrast (INV-THEME-01) | PASS |
| selftest:theme_contrast (INV-THEME-01 — uji mutasi) | PASS |
| health_check (isi endpoint kritis) | PASS |
| audit_endpoint_sweep (semua GET → 5xx) | PASS |
| mutation_smoke (write-path) | PASS |
| verify_state_machine (RC-02/03/04/05) | PASS |
| verify_concurrency (RC-01 / INV-2) | PASS |
| verify_cross_entity (RC-06/RC-07) | PASS |
| guard:adversarial_5xx (INV-5XX-01) | PASS |
| guard:identity_race (INV-IDENT-01) | PASS |
| guard:settings_bounds (INV-SET-01) | PASS |
| guard:rbac_runtime (INV-RBAC-06) | PASS |
| guard:media_runtime (INV-MEDIA-04) | PASS |
| guard:pricing_integrity (INV-PRICE-01) | PASS |
| guard:booking_public (INV-BOOK-02) | PASS |
| guard:string_bounds (INV-STR-01) | PASS |
| guard:reference_integrity (INV-REF-01) | PASS |
| guard:ssot_relations (INV-REF-02) | PASS |
| selftest:booking_guards (INV-PRICE-01/BOOK-02/STR-01 — uji mutasi) | PASS |
| guard:content_lifecycle (INV-CMS-01) | PASS |
| selftest:content_lifecycle (INV-CMS-01 — uji mutasi) | PASS |
| guard:no_test_pollution (INV-CLEAN-01) | PASS |
| selftest:no_test_pollution (INV-CLEAN-01 — uji mutasi) | PASS |

## ✅ VERDICT: HIJAU — boleh lanjut / klaim selesai (untuk cakupan yang TIDAK di-skip).

_Catatan: SKIP bukan PASS. Gate runtime harus dijalankan ulang saat backend sudah hidup._
