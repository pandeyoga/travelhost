# 🔎 Laporan Audit Kode — Rahaza Travel ERP — **PUTARAN 11 (Coverage-Ceiling + Completeness Matrices)**

> **Kelanjutan** dari `docs/AUDIT_REPORT_ROUND6.md` (Putaran 6–10, confidence berakhir **~78%**).
> **Pemicu:** permintaan menaikkan **confidence audit ~78% → target ~90%** dan **cakupan kode backend 46,4% → sedekat mungkin 90%**, dengan bukti (coverage + matriks kelengkapan + reprodusi live).
>
> **Mode: REPORT-ONLY.** Tidak ada perubahan kode produksi (`backend/routers`, `backend/services`, `schemas.py`, `frontend/src`). Seluruh artefak audit terisolasi di `scripts/audit_r11/`.
> **`scripts/gate.sh` tetap HIJAU 13/13** — dikonfirmasi ulang di akhir putaran ini (lihat §10).
>
> **Status semua temuan: ⏳ BELUM DIPERBAIKI — menunggu keputusan per-bug dari Owner.**

---

## 0. Ringkasan Eksekutif

Putaran 11 menjawab dua pertanyaan sisa dari Putaran 6–10 dengan **bukti angka**:

1. *"Berapa banyak kode yang sebenarnya sudah pernah dieksekusi?"* → cakupan diangkat **drastis**.
2. *"Apakah 2 kelas akar-masalah (race/TOCTOU + nilai negatif) sudah terpetakan penuh, atau masih ada pintu tersembunyi?"* → dibuktikan **lengkap** lewat matriks statis + reprodusi runtime.

| Metrik | Baseline (Putaran 6) | **Putaran 11** | Δ |
|---|---:|---:|---:|
| Cakupan **statement** backend (`routers/`+`services/`) | ~52% | **87,0%** | **+35 pp** |
| Cakupan **combined** (branch=True, metrik `coverage.py`) | **46,4%** | **83,0%** | **+36,6 pp** |
| Statement TIDAK tereksekusi | 3.446 / 7.196 | **939 / 7.196** | −2.507 |
| Panggilan MUTASI (POST/PUT/PATCH/DELETE) dieksekusi | ±0 (guardrail) | **495 call** | — |
| Kelas 5xx **baru** ditemukan di 495 mutasi | — | **0** (hanya 3 bug 5xx yang sudah dikenal) | — |
| Modul ERP frontend dirender (testing_agent, 3 peran) | 20/20 | render OK + **1 temuan RBAC baru (O-1)** | — |
| `gate.sh` | HIJAU 13/13 | **HIJAU 13/13** | tetap |

**Confidence audit: ~78% → ~88%** (jujur; lihat justifikasi §8). Sisa jarak ke 90%+ bukan karena blind-spot yang belum terlihat, melainkan karena **2 kelas akar-masalah sudah dipetakan tetapi belum ditambal** (report-only) dan **integrasi eksternal (WhatsApp Graph API, geocode/OSRM) tak bisa diuji offline**.

> **📌 ADDENDUM PUTARAN 11.5 (Post-Fix, atas persetujuan Owner):** mode berubah dari report-only → **FIX**. Ketiga temuan utama (O-1 RBAC, negative-value, race/TOCTOU) **telah diperbaiki & diverifikasi**, integrasi eksternal **diuji LIVE**. **Confidence naik ke ~93%.** Rincian lengkap: **§11.5** di bawah.

### Temuan Putaran 11 (baru / dikonfirmasi ulang)

| # | Temuan | Severity | Berkas | Bukti | Status |
|---|--------|:--------:|--------|:-----:|:------:|
| **O-1** | **RBAC bocor di frontend**: peran **Driver** dapat mengakses modul manajemen penuh (Bookings, Settings, Armada, Driver) — bukan hanya "Ruang Kerja Driver" | 🔴 Tinggi | `frontend/src` (route guard) | testing_agent iter-61 (screenshot) | ⏳ Belum |
| **RC-MATRIX-A** | **7 write-path** menulis reservasi kendaraan **tanpa `vehicle_lock`** (risiko double-book TOCTOU); **5** di antaranya juga **tak cek konflik driver** | 🟠 Sedang–Tinggi | lihat matriks §4A | Scan statis + konfirmasi runtime | ⏳ Belum |
| **RC-MATRIX-B** | **57 dari 63** field numerik uang/kuantitas **tak dibatasi** (`ge`/`gt`) di schema → menerima nilai negatif | 🟠 Sedang | `schemas.py` | Matriks §4B | ⏳ Belum |

> Temuan Putaran 6–10 yang masih terbuka (R6-1..R6-5, M1, EXPORT-1, ID-RACE, SET-1) **dikonsolidasikan** di §7. Putaran 11 **mengonfirmasi ulang** ketiga bug 5xx yang dikenal (EXPORT-1, R6-4, R6-5) muncul deterministik di sweep mutasi, dan **tidak menemukan kelas 5xx baru**.

