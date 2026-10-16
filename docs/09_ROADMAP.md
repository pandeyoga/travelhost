# 09 — ROADMAP & TIMELINE
## Travel & Fleet Management Ecosystem

> Status fase: **RENCANA** kecuali ditandai. Tiap fase ditutup dengan gate hijau + `testing_agent_v3` + update dokumen.
>
> **GATE penjaga (jalankan `bash scripts/gate.sh` = orkestrator semua gate → `memory/GATE_RECEIPT.md`):**
> `seed_reset` · `verify_contract` · `verify_schema` · `verify_api_contract` · `verify_data_integrity` ·
> `verify_architecture` · `verify_delivery` · `ux_audit --strict` · `validate_compliance` · `check_nav_map` ·
> `health_check` · `audit_endpoint_sweep` · `mutation_smoke`. Detail per-fase: lihat `plan.md` §3.
>
> **Revamp:** tiap fase boleh di-revamp; ikuti `docs/PLAYBOOKS.md` → PLAYBOOK REVAMP (baseline gate → ubah → gate lagi).

---

## DEPENDENCY GRAPH
```
Phase 0 (Foundation) ─▶ Phase 1 (POC: GPS+booking-availability)
                          │
                          ▼
Phase 2 (ERP Core) ─▶ Phase 3 (Website+Lead) ─▶ Phase 4 (CRM)
      │                                              │
      ▼                                              ▼
Phase 5 (Finance & Reports) ─▶ Phase 6 (GPS lengkap + Maintenance)
```

---

## PHASE 0 — Governance & Foundation · **COMPLETED ✅**
Docs SSOT (13) + **Agent Operating System** (Layer 1–3: `AGENT_START_HERE`, `PLAYBOOKS`, `13`, `14` + script `preflight`/`verify_schema`/`verify_delivery`/`verify_architecture`/`mutation_smoke`/`gate.sh` + memory `BUG_REGISTRY`/`DELIVERY_MANIFEST`) + auth/RBAC + seed + skeleton FE/BE dual-surface.
- **0.1 Docs SSOT** ✅ · **0.2 Guardrail awal** ✅ · **0.3 Agent OS** ✅ (gate.sh EXIT 0, uji-negatif lulus) · **0.4 Auth+RBAC+skeleton** ✅ DONE (gate HIJAU 10/10; testing_agent 100%).
**GATE 0.4:** `bash scripts/gate.sh` dengan backend hidup → `health_check`/`audit_endpoint_sweep`/`mutation_smoke` TIDAK boleh skip + `testing_agent_v3`.
**Exit:** login owner/ops_admin/driver berfungsi; shell tampil tanpa error; semua gate hijau.

## PHASE 1 — POC Core (Isolation) · ~30 mnt · **COMPLETED ✅**
GPS geolocation → `locations` → live map (Leaflet) + ETA (OSRM) + status trip. Engine **anti double-booking**. Python test script membuktikan semua.
**Exit:** driver share lokasi → map update di preview; invarian overlap & lokasi lulus; 0 5xx.

## PHASE 2 — ERP Core · ~45 mnt · **COMPLETED ✅**
Master `vehicles`/`drivers`/`customers` (CRUD penuh + guard FK); Booking create/edit + transisi + Kalender; pencatatan pembayaran (DP/pelunasan, INV-2/INV-3); Customer 360 (riwayat + statistik); Dashboard role-specific + reminder dokumen due-soon + booking terbaru.
**Exit:** ✅ CRUD lengkap dengan states; `verify_api_contract`/`verify_delivery` P0 100% lulus; `mutation_smoke` AKTIF & HIJAU (create→bayar→lunas); `testing_agent_v3` 100% (52/52 BE, FE+RBAC pass, 0 bug); gate HIJAU 10/10.

## PHASE 3 — Website Publik (66nord-inspired) · ~45 mnt
Home+trip-finder, Fleet, Destinasi+hotel, Trip Calculator, Quotation→leads, Blog, ThankYou, WA floating.
**Exit:** form lead masuk DB & muncul di CRM; mobile-first; no broken link.

## PHASE 4 — CRM Internal · ~40 mnt
Pipeline kanban, inbox multi-admin, auto-assignment, reminder H-7/H-3/H-1, broadcast (struktur).
**Exit:** lead website → pipeline; invarian stage; testing agent.

## PHASE 5 — Keuangan & Laporan · ~40 mnt
DP/pelunasan, expenses, Laba-Rugi per trip & bulanan, AR/piutang, invoice, export PDF/Excel, laporan.
**Exit:** invarian profit & pembayaran lulus; export berfungsi; testing agent.

## PHASE 6 — GPS lengkap + Maintenance · ~40 mnt · **COMPLETED ✅**
Live fleet map semua unit + indikator stale/offline, histori track lintas-trip, geofence auto-status (tiba pickup/tujuan), reminder KIR/pajak/servis (H-30/14/7) + window perawatan blok booking (INV-21), share-link korporat (token+expiry+revoke) + halaman publik `/track/:token`, adapter Maps (OSRM default, Google stub siap).
**Exit:** ✅ alur penuh booking→assign→tracking→complete→report; gate HIJAU 10/10; `verify_delivery` Phase 6 10/10 P0 (0 orphan); INV-21/22 PASS; `testing_agent_v3` Backend 97.5% (0 bug nyata) · Frontend 100%.

---

## RISIKO & MITIGASI
- **Izin geolocation browser** → minta bantuan user untuk test di Phase 1; fallback input manual koordinat.
- **Akurasi ETA OSRM** (tanpa traffic) → tandai "estimasi"; jalur upgrade Google Maps.
- **Double-booking** → invarian + cek server-side saat create (400 bila overlap).
- **Profit on partial payment** → kebijakan eksplisit + uji angka.
- **File membengkak** → router thin + service; patuhi batas ukuran.
- **Revamp merusak fase lain** → kontrak API/data stabil + adapter pattern + `gate.sh` baseline-vs-after (regresi langsung ketahuan).
- **Agent under-deliver** → `DELIVERY_MANIFEST.md` + `verify_delivery.py` (completeness P0 + orphan) + protokol `docs/14`.
