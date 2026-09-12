# 🔒 Laporan Audit Kode — Rahaza Travel ERP

**Cakupan:** 5 putaran audit dengan 5 pendekatan berbeda, terhadap seluruh backend
(FastAPI · 40+ router · 40+ service) + titik singgung frontend (React) dan gate
guardrails (`scripts/gate.sh`, 13 gate).
**Hasil:** **9 bug diperbaiki** + **2 invarian gate baru (INV-25, INV-26)** + **1 fitur idempotensi pembayaran**.
Semua perbaikan **terverifikasi oleh testing_agent** dan `gate.sh` tetap **HIJAU 13/13**.

---

## 0. Ringkasan Eksekutif

| # | Bug | Severity | Berkas | Status |
|---|-----|:--------:|--------|:------:|
| B1 | `PATCH /bookings/{id}` melewati validasi bentrok sopir (RC-07) | 🔴 Tinggi | `routers/bookings.py` | ✅ Fixed |
| B2 | `cancel_booking` bisa membatalkan booking `completed` (state-machine) | 🔴 Tinggi | `routers/bookings.py` | ✅ Fixed |
| B3 | `cancel_booking` timestamp naive `utcnow()` + shadow fungsi `now_iso` | 🟠 Sedang | `routers/bookings.py` | ✅ Fixed |
| B4 | `confirm_booking` tak cek perawatan (INV-21) & sopir (RC-07) | 🟠 Sedang | `routers/bookings.py` | ✅ Fixed |
| B5 | Dispatch re-assign meninggalkan armada lama nyangkut `on_trip` | 🟠 Sedang | `routers/dispatch.py` | ✅ Fixed |
| B6 | Line-item negatif → `total_amount` NEGATIF (booking/group/quotation) | 🔴 Tinggi | `schemas.py` | ✅ Fixed |
| B7 | **Race TOCTOU → double-booking armada** (13 dari 16 request paralel) | 🔴 **Kritis** | `services/availability.py`, `routers/bookings.py` | ✅ Fixed |
| B8 | Hapus driver di booking `hold`/`pending` → foreign key menggantung | 🟠 Sedang | `routers/drivers.py` | ✅ Fixed |
| B9 | `POST /payments` tanpa idempotensi → double-submit menggandakan bayar | 🟠–🔴 Sedang-Tinggi | `routers/payments.py`, `schemas.py`, `server.py`, FE `PaymentDialog.jsx` | ✅ Fixed |

**Penambahan guardrail permanen:** `verify_data_integrity.py` → **INV-25** (integritas referensial / FK tak menggantung) & **INV-26** (konsistensi `vehicle.status` ↔ trip aktif).

---

## 1. Metodologi (5 pendekatan berbeda)

| Putaran | Pendekatan | Ide inti | Temuan |
|:---:|---|---|---|
| 1 | **Statik / kontrak** | Bandingkan kode ↔ invarian SSOT (INV-1..24, RC-01..20); *differential analysis* lintas-endpoint | B1–B5 |
| 2 | **Dinamis 1-request (adversarial)** | Enumerasi 268 route dari OpenAPI; RBAC/IDOR matrix; fuzzing input; sweep 500 | B6 |
| 3 | **Konkurensi / TOCTOU** | Tembak N request PARALEL ke resource sama; cek di level data | B7 (kritis) |
| 4 | **Forensik referensial + workflow** | Rekonsiliasi lintas-koleksi langsung di MongoDB; jalankan workflow lalu cek FK & drift status | B8 + INV-25/26 |
| 5 | **Idempotency + Time/Boundary + Financial recon** | Replay/retry paralel; batas waktu/timezone; hitung ulang keuangan independen | B9 (time & finance **terbukti bersih**) |

Setiap perbaikan menjalani siklus: **reproduksi empiris → fix di titik paling tepat/DRY → `gate.sh` (regresi invarian) → `testing_agent` (verifikasi independen)**.

---

## 2. Detail Bug & Perbaikan