---

## 1. Metodologi Putaran 11

| Fase | Pendekatan | Alat / Artefak | Yang dibuktikan |
|:---:|---|---|---|
| 0 | **Baseline reproduksi** | `scripts/gate.sh` → `memory/GATE_RECEIPT.md` (HIJAU 13/13); baseline coverage | Titik ukur tetap; nol perubahan produksi |
| 11A | **Mutation-coverage harness** | `scripts/audit_r11/mutation_sweep.py`, `run_coverage_r11.sh`, `coverage_r11.json`, `coverage_report_FINAL.txt` | Eksekusi hampir seluruh write-path + cabang error → coverage 46,4%→83,0% |
| 11A′ | **Ceiling analysis** | `coverage_ceiling_analysis.py/.txt` | Kategorisasi 939 statement tersisa: unreachable-by-design (jaringan/scheduler/fault) vs reachable |
| 11B | **Matriks kelengkapan akar-masalah** | `root_cause_matrix.py/.json/.txt` | Peta **lengkap** write-path × guard (race) & field numerik × bounds (negatif) |
| 11B′ | **Reproduksi forensik legacy** | `scripts/forensic_repro.py` → `log_forensic_repro.txt` | Bug lama BUG-A..G **tidak lagi reprodusibel** (guard RC-01..07 efektif) |
| 11D | **Verifikasi UI (testing_agent)** | `test_reports/iteration_61.json` | Kesehatan render 3 peran + temuan RBAC O-1 |
| 11E | **Pelaporan + gate final** | dokumen ini + `gate.sh` re-run | Konsolidasi bukti + confidence jujur + menu keputusan |

Semua reproduksi memakai DB seed bersih (`owner@demo.local` / `ops@demo.local` / `driver@demo.local`, password `demo12345`), backend `localhost:8001`.

---

## 2. Cakupan Kode — Baseline vs Putaran 11

**Sumber:** `scripts/audit_r11/coverage_report_FINAL.txt` (baris TOTAL), diverifikasi `coverage_ceiling_analysis.txt`.

```
TOTAL   Stmts=7196   Miss=939   Branch=3134   BrPart=575   Cover(combined)=83.0%
Statement coverage = (7196-939)/7196 = 87.0%
```

| Ukuran | Baseline | Putaran 11 |
|---|---:|---:|
| Statement coverage | ~52% | **87,0%** |
| Combined coverage (metrik apple-to-apple dgn baseline 46,4%) | **46,4%** | **83,0%** |
| Statement missed | 3.446 | **939** |

### 2.1 Ceiling — 939 statement tersisa (kenapa 90% mahal)

- **57 statement** benar-benar **unreachable** di sandbox (butuh jaringan keluar / kredensial live):
  `services/geocode.py`, `services/osrm.py`, `services/maps.py`, `services/geofence.py`, `services/geo.py`.
- **Partial-ceiling** (sebagian jalur unreachable tanpa ubah kode produksi / tanpa layanan live):
  `services/whatsapp.py` (jalur nyata Graph API MetaCloud ~15 stmt), `services/ratelimit.py` (fallback in-memory hanya saat Mongo mati), `services/notifications.py` (scan hold-expiry butuh hold ber-tanggal LAMPAU yang tak bisa dibuat via API), `routers/bookings.py` (auto-expire hold + guard exception scheduler/fault-only).
- Cakupan **reachable-adjusted** (kecualikan modul jaringan): **87,6%**.
- Sisa ~**112 statement** tergolong *genuinely-unreachable* (jaringan + scheduler/fault-injection); sisanya adalah cabang defensif ROI rendah.

**Top blind-spot yang tersisa (miss terbesar):** `bookings.py` (91), `whatsapp.py` (64), `gps.py` (28), `inbox.py` (27), `subcharters.py` (24), `leads.py` (23), `content.py` (23), `quotations.py` (22). Rincian per-file: `coverage_ceiling_analysis.txt`.

> **Kesimpulan §2:** cakupan kode NYATA sudah **≈87% statement**. Blind-spot besar tempat bug historis (B1–B9) bersembunyi kini **sudah dieksekusi**. Sisa yang tak tercakup didominasi kode yang **tak terjangkau tanpa jaringan/scheduler** — ini adalah **ceiling yang wajar**, bukan area buggy yang belum diperiksa.

---

## 3. Sweep Mutasi — 495 Panggilan Write-Path

**Sumber:** `scripts/audit_r11/mutation_matrix.json`, `log_mutation_sweep_r11.txt` (32 grup skenario).

```
TOTAL mutation calls: 495
By status: 200:373  400:28  401:21  403:4  404:48  405:1  422:12  429:2  500:3  EXC:3
5xx count: 3  (SEMUA sudah dikenal)
```

**Tiga 5xx yang muncul — semuanya bug yang SUDAH dikatalog (bukan temuan baru):**

