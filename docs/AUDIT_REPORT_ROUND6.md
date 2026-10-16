# 🔎 Laporan Audit Kode — Rahaza Travel ERP — **PUTARAN 6 (Coverage-Driven)**

> **Kelanjutan** dari `docs/AUDIT_REPORT.md` (Putaran 1–5, B1–B9 sudah diperbaiki).
> **Pemicu:** keraguan bahwa pengujian sebelumnya hanya menutup **sebagian flow**, bukan **seluruh kode**.
> **Pendekatan baru (ke-6):** *white-box coverage-driven* — ukur cakupan kode NYATA, temukan
> baris/cabang yang **tak pernah dieksekusi**, lalu audit celah itu backend **dan** frontend **dan** flow integrasi.
>
> **Status semua temuan di dokumen ini: ⏳ BELUM DIPERBAIKI — MENUNGGU KEPUTUSAN PER-BUG DARI OWNER.**
> (Sesuai permintaan: ronde ini *lapor dulu*, tidak mengubah kode produksi tanpa persetujuan.)
> `gate.sh` tetap **HIJAU 13/13** — tidak ada perubahan kode produksi yang dilakukan.

---

## 0. Ringkasan Eksekutif

Menjawab langsung keraguan Anda dengan **bukti angka**:

| Metrik cakupan (diukur `coverage.py` atas suite guardrail runtime) | Hasil |
|---|---:|
| **Cakupan baris backend oleh seluruh guardrail (`gate.sh`) + sweep GET multi-peran** | **46,4%** (3.446 dari 7.196 statement TIDAK tereksekusi) |
| Endpoint GET (`/api`) diuji lintas 4 konteks (owner/ops/driver/unauth) | 130 rute × 4 = 520 hit → **0 error 5xx** |
| Endpoint MUTASI (POST/PUT/PATCH/DELETE) yang **nyaris tak tersentuh** guardrail | ±138 rute |
| Kontrak FE↔BE (`apiClient`) — path FE cocok ke rute BE | 212 unik → **0 drift nyata** |
| Modul ERP frontend yang berhasil dirender (testing_agent) | **20/20 (100%)** |

**Kesimpulan cakupan:** Keraguan Anda **benar & terbukti**. Guardrail permanen hanya mengeksekusi
**~46% kode backend**; sisi **mutasi + service** (tempat B1–B9 dulu bersembunyi) sebagian besar
**tidak pernah diuji**. Selain itu ditemukan **1 guardrail yang “hijau palsu”** (gate kontrak FE↔BE tidak
mendeteksi satupun call FE → efektif tidak memeriksa apa-apa).

### Temuan Putaran 6

| # | Temuan | Severity | Berkas | Bukti | Status |
|---|--------|:--------:|--------|:-----:|:------:|
| **R6-1** | `PATCH /subcharters/{id}` **lewati cek bentrok** → double-booking unit MITRA (+ terima `end < start`) | 🔴 Tinggi | `routers/subcharters.py` | Reprodusi live | ⏳ Belum |
| **R6-2** | `POST /invoices` terima **amount NEGATIF** → faktur bernilai minus | 🟠 Sedang | `schemas.py` / `routers/invoices.py` | −5.000.000 tersimpan | ⏳ Belum |
| **R6-3** | `POST`/`PATCH /maintenance` terima **cost NEGATIF** | 🟡 Rendah–Sedang | `schemas.py` / `routers/maintenance.py` | −3.000.000 tersimpan | ⏳ Belum |
| **R6-4** | `GET /crm/segments/{id}/preview` **HTTP 500** untuk kriteria tak valid | 🟠 Sedang | `services/segments.py` | 2 varian → 500 | ⏳ Belum |
| **R6-5** | `POST`/`PUT /content/{resource}` **HTTP 500** bila field angka diisi non-numerik | 🟡 Rendah | `routers/content.py` | 2 varian → 500 | ⏳ Belum |
| **M1** | Gate kontrak FE↔BE **hijau palsu** — regex hanya cocok `axios.(...)`, padahal FE pakai `apiClient.(...)` → deteksi **0 call** | 🟠 Sedang (guardrail) | `scripts/verify_api_contract.py` | 0 call terdeteksi | ⏳ Belum |

Selain itu: **1 alarm palsu** (session “expired 2–3 menit” dari testing_agent = artefak Playwright,
**bukan** bug — lihat §4) dan beberapa **observasi minor** (§3).

---

## 1. Metodologi Putaran 6 (menjamin "seluruh kode")

| Fase | Pendekatan | Alat | Yang dibuktikan |
|:---:|---|---|---|
| 6A | **White-box coverage** | `coverage.py` membungkus uvicorn; jalankan semua gate runtime + sweep GET multi-peran | Baris/cabang mana yang TAK PERNAH dieksekusi (peta buta) |
| 6B | **Matriks endpoint × peran** | Enumerasi 268 rute dari `app.routes`; hit tiap GET sbg owner/ops/driver/unauth | 5xx tersembunyi, kebocoran unauth, RBAC nyata |
| 6C | **Adversarial pada celah** | Audit kode + reprodusi API di endpoint MUTASI ber-cakupan rendah | Bug bisnis/robustness di kode tak teruji |
| 6D | **Frontend + flow** | scanner `apiClient` (koreksi M1) + `testing_agent` (20 modul, 3 peran) | Drift FE↔BE, kesehatan flow UI, keterjangkauan bug via UI |

Semua reproduksi menggunakan DB seed bersih (`owner@demo.local`, `demo12345`), backend `localhost:8001`.

---

## 2. Detail Temuan

### 🔴 R6-1 — `PATCH /subcharters/{id}` melewati validasi bentrok (double-booking unit mitra)

**Berkas:** `backend/routers/subcharters.py` → `update_subcharter` (baris 128–152).

**Deskripsi.** Saat **membuat** sub-charter (`create_subcharter`), sistem memanggil
`find_subcharter_conflicts` dan menolak bila unit mitra bentrok (400). Namun endpoint **PATCH**
memperbolehkan mengubah `start_datetime`, `end_datetime`, dan `vehicle_id` **tanpa** memanggil ulang
`find_subcharter_conflicts`. Ini **persis pola B1** (yang dulu ditemukan di `PATCH /bookings`), tetapi
di modul sub-charter yang cakupannya hanya **20,4%** — tak pernah diuji guardrail.

