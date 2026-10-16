# 13 — ARCHITECTURE & PERFORMANCE BEST PRACTICES
## Travel & Fleet Management Ecosystem

> **Status:** TIER 0 (wajib). **Prinsip:** *kode efisien, ringkas, jelas; performa & skalabilitas sejak awal; tech-debt minimal.*
> Penegak: `scripts/verify_architecture.py` (statis) + review. **Kode menang atas dokumen.**

---

## 1. MINIMUM BEST-PRACTICE ARCHITECTURE
```
React (thin pages + shared components)  →  apiClient (axios)  →  /api/* 
FastAPI: routers (THIN, hanya I/O & validasi)  →  services (business logic)  →  Motor/MongoDB
```
- **Separation of concerns**: router TIDAK berisi logika bisnis. Logika → `services/`. DB akses → lewat helper.
- **Single Responsibility**: 1 file = 1 tanggung jawab jelas. Router ≤ 800 baris, komponen ≤ 500, util/hook/service ≤ 300.
- **DRY**: util dipakai-ulang (`core_utils.py`, `utils/formatters.js`). Dilarang menyalin-tempel logika (gate mendeteksi duplikasi kasar).
- **Stateless API**: state di DB/sessions, bukan di memori proses (cegah RC saat restart).
- **Idempotent seed & migration**: aman dijalankan berulang.

---

## 2. REALTIME (WAJIB untuk GPS/Tracking & status)
Fitur yang **harus terasa realtime**: posisi kendaraan di peta, status driver/trip, notifikasi.
- **Default v1: polling cerdas** (interval 3–5 dtk) pada endpoint ringan (`GET /api/locations/live`) — sederhana, tahan-banting, tanpa infra tambahan.
- **Throttling klien**: driver kirim lokasi tiap **5–10 dtk** (bukan tiap milidetik). Hormati battery & kuota.
- **Jalur upgrade**: abstraksi `realtimeChannel` → bisa pindah ke **SSE/WebSocket** tanpa rewrite UI (adapter pattern, sejajar AD-4 map provider).
- **Data freshness**: tandai "terakhir update Xs lalu"; marker basi (> 60 dtk) ditandai pudar.
- **Server**: query `locations` selalu **berbatas** (`limit` N titik terakhir per trip), index `{trip_id, timestamp}`.
> `verify_architecture.py` menandai endpoint live tanpa `limit` & polling tanpa interval.

---

## 3. PERFORMA (di-cek `verify_architecture.py`)
| Aturan | Wajib | Anti-pattern (ERROR/WARN) |
|--------|-------|---------------------------|
| **Pagination** | Semua list endpoint dukung `limit` (default 20–50) + `skip`/`page` | `find({}).to_list(None)` / tanpa limit |
| **Projection** | Ambil field yang diperlukan saja untuk list besar | tarik dokumen penuh utk tabel ringkas |
| **Index** | Index pada field query panas: `vehicle_id`, `status`, `start_datetime`, `trip_id+timestamp`, `email(unik)` | scan koleksi tanpa index |
| **No N+1** | Batukan query (aggregate/`$in`), jangan query di dalam loop | `for x: await db...` per item |
| **Hitung di DB** | Pakai `count_documents`/aggregate utk KPI | tarik semua lalu `len()` di Python |
| **FE list** | Tabel besar → pagination/virtualisasi + skeleton | render 1000 baris sekaligus |
| **Payload** | Respons ringkas; jangan kirim field rahasia (`password_hash`) | bocor field sensitif |
| **Debounce** | Search/autosuggest di-debounce (300 ms) | request tiap ketukan |

**Target kasar (MVP):** list endpoint < 300 ms pada data seed; peta live render < 1 dtk; tidak ada query unbounded.

---

## 4. KUALITAS & KERINGKASAN KODE (anti "muter-muter")
- **Tulis sependek mungkin yang tetap jelas.** Hapus kode mati, komentar usang, dan abstraksi prematur.
- **Early-return** alih-alih nested if dalam. Fungsi fokus, nama deskriptif.
- **Tanpa `console.log`/`print` debug** tertinggal (`validate_compliance.py` CHECK 2).
- **Tanpa TODO/FIXME baru** yang dibiarkan (tech-debt). Bila tak sempat → catat di `01_PRD.md` backlog, jangan diam-diam.
- **Reuse sebelum tulis baru**: cek `10_CODEBASE_MAP.md` + `preflight.py`.
- **Defensif**: `.get()` + guard `Array.isArray` + `safe_doc()`.

---

## 5. MINIMALKAN TECH-DEBT
- Tiap fitur baru WAJIB mendaftarkan dirinya ke gate terkait (lihat doc 07 §7) — guardrail tumbuh bersama kode.
- Refactor file yang melewati batas ukuran **segera**, jangan ditunda.
- Satu sumber kebenaran: izin (`permissions_config.py`), nav (`navigationConfig.js` ↔ `05_NAVIGATION_MAP.md`), data (`03_DATA_MODEL.md`).
- Dependency baru = **STOP & ASK** (doc 11 §4). Jangan tambah library untuk hal yang bisa diselesaikan ringkas.

---

## 6. INFORMATION ARCHITECTURE (IA)
- **Dua surface terpisah** (`data-surface=public|app`) — jangan campur navigasi/visual.
- **App (ERP)**: navigasi berkelompok & role-filtered → *Operasional* (Dashboard, Bookings, GPS), *Master Data* (Vehicles, Drivers, Customers), *CRM*, *Keuangan*, *Sistem* (Users, Settings). Maks kedalaman 2 level.
- **Public**: alur konversi jelas → Home → Fleet/Destinations → Trip Calculator → Quotation (lead) → ThankYou.
- **Konsistensi**: 1 konsep = 1 istilah (lihat glosarium koleksi kanonik). Hindari sinonim membingungkan.
- **Wayfinding**: breadcrumb bila > 2 level; active state jelas; empty state mengarahkan ke aksi.
- SSOT IA = `05_NAVIGATION_MAP.md`. Menu di luar map = **STOP & ASK** (cegah "menu liar", `check_nav_map.py`).

---

## 7. TECH STACK HARUS MENDUKUNG TUJUAN
| Kebutuhan | Pilihan | Alasan |
|-----------|---------|--------|
| Realtime peta gratis | **Leaflet + OSM**, ETA **OSRM** | gratis, swappable ke Google Maps (AD-4) |
| Async I/O DB | **Motor** | non-blocking, cocok polling/realtime |
| Validasi & kontrak | **Pydantic** | response model, kurangi drift |
| UI konsisten & cepat | **shadcn/ui + Tailwind** | komponen teruji, a11y, tokenized |
| Chart | **Recharts** | ringan, cukup utk dashboard MVP |
| Export | **reportlab/openpyxl** (BE) | tak bergantung browser |

---

## 8. KETERKAITAN DENGAN REVAMP (penting)
Arsitektur ini **mengasumsikan revamp akan terjadi** tiap fase. Karena itu:
- Modular & adapter-based (map, realtime, export) → ganti implementasi tanpa rewrite besar.
- Gate + invarian + receipt → revamp aman (regresi langsung ketahuan).
- Kontrak API stabil → FE & BE bisa di-revamp independen selama kontrak dijaga.