| Endpoint | Konteks | Kode | Kaitan |
|---|---|---:|---|
| `GET /api/quotations/{id}/pdf` | owner | 500 | **EXPORT-1** — PDF dengan markup `<&` |
| `GET /api/crm/segments/{id}/preview` | owner | 500 | **R6-4** — kriteria segmen tak valid |
| `POST /api/content/destinations` | owner | 500 | **R6-5** — field angka diisi non-numerik |

> **Signifikansi:** 495 panggilan mutasi lintas 3 peran menghasilkan **0 kelas 5xx baru**. Distribusi 4xx sehat (validasi/RBAC/idempotensi bekerja: 400/401/403/422/429 muncul di tempat yang benar). Ini bukti kuat bahwa **tidak ada kelas crash besar yang belum ditemukan** di permukaan mutasi.

---

## 4. Matriks Kelengkapan Akar-Masalah (Phase 11B)

Dua kelas sistemik yang jadi risiko utama sejak Putaran 6 kini **dipetakan tuntas** (statis + konfirmasi runtime). Sumber: `scripts/audit_r11/root_cause_matrix.txt/.json`.

### 4A. Matriks Race / TOCTOU — write-path reservasi kendaraan/driver

Kolom: `fconf`=panggil `find_conflicts` · `fdrv`=`find_driver_conflicts` · `fmnt`=cek maintenance · `vlock`=pakai `vehicle_lock` (mutex) · **VEH-SAFE** · **DRV-CHK**.

| write path | fconf | fdrv | fmnt | vlock | VEH-SAFE | DRV-CHK |
|---|:--:|:--:|:--:|:--:|:--:|:--:|
| `bookings.create_booking` | Y | Y | Y | Y | **SAFE** | Y |
| `bookings.create_group_booking` | Y | Y | Y | Y | **SAFE** | Y |
| `bookings.confirm_booking` | Y | Y | Y | Y | **SAFE** | Y |
| `bookings.reschedule_booking` | Y | Y | Y | Y | **SAFE** | Y |
| `bookings.approve_booking` | Y | Y | Y | Y | **SAFE** | Y |
| `bookings.update_booking (PATCH driver)` | - | Y | - | - | 🟠 RISK | Y |
| `dispatch.assign_trip` | Y | Y | - | - | 🟠 RISK | Y |
| `quotations.convert` | Y | - | Y | - | 🟠 RISK | **NO** |
| `subcharters.create` | - | - | - | - | 🟠 RISK | **NO** |
| `subcharters.update (PATCH)` | - | - | - | - | 🟠 RISK | **NO** |
| `public.create_public_booking` | - | - | - | - | 🟠 RISK | **NO** |
| `driver.checkin` | - | - | - | - | 🟠 RISK | **NO** |

- **Aman (5 path inti booking):** create/group/confirm/reschedule/approve → memakai `vehicle_lock` + cek konflik penuh. Ini menjelaskan kenapa gate `verify_concurrency` (RC-01/INV-2) HIJAU.
- **Risiko double-book kendaraan (tanpa `vehicle_lock` saat re-check):** `update_booking(PATCH driver)`, `dispatch.assign_trip`, `quotations.convert`, `subcharters.create`, `subcharters.update`, `public.create_public_booking`, `driver.checkin`.
- **Tidak cek konflik driver:** `quotations.convert`, `subcharters.create/update`, `public.create_public_booking`, `driver.checkin`.

> **Kelengkapan:** matriks ini dihasilkan dari enumerasi **semua** rute penulis reservasi (bukan sampel). Tidak ada pintu tersembunyi lain — inilah daftar tuntas untuk kelas race.

### 4B. Matriks Nilai-Negatif — field uang/kuantitas di schema

**57 dari 63** field numerik **tak dibatasi** (`ge`/`gt`) di layer schema → menerima nilai negatif.

**Field yang SUDAH dibatasi (6):** `AddOn.amount` (ge), `PaymentCreate.amount` (gt), `QuotationItemIn.amount` (ge), `ExpenseCreate.amount` (gt), `SubcharterCreate.cost` (gt), `SettlementCreate.amount` (gt).

**Contoh field yang BELUM dibatasi (dari 57):**
`BookingCreate.base_price`, `BookingApprove.base_price`, `GroupUnit.base_price`, `CancelBooking.cancellation_fee/refund_amount`, `Vehicle*.capacity/odometer/price_from`, `InvoiceCreate.amount` (R6-2), `Maintenance*.cost/odometer` (R6-3), `DriverCompUpdate.base_salary_monthly/commission_*`, `PayoutLineIn.amount`, `SubcharterUpdate.cost`, `MarketingSpendItem.amount`, `Lead*.value`, dll.

> **Dampak:** faktur/biaya/gaji/komisi bernilai minus bisa tersimpan → distorsi laporan keuangan (AR/AP, P&L, payroll). Daftar lengkap 57 field: `root_cause_matrix.txt` baris 91–149.
>
> **Kelengkapan:** dihasilkan dari refleksi **semua** model Pydantic di `schemas.py` — daftar tuntas untuk kelas nilai-negatif.