**Dampak.** Satu unit MITRA bisa **di-booking ganda** pada jendela waktu yang sama dengan mengedit
order `requested` yang sudah ada → melanggar anti-double-booking unit partner (INV-4 untuk unit mitra) →
konflik operasional + potensi utang (AP) ganda ke mitra.

**Bukti reproduksi (live).**
```
create SC1 (win: H+10..H+11)                 -> 200
create SC2 (win: H+20..H+21)                 -> 200
create SC overlapping win1 (via CREATE)      -> 400   (benar: create menolak)
PATCH SC2 -> ubah ke win1 (overlap SC1)      -> 200   ← BUG: PATCH menerima overlap
PATCH SC2 -> start=H+11, end=H+10 (end<start)-> 200   ← BUG: terima jendela tak valid
```

**Akar masalah.** `update_subcharter` menerapkan `$set` tanpa (a) `find_subcharter_conflicts` dan
(b) validasi `end > start` yang ada di path create.

**Usulan perbaikan (bila disetujui).** Setelah menghitung nilai baru start/end/vehicle_id, jalankan
kembali `find_subcharter_conflicts(db, vehicle_id, start, end, exclude_id=subcharter_id)` dan validasi
`end > start` — sama seperti path create (dan sebagaimana B1 diperbaiki untuk bookings).

---

### 🟠 R6-2 — `POST /invoices` menerima `amount` NEGATIF

**Berkas:** `backend/schemas.py` (`InvoiceCreate.amount: Optional[float] = None` — **tanpa batas**) → `routers/invoices.py` (`money(amount)` tidak meng-clamp).

**Deskripsi.** `InvoiceCreate.amount` tak punya `gt=0`/`ge=0`; `money()` (core_utils) hanya membulatkan ke
integer tanpa clamp negatif. Faktur dengan nilai **minus** tersimpan.

**Bukti.** `POST /api/invoices {amount: -5000000}` → **200**, `amount = -5.000.000` tersimpan.

**Dampak.** Faktur (dokumen finansial resmi) bernilai negatif — nonsens akuntansi; bisa membingungkan
export PDF/Excel. *Catatan:* invoice **tidak** dipakai untuk AR/P&L (AR dari `bookings`, P&L dari
`payments`/`expenses`), sehingga dampak ke laporan keuangan agregat **terbatas** → severity **Sedang**.

**Usulan perbaikan.** Beri batas di skema (`amount: Optional[float] = Field(default=None, gt=0)`) — sejalan dengan pola B6.

---

### 🟡 R6-3 — `POST`/`PATCH /maintenance` menerima `cost` NEGATIF

**Berkas:** `backend/schemas.py` (`MaintenanceCreate.cost: Optional[float] = 0` — tanpa batas) → `routers/maintenance.py`.

**Bukti.** `POST /api/maintenance {cost: -3000000}` → **200**, `cost = -3.000.000` tersimpan.

**Dampak.** *Terbatas*: biaya perawatan disimpan di koleksi `maintenance_records` dan **tidak** ikut
dijumlahkan pada P&L (`profit_loss` hanya menjumlah koleksi `expenses`). Jadi ini kotoran data pada
catatan perawatan (dan `odometer` negatif juga bisa), bukan pencemaran P&L. Severity **Rendah–Sedang**.

**Usulan perbaikan.** Tambah `ge=0` untuk `cost` & `odometer` di skema Maintenance (create/update/complete).

---

### 🟠 R6-4 — `GET /crm/segments/{id}/preview` → **HTTP 500** untuk kriteria tak valid

**Berkas:** `backend/services/segments.py` → `build_query` (baris 38–48).

**Deskripsi.** `SegmentCreate.criteria` adalah `dict` bebas (tak divalidasi). `build_query` memanggil
`float(c["min_value"])` dan `int(c["last_activity_days"])` **tanpa try/except**. Segmen yang dibuat
dengan kriteria non-numerik menyebabkan **ValueError → 500** saat di-*preview*/resolve — dan
`audit_endpoint_sweep` tak pernah menangkapnya karena hanya menguji segmen seed dengan kriteria valid.

**Bukti.**
```
create segment {criteria:{min_value:"abc"}}         -> 200
GET  /crm/segments/{id}/preview                      -> 500  ← BUG
create segment {criteria:{last_activity_days:"xyz"}} -> 200
GET  /crm/segments/{id}/preview                      -> 500  ← BUG
```

**Dampak.** Kegagalan 5xx (robustness) di modul CRM Segments (cakupan `services/segments.py` = **7,8%**).
Terkait: `q`/`city` dimasukkan mentah ke `$regex` (potensi ReDoS/regex-injection oleh peran ber-akses CRM).

**Usulan perbaikan.** Koersi angka defensif (`_num`) di `build_query`, atau validasi tipe `criteria` saat
`create_segment`/`update_segment`; escape regex untuk `q`/`city`.

---

### 🟡 R6-5 — `POST`/`PUT /content/{resource}` → **HTTP 500** untuk field angka non-numerik

**Berkas:** `backend/routers/content.py` → `_clean` (baris 77–90): `v = int(v or 0)` / `float(v or 0)`.

**Deskripsi.** Bila field bertipe int/num (mis. `position`, `price_from`, `days`) diisi string non-numerik
(mis. `"abc"`), `int("abc")` melempar ValueError → **500**.

**Bukti.**
```
POST /content/destinations {position:"abc"}        -> 500  ← BUG
POST /content/packages     {price_from:"NaNstr"}   -> 500  ← BUG
```

**Dampak.** *Terbatas*: via **form UI standar** (ContentFormDialog) hampir tidak terpicu karena ada
fallback `|| 0` + input `type="number"` (dikonfirmasi testing_agent). Terjangkau terutama via API
langsung/integrasi. Severity **Rendah**.

**Usulan perbaikan.** Koersi defensif di `_clean` (mis. `int(v)` dibungkus try/except → 422 yang rapi).

---

### 🟠 M1 — Gate kontrak FE↔BE **hijau palsu** (guardrail tidak memeriksa apa-apa)

