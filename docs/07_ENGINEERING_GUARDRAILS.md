# 07 — ENGINEERING GUARDRAILS (Backend)
## Travel & Fleet Management Ecosystem

> **Status:** WAJIB untuk semua development backend.
> **Prinsip emas:** *Guardrail = kode yang bisa GAGAL (exit ≠ 0).* **Kode menang atas dokumen.**

---

## 0. CARA PAKAI (TL;DR)
Sebelum menyatakan task "selesai", jalankan GATE dari `/app`:
```bash
bash scripts/seed_reset.sh             # seed bersih + [GATE] contract + api_contract + integrity
python scripts/health_check.py         # cek ISI endpoint kritis (bukan cuma 200)
python scripts/audit_endpoint_sweep.py # sweep SEMUA GET /api → cari 5xx
python scripts/ux_audit.py --strict    # baseline UX file yang disentuh
python scripts/validate_compliance.py  # file-size & naming & docs
```
Semua hijau → boleh `finish`. Ada FAIL → **perbaiki dulu** (atau catat eksplisit sebagai keputusan owner — jangan dipalsukan).

---

## 1. RANTAI DESYNC (akar semua bug data)
```
SEED ─tulis→ KOLEKSI MONGO ←baca─ SERVICE ← ROUTER ─JSON→ FRONTEND
  nama koleksi    nama field      signature   /api prefix   import & parsing
```
Satu lapis "geser" (drift) → seluruh rantai patah **tanpa error jelas** (endpoint tetap 200, tetapi tabel kosong / angka salah / 500). Gate menutup tiap titik geser.

---

## 2. TAKSONOMI ROOT CAUSE (domain Travel & Fleet)
Setiap bug WAJIB dipetakan ke salah satu RC. Tidak ada yang cocok → tambahkan RC baru.

| RC | Nama | Contoh domain ini | Gate penangkap |
|----|------|-------------------|----------------|
| **RC-1** | Collection name drift | seed tulis `cars`, app baca `vehicles` | `verify_contract.py` |
| **RC-2** | Field/schema drift | seed pakai `qty`, app pakai `pax`; `payment_status` beda enum | `verify_data_integrity.py` |
| **RC-3** | Response shape drift | FE harap array, BE bungkus `{items,total}`. **Kontrak = ARRAY langsung** | `health_check.py`, `audit_endpoint_sweep.py` |
| **RC-4** | Import JSX/komponen hilang | layar putih | esbuild / runtime |
| **RC-5** | Number-series desync | `INV-0001` tanpa naikkan counter → duplikat invoice/booking code | `verify_data_integrity.py` |
| **RC-6** | Linkage/snapshot putus | booking tanpa `vehicle_name`/`driver_name` snapshot → render 500 | `audit_endpoint_sweep.py` (5xx) |
| **RC-7** | Bug semantik | KPI "trip aktif" dihitung dari 20 booking terakhir saja | invarian lintas-endpoint |
| **RC-8** | Hardcoded value | tanggal/periode literal → "bulan ini" kosong | review + integrity |
| **RC-9** | RBAC dua sumber | peta izin FE ≠ `permissions_config.py` BE | review + test |
| **RC-10** | **False-positive testing** | "status 200" dianggap selesai | **ATURAN:** cek ISI & invarian |
| **RC-11** | Service contract drift | ubah signature service tanpa update caller | review + test |
| **RC-12** | React StrictMode double-fetch | `body stream already read` | async IIFE + cleanup |
| **RC-13** | Guard status/izin (benar) | booking belum approved → 400 (terkontrol, bukan bug) | sweep (4xx = review) |
| **RC-14** | Shell blank page | error di shell, bukan modul | runtime |
| **RC-15** | Eskalasi bug persisten | lihat §6 | proses |
| **RC-16 (domain)** | **Double-booking** | dua booking aktif overlap utk `vehicle` yang sama | `verify_data_integrity` invarian overlap |
| **RC-17 (domain)** | **Payment status drift** | `paid >= total` tapi status ≠ `lunas` | invarian status pembayaran |
| **RC-18 (domain)** | **Profit calc drift** | `trip.profit ≠ revenue − Σ expenses` | invarian P/L |
| **RC-19 (domain)** | **Location time-series** | timestamp lokasi tidak monotonik / lat-lng di luar rentang | invarian lokasi |
| **RC-20 (domain)** | **Lead stage drift** | `lead.stage` di luar himpunan sah | invarian pipeline |

---

## 3. KONTRAK KANONIK (ringkas — detail di `04_API_CONTRACT.md` & `03_DATA_MODEL.md`)

**Auth**
- `POST /api/auth/login {email, password}` → `{"token": "sess_...", "user": {...}}`.
- Field token = **`token`** (BUKAN `access_token`); respons **langsung** (tanpa envelope).
- Header: `Authorization: Bearer sess_...`. Hash password = **SHA256 + salt** (lihat `core_utils.hash_password`).

**Bentuk respons**
- List endpoint → **ARRAY langsung** (`[...]`). Detail/dashboard → **objek langsung**. TIDAK ada envelope `{items,total}`.