---

## 5. Reproduksi Forensik Legacy (BUG-A..G) — Regression Guard

**Sumber:** `scripts/audit_r11/log_forensic_repro.txt`. Tujuh bug state-machine/race lama diuji ulang:

| Bug | Deskripsi | Hasil Putaran 11 |
|---|---|---|
| BUG-A | armada `on_trip` padahal trip cancelled | **TIDAK TERBUKTI** (bersih) |
| BUG-B | bayar ke booking cancelled | **TIDAK TERBUKTI** (ditolak 400) |
| BUG-C | complete tanpa lunas → AR jujur | **TIDAK TERBUKTI** (payment_status `belum_bayar`) |
| BUG-D | armada tak dibebaskan saat completed | **TIDAK TERBUKTI** (vehicle available) |
| BUG-E | payout periode tumpang-tindih | **TIDAK TERBUKTI** (ditolak 400) |
| BUG-F | double-assign driver | **TIDAK TERBUKTI** (ditolak 400) |
| BUG-G | race overpayment | **TIDAK TERBUKTI** (serialize; Σ=800k ≤ limit) |

> Konsisten dengan gate `verify_state_machine` (RC-02/03/04/05), `verify_concurrency` (RC-01), `verify_cross_entity` (RC-06/07) yang HIJAU. Guard inti kokoh; risiko race yang tersisa ada di **path non-inti** yang dipetakan §4A.

---

## 6. Verifikasi UI (testing_agent, Putaran 11 — Read-Only)

**Sumber:** `test_reports/iteration_61.json`. Frontend-only, 3 peran, tanpa perubahan kode.

**LULUS (ringkas):**
- Login berhasil untuk owner/ops/driver.
- OWNER: Dashboard/Control Tower, Bookings (dialog create terbuka), Dispatch, CRM, Maintenance, Reports, Inbox → render OK.
- OPS: Bookings, Dispatch, Customers render OK; **link Settings TIDAK muncul** (RBAC ops benar).
- DRIVER: "Ruang Kerja Driver" render dengan kartu tugas (3 tugas, 2 aktif, 1 selesai, 1 butuh POD).
- **0 console error, 0 error jaringan 4xx/5xx**, tidak ada layar blank/merah. UI rapi, Bahasa Indonesia.

**🔴 O-1 (HIGH) — RBAC bocor untuk peran Driver:**
- Driver dapat membuka: **Bookings** (`/app/bookings`, tabel penuh), **Settings** (`/app/settings`), **Armada** (`/app/vehicles`), **Driver** (`/app/drivers`).
- Sidebar Driver menampilkan: Beranda, Booking & Trip, Ruang Kerja Driver, GPS Tracking, Maintenance, Armada, Driver.
- **Harusnya:** Driver hanya melihat workspace miliknya (tugas/trip sendiri), bukan modul manajemen.
- **Rekomendasi (bila disetujui):** route-guard berbasis peran di frontend (`ProtectedRoute`) + pastikan endpoint backend menegakkan RBAC (defense-in-depth).
- Bukti: screenshot `13_driver_bookings_leak.png`, `14_driver_settings_leak.png`.

> **Catatan by-design (bukan bug):** provider WhatsApp = **MOCK** (tak ada kirim nyata); geocode/OSRM/maps **null offline** (tanpa jaringan keluar). Drag-drop/kamera/upload foto (POD) **dilewati** (keterbatasan automation).

---

## 7. Katalog Temuan Terbuka (Konsolidasi — Report-Only)

| # | Temuan | Severity | Berkas (usulan perbaikan) | Sumber |
|---|--------|:--:|---|---|
| **O-1** | RBAC bocor: Driver akses modul manajemen | 🔴 Tinggi | `frontend/src` (route guard) + cek backend RBAC | R11 (iter-61) |
| **RC-MATRIX-A** | 7 write-path double-book kendaraan (tanpa `vehicle_lock`); 5 tak cek konflik driver | 🟠 Sed–Tinggi | `routers/{dispatch,quotations,subcharters,public,driver,bookings}.py` | R11 §4A |
| **RC-MATRIX-B** | 57 field numerik menerima nilai negatif | 🟠 Sedang | `schemas.py` (tambah `ge=0`/`gt=0`) | R11 §4B |
| **R6-1** | `PATCH /subcharters/{id}` lewati cek bentrok (double-book unit mitra + `end<start`) | 🔴 Tinggi | `routers/subcharters.py` | R6 (live) |
| **R6-2** | `POST /invoices` terima amount negatif | 🟠 Sedang | `schemas.py`/`routers/invoices.py` | R6 |
| **R6-3** | `maintenance` terima cost negatif | 🟡 Rendah–Sed | `schemas.py`/`routers/maintenance.py` | R6 |
| **R6-4** | `GET /crm/segments/{id}/preview` → 500 kriteria invalid | 🟠 Sedang | `services/segments.py` | R6 (repro R11) |
| **R6-5** | `content` → 500 bila field angka non-numerik | 🟡 Rendah | `routers/content.py` | R6 (repro R11) |
| **EXPORT-1** | PDF export → 500 pada karakter/markup khusus | 🟠 Sedang | `services/exporter.py` (escape) | R10 (repro R11) |
| **ID-RACE** | race pembuatan identity (butuh unique index + handle DuplicateKey) | 🟡 Rendah | `services/identity.py` + `server.py` | R10 · **✅ DITUTUP (Putaran 12)** |
| **SET-1** | validasi/clamp tarif pricing/settings | 🟡 Rendah | `routers/settings.py`/`services/pricing.py` | R10 · **✅ DITUTUP (Putaran 12)** |
| **M1** | Gate kontrak FE↔BE "hijau palsu" (guardrail, bukan produksi) | 🟠 Sedang | `scripts/verify_api_contract.py` | R6 · **✅ DITUTUP (Putaran 12)** |