**Berkas:** `scripts/verify_api_contract.py` → `FE_CALL_RE` & `BINDINGS`.

**Deskripsi.** CHECK B memakai regex `axios\.(get|post|...)\(` untuk menemukan call FE. Namun seluruh
frontend memanggil API via instance bernama **`apiClient.get(...)`**, bukan `axios.get(...)`. Akibatnya
gate mendeteksi **0 call** lalu mencetak *“Tidak ada FE call terdeteksi (frontend belum dibangun?)”* dan
tetap **lulus (OK)**. CHECK C juga mati karena `BINDINGS = []`. Jadi gate yang seharusnya menangkap
**drift FE↔BE / silent-404 / label kosong** sebenarnya **tidak menguji apa-apa** — inti dari keraguan Anda.

**Bukti.** Scanner terkoreksi (mendeteksi `apiClient.<m>(...)`) menemukan **260 call (212 unik)**;
gate bawaan menemukan **0**.

**Dampak.** Hari ini FE↔BE kebetulan **selaras** (scanner terkoreksi: **0 drift nyata** setelah menyaring
false-positive query-string/segmen dinamis). Tetapi **regresi drift di masa depan tidak akan tertangkap**.

**Usulan perbaikan.** Perbaiki `FE_CALL_RE` agar mencakup `apiClient\.(get|post|put|patch|delete)\(` (dan
string biasa, bukan hanya template literal); isi `BINDINGS` untuk endpoint kritikal.

---

## 3. Observasi Minor (belum tentu bug — perlu keputusan)

| # | Observasi | Berkas | Catatan |
|---|-----------|--------|---------|
| O-1 | Driver dapat `GET /api/bookings` (semua booking + PII + finansial), bukan hanya miliknya | `permissions_config.py` (`bookings` mengizinkan driver) | Sesuai matriks SSOT, tapi lebih longgar dari `/api/driver/my-trips` yang ter-scope. Pertimbangkan pembatasan data. |
| O-2 | `POST /driver/checkin` tak cek status booking → bisa membuat trip & set kendaraan `on_trip` untuk booking `pending`/`hold`/`cancelled` (butuh driver ter-assign) | `routers/driver.py` | Gap state-machine (sekeluarga dgn "complete pending/hold/draft"). |
| O-3 | Pembuatan window `maintenance` tak cek booking terjadwal yang overlap (asimetris dgn INV-21 dari sisi booking) | `routers/maintenance.py` | Booking menolak jadwal saat maintenance, tapi maintenance tak menolak saat sudah ada booking. |
| O-4 | Regex mentah (`$regex`) dari input di segments/content (`q`, `city`) | `services/segments.py`, `routers/content.py` | Potensi ReDoS oleh peran terautentikasi; escape saat build query. |

---

## 4. Alarm Palsu yang Diklarifikasi (BUKAN bug)

- **“Session expired 2–3 menit”** (dilaporkan testing_agent, severity CRITICAL): **artefak pengujian**, bukan bug.
  Bukti: token disimpan di `localStorage["tf_token"]` dan dipulihkan saat load (`AuthContext.js`); sesi
  server **7 hari** (`auth.py _SESSION_DAYS=7`); **tidak ada** timer idle/auto-logout maupun interceptor 401
  di frontend. Kemungkinan besar konteks Playwright tidak mempertahankan `localStorage` antar-navigasi.

---

## 5. Area yang Diuji & TERBUKTI BERSIH (Putaran 6)

- **RBAC manajemen user** (`routers/users.py`): guard "min 1 owner aktif", larang ubah-peran/nonaktif diri
  sendiri, validasi peran — **kokoh** (cakupan rendah 23% = *belum diuji*, **bukan** buggy).
- **Expenses**: `ExpenseCreate.amount = Field(gt=0)` → nilai negatif **ditolak 422** (aman, tak seperti invoice/maintenance).
- **Pricing engine** (`services/pricing.py`): `days`/`distance` di-clamp (`max(...,1)`/`max(...,0)`) → tak bisa negatif.
- **Upload CMS & POD**: whitelist content-type, batas 6MB, nama file di-random (anti path-traversal) — **aman**.
- **Driver mutations**: cek kepemilikan objek (`_owned_trip`, `driver_id == my_id`) konsisten — **aman**.
- **Sweep GET (130 rute × 4 konteks):** **0 error 5xx**; unauth-200 hanya `/api/public/*` (memang publik); RBAC cocok dgn matriks SSOT (mis. `customers` menolak driver 403).
- **FE↔BE:** 212 path `apiClient` unik → **0 drift nyata**; **20/20 modul ERP** dirender (testing_agent).

---

## 6. Peta Buta Cakupan (blind spots) — kandidat audit lanjutan

Berkas ber-cakupan terendah (kandidat bug tersembunyi berikutnya), diukur `coverage.py`:

| Berkas | Cakupan |
|--------|:------:|
| `services/segments.py` | 7,8% |
| `services/geofence.py` | 12,5% |
| `services/payroll_export.py` | 12,8% |
| `services/attribution.py` | 14,5% |
| `services/ads.py` | 15,3% |
| `routers/content.py` | 16,2% |
| `services/sequences.py` | 17,0% |
| `routers/subcharters.py` | 20,4% |
| `services/osrm.py` | 20,6% |
| `routers/users.py` | 23,2% |
| `services/campaigns.py` | 23,3% |
| `routers/quotations.py` | 24,0% |
| `routers/maintenance.py` | 26,5% |
| `services/pricing.py` | 28,3% |
| **TOTAL backend** | **46,4%** |

> Artefak audit lengkap tersimpan di `scripts/audit_r6/` (harness coverage, sweep matrix, reproduksi).
> Semua bersifat READ-ONLY; **tidak ada** perubahan kode produksi.

---

## 7. Keputusan yang Diminta (report-only)

Silakan pilih bug mana yang saya perbaiki (semua akan diverifikasi ulang + `gate.sh` + testing_agent):
1. **R6-1** (subcharter double-book) — direkomendasikan (Tinggi, pola sama B1).
2. **R6-4 & R6-5** (500 robustness segments/content) — direkomendasikan (mudah, hilangkan 5xx).
3. **R6-2 & R6-3** (batas negatif invoice/maintenance) — direkomendasikan (pola sama B6).
4. **M1** (perbaiki gate kontrak FE↔BE agar tidak hijau palsu) — direkomendasikan (menutup blind-spot permanen).
5. Observasi O-1..O-4 — perlu keputusan bisnis.