### 🔴 B1 — `PATCH /bookings/{id}` melewati validasi bentrok sopir (RC-07)

**Kategori:** Business-rule bypass · **Berkas:** `backend/routers/bookings.py` → `update_booking`

**Deskripsi.** Endpoint edit booking memperbolehkan mengganti `driver_id` **tanpa** memeriksa apakah
sopir tersebut sudah ditugaskan ke booking aktif lain yang jam-nya tumpang-tindih. Validasi ini
dijaga ketat di `create`/`approve`/`reschedule`/`dispatch-assign`, **tapi hilang di PATCH**.

**Dampak.** Satu sopir bisa **double-booking** (mengemudi 2 trip di waktu bersamaan). Tidak ada
invarian data yang menangkapnya (INV-4 hanya untuk armada, bukan sopir).

**Reproduksi (terbukti live).** `PATCH BK-0004` meng-assign sopir yang sudah punya `BK-0003` di jam
tumpang-tindih → sebelum fix **berhasil (200)**.

**Akar masalah.** `update_booking` hanya memvalidasi keberadaan driver, tidak memanggil
`find_driver_conflicts`.

**Perbaikan.** Menambah cek bentrok sopir saat `driver_id` berubah pada booking aktif:
```python
if booking.get("status") not in ("cancelled", "completed") and body.driver_id != booking.get("driver_id"):
    dconf = await find_driver_conflicts(db, body.driver_id,
                                        booking.get("start_datetime"), booking.get("end_datetime"),
                                        exclude_booking_id=booking_id)
    if dconf:
        raise HTTPException(status_code=400, detail=f"Driver bentrok dengan booking aktif: {dconf[0].get('code')}")
```
**Verifikasi.** Setelah fix PATCH dengan sopir bentrok → **400**; sopir bebas → **200**. (testing_agent PASS)

---

### 🔴 B2 — `cancel_booking` bisa membatalkan booking `completed`

**Kategori:** State-machine gap · **Berkas:** `backend/routers/bookings.py` → `cancel_booking`

**Deskripsi.** Tidak ada penjaga status. Booking berstatus `completed` bisa dibatalkan → merusak
pengakuan pendapatan & riwayat operasional. Membatalkan booking yang sudah `cancelled` juga bisa
memicu ulang efek samping.

**Dampak.** Data pendapatan/histori korup (completed→cancelled), potensi refund/denda ganda.

**Akar masalah.** `cancel_booking` langsung memproses tanpa memeriksa status saat ini
(bandingkan `complete`/`reschedule` yang menjaga status).

**Perbaikan.** Menambah guard + idempotensi:
```python
if booking.get("status") == "completed":
    raise HTTPException(status_code=400, detail="Booking sudah selesai — tidak bisa dibatalkan")
if booking.get("status") == "cancelled":
    return safe_doc(booking)   # idempotent: tanpa refund/denda ganda
```
**Verifikasi.** Cancel booking `completed` → **400**; cancel ganda idempoten (tak ada refund/invoice ganda). (testing_agent PASS)

---

### 🟠 B3 — Timestamp naive `datetime.utcnow()` + shadow fungsi `now_iso`

**Kategori:** Konsistensi data waktu / code smell · **Berkas:** `backend/routers/bookings.py` → `cancel_booking`

**Deskripsi.** Di alur pembatalan, variabel lokal `now_iso = datetime.utcnow().isoformat()` menghasilkan
timestamp **naive (tanpa `+00:00`)** — beda dari fungsi kanonik `now_iso()` (tz-aware UTC) yang dipakai
seluruh aplikasi — **sekaligus men-shadow fungsi `now_iso`** di dalam scope (bahaya laten).

**Dampak.** `cancelled_at`, `paid_at` refund, dan seluruh timestamp invoice pembatalan tersimpan naive →
urutan/komparasi waktu tak konsisten; rawan bug bila `now_iso()` dipanggil setelahnya.