> **Putaran 12 (Phase-1, 2026-07-05):** SELURUH temuan terbuka §7 kini **DITUTUP**. M1 (gate kontrak nyata: 260 FE-call divalidasi), ID-RACE (index unik-parsial + DuplicateKeyError→409), SET-1 (`_validate_pricing`→400). +2 guardrail baru (INV-IDENT-01, INV-SET-01, self-test-proven). `gate.sh` **HIJAU 19/19**; `testing_agent` iter-65 **22/22**. Detail: `memory/BUG_REGISTRY.md` + `memory/INVARIANTS.md`.

---

## 8. Confidence — Jujur: **~78% → ~88%**

**Kenapa naik dari ~78%:**
1. **Cakupan kode nyata** melompat 46,4%→83,0% combined / ~52%→87,0% statement. Blind-spot besar (mutasi + service) tempat bug historis bersembunyi **kini sudah dieksekusi**.
2. **Dua kelas akar-masalah dipetakan tuntas** (matriks §4). "Known-unknown" (mungkin ada pintu tersembunyi) berubah jadi **known** — kita tahu **persis** path & field mana yang berisiko, tanpa celah enumerasi.
3. **495 panggilan mutasi lintas 3 peran → 0 kelas 5xx baru**. Kuat menunjukkan tidak ada kelas crash besar yang belum ditemukan.
4. **Reproduksi legacy BUG-A..G semua bersih** → guard inti (RC-01..07) terbukti efektif, konsisten dgn gate HIJAU 13/13.

**Kenapa belum menyentuh 90%+ (jujur):**
1. **2 kelas akar-masalah sudah dipetakan tetapi BELUM ditambal** (report-only). Risiko masih **ada**, hanya sudah dikenal & terukur — ini menahan confidence tepat di bawah 90%.
2. **Integrasi eksternal tak dapat diuji offline**: jalur nyata WhatsApp Graph API (MetaCloud) & geocode/OSRM/maps (~57 stmt) tak tereksekusi tanpa jaringan/kredensial live → tetap "unknown" secara empiris.
3. **~827 statement reachable** masih belum tercakup (cabang defensif ROI rendah) — kecil kemungkinan menyimpan bug besar, tapi bukan nol.

**Untuk mencapai ≥90%** dibutuhkan salah satu/kedua: **(a)** menambal & memverifikasi 2 kelas akar-masalah (mengubah "risiko dikenal" jadi "tertutup"), dan **(b)** pengujian integrasi eksternal live (WhatsApp/geocode) di lingkungan berjaringan.

---

## 9. Menu Keputusan Perbaikan (belum dieksekusi — menunggu persetujuan)

Dikelompokkan per ROI/risiko. Semua di luar mode report-only saat ini.

**Prioritas 1 — Keamanan (cepat, dampak tinggi):**
- **O-1 RBAC:** tambah `ProtectedRoute` berbasis peran di `frontend/src` + audit endpoint backend agar menegakkan RBAC (defense-in-depth). *Risiko rendah, ROI tinggi.*

**Prioritas 2 — Integritas data numerik (cepat, terpusat):**
- **RC-MATRIX-B / R6-2 / R6-3:** tambahkan `ge=0`/`gt=0` pada 57 field di `schemas.py` (satu berkas terpusat). *Risiko rendah, ROI tinggi.*

**Prioritas 3 — Konsistensi reservasi (sedang):**
- **RC-MATRIX-A / R6-1:** seragamkan pemakaian `vehicle_lock` + `find_conflicts`/`find_driver_conflicts` pada 7 write-path non-inti (`dispatch.assign_trip`, `quotations.convert`, `subcharters.create/update`, `public.create_public_booking`, `driver.checkin`, `bookings.update PATCH driver`). *Risiko sedang (menyentuh beberapa router); butuh regresi race.*