---
---

# 🔬 PUTARAN 7 — Audit Mendalam Modul Cakupan-Terendah (lanjutan report-only)

> **Pemicu:** permintaan menaikkan confidence dari ~60% → ~85%+ dengan mengaudit **modul
> cakupan terendah** yang belum ditelaah dalam (payroll, quotations, automation, whatsapp, dst).
> **Hasil:** ditemukan **3 bug baru** — dua di antaranya **membuktikan bahwa perbaikan lama B1 & B7
> TIDAK diterapkan konsisten** ke SEMUA jalur pembuatan booking. `gate.sh` tetap **HIJAU 13/13**
> (artinya bug-bug ini **tak terdeteksi** guardrail — inti keraguan Anda).

## Ringkasan Temuan Putaran 7

| # | Temuan | Severity | Berkas | Bukti (live) | Status |
|---|--------|:--------:|--------|:---:|:------:|
| **Q-BUG-1** | `POST /quotations/{id}/convert` **tak cek bentrok SOPIR** (RC-07) → sopir double-booking | 🔴 **Tinggi** | `routers/quotations.py` | konversi sopir sibuk → **200** (padahal `/bookings` menolak 400) | ⏳ Belum |
| **Q-BUG-2** | `convert` **tak dibungkus `vehicle_lock`** (B7) → double-booking ARMADA saat konkuren | 🔴 **Kritis** | `routers/quotations.py` | **6/6** convert paralel sukses → 6 booking overlap 1 armada | ⏳ Belum |
| **PAY-RACE** | `approve_payout` konkuren → **expense `gaji_driver` GANDA** (dobel P&L) | 🟠 Sedang | `routers/payroll.py` | 6 approve paralel → **2 expense** utk 1 payout | ⏳ Belum |

Plus observasi: **O-5** (webhook WA mock-mode tanpa auth → injeksi lead) & **O-6** (bonus/potongan payroll negatif tak dibatasi).

---

## 🔴 Q-BUG-1 — `convert_quotation` melewati cek bentrok SOPIR (RC-07)

**Berkas:** `backend/routers/quotations.py` → `convert_quotation` (baris 212–289).

**Deskripsi.** Saat mengonversi penawaran → booking, sistem memeriksa bentrok **armada**
(`find_conflicts`) dan **perawatan** (`find_maintenance_conflicts`), **tetapi TIDAK** memanggil
`find_driver_conflicts`. Faktanya modul ini bahkan **tidak meng-import** `find_driver_conflicts`.
Ini **lubang pada perbaikan B1** (yang menambal cek sopir di `create/approve/reschedule/PATCH bookings`)
— jalur convert terlewat.

**Bukti reproduksi (live).**
```
create B1 (sopir d1 sibuk window W)                 -> 200 (BK-0013)
create B2 sopir d1 sama via /bookings (kontrol)     -> 400  ← guard bekerja di /bookings
convert penawaran + sopir d1 sama window W          -> 200  ← BUG: convert TIDAK cek sopir
```

**Dampak.** Satu sopir bisa mengemudi 2 trip bersamaan (RC-07) via jalur convert. INV data tak menangkap
(INV-4 hanya armada). Cakupan `routers/quotations.py` hanya **24%** → tak pernah teruji.

**Usulan perbaikan.** Import & panggil `find_driver_conflicts(db, body.driver_id, start_iso, end_iso)`
bila `driver_id` diisi (persis sebagaimana B1 diperbaiki untuk bookings).

---

## 🔴 Q-BUG-2 — `convert_quotation` di luar mutex `vehicle_lock` (lubang B7, KRITIS)

**Berkas:** `backend/routers/quotations.py` → `convert_quotation`.

**Deskripsi.** Perbaikan **B7** (mutex per-armada anti double-booking TOCTOU) diterapkan ke **5 jalur**:
`create_booking`, `create_group_booking`, `confirm_booking`, `approve_booking`, `reschedule_booking`.
Namun **jalur ke-6 — konversi penawaran** — membuat booking `confirmed` langsung via
`find_conflicts()` → `insert_one()` **tanpa** `vehicle_lock`. Jadi lubang race B7 **masih terbuka** di sini.

**Bukti reproduksi (live).**
```
6× POST /quotations/{id}/convert PARALEL, armada+window sama
   -> statuses: [200,200,200,200,200,200]   (6 sukses)
   -> booking 'confirmed' overlap pada 1 armada di window itu: 6
```
Bandingkan B7 yang kini menghasilkan **tepat 1 sukses** untuk `create_booking` — jalur convert **tidak
terlindungi**, menghasilkan **6 double-booking** deterministik.

**Dampak.** Pelanggaran anti-double-booking armada (INV-4) — **severity Kritis**, kelas sama dengan B7.
**Kenapa lolos:** `verify_concurrency` hanya menguji race *pembayaran* & seluruh gate single-thread.

**Usulan perbaikan.** Bungkus bagian kritis convert (cek-final `find_conflicts` + `insert_one` booking)
dengan `async with vehicle_lock(db, body.vehicle_id):` — sama seperti B7 pada jalur lain.

---

## 🟠 PAY-RACE — `approve_payout` konkuren → expense `gaji_driver` ganda

**Berkas:** `backend/routers/payroll.py` → `approve_payout` (baris 144–162).

**Deskripsi.** `approve_payout` melakukan baca-lalu-tulis: cek `status=='draft'` → `create_payout_expense`
→ set `approved`. Tanpa guard atomik, dua approve konkuren sama-sama lolos cek `draft` lalu **masing-masing
membuat expense** `gaji_driver` (karena keduanya membaca `expense_id=None`). Ini gap yang **sudah diflag**
di laporan Putaran 1–5 ("race payroll generate/approve, frekuensi rendah") — kini **dikonfirmasi nyata**.

**Bukti reproduksi (live).**
```
6× POST /payroll/payouts/{id}/approve PARALEL
   -> statuses: [200,200,400,400,400,400]
   -> expense gaji_driver utk payout ini: 2  (seharusnya 1)  ← dobel beban P&L
```