**Perbaikan.** Ganti ke fungsi kanonik & rename variabel:
```python
ts = now_iso()   # tz-aware UTC; sebelumnya `now_iso = datetime.utcnow().isoformat()` (naive + shadow)
# semua field cancel/refund/invoice memakai `ts`
```
Import `from datetime import datetime` yang jadi tak terpakai di berkas ini juga dihapus.

**Verifikasi.** `cancelled_at` & refund `paid_at` kini berakhiran `+00:00`. (testing_agent PASS)

---

### 🟠 B4 — `confirm_booking` tak cek perawatan & bentrok sopir

**Kategori:** Konsistensi validasi · **Berkas:** `backend/routers/bookings.py` → `confirm_booking`

**Deskripsi.** Saat konfirmasi, hanya bentrok **armada** yang dicek. Jendela **perawatan** (INV-21)
dan bentrok **sopir** (RC-07) tidak — inkonsisten dengan `create`/`approve`/`reschedule`.

**Dampak.** Bisa mengonfirmasi booking yang armadanya sedang servis, atau sopirnya bentrok.

**Perbaikan.** Menambah `find_maintenance_conflicts` + `find_driver_conflicts` sebelum set `confirmed`
(kini juga di dalam mutex per-armada — lihat B7).
**Verifikasi.** Konfirmasi saat perawatan/bentrok sopir → **400**; kasus bersih → **200**. (testing_agent PASS)

---

### 🟠 B5 — Dispatch re-assign meninggalkan armada lama `on_trip`

**Kategori:** Resource leak / drift status · **Berkas:** `backend/routers/dispatch.py` → `assign_trip`

**Deskripsi.** Saat trip di-assign ulang ke armada berbeda, armada **lama** tidak dikembalikan ke
`available` → nyangkut `on_trip` selamanya, tampak sibuk padahal bebas, memblok booking baru.

**Akar masalah.** `assign_trip` hanya menyetel armada baru ke `on_trip`, tak membebaskan yang lama.

**Perbaikan (final, selaras `_release_booking_resources`).** Bebaskan armada lama **hanya bila tak
ada TRIP aktif lain** & statusnya memang `on_trip`:
```python
if prev_vehicle_id and prev_vehicle_id != veh["id"]:
    other_trip = await db.trips.find_one({"vehicle_id": prev_vehicle_id, "id": {"$ne": trip_id},
                                          "status": {"$in": ["standby","to_pickup","on_trip"]}}, {"_id":0,"id":1})
    prev_veh = await db.vehicles.find_one({"id": prev_vehicle_id}, {"_id":0,"status":1})
    if not other_trip and prev_veh and prev_veh.get("status") == "on_trip":
        await db.vehicles.update_one({"id": prev_vehicle_id}, {"$set": {"status": "available"}})
```
> Catatan: iterasi pertama (mengecek booking `confirmed` terjadwal) terlalu ketat dan **ditangkap oleh
> testing_agent**; diperbaiki agar hanya mengecek TRIP aktif. **Verifikasi:** re-assign → armada lama
> `available`, armada baru `on_trip`. (testing_agent PASS)

---

### 🔴 B6 — Line-item negatif → `total_amount` NEGATIF

**Kategori:** Validasi input / integritas finansial · **Berkas:** `backend/schemas.py` (`AddOn`, `QuotationItemIn`)

**Deskripsi.** `add_ons[].amount` (booking & group) dan `items[].amount` (quotation) **tanpa batas bawah**.
Nilai negatif diterima → menghasilkan **total negatif**.

**Dampak.** Pendapatan negatif mencemari dashboard/P&L/AR; booking `confirmed` dengan total minus.
**Kenapa lolos gate:** INV-1 (`total == base + Σaddons`) **tetap valid** (mis. `2jt + (−99jt) = −97jt`).

**Reproduksi (terbukti).** `POST /api/bookings` dengan `add_ons:[{amount:-99000000}]` → booking
`total_amount = −97.000.000`. Sama di `/api/bookings/group` (−47jt) & `/api/quotations` (−8jt).