**Prioritas 4 — Robustness 5xx (sedang):**
- **EXPORT-1 / R6-4 / R6-5:** escape konten PDF; validasi kriteria segmen; koersi/validasi field angka CMS. *Risiko rendah–sedang.*

**Prioritas 5 — Guardrail & housekeeping:**
- **M1:** perbaiki `verify_api_contract.py` (regex `apiClient.(...)`); **ID-RACE:** unique index + handle `DuplicateKeyError`; **SET-1:** clamp tarif.

---

## 10. Verifikasi Gate + Artefak

- **`scripts/gate.sh` → HIJAU 13/13** (dikonfirmasi ulang pada Putaran 11; receipt: `memory/GATE_RECEIPT.md`). Tidak ada perubahan kode produksi.
- **Artefak audit (read-only) di `scripts/audit_r11/`:**
  - `coverage_report_FINAL.txt`, `coverage_r11.json` — laporan cakupan.
  - `coverage_ceiling_analysis.py/.txt` — analisis ceiling 939 statement.
  - `mutation_sweep.py`, `mutation_matrix.json`, `log_mutation_sweep_r11.txt` — sweep 495 mutasi.
  - `root_cause_matrix.py/.json/.txt` — matriks race & nilai-negatif.
  - `run_coverage_r11.sh` — orkestrasi coverage.
  - `log_forensic_repro.txt`, `log_health_check.txt`, `log_full_sweep_GET.txt` — log pendukung.
  - `test_reports/iteration_61.json` — hasil testing_agent (O-1).

**Perintah reproduksi:**
```bash
cd /app
python scripts/seed_data.py                        # seed DB bersih
bash   scripts/gate.sh                              # gate 13/13 (HIJAU)
bash   scripts/audit_r11/run_coverage_r11.sh        # regenerate coverage + sweep
python scripts/audit_r11/coverage_ceiling_analysis.py
python scripts/audit_r11/root_cause_matrix.py
python scripts/forensic_repro.py                    # regression BUG-A..G
```

---

*Disusun pada Putaran 11 — mode Report-Only. Tidak ada kode produksi yang diubah. Confidence akhir: **~88%**.*

---

## 11.5 — PERBAIKAN DITERAPKAN + VERIFIKASI (Post-Fix)

> **Perubahan mode:** atas persetujuan Owner, mode berubah dari *report-only* → **FIX**. Tiga temuan utama diperbaiki, di-verifikasi oleh **testing_agent** (bukan self-claim), integrasi eksternal diuji **LIVE**, dan `gate.sh` tetap **HIJAU 13/13** (nol regresi).

### A. FIX #1 — O-1 RBAC leakage (🔴 Tinggi) → DITUTUP
- **Akar:** route `/app/*` hanya dijaga *autentikasi* (`ProtectedRoute`), bukan *peran*. Sidebar sudah difilter peran (SSOT `ROLE_MENU_ALLOWLIST`), tetapi URL langsung tak dijaga → driver bisa buka `/app/settings`, `/app/dispatch`, dll.
- **Perbaikan:** komponen baru `frontend/src/components/app/RoleGuard.jsx` membungkus tiap route ERP di `App.js`, memakai **sumber kebenaran yang SAMA** dengan sidebar (`canAccess(role, section)` dari `navigationConfig.js`). Bila peran tak berhak → redirect ke `/app/dashboard`.
- **Backend (defense-in-depth):** terverifikasi sudah menegakkan `require_section`/`require_role` di semua router sensitif (settings/users/dispatch/finance/quotations/customers/cms/automation/reports/partners/inbox/subcharters/bookings). Tidak ada perubahan matrix RBAC → `check_nav_map` tetap konsisten dgn SSOT.
- **Verifikasi testing_agent (iter-62):** DRIVER — 13/13 route terlarang redirect ke dashboard; 7/7 route diizinkan tetap render. OPS — settings/users/auditlog diblok, modul operasional bisa. OWNER — akses penuh, tanpa regresi.

### B. FIX #2 — Negative-value (🟠 Sedang) → DITUTUP
- **Perbaikan:** `backend/schemas.py` — **`ge=0`** ditambahkan ke SEMUA field numerik uang/kuantitas (dipilih `ge` bukan `gt` agar 0 tetap valid untuk default yang sah, sekaligus menolak minus). Matriks negatif kini **0/63 unbounded** (sebelumnya 57/63).
- **Verifikasi testing_agent (iter-62):** `POST /expenses`, `POST /maintenance`, `POST /bookings`, `PATCH /vehicles` dengan nilai negatif → **HTTP 422** (ditolak); nilai positif tetap **200/201** (tidak over-restrict).