**Dampak.** Beban gaji driver dobel di P&L (`profit_loss` menjumlah `expenses`) → laba understated.
Severity Sedang (perlu klik/approve konkuren; frekuensi rendah tapi berdampak finansial).

**Usulan perbaikan.** Approve atomik: `update_one({"id":id,"status":"draft"}, {"$set":{"status":"approved",...}})`
dan hanya buat expense bila `matched_count==1` (guard state-transition atomik), atau pola mutex seperti B7.

---

## Observasi Tambahan Putaran 7

| # | Observasi | Berkas | Catatan |
|---|-----------|--------|---------|
| O-5 | `POST /api/wa/webhook` **tanpa auth** memproses inbound → buat lead/percakapan + trigger otomasi. Signature hanya dicek bila `provider==meta_cloud` **dan** `app_secret` diisi. Mode `mock` (default) = **terbuka** untuk injeksi lead/spam. | `routers/whatsapp.py` | Webhook publik memang kontrak Meta, tapi mode mock sebaiknya menolak/round-trip verifikasi. |
| O-6 | `PATCH /payroll/payouts/{id}` menerima **bonus/potongan negatif** (tanpa `ge=0`). Potongan negatif menaikkan `total`. | `routers/payroll.py` | Dibatasi sebagian karena `create_payout_expense` melewati bila `total<=0`. Severity rendah. |

## Terbukti Bersih / Solid (Putaran 7)

- **Payroll state-machine**: draft→approved→paid; expense dibuat **sekali** (`expense_id or create`);
  delete hanya draft; RC-06 anti-overlap periode (create & bulk) — **kokoh** (kecuali race approve di atas).
- **Quotation lifecycle**: guard status transisi, INV-19 anti double-convert (`booking_id`), item `ge=0` (B6),
  nomor QUO atomik — **kokoh** (kecuali dua lubang convert di atas).
- **WhatsApp config**: rahasia di-mask (`access_token`/`app_secret` tak pernah dibocorkan), RBAC owner.
- **Automation engine** (`services/automation.py`): dedupe per-(rule,event), **try/except per-aksi**
  (satu aksi gagal tak menjatuhkan run), idempotent, tak ada loop emisi-event — **kokoh & defensif**
  (contoh cakupan rendah ≠ buggy).

---

## 📊 Dampak ke Confidence (jujur, diperbarui)

Putaran 7 **menemukan 3 bug (2 di antaranya Tinggi/Kritis)** di modul yang sebelumnya tak diaudit —
artinya sistem **belum konvergen** (masih ada bug material di jalur tak-teruji). Temuan terpenting:
**perbaikan B1 & B7 tidak menyeluruh** — hanya jalur `bookings` yang ditambal, jalur `quotations/convert`
terlewat. Ini menegaskan bahwa audit berbasis-flow sebelumnya memang **hanya menutup sebagian jalur**.

**Rekomendasi audit lanjutan (untuk benar-benar ~85%+):** telusuri SEMUA jalur pembuatan/pengubahan
booking & sumber daya (dispatch, subcharter, driver check-in, group, convert) terhadap konsistensi
RC-07 + mutex B7; audit `automation`/`finance_automation` rule-engine; naikkan `coverage` terarah ≥85%.

## Berkas terdampak (usulan perbaikan bila disetujui)
- `routers/quotations.py` — Q-BUG-1 (import + `find_driver_conflicts`), Q-BUG-2 (`vehicle_lock`).
- `routers/payroll.py` — PAY-RACE (approve atomik / mutex), O-6 (`ge=0`).
- `routers/whatsapp.py` — O-5 (verifikasi webhook mode mock).


---
---

# 🧭 PUTARAN 8 — Konsistensi Lintas-Jalur & Rekonsiliasi Finansial (report-only)

> **Fokus:** matriks konsistensi **RC-07 (cek sopir)** + **B7 (mutex `vehicle_lock`)** di SEMUA jalur
> pembuatan/penugasan booking, plus audit `finance_automation`, `sequences`, `campaigns`, `dispatch`.
> **Hasil:** **2 bug konkurensi baru** (DISP-RACE, CAMP-RACE) + **koreksi severity KRITIS** untuk R6-2 & R6-3
> (ternyata **merusak P&L komprehensif & rekonsiliasi**, bukan kosmetik). `gate.sh` tetap **HIJAU 13/13**.

## Ringkasan Temuan Putaran 8

| # | Temuan | Severity | Berkas | Bukti (live) | Status |
|---|--------|:--------:|--------|:---:|:------:|
| **DISP-RACE** | `POST /dispatch/{id}/assign` **di luar `vehicle_lock`** → double-booking armada saat konkuren | 🔴 **Tinggi/Kritis** | `routers/dispatch.py` | 2 assign paralel → **2 booking 1 armada** window sama | ⏳ Belum |
| **CAMP-RACE** | `POST /crm/campaigns/{id}/send` guard status **tak atomik** → broadcast berulang | 🟠 Sedang | `routers/campaigns.py`, `services/campaigns.py` | 5 send paralel → **12 penerima utk 4 customer** (3×) | ⏳ Belum |
| **R6-2↑** | **Koreksi:** invoice negatif **merusak `/finance/reconciliation`** | 🔴 **Tinggi** (naik dari Sedang) | `schemas.py`/`invoices.py` | `total_invoiced` **7.850.000 → −22.150.000** | ⏳ Belum |
| **R6-3↑** | **Koreksi:** maintenance cost negatif **merusak `/finance/pl-full`** (P&L E5) | 🔴 **Tinggi** (naik dari Rendah) | `schemas.py`/`maintenance.py` | profit **−2.720.000 (rugi) → +47.280.000 (laba palsu)** | ⏳ Belum |

Plus observasi **O-7** (scheduler `sequences.process_due`: `delay_hours` non-numerik meng-crash batch).

---

## 📐 Matriks Konsistensi RC-07 + B7 (differential analysis) — temuan inti

Menelusuri **SEMUA jalur** yang membuat booking / menugaskan armada+sopir:

| Jalur | cek armada (`find_conflicts`) | cek sopir (`find_driver_conflicts`, RC-07) | mutex `vehicle_lock` (B7) | Verdict |
|---|:---:|:---:|:---:|---|
| `bookings.create` | ✓ | ✓ | ✓ | OK |
| `bookings.group` | ✓ | ✓ | ✓ | OK |
| `bookings.update` (PATCH) | n/a¹ | ✓ | n/a¹ | OK (B1) |
| `bookings.confirm` | ✓ | ✓ | ✓ | OK |
| `bookings.approve` | ✓ | ✓ | ✓ | OK |
| `bookings.reschedule` | ✓ | ✓ | ✓ | OK |
| `public.create` (pending) | ditunda² | ditunda² | ditunda² | OK (approve menegakkan) |
| **`dispatch.assign_trip`** | ✓ | ✓ | **✗** | **DISP-RACE** |
| **`quotations.convert`** | ✓ | **✗** | **✗** | **Q-BUG-1 + Q-BUG-2** |
| `driver.checkin` (buat trip) | ✗ | ✗ | ✗ | O-2 (status/konflik tak dicek) |

¹ PATCH hanya ubah origin/destination/notes/driver_id (tak ubah armada/tanggal) → cukup cek sopir (B1).
² Booking publik berstatus `pending` belum menempati armada; penegakan penuh di `approve` (ada mutex + cek).

**Simpulan差 (kesenjangan):** mutex **B7 punya 2 lubang** (`dispatch.assign_trip`, `quotations.convert`)
dan **RC-07 punya 1 lubang** (`quotations.convert`). Artinya perbaikan lama **B1 & B7 tidak diterapkan
konsisten**; audit berbasis-flow sebelumnya melewatkan **2 jalur penugasan armada**.

---

## 🔴 DISP-RACE — `dispatch.assign_trip` di luar mutex `vehicle_lock`

**Berkas:** `backend/routers/dispatch.py` → `assign_trip` (baris 108–194).

**Deskripsi.** `assign_trip` MEMANG memeriksa bentrok armada (124) & sopir (129), tetapi **tidak dibungkus
`vehicle_lock`**. Dua assign konkuren yang menugaskan **armada bebas yang sama** ke dua booking berbeda
(window tumpang-tindih) sama-sama lolos `find_conflicts` (baca) lalu sama-sama menulis → double-booking
armada. Ini **lubang B7 ketiga** (selain `quotations.convert`).

**Bukti reproduksi (live).**
```
B1 (BK-0013, armada V1) & B2 (BK-0014, armada V2), window sama
2× POST /dispatch/{id}/assign PARALEL → armada bebas V3
   -> statuses: [200, 200]
   -> booking memegang V3 di window: 2  (BK-0013 & BK-0014)  ← double-booking armada
```

**Usulan perbaikan.** Bungkus bagian kritis assign (cek `find_conflicts`/`find_driver_conflicts` + update
booking + set kendaraan) dalam `async with vehicle_lock(db, body.vehicle_id):` — konsisten dengan B7.

---

## 🟠 CAMP-RACE — `send_campaign` guard status tidak atomik → broadcast berulang

**Berkas:** `backend/routers/campaigns.py` (`send_campaign`, 181) → `services/campaigns.py` (`send_campaign`, 25).

**Deskripsi.** Router membaca campaign lalu memanggil service; service mengecek `status in (sending,sent)`
pada dict **basi** lalu baru `update_one status=sending`. Dua request konkuren sama-sama membaca `draft`
→ sama-sama lolos → **broadcast ganda** (biaya WA ganda + spam pelanggan).

**Bukti reproduksi (live).**
```
5× POST /crm/campaigns/{id}/send PARALEL
   -> statuses: [200,200,200,400,400]  (3 lolos)
   -> campaign_recipients: 12  untuk 4 customer  → tiap pelanggan dikirim 3×
```

**Usulan perbaikan.** Klaim atomik: `update_one({"id":id,"status":{"$in":["draft","scheduled"]}},
{"$set":{"status":"sending"}})` dan hanya lanjut bila `matched_count==1` (pola sama disarankan PAY-RACE).

---

## 🔴 KOREKSI SEVERITY — R6-2 & R6-3 ternyata merusak laporan keuangan (bukan kosmetik)

Pada Putaran 6 saya menilai invoice/maintenance negatif "terbatas/kosmetik" karena hanya mengecek
`services/finance.py::profit_loss` (yang hanya menjumlah `expenses`). **Itu keliru.** Ada **mesin P&L
kedua** — `services/finance_automation.py` (E5) — yang **mengonsumsi** `maintenance_records.cost` dan
`invoices.amount`:

**Bukti live (setelah 1 record negatif):**
```
/finance/pl-full     : maintenance_cost 2.500.000 → −47.500.000 ; profit −2.720.000 (RUGI) → +47.280.000 (LABA PALSU)
/finance/reconciliation : total_invoiced 7.850.000 → −22.150.000
```

**Dampak.** Satu record negatif bisa **mengubah rugi menjadi laba** di laporan `/finance/pl-full`,
`/finance/cashflow`, `/finance/export`, dan mengacaukan rekonsiliasi AR. → **Severity R6-2 & R6-3 dinaikkan
menjadi TINGGI.** Perbaikan tetap sama (batas `ge=0`/`gt=0` di skema), tapi urgensinya kini tinggi.

---

## Observasi Tambahan & Bersih (Putaran 8)

| # | Item | Berkas | Catatan |
|---|------|--------|---------|
| O-7 | `sequences.process_due`: `float(steps[nxt].get("delay_hours"))` tanpa try/except → step `delay_hours` non-numerik meng-crash batch scheduler | `services/sequences.py` | Robustness scheduler; koersi defensif. Rendah. |
| ✅ | `finance_automation` (recon/cashflow/AR) — aritmetika & aging **konsisten**; `_age_days` aman (try/except); reminder AR `dedupe_key` unik | `services/finance_automation.py` | Bersih (kecuali sensitif terhadap input negatif di atas). |
| ✅ | `sequences.enroll` idempotent (1 enrollment aktif/target); `campaigns` hormati opt-out & lacak biaya | `services/{sequences,campaigns}.py` | Bersih (kecuali CAMP-RACE). |