**Perbaikan (DRY di lapisan skema — menutup 3 endpoint sekaligus).**
```python
class AddOn(BaseModel):
    label: str = ""
    amount: float = Field(default=0, ge=0)   # tak boleh negatif
class QuotationItemIn(BaseModel):
    label: str = ""
    amount: float = Field(default=0, ge=0)   # tak boleh negatif
```
Karena `base_price ≤ 0` otomatis di-reprice positif dan semua line-item `≥ 0`, `total ≥ 0` dijamin.
Nilai `0` (mis. trip komplimen) tetap diperbolehkan.

**Verifikasi.** Negatif di 3 endpoint (termasuk PATCH quotation) → **422**; positif → **200** total benar. (testing_agent 18/18 PASS)

---

### 🔴 B7 — Race TOCTOU → Double-Booking Armada (KRITIS)

**Kategori:** Concurrency / race condition · **Berkas:** `backend/services/availability.py`, `backend/routers/bookings.py`, `backend/server.py`

**Deskripsi.** Pembuatan booking memakai pola **baca-lalu-tulis** (`find_conflicts()` → `insert_one()`)
yang **tidak atomik**. MongoDB di sini **standalone (tanpa transaksi)**. Banyak request paralel untuk
**armada + jendela waktu sama** semua membaca "tidak ada bentrok" lalu semua menulis.

**Dampak (paling parah).** Pelanggaran anti-double-booking (INV-4): satu armada "terjual" berkali-kali
di slot sama → konflik operasional.
**Kenapa lolos semua lapisan:** gate `verify_concurrency` hanya menguji race **pembayaran**, dan seluruh
gate berjalan **single-thread** — mustahil menangkap race pembuatan booking.

**Reproduksi (terbukti).** 16 `POST /api/bookings` **paralel** armada+jendela sama → **13 BERHASIL**
membuat booking `confirmed` yang saling tumpang-tindih.

**Perbaikan — Mutex per-armada (lock-free, cocok untuk MongoDB standalone).**
Memanfaatkan atomicity *insert `_id` unik*:
```python
# services/availability.py — koleksi booking_locks (_id="vehicle:{id}")
@asynccontextmanager
async def vehicle_lock(db, vehicle_id):
    key = await _acquire_vehicle_lock(db, vehicle_id)   # insert _id unik = ambil kunci;
    try:                                                # DuplicateKeyError → retry backoff;
        yield                                           # takeover lock basi (>20s) utk crash-safety
    finally:
        await _release_vehicle_lock(db, key)
```
Bagian kritis (cek-final ketersediaan + tulis) dibungkus mutex → **serial per armada**; request kedua
melihat booking pertama → **ditolak 400**. Diterapkan ke **5 jalur**: `create_booking`,
`create_group_booking` (kunci semua armada berbeda, urut → anti-deadlock, all-or-nothing),
`confirm_booking`, `approve_booking`, `reschedule_booking`.
**Jaring pengaman:** `server.py` menambah **TTL index** `booking_locks.acquired_at expireAfterSeconds=60`
(hapus lock yatim) + *fail-safe* HTTP 409 saat kontensi ekstrem. Koleksi `booking_locks` didaftarkan di
`verify_contract.py` & `validate_compliance.py`.

**Verifikasi.** 16 paralel → **tepat 1 sukses / 15 ditolak**; 0 lock nyangkut; race group-booking maks 1
sukses; lock hygiene OK (armada lain langsung 200 dalam 0,11 dtk). (testing_agent 12/12 PASS)

---

### 🟠 B8 — Hapus driver di booking `hold`/`pending` → FK menggantung

**Kategori:** Integritas referensial · **Berkas:** `backend/routers/drivers.py` → `delete_driver`

**Deskripsi.** Guard hapus driver hanya memblok status `["confirmed","ongoing"]`, padahal status aktif
sistem mencakup `hold` (reservasi DP-gate) dan `pending` (permintaan publik). Sopir di booking
`hold`/`pending` bisa dihapus → `booking.driver_id` menunjuk driver yang **sudah tiada**.