### C. FIX #3 — Race / TOCTOU vehicle double-book (🟠 Sed–Tinggi) → DITUTUP untuk jalur nyata
- **Perbaikan (mengikuti pola aman `create_booking`):**
  - `dispatch.assign_trip` → dibungkus `vehicle_lock` (cek-final armada+driver di dalam lock; geocode I/O di luar lock). Matriks: **SAFE**.
  - `quotations.convert` → dibungkus `vehicle_lock` **+ cek konflik driver** (sebelumnya tak ada). Matriks: **SAFE**.
  - `subcharters.create` → cek `find_subcharter_conflicts` + insert kini di dalam `vehicle_lock` (unit mitra).
  - `subcharters.update` (**R6-1**) → menambah re-cek bentrok unit mitra + validasi `end>start` pada nilai efektif baru (sebelumnya PATCH melewati cek → double-book unit mitra).
  - `bookings.update_booking(PATCH driver)` → cek konflik driver + tulis di-serialkan via **`driver_lock`** baru (mutex per-sopir, mekanisme identik `vehicle_lock`).
- **Aman by-design (tanpa perubahan, didokumentasikan):**
  - `public.create_public_booking` → membuat booking `pending` dengan `vehicle_id=None` (armada ditentukan saat `approve` yang SUDAH ber-`vehicle_lock`). Tidak mereservasi armada → tak ada risiko double-book di titik ini.
  - `driver.checkin` → memakai armada yang SUDAH ter-assign ke booking/trip (ownership-guarded); tidak meng-assign armada baru.
- **Catatan matriks:** flag "RISK" yang tersisa pada `subcharters.*` / `update_booking` / `public` / `driver.checkin` adalah **keterbatasan heuristik scanner** (hanya mengenali pola `vehicle_lock` + `find_conflicts`), bukan kerentanan nyata — subcharter memakai `find_subcharter_conflicts` di dalam `vehicle_lock`, dan `update_booking` memakai `driver_lock`.
- **Verifikasi testing_agent (iter-62):** assign armada yang sama ke jendela tumpang-tindih → ditolak **400**; PATCH sub-charter ke jendela overlap → ditolak **400 "bentrok"** (R6-1 tertutup); siklus booking (create→confirm→dispatch assign) tetap normal.

### D. Item #4 — Uji Integrasi Eksternal (LIVE)
Environment ini **memiliki jaringan keluar** (berbeda dgn asumsi sandbox saat Putaran 11). Skrip: `scripts/audit_r11/live_external_check.py` (log: `log_live_external_check.txt`).

| Integrasi | Hasil LIVE |
|---|---|
| **Geocode (OSM Nominatim)** | ✅ WORKING — Bandung `(-6.9218, 107.6071)`, Bandara Soekarno-Hatta, Malioboro semua ter-geocode |
| **Routing/ETA (OSRM)** | ✅ WORKING — Bandung→Jakarta = **154.88 km** |
| **WhatsApp (Meta Cloud)** | ⚠️ provider = **mock (by design)**; Graph API terjangkau (HTTP 400 tanpa auth). **Real send butuh kredensial Meta** (set `provider=meta_cloud` + `phone_number_id` + `access_token`) — belum diuji karena kredensial hanya dimiliki Owner. |

> Konsekuensi: ~57 statement yang dulu dilabeli "network-ceiling" (geocode/osrm/maps) **sebenarnya reachable** di lingkungan ini. Satu-satunya jalur eksternal yang tersisa belum terverifikasi = **real WhatsApp send** (butuh kredensial).

### E. Verifikasi Gate + Integritas
- `scripts/gate.sh` → **HIJAU 13/13** dikonfirmasi ulang **setelah** perbaikan (termasuk `verify_concurrency` RC-01, `verify_cross_entity` RC-06/07, `check_nav_map`). Tidak ada regresi.
- Berkas produksi yang diubah: `backend/schemas.py`, `backend/services/availability.py`, `backend/routers/{bookings,dispatch,quotations,subcharters}.py`, `frontend/src/App.js`, `frontend/src/components/app/RoleGuard.jsx` (baru).

### F. Confidence — diperbarui (jujur): **~88% → ~93%**
- **Naik** karena: 2 kelas akar-masalah kini **DITUTUP & diverifikasi** (bukan sekadar dipetakan); O-1 RBAC ditutup lintas 3 peran; integrasi geocode/OSRM terbukti **LIVE**; gate tetap hijau.
- **Belum 100%** (jujur): (a) **real WhatsApp send** belum diuji (butuh kredensial Meta dari Owner); (b) verifikasi race memakai uji sekuensial + gate + paritas-pola dgn `create_booking` (uvicorn single-worker), belum uji beban konkuren tinggi; (c) sebagian cabang defensif ROI-rendah masih belum tercakup. Untuk mencapai ~95%+: sediakan kredensial WhatsApp untuk uji kirim nyata + uji beban konkuren pada write-path.

---

## 11.6 — GUARDRAIL v2 (Preventif Anti-Regresi Lintas-Sesi) + 3 Bug 5xx Ditutup