---

## 📊 Confidence — diperbarui (jujur)

Putaran 8 **masih menemukan bug Tinggi** (DISP-RACE) + **koreksi 2 severity ke Tinggi** + **1 bug Sedang**
(CAMP-RACE). Pola race TOCTOU kini terlihat **berulang** di banyak jalur (booking-convert, dispatch,
campaign, payroll) — mengindikasikan **kelemahan arsitektural sistemik** (MongoDB standalone tanpa
transaksi; guard baca-tulis non-atomik). Ini menurunkan keyakinan bahwa "semua bug sudah ketemu".

**Ringkasan lintas-putaran (6→8): 5 → 6 → 5 temuan** — **belum konvergen**. Rekomendasi kuat: setelah
menambal, tambahkan **guardrail konkurensi generik** (uji race di SEMUA endpoint penulis-sumber-daya) &
**invarian finansial** (tolak/deteksi nilai negatif lintas koleksi) ke `gate.sh`.

## Berkas terdampak (usulan perbaikan bila disetujui)
- `routers/dispatch.py` — DISP-RACE (`vehicle_lock`).
- `routers/campaigns.py` / `services/campaigns.py` — CAMP-RACE (klaim status atomik).
- `schemas.py` — R6-2 (`InvoiceCreate.amount gt=0`), R6-3 (`MaintenanceCreate.cost ge=0`).
- `services/sequences.py` — O-7 (koersi `delay_hours`).


---
---

# 🌐 PUTARAN 9 — Marketing / Geo / Analytics (report-only)

> **Fokus:** modul cakupan-terendah yang tersisa — `attribution` (14,5%), `ads` (15,3%),
> `geofence` (12,5%), `osrm` (20,6%), `geocode` (27,1%), `maps`, `geo`, dan **growth analytics**.
> **Hasil:** **0 bug material** — semua modul **defensif & robust**. Ini **putaran pertama yang bersih**,
> indikasi konvergensi untuk kelas kode ini. Hanya **2 observasi informational**.

## Ringkasan Putaran 9

| Modul | Cakupan | Verdikt | Catatan |
|-------|:------:|:------:|---------|
| `services/attribution.py` | 14,5% | ✅ Bersih | Fungsi murni; `_clean` None-safe; slicing dibatasi [:300]; tanpa div/DB/network. |
| `services/ads.py` | 15,3% | ✅ Bersih | `parse_lead_payload` toleran (try/except envelope), koersi string; `normalize_phone` di-guard; emit dedupe. |
| `services/geofence.py` | 12,5% | ✅ Bersih | `within_radius`/`evaluate` cek None + try/except; haversine murni. |
| `services/osrm.py` | 20,6% | ✅ Bersih | HTTP di try/except (timeout 15s) → None saat gagal; base URL dari env. |
| `services/geocode.py` | 27,1% | ✅ Bersih | try/except (timeout 12s), cache, None-safe; URL dari env (tanpa SSRF). |
| `services/maps.py`,`geo.py` | — | ✅ Bersih | adapter bersih; `parse_iso`/`valid_coord`/`haversine` defensif. |
| `services/analytics.py` (415 baris) | — | ✅ Bersih | **SEMUA pembagian ter-guard** (`if x>0 else`, `_delta` cek `prev==0`) → tak ada div-by-zero. |

### Bukti robustness (stress test live) — 16 permintaan
```
Semua endpoint /analytics/* & /crm/{scoreboard,aging,rfm} → 200 (0 dari 16 → 5xx)
Termasuk input rusak: start=GARBAGE, tanggal mustahil (2026-13-45), rentang terbalik,
jendela-nol (1900-01-01..1900-01-01) → tetap 200 (degradasi anggun, bukan crash).
```

### Entry-point koordinat (potensi 5xx `float()` di osrm) — TERBUKTI AMAN
- `POST /locations` (GPS ping) memvalidasi `valid_coord(body.lat, body.lng)` sebelum dipakai.
- `GET /trips/{id}/eta` memakai `dest_lat/dest_lng: float` (FastAPI → 422 bila non-numerik) + koordinat tersimpan.
- `dispatch`/`public` memakai koordinat hasil geocode (float). → tak ada jalur koordinat mentah tak-tervalidasi ke `osrm.route_eta`.

## Observasi Informational (Putaran 9)

| # | Observasi | Berkas | Severity |
|---|-----------|--------|:---:|
| O-8 | Endpoint `/analytics/*` **menerima rentang tanggal rusak/terbalik tanpa 400** (silently degrade ke jendela tak diinginkan, bukan crash) | `routers/analytics.py` | 🔵 Info |
| O-5b | Webhook **E-ADS Lead Ads publik** (`ads.py`) — injeksi lead tanpa auth di mode mock (sekeluarga O-5 WhatsApp) | `routers/ads.py` | 🟡 Rendah |

## 📊 Confidence — diperbarui

Putaran 9 = **putaran pertama tanpa temuan material** (0 bug di 8 modul). Skala lintas-putaran kini
**6 → 6 → 5 → 0**. Kombinasikan dengan Putaran 5 lama (sebagian besar bersih), ini menandakan **konvergensi
mulai tercapai untuk lapisan marketing/geo/analytics** (kode di sini konsisten defensif: guard div-by-zero,
try/except HTTP, None-safe, koersi input).

**Namun** kelas bug **race TOCTOU** (Putaran 7–8) & **validasi nilai negatif** (Putaran 6/8) **belum
tertutup** — itu tetap risiko utama tersisa. Confidence keseluruhan naik moderat ke **~70%** (dari ~55%),
karena area yang belum-teraudit menyusut & akar masalah tersisa sudah terpetakan jelas (2 kelas).

**Modul backend yang belum diaudit-dalam** (untuk ~85%+): `inbox`, `onboarding`, `notifications`,
`settings`, `audit`, `counters`, `identity/dedupe`, `exporter/PDF`, `public` (selain booking) — sebagian
besar CRUD/util berisiko rendah. Rekomendasi: setelah menambal 2 kelas akar, cukup 1 putaran sapuan util.


---
---

# 🧩 PUTARAN 10 — Sapuan Util Terakhir (report-only)