**Dampak.** Foreign key menggantung pada booking hidup → confirm/dispatch gagal menemukan sopir.
**Kenapa lolos:** butuh urutan create-hold → delete-driver; gate berjalan di seed bersih tanpa operasi delete.

**Reproduksi (terbukti).** Buat booking `hold` bersopir → `DELETE /api/drivers/{id}` → **200**;
sweep forensik menyala `REF bookings.driver_id → drivers`.

**Perbaikan.** Perlebar definisi "aktif" (selaras `ACTIVE_BOOKING_STATUSES` + pending):
```python
active = await db.bookings.count_documents(
    {"driver_id": driver_id, "status": {"$in": ["pending", "hold", "confirmed", "ongoing"]}})
if active:
    raise HTTPException(status_code=400, detail="Driver masih ditugaskan ke booking aktif (pending/hold/confirmed/ongoing)")
```
**Guardrail permanen ditambah:** `verify_data_integrity.py` → **INV-25** (integritas referensial FK) &
**INV-26** (konsistensi `vehicle.status` ↔ trip aktif).
**Verifikasi.** DELETE di booking hold → **400**; sweep 22 pemeriksaan bersih; gate 35 invarian PASS. (testing_agent 13/13 PASS)

---

### 🟠 B9 — `POST /payments` tanpa idempotensi (double-submit menggandakan bayar)

**Kategori:** Idempotency / retry-safety · **Berkas:** `backend/routers/payments.py`, `backend/schemas.py`, `backend/server.py`, `frontend/.../PaymentDialog.jsx`

**Deskripsi.** Pencatatan pembayaran tak punya proteksi idempotensi. Double-click / retry jaringan /
request ganda mencatat pembayaran yang sama berkali-kali. Guard atomik `$inc` hanya mencegah
*overpay melebihi total*, bukan *pencatatan ganda* di bawah total.

**Dampak.** Over-recording kas / phantom payment (pelanggan tampak membayar lebih dari kenyataan).
**Reproduksi (terbukti).** 6 request identik paralel → **6 catatan**, `paid_amount` = **1.800.000** (harusnya 300.000).

**Perbaikan (end-to-end, backward-compatible).**
1. Skema: `PaymentCreate.idempotency_key: Optional[str] = None`.
2. `create_payment`: pre-check replay (kembalikan pembayaran lama, **tanpa** `$inc`) + penanganan
   balapan konkuren via **rollback `$inc`** saat kalah di unique-index:
   ```python
   idem = (body.idempotency_key or "").strip() or None
   if idem:
       prior = await db.payments.find_one({"idempotency_key": idem}, {"_id": 0})
       if prior: return safe_doc(prior)          # replay: tak menambah paid_amount
   # ... guard atomik $inc + insert (unique index) ...
   except DuplicateKeyError:                      # replay konkuren
       await db.bookings.update_one({"id": bid}, {"$inc": {"paid_amount": -amount}})  # undo
       return safe_doc(winner)
   ```
3. `server.py`: **index unik-parsial** `payments.idempotency_key`
   (`partialFilterExpression={"idempotency_key": {"$type": "string"}}`).
4. Frontend `PaymentDialog.jsx`: buat **UUID key per sesi dialog** & kirim → klik-ganda/retry aman otomatis.

**Verifikasi.** 6 paralel key-sama → **1 catatan, paid=300k**; replay → tetap 1; tanpa-key backward compat OK;
overpay/cancelled guard tetap 400. (testing_agent 28/28 PASS)

---

## 3. Gap Dilaporkan (belum diubah — perlu keputusan bisnis)