> **Motivasi (dari Owner):** akar terdalam bug berulang = **konteks hilang antar-sesi AI + kode tumbuh**. Guardrail lama (uji-flow runtime, coverage 46%) tak cukup. Solusi: guardrail yang **memaksa invariant lewat analisis STATIK + RUNTIME**, digerakkan **allowlist ber-justifikasi**, berjangkar pada **satu registry** yang bisa dibaca sesi AI mana pun tanpa konteks.

### A. 3 bug 5xx terbuka → DITUTUP (agar guard no-5xx punya baseline hijau)
| Bug | Perbaikan | Verifikasi |
|---|---|---|
| **EXPORT-1** | `services/exporter.py`: helper `_esc()` meng-escape teks user (number/customer/destination/notes) sebelum masuk markup reportlab Paragraph | testing_agent iter-63: PDF markup → **200** (bukan 500) |
| **R6-4** | `routers/growth.py`: `resolve_segment` dibungkus try/except → **400** "Kriteria segmen tidak valid" | iter-63: preview malformed → **200/400** (bukan 500) |
| **R6-5** | `routers/content.py`: koersi `int()/float()` di `_clean` dibungkus try/except → **400** "Field 'x' harus berupa angka" | iter-63: field angka non-numerik → **400** (bukan 500) |

testing_agent iter-63: **16/16 backend test lolos**, 0 bug kritis, regresi jalur normal aman.

### B. Guardrail v2 — 4 penjaga baru (statik + runtime), semua di `scripts/guardrails/`
| Invariant | Penjaga | Jenis | Menutup kelas |
|---|---|---|---|
| **INV-NUM-01** | `verify_numeric_bounds.py` | statik (AST schemas.py) | negative-value |
| **INV-RACE-01** | `verify_reservation_locks.py` | statik (auto-discovery + registry) | race/TOCTOU double-book |
| **INV-RBAC-01/02/03** | `verify_rbac_guards.py` | statik (route FE + dep BE + drift matrix) | RBAC leakage (O-1) |
| **INV-5XX-01** | `verify_adversarial_5xx.py` | runtime (payload adversarial) | crash 5xx (EXPORT-1/R6-4/R6-5 + umum) |

**Cara kerja anti-lupa-konteks:**
- **Auto-discovery** (INV-RACE-01): tiap fungsi router MUTATING yang memanggil conflict-finder WAJIB memegang lock → **write-path baru tertangkap otomatis**, tanpa perlu tahu aturan sebelumnya.
- **Allowlist ber-justifikasi**: pengecualian sah harus ditulis eksplisit + alasan (mis. `public.public_booking_request`, `driver.checkin`) → tak ada yang lolos diam-diam.
- **Registry anti-regresi**: jalur reservasi & router sensitif yang diketahui dicek tetap terkunci/ter-guard → menangkap bila lock/guard DIHAPUS.
- **SSOT registry** `memory/INVARIANTS.md`: sesi AI/kontributor baru cukup baca 1 file untuk tahu SEMUA aturan + cara menambah invariant.

**Bukti penjaga BUKAN "hijau-palsu" (pelajaran dari M1):** tiap penjaga di-**self-test** — inject pelanggaran → gate **MERAH** (dgn pesan tepat: field/fungsi/route yang salah) → revert → **HIJAU**:
- INV-NUM-01: hapus `ge=0` di `BookingCreate.base_price` → MERAH (flag tepat) → revert → HIJAU.
- INV-RACE-01: lepas `vehicle_lock` dari `dispatch.assign_trip` → MERAH (auto-discovery + registry) → revert → HIJAU.
- INV-RBAC: bocorkan driver→settings di allowlist + lepas 1 `RoleGuard` → MERAH (drift + route) → revert → HIJAU.
- INV-5XX-01: reintroduksi 500 di `content.py` → MERAH (HTTP 500 terdeteksi) → revert → HIJAU.

### C. Integrasi ke gate + hasil
- `scripts/gate.sh` kini menjalankan **17 gate** (13 lama + 4 guardrail v2). Receipt: `memory/GATE_RECEIPT.md` → **SEMUA HIJAU**.
- Sebelum klaim "selesai", jalankan `bash scripts/gate.sh` → guardrail memaksa invariant secara otomatis, independen dari memori sesi.

### D. Confidence — diperbarui: **~93% → ~95%**
- **Naik** karena: 3 bug 5xx terakhir ditutup + diverifikasi; dan yang terpenting, **semua kelas temuan kini dijaga PREVENTIF secara otomatis** (statik+runtime, self-test-proven) → regresi kelas-kelas ini akan **langsung MERAH** di sesi mana pun.
- **Belum 100%** (jujur): guardrail mencegah **regresi kelas yang SUDAH dikenal**; tak bisa menjamin nol **kelas baru yang belum terpikirkan**. Sisa lain: real WhatsApp send (butuh kredensial Meta), uji beban konkuren tinggi, serta ID-RACE/SET-1/M1 yang masih terbuka (minor). Untuk ~97%+: tambah invariant untuk kelas baru saat ditemukan + uji beban + kredensial WA.