**Serialisasi**
- Semua dokumen Mongo dilewatkan `safe_doc()` (strip `_id`, koersi `ObjectId`/`datetime` → ISO string). Cegah `datetime not JSON serializable`.

**Invarian data wajib** (di-enforce `verify_data_integrity.py`):
- **Booking total**: `booking.total_amount == base_price + Σ add_ons` (atau `Σ items.subtotal`).
- **Pembayaran**: `Σ payments[booking] <= booking.total_amount`; `payment_status` derivasinya konsisten: `lunas` jika paid ≥ total; `dp` jika 0 < paid < total; `belum_bayar` jika paid == 0; `selesai` jika trip selesai.
- **Anti double-booking**: untuk satu `vehicle_id`, tidak ada 2 booking status aktif (confirmed/ongoing) yang rentang waktunya overlap.
- **Profit per trip**: `trip.profit == trip.revenue − Σ expenses[trip]`.
- **Lokasi**: per `trip_id`, `timestamp` monotonik naik; `-90 ≤ lat ≤ 90`, `-180 ≤ lng ≤ 180`.
- **Lead stage** ∈ `{new, contacted, quoted, negotiation, won, lost}`.
- **Intent KPI**: `dashboard.active_bookings == len(/bookings?status=active)`.

---

## 4. CHECKLIST 3-GATE

### Gate A — PRE-CODE
- [ ] Konsep/koleksi sudah ada? Cek `03_DATA_MODEL.md` + `verify_contract.py --list-canonical`. **Jangan buat duplikat.**
- [ ] Bentuk respons mengikuti kontrak (array langsung, field `token`).
- [ ] Posisi fitur di `05_NAVIGATION_MAP.md` ditentukan.
- [ ] Integrasi pihak ke-3 → minta playbook + simpan kredensial di `.env`.

### Gate B — DURING-CODE
- [ ] Akses Mongo pakai nama kanonik (`db.vehicles`, bukan `db.cars`).
- [ ] Render/serialisasi **defensif** (`.get()` + `safe_doc()`).
- [ ] Endpoint `/api`-prefixed; ENV via `os.environ` (jangan hardcode/ubah `.env`).
- [ ] Seed mengikuti kontrak API — bukan sebaliknya.
- [ ] File router ≤ 800 baris; service terpisah bila besar.

### Gate C — POST-CODE (sebelum "selesai")
- [ ] `bash scripts/seed_reset.sh` → hijau (contract + api_contract + integrity).
- [ ] `python scripts/health_check.py` → 0 FAIL.
- [ ] `python scripts/audit_endpoint_sweep.py` → 0 entri 5xx.
- [ ] `python scripts/ux_audit.py --strict` → file disentuh tidak menambah ERROR.
- [ ] `python scripts/validate_compliance.py` → tidak menambah pelanggaran.
- [ ] `testing_agent_v3` untuk perubahan signifikan; semua bug difix.

---

## 5. DEFINITION OF DONE (backend)
DONE hanya jika SEMUA benar:
1. Gate A–C hijau (atau FAIL didokumentasikan sebagai keputusan owner).
2. Tidak ada 5xx baru pada sweep.
3. Invarian valid pada **seed bersih**.
4. Frontend mencerminkan 100% fitur backend (tidak ada endpoint "yatim").
5. Tidak ada koleksi/field/endpoint duplikat.
6. Bila belum beres → **dilaporkan jujur** ("BELUM SELESAI" + bukti), bukan diklaim hijau.

---

## 6. RC-15 — PROTOKOL ESKALASI BUG PERSISTEN
1. **Self-debug** maksimal **2×** (baca log, reproduksi minimal).
2. **`troubleshoot_agent`** untuk RCA independen.
3. **`testing_agent_v3`** untuk reproduksi terstruktur (skip drag-drop/voice/kamera).
4. **`web_search`** bila dugaan versi/SDK.
5. **`integration_playbook_expert_v2`** bila integrasi.
6. Buntu → **lapor jujur** + bukti + opsi (rollback/model lebih kuat). DILARANG klaim selesai tanpa bukti.

**Anti-RC-10:** "HTTP 200", "service running", "tidak ada error di log" BUKAN bukti. Bukti = nilai data benar + invarian lintas-endpoint + UI merender data.

---

## 7. KAPAN MENAMBAH GATE BARU
Tambah fitur/koleksi ⇒ WAJIB:
- Tambah koleksi ke `CANONICAL_COLLECTIONS` (`verify_contract.py`) **dan** `03_DATA_MODEL.md`.
- Tambah `Concept(...)` + invarian ke `verify_data_integrity.py`.
- Tambah endpoint kritis ke `CRITICAL_ENDPOINTS` (`health_check.py`).
- Tambah field-binding FE↔BE ke `verify_api_contract.py`.
- Update RC taxonomy bila muncul kelas bug baru.

> Guardrail yang tidak tumbuh bersama kode akan **membusuk** dan menutupi drift.