| Gap | Berkas | Rekomendasi |
|-----|--------|-------------|
| Denda vs refund pembatalan tak divalidasi silang (bisa invoice denda "paid" tanpa kas) | `bookings.py cancel` | Enforce `cfee ≈ paid − refund` atau beri peringatan |
| `subcharter` overlap pakai string-compare mentah (rawan timezone) | `services/subcharter.py` | Normalisasi ke UTC via `parse_iso` sebelum bandingkan |
| `complete_booking` izinkan complete `pending/hold/draft` | `bookings.py` | Batasi ke `confirmed`/`ongoing` |
| Doc-drift `payment_status='selesai'` (kode sengaja tak set) | `docs/03_DATA_MODEL.md` | Sinkronkan dokumen dgn keputusan RC-02 |
| Konten disimpan mentah (`<script>`) — aman di React, risiko di PDF/WA | banyak router | Escape saat render non-React |
| Race konkuren payroll `generate`/`approve` (frekuensi sangat rendah) | `payroll.py` | Terapkan pola mutex spt B7 bila perlu |
| Match driver by `name` (fallback rapuh) di object-level check trip | `trips.py` | Andalkan `user_id` saja |

---

## 4. Area yang Diuji & TERBUKTI BERSIH (hasil audit positif)

- **Otorisasi:** 0 kebocoran tanpa-token (130 GET), 0 eskalasi privilege driver→owner/ops (138 mutasi),
  `trips/{id}/status` punya object-level ownership check, tak ada IDOR.
- **Ketahanan auth:** token sampah/kosong → 401 (bukan 500); brute-force login → 429 (ambang 8).
- **Injeksi:** NoSQL injection → 422; tanggal rusak → 400; `0 dari 268` endpoint melempar 5xx.
- **Time/Timezone/Boundary (5b):** offset `+07:00` dinormalisasi ke UTC; batas overlap `end==start`
  tidak false-conflict; perhitungan hari `ceil` konsisten web↔ERP; uang integer.
- **Financial recon (5c):** revenue(period), revenue(all), AR — **cocok persis** perhitungan independen ↔
  `/api/finance/*` ↔ `/api/dashboard`; skenario refund + denda pembatalan konsisten (tanpa double-count).
- **Payroll idempotensi** via status-guard (draft→approved→paid, `expense_id = existing or create`, overlap-period RC-06).
- **Baseline DB:** 22 pemeriksaan referensial/status/duplikat semua bersih.

---

## 5. Ringkasan Berkas yang Diubah

**Backend**
- `routers/bookings.py` — B1, B2, B3, B4, B7 (create/group/confirm/approve/reschedule)
- `routers/dispatch.py` — B5
- `routers/drivers.py` — B8
- `routers/payments.py` — B9
- `services/availability.py` — B7 (`vehicle_lock` mutex)
- `schemas.py` — B6 (`AddOn`, `QuotationItemIn`), B9 (`PaymentCreate.idempotency_key`)
- `server.py` — B7 (TTL index `booking_locks`), B9 (unique index `payments.idempotency_key`)

**Frontend**
- `src/components/app/PaymentDialog.jsx` — B9 (kirim `idempotency_key`)

**Gate / guardrails**
- `scripts/verify_data_integrity.py` — INV-25 (referensial), INV-26 (state consistency)
- `scripts/verify_contract.py`, `scripts/validate_compliance.py` — daftarkan koleksi `booking_locks`

---

## 6. Status Akhir

- **Semua service RUNNING** (backend/frontend/mongodb).
- **`gate.sh` HIJAU 13/13** — kini **35 pemeriksaan integritas (INV-1..26)**.
- **9 bug** diperbaiki + **2 invarian gate baru** + **idempotensi pembayaran** — semuanya **terverifikasi `testing_agent`**.
- Skala temuan per putaran mengecil: **5 → 1 → 1 → 1 → 1** (dua putaran terakhir sebagian besar "bersih") — indikasi konvergensi menuju sistem yang solid.

> **Catatan operasional:** koleksi baru `booking_locks` bersifat internal (mutex, TTL 60s) dan tidak
> menyimpan data bisnis. Kredensial demo: `owner@demo.local` / `ops@demo.local` / `driver@demo.local`
> (password `demo12345`).