> **Fokus:** `counters`, `identity/dedupe`, `settings`, `audit_logs`, `notifications`, `inbox`,
> `onboarding`, `exporter/PDF`. **Hasil:** **1 bug baru terbukti** (EXPORT-1, PDF 500) + **2 kandidat
> rendah** (ID-RACE, SET-1). Sisanya **bersih**. `gate.sh` tetap **HIJAU 13/13**.

## Ringkasan Putaran 10

| # | Temuan | Severity | Berkas | Bukti | Status |
|---|--------|:--------:|--------|:---:|:------:|
| **EXPORT-1** | Konten user tak di-escape masuk `Paragraph()` ReportLab → **PDF 500** bila ada `<`/`&` | 🟠 Sedang | `services/exporter.py` | quotation PDF → **500** | ⏳ Belum |
| **ID-RACE** | `ensure_customer` find-then-insert **non-atomik** + **tak ada unique index** `customers.phone_normalized` → customer ganda saat konkuren | 🟡 Rendah | `services/identity.py`, `server.py` | code-review (tak direpro) | ⏳ Belum |
| **SET-1** | `PATCH /settings` tak validasi nilai `pricing_rules` → tarif negatif → **quote negatif** (hanya owner) | 🟡 Rendah | `routers/settings.py`, `services/pricing.py` | code-review | ⏳ Belum |

## 🟠 EXPORT-1 — Injeksi markup / 500 pada PDF (konten tak di-escape)

**Berkas:** `backend/services/exporter.py` → `quotation_pdf` / `invoice_pdf`.

**Deskripsi.** Field milik user (`customer_name`, `notes`, item `label`) diinterpolasi langsung ke
`Paragraph(f"...{value}...")` ReportLab, yang **mem-parse markup mini-HTML**. Bila value mengandung
`<` atau `&` (mis. nama/catatan biasa "A & B" atau input `<script>`), parser ReportLab **melempar
exception → HTTP 500**, dan berpotensi injeksi format. Ini mengonkretkan gap yang dulu hanya dicatat
("konten mentah aman di React, berisiko di PDF/WA").

**Bukti reproduksi (live).**
```
POST /quotations {customer_name:"A < B & <script>x</script>", notes:"unclosed <b> & amp", items:[{label:"Sewa <b>"}]}
GET  /quotations/{id}/pdf  -> 500   ← BUG (Paragraph markup parse gagal)
```

**Dampak.** Export PDF penawaran **gagal (500)** untuk record apa pun yang namanya/catatannya
mengandung `<`/`&` — umum pada teks nyata ("PT A & B"). DoS dokumen + risiko injeksi format PDF.
*(Endpoint invoice `/pdf` tidak terdaftar → 404; fungsi `invoice_pdf` punya risiko sama bila diekspos.)*

**Usulan perbaikan.** Escape konten sebelum masuk `Paragraph` — `xml.sax.saxutils.escape(str(v))`
(atau helper `_esc`) untuk `customer_name`, `notes`, `label`, `destination`.

## 🟡 ID-RACE — Duplikasi customer saat konkuren

**Berkas:** `services/identity.py::ensure_customer` (find→insert non-atomik); `server.py` (tak ada
`create_index("phone_normalized", unique)` untuk `customers`).

**Deskripsi.** Dua permintaan konkuren yang men-dedupe kontak dengan telepon sama (mis. konversi
penawaran / booking publik paralel) sama-sama `find_customer_by_identity` (kosong) lalu sama-sama
`insert_one` → **2 customer duplikat**. Tanpa unique index, tak ada jaring pengaman DB.

**Usulan perbaikan.** Unique **partial index** pada `customers.phone_normalized` (untuk string non-kosong)
+ tangani `DuplicateKeyError` di `ensure_customer` (re-fetch pemenang) — pola sama seperti idempotensi B9.

## 🟡 SET-1 — `pricing_rules` tanpa validasi nilai

**Berkas:** `routers/settings.py` (`update_settings` tak validasi isi) + `services/pricing.py`
(`_num` tak meng-clamp tarif; hanya `days`/`distance` di-clamp).

**Deskripsi.** Owner dapat menyetel `pricing_rules` dengan tarif **negatif** → `compute_quote`
menghasilkan komponen/total **negatif** → penawaran ber-total minus (item auto-generate melewati
guard `QuotationItemIn.ge=0` karena dihitung server-side). Terbatas: **owner-only** (self-inflicted).

**Usulan perbaikan.** Validasi `pricing_rules` (semua tarif `>= 0`) di `update_settings`, atau clamp
di `compute_quote`.

## Terbukti Bersih / Solid (Putaran 10)

- **`counters.next_seq`**: `find_one_and_update($inc, upsert, AFTER)` — **atomik**, race-safe (SSOT nomor BK/INV/QUO). ✅
- **`notifications`**: semua endpoint di-scope `visibility_query(user)`; `mark_read`/`dismiss` cek visibility dulu (object-level) → **tanpa IDOR**. ✅
- **`inbox`**: section CRM (owner/ops_admin) — percakapan sengaja dibagikan lintas-tim (multi-admin). ✅ (regex `q` = keluarga O-4)
- **`onboarding`**: seluruh state di-scope `user["id"]`; tanpa upload → tanpa IDOR. ✅
- **`audit_logs`**: `require_section("audit")` — ter-gate peran. ✅
- **`identity.normalize_phone`**: defensif (regex digit, prefix +62). ✅

## 📊 Confidence — final (jujur): **~70% → ~78%**

Putaran 10: **1 bug Sedang** (EXPORT-1) + 2 kandidat Rendah. Sebagian besar util **bersih**. Area
backend yang belum-diaudit kini tinggal sedikit & berisiko rendah (mis. `public` non-booking, beberapa
util kecil). Confidence naik ke **~78%**. **Sisa risiko utama tetap 2 kelas akar** (race TOCTOU +
validasi nilai negatif) — belum ditambal (report-only).

### Berkas terdampak (usulan perbaikan bila disetujui)
- `services/exporter.py` — EXPORT-1 (escape konten).
- `services/identity.py` + `server.py` — ID-RACE (unique index + handle DuplicateKeyError).
- `routers/settings.py`/`services/pricing.py` — SET-1 (validasi/clamp tarif).

