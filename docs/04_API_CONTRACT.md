# 04 — API CONTRACT (Canonical)
## Travel & Fleet Management Ecosystem

> Kontrak yang **diverifikasi**, bukan diasumsikan. Bila kode ≠ dokumen → kode menang, perbaiki dokumen.

---

## 1. ATURAN UMUM
- Semua endpoint berprefiks **`/api`**.
- **Auth**: `POST /api/auth/login {email,password}` → `{"token":"sess_...","user":{...}}`. Field token = **`token`**. Header: `Authorization: Bearer sess_...`.
- **List endpoint** → **ARRAY langsung** `[...]`. **Detail/dashboard** → **objek langsung**. TANPA envelope `{success,data}`/`{items,total}`.
- **Serialisasi** lewat `safe_doc()` (tanpa `_id`, datetime→ISO string).
- **Error**: HTTP 4xx untuk validasi/izin (pesan jelas), 5xx HARUS 0 (gate sweep).
- **RBAC**: `require_role`/`require_permission`; matrix di `permissions_config.py`.

---

## 2. ENDPOINTS (per modul — target)

### Auth & Users
```
POST /api/auth/login            → {token,user}
GET  /api/auth/me               → user (objek)
POST /api/auth/logout
GET  /api/users                 → [user]            (owner)
POST /api/users                 → user              (owner)
PATCH/api/users/{id}            → user              (owner)
```
### Master Data
```
GET/POST /api/vehicles ; PATCH/DELETE /api/vehicles/{id} ; GET /api/vehicles/{id}
GET/POST /api/drivers  ; PATCH/DELETE /api/drivers/{id}
GET/POST /api/customers; PATCH /api/customers/{id} ; GET /api/customers/{id}  (Customer 360)
```
### Bookings & Trips
```
GET  /api/bookings                       → [booking]   (filter: status,date,vehicle)
POST /api/bookings                       → booking     (availability check → 400 bila overlap)
GET  /api/bookings/{id}                   → booking
PATCH/api/bookings/{id}
POST /api/bookings/{id}/confirm | /cancel | /complete
GET  /api/bookings/calendar?month=YYYY-MM → [booking ringkas: code, customer_name, vehicle_id,
                                            vehicle_name, driver_id, driver_name, start/end_datetime,
                                            status, payment_status, hold_expires_at, source,
                                            requested_vehicle_type, pax]
GET  /api/bookings/calendar/export?month=YYYY-MM|start&end[&group=vehicle]&format=pdf|excel
GET  /api/departures/attention?month=YYYY-MM            # E27 lapisan risiko kalender
GET  /api/departures/attention?start=YYYY-MM-DD&end=YYYY-MM-DD
     → {period:{start,end,label},
        summary:{total,high,medium,by_type:{<risk_type>:n}},
        meta:[{type,label,severity}],
        items:[{booking_id,code,status,payment_status,customer_name,vehicle_id,vehicle_name,
                driver_name,start_datetime,end_datetime,source,severity,risk_types[],
                risks:[{type,label,severity,message,related:[{id,code}]}]}]}
     # 8 kelas risiko: vehicle_conflict | driver_conflict | maintenance_conflict | hold_expired |
     #                 hold_expiring | no_driver | pending_request | unpaid_soon
     # Sumber tunggal (server-side) — FE TIDAK menghitung ulang bentrok.
GET  /api/bookings/availability?vehicle_id&start&end → {available:bool, conflicts:[]}
GET  /api/trips ; GET /api/trips/{id} ; POST /api/trips/{id}/status
```
### GPS / Locations
```
POST /api/locations                      ← driver kirim {trip_id,lat,lng,speed,heading}
GET  /api/locations/live                  → [posisi terbaru per vehicle/driver]
GET  /api/trips/{id}/track                → [locations] (polyline history)
GET  /api/trips/{id}/eta?dest_lat&dest_lng→ {eta_minutes, distance_km} (OSRM)
POST /api/driver/checkin | /checkout
```
### CRM
```
# IMPLEMENTED (Phase 4):
GET/POST /api/leads ; PATCH /api/leads/{id} ; POST /api/leads/{id}/assign ; POST /api/leads/{id}/stage
POST /api/leads/{id}/activities ; POST /api/leads/{id}/convert ; GET /api/leads/pipeline ; GET /api/leads/reminders ; GET /api/leads/agents
GET/POST /api/broadcasts ; POST /api/broadcasts/{id}/send        (WA = SIMULASI)
# TARGET (Inbox — BELUM diimplementasi; lihat plan.md §0.5-C):
GET  /api/conversations ; GET /api/conversations/{id}/messages ; POST /api/conversations/{id}/messages
GET/POST /api/notification-tasks
```
### Finance (IMPLEMENTED — Phase 5)
```
GET/POST /api/payments (per booking) ; GET/POST /api/expenses
GET/POST /api/invoices ; GET /api/invoices/{id} ; PATCH /api/invoices/{id} (status) ; GET /api/invoices/{id}/export?format=pdf|excel
GET /api/finance/profit-loss?period=YYYY-MM ; GET /api/finance/ar ; GET /api/finance/summary
GET /api/reports/summary?period= ; GET /api/reports/export?format=excel
# Rekap Payroll di Laporan (E12):
GET /api/reports/payroll?period=                   # rekap payroll periode (by_status, total_*, per_driver+ytd, sdm_vs_revenue)
GET /api/reports/payroll/export?format=pdf|excel&period=   # export rekap payroll (reportlab/openpyxl)
# Laporan Driver Leaderboard + Revenue-per-Trip (E13):
GET /api/reports/drivers?period=                   # {period, fleet{trips,completed,completion_rate,km,revenue,revenue_per_trip,avg_km_per_trip,active_drivers}, drivers[{rank,driver_id,driver_name,trips,completed,completion_rate,km,revenue,revenue_per_trip,avg_km_per_trip}]}
GET /api/reports/drivers/export?format=pdf|excel&period=   # export laporan driver (reportlab/openpyxl)
GET /api/reports/hold-expired?days=30              # laporan "hold hangus": {summary{count,potential_value,dp_value,with_proof,recovered,holds_started,expiry_rate,avg_hold_hours}, by_vehicle[], by_service[], daily[], rows[], insights[]}
GET /api/reports/hold-expired/export?days=30       # CSV (UTF-8 BOM, pemisah ';') untuk tindak lanjut ops
# Catatan: /api/reports/summary juga memuat key 'payroll' (E12) & 'drivers_report' (E13).
# Finance Automation (E5):
GET /api/finance/pl-full?period=YYYY-MM            # P&L komprehensif (revenue - opex - maintenance) total + per_unit (G4)
GET /api/finance/reconciliation                    # rekonsiliasi invoice↔pembayaran + summary (G5)
POST /api/finance/reconciliation/sync              # selaraskan invoices.status (paid/partial/sent), idempotent
GET /api/finance/cashflow?months=6&horizon=3       # arus kas bulanan + proyeksi moving-average
GET /api/finance/ar/overdue                        # AR jatuh tempo (age_days) kandidat reminder
POST /api/finance/ar/{booking_id}/remind           # reminder WA (emit invoice.overdue→automation→WA mock)
POST /api/finance/ar/remind-all                    # reminder massal untuk semua AR overdue
GET /api/finance/export?format=pdf|excel&period=   # laporan keuangan (reportlab/openpyxl)
```
### Finance
```
# Lihat blok "Finance (IMPLEMENTED — Phase 5)" di atas (§CRM) untuk daftar lengkap & terkini.
```
### Dashboard, Reports, Maintenance, Public, Settings
```
GET /api/dashboard                       → metrics (objek; role-aware)              [IMPLEMENTED]
GET /api/reports/summary ; /api/reports/export?format=excel                          [IMPLEMENTED Phase 5]
GET/POST /api/maintenance-records ; GET /api/maintenance/due                          [TARGET — Phase 6, belum]
GET /api/public/destinations ; /api/public/destinations/{slug}                        [IMPLEMENTED]
    → detail fields [P10/FASE 3]: intro, highlights[], itinerary[]({day,title,detail}),
      route_points[]({name,lat,lng,note}), faqs[]({q,a}), best_time, lat, lng, tour_scenes[]
GET /api/public/fleet ; /api/public/fleet/{id}                                        [IMPLEMENTED]
    → fields publik: id,code,name,type,capacity,features[],photos[],
      gallery[]({url,caption}), tour_scenes[]({id,label,panorama,thumbnail,links[]}),
      specs[]({key,label,value}), highlights[], year, color, price_from, status   [P10/FASE 2]
GET /api/public/articles ; /api/public/articles/{slug}                                [IMPLEMENTED]
    → list = published saja; fields [P10/FASE 4]: category, featured, read_minutes,
      author, excerpt, cover_image, tags[], published_at
GET /api/public/testimonials ; /api/public/company                                    [IMPLEMENTED]
GET /api/public/theme                    → {preset, mode}          [no auth]          [IMPLEMENTED P10/FASE 1]
GET /api/public/stats                    → {stats:[{key,label,value,suffix,decimals}]} [IMPLEMENTED P10/FASE 1]
POST/api/public/quotation                ← form lead (buat leads) + attribution+consent (E-ADS) [no auth] [IMPLEMENTED]
POST/api/public/lead-ads/{provider}      ← webhook Lead Ads meta|google|tiktok (mock) → lead ber-atribusi [no auth] [IMPLEMENTED E-ADS]
POST/api/public/trip-estimate            → {breakdown, total}      [no auth]          [IMPLEMENTED]
GET/PUT /api/settings/{key}              (owner)                                       [TARGET — belum]
```

### Pricing Engine (IMPLEMENTED — Phase 9 / B1)
```
GET /api/settings ; PATCH /api/settings   (key `pricing_rules` ditambah; owner)        [IMPLEMENTED]
GET  /api/pricing/rules                   → aturan harga aktif (DB+default)  (auth)     [IMPLEMENTED]
POST /api/pricing/quote {vehicle_id|vehicle_type,days,distance_km,start_date}
     → {breakdown[],subtotal,surcharge_percent,total,dp_percent,dp_amount,days}  (auth) [IMPLEMENTED]
POST /api/public/trip-estimate            → rincian dari Pricing Engine (no auth)       [IMPLEMENTED]
# Booking auto-base: POST /api/bookings dgn base_price≤0 → harga dihitung dari pricing_rules.
```

### Quotation Lifecycle (IMPLEMENTED — Phase 9 / B2, section RBAC 'crm')
```
GET  /api/quotations[?status=&lead_id=&q=]   → daftar penawaran                         [IMPLEMENTED]
POST /api/quotations {lead_id?|customer*, vehicle_type,days,distance_km, items?, valid_days}
     → buat penawaran (items auto dari Pricing Engine bila kosong); status 'draft'       [IMPLEMENTED]
GET   /api/quotations/{id}                    → detail                                   [IMPLEMENTED]
PATCH /api/quotations/{id}                    → ubah (draft/sent)                        [IMPLEMENTED]
POST  /api/quotations/{id}/send               → status 'sent'                            [IMPLEMENTED]
POST  /api/quotations/{id}/accept             → status 'accepted'                        [IMPLEMENTED]
POST  /api/quotations/{id}/reject             → status 'rejected'                        [IMPLEMENTED]
POST  /api/quotations/{id}/convert {vehicle_id,driver_id?,start,end}
      → buat booking (base_price=total) + customer dedupe; lead→won; INV-19 anti-double  [IMPLEMENTED]
GET   /api/quotations/{id}/pdf                → unduh penawaran PDF (reportlab)          [IMPLEMENTED]
```

### Light CMS (IMPLEMENTED — Phase 9 / B3, section RBAC 'cms')
```
# Generik utk resource ∈ {destinations, packages, articles, testimonials, promos}
GET    /api/content/{resource}                → daftar semua item (admin)               [IMPLEMENTED]
POST   /api/content/{resource}                → buat (whitelist field, ko-ersi tipe)    [IMPLEMENTED]
PUT    /api/content/{resource}/{id}           → ubah                                     [IMPLEMENTED]
DELETE /api/content/{resource}/{id}           → hapus                                    [IMPLEMENTED]
# Read publik (active only utk packages/promos):
GET    /api/public/packages ; GET /api/public/promos                                     [IMPLEMENTED]
```

### Identity & Dedupe + Contact 360 (IMPLEMENTED — Phase 9 / B4)
```
# Normalisasi +62 (services.identity.normalize_phone) dipakai lintas modul.
POST /api/customers            → DEDUPE: 409 bila nomor/email sudah terdaftar; set phone_normalized [IMPLEMENTED]
GET  /api/customers/{id}       → Contact 360: profil + bookings + leads + quotations + conversations
                                  + timeline terpadu + stats (by id ATAU phone_normalized)            [IMPLEMENTED]
POST /api/leads                → auto-link ke customer existing (linked_customer_id) bila nomor cocok  [IMPLEMENTED]
POST /api/leads/{id}/convert   → ensure_customer (dedupe-or-create), set converted+linked_customer_id  [IMPLEMENTED]
POST /api/quotations/{id}/convert → konversi pakai ensure_customer (dedupe)                            [IMPLEMENTED]
```

### Event Bus · Automation Engine · WhatsApp Adapter (IMPLEMENTED — E1, section RBAC 'automation')
```
# Otomasi (owner/ops_admin). Event domain → rules (kondisi→aksi) idempotent + audit.
GET    /api/automation/event-types          → katalog event + jenis aksi (utk rule-builder)        [IMPLEMENTED]
GET    /api/automation/stats                 → KPI (rules_active, runs_today, wa_sent, wa_cost, ...)  [IMPLEMENTED]
GET    /api/automation/rules                  → list aturan (filter event_type/enabled)              [IMPLEMENTED]
POST   /api/automation/rules                  → buat aturan {name,event_type,conditions[],actions[]} [IMPLEMENTED]
GET    /api/automation/rules/{id}             → detail aturan                                         [IMPLEMENTED]
PATCH  /api/automation/rules/{id}             → ubah/enable-disable aturan                            [IMPLEMENTED]
DELETE /api/automation/rules/{id}             → hapus aturan                                          [IMPLEMENTED]
POST   /api/automation/rules/reset-defaults   → pasang ulang 8 aturan sistem (owner)                  [IMPLEMENTED]
GET    /api/automation/runs                   → log eksekusi (filter rule_id/status/event_type)       [IMPLEMENTED]
GET    /api/automation/events                 → event stream (filter type)                            [IMPLEMENTED]

# WhatsApp Adapter (provider-agnostic; mock aktif, meta_cloud stub E6). Webhook PUBLIK.
GET    /api/wa/config                          → konfigurasi WA (owner; rahasia di-mask)              [IMPLEMENTED]
PATCH  /api/wa/config                          → ubah provider/biaya/sesi/auto-reply/meta (owner)     [IMPLEMENTED]
GET    /api/wa/templates                        → daftar template                                     [IMPLEMENTED]
PUT    /api/wa/templates/{key}                  → upsert template (owner)                              [IMPLEMENTED]
DELETE /api/wa/templates/{key}                  → hapus template (owner)                               [IMPLEMENTED]
POST   /api/wa/simulate-inbound                 → simulasi pesan WA masuk (mock, owner/ops)            [IMPLEMENTED]
POST   /api/wa/test-send                         → kirim pesan tes via provider aktif (owner; E6 prep)  [IMPLEMENTED]
GET    /api/wa/webhook                           → verifikasi Meta (hub.challenge) — PUBLIK            [IMPLEMENTED]
POST   /api/wa/webhook                           → ingest pesan inbound (signature verify) — PUBLIK    [IMPLEMENTED]

# Inbox WA real-ready (extend section 'crm'):
POST   /api/conversations/{id}/messages         → kanal whatsapp → kirim via provider (cost/status); {template_key?} [IMPLEMENTED]
POST   /api/conversations/{id}/wa-optout|wa-optin → opt-out / opt-in WhatsApp                          [IMPLEMENTED]

### Dispatch & Komunikasi Operasi (IMPLEMENTED — E3, section RBAC 'dispatch')
# Ops Cockpit "Hari Ini" + assign+geocode + status driver→customer (WA via Event Bus) + POD lokal.
GET    /api/dispatch/today?date=YYYY-MM-DD       → {date, summary{...}, departures[]}                  [IMPLEMENTED]
POST   /api/dispatch/{booking_id}/assign         → {driver_id,vehicle_id} → trip standby + geocode tujuan + trip.assigned [IMPLEMENTED]
POST   /api/dispatch/{booking_id}/confirm-departure → booking.departure_confirmed (WA)                 [IMPLEMENTED]
POST   /api/dispatch/trips/{trip_id}/enroute     → trip to_pickup + trip.enroute (WA)                  [IMPLEMENTED]
POST   /api/dispatch/trips/{trip_id}/arrived     → trip arrived + trip.arrived (WA)                    [IMPLEMENTED]
POST   /api/dispatch/trips/{trip_id}/pod         → multipart(photo,recipient_name,note) → trip.pod (lokal /api/uploads) [IMPLEMENTED]

### BI & Management Cockpit (IMPLEMENTED — E4, section RBAC 'analytics')
# Read-only agregasi (services/analytics.py). Rentang via ?days=N atau ?start&end. Respons OBJEK/ARRAY telanjang.
GET    /api/analytics/summary    ?days|start&end → {range, metrics{revenue/profit/... :{value,prev,delta_pct}, outstanding_ar}} [IMPLEMENTED]
GET    /api/analytics/funnel                      → {range, stages[Lead/Kontak/Penawaran/Menang], overall_conversion} [IMPLEMENTED]
GET    /api/analytics/channels                    → {channels[{leads,won,revenue,spend,cpl,cac,roas}], totals} (ad-spend manual) [IMPLEMENTED]
GET    /api/analytics/fleet                       → {vehicles[{trips,revenue,expenses,profit,roi_pct}], active/idle} [IMPLEMENTED]
GET    /api/analytics/drivers                     → {drivers[{trips,completed,completion_rate,revenue,distance_km}]} [IMPLEMENTED]
GET    /api/analytics/ar-aging                    → {total_outstanding, buckets[belum/0-30/31-60/61-90/90+]} (Σ==outstanding) [IMPLEMENTED]
GET    /api/analytics/retention                   → {repeat_rate, returning/new/one_time, by_rfm[], by_lifecycle[]} [IMPLEMENTED]
GET    /api/analytics/forecast   ?metric=revenue  → {method:moving_average, history[], forecast[]}      [IMPLEMENTED]
GET    /api/analytics/ad-spend                     → {items[{channel,amount}], spend_map} (settings.marketing_spend) [IMPLEMENTED]
PUT    /api/analytics/ad-spend                     → {items[],note} upsert ad-spend per channel          [IMPLEMENTED]
GET    /api/analytics/export     ?format=pdf|excel → unduh cockpit (reportlab/openpyxl)                  [IMPLEMENTED]
```

---

## 3. CONTOH KONTRAK RESPONS
```jsonc
// GET /api/bookings  → ARRAY langsung
[{ "id":"bk_a1", "code":"BK-0001", "customer_name":"PT X", "vehicle_name":"Hiace Premio 01",
   "start_datetime":"2026-07-01T07:00:00Z", "total_amount":3500000, "paid_amount":1000000,
   "payment_status":"dp", "status":"confirmed" }]

// POST /api/auth/login → objek
{ "token":"sess_xxx", "user":{"id":"usr_1","name":"Owner","role":"owner"} }
```

> Tambah endpoint ⇒ update dokumen ini + `health_check.CRITICAL_ENDPOINTS` (bila kritis) + binding `verify_api_contract` (bila FE membaca field baru).

---

## 4. ENDPOINT MARKETING & ADS (FASE F3–F7)

Semua endpoint di bawah **tidak pernah 5xx saat kredensial kosong**; jawabannya
`{"status":"not_configured","reason":"<alasan Bahasa Indonesia>"}` (INV-5XX-01), dan semua
penulisan ke platform melewati `services/ads_safety.py` (INV-ADS-01).

| Method | Path | RBAC | Fungsi |
|--------|------|------|--------|
| GET | `/api/ads/overview` | section `ads` (owner/ops_admin/marketing_admin) | Ringkasan dashboard: performa per entitas (biaya platform ⨯ booking ERP), seri harian, kesiapan, riwayat tarikan, biaya manual |
| GET | `/api/ads/entities` | section `ads` | Daftar kampanye/adset/iklan hasil sinkron |
| GET | `/api/ads/accounts` | section `ads` | Metadata akun iklan (currency/timezone) + kesiapan |
| POST | `/api/ads/sync` | owner/marketing_admin | Tarik metrik Meta Insights + Google GAQL (idempoten per hari) |
| PUT | `/api/ads/manual-spend` | owner/marketing_admin | Biaya iklan manual per channel (sumber cadangan) |
| GET | `/api/ads/platform-leads` | section `ads` | Lead mentah dari platform + status pengambilan isi form |
| POST | `/api/ads/platform-leads/simulate` | owner/marketing_admin | Simulasi webhook Lead Ads bertanda tangan (uji tanpa kredensial) |
| POST | `/api/ads/platform-leads/backfill` | owner/marketing_admin | Ambil ulang lead per `form_id` (jaring pengaman webhook) |
| GET | `/api/public/webhooks/meta/leads` | **PUBLIK** (allowlist) | Verifikasi langganan webhook (`hub.challenge`) |
| POST | `/api/public/webhooks/meta/leads` | **PUBLIK** (allowlist) | Callback Lead Ads — wajib lolos HMAC `X-Hub-Signature-256`, dedup `leadgen_id` |
| GET | `/api/ads/audiences` | section `ads` | Daftar segmen CRM + riwayat sinkron audiens |
| POST | `/api/ads/audiences/preview` | section `ads` | Hitung anggota: layak kirim vs tersaring consent |
| POST | `/api/ads/audiences/sync` | owner/marketing_admin | Segmen → Custom Audience (Meta) / Customer Match (Google); mode `validate`/`publish` |
| POST | `/api/ads/audiences/lookalike` | owner/marketing_admin | Lookalike Audience dari audiens sumber (min. 100 kontak) |
| POST | `/api/ads/campaigns/validate` | owner/marketing_admin | Langkah 1: platform memvalidasi payload (`validate_only`) — tanpa objek & tanpa biaya |
| POST | `/api/ads/campaigns/publish` | owner/marketing_admin | Langkah 2: buat objek NYATA status **PAUSED**; wajib `confirm_name` = nama kampanye |
| POST | `/api/ads/campaigns/status` | owner/marketing_admin | Jeda / aktifkan; `ACTIVE` wajib `confirm_name` |
| POST | `/api/ads/campaigns/budget` | owner/marketing_admin | Ubah budget harian; wajib `confirm_name` + di bawah plafon ERP |
| POST | `/api/tracking/dispatch` | owner/marketing_admin | Jalankan pekerja outbox konversi sekarang (normalnya otomatis tiap 2 menit) |
| GET | `/api/tracking/health?status=&provider=` | section `tracking` | Ringkasan + daftar percobaan konversi (bisa difilter) + status pekerja |

### Landing Page Builder + Media Library (IMPLEMENTED — Fase F8, section RBAC 'landing' = owner + marketing_admin)
```
# ---- Editor (butuh login; ops_admin & driver -> 403) ----
GET    /api/landing/templates                     → 8 template + block_types + theme_presets
                                                    + conversion_blocks + ab_override_fields      [IMPLEMENTED]
GET    /api/landing/pages?segment=&status=&q=      → daftar + stats{views,cta_clicks,leads}
                                                    + ab_enabled (tanpa blocks, ringan)           [IMPLEMENTED]
POST   /api/landing/pages {template,title?,slug?}  → buat dari template (slug dibuat unik otomatis)[IMPLEMENTED]
GET    /api/landing/pages/{id}                     → detail + media terpakai + publish_errors
                                                    + ab + public_url                             [IMPLEMENTED]
PATCH  /api/landing/pages/{id}                     → title/slug/segment/theme/seo/tracking/
                                                    blocks/ab → {page,warnings,publish_errors}    [IMPLEMENTED]
POST   /api/landing/pages/{id}/publish {unpublish?} → terbit / tarik. 400 + alasan bila belum
                                                    layak (INV-LP-01)                             [IMPLEMENTED]
POST   /api/landing/pages/{id}/duplicate {title?}   → DRAF baru, slug unik, statistik TIDAK dibawa [IMPLEMENTED]
GET    /api/landing/pages/{id}/ab?since=            → laporan A/B per varian + winner +
                                                    winner_reason + uplift_percent + enough_data  [IMPLEMENTED]
GET    /api/landing/pages/{id}/leads                → lead yang masuk dari halaman ini            [IMPLEMENTED]
DELETE /api/landing/pages/{id}                      → hapus halaman + statistiknya                [IMPLEMENTED]

# ---- Media Library (INV-MEDIA-01/02) ----
GET    /api/landing/media?q=&kind=image|video       → aset + counts + storage{backend,ready,
                                                    reason,max_image_mb,max_video_mb,used_mb}     [IMPLEMENTED]
POST   /api/landing/media  (multipart: file, alt?)  → unggah. 400 berALASAN bila MIME/ukuran
                                                    salah atau penyimpanan belum siap            [IMPLEMENTED]
PATCH  /api/landing/media/{id} {alt}                → ubah teks alternatif (SEO/aksesibilitas)    [IMPLEMENTED]
DELETE /api/landing/media/{id}                      → soft-delete + used_by_pages (peringatan)    [IMPLEMENTED]

# ---- Publik (TANPA auth — halaman iklan tidak login) ----
GET    /api/public/landing/{slug}?vid=&variant=      → hanya status=published (draf -> 404);
                                                    blok hidden tidak dikirim; varian A/B dipilih
                                                    DETERMINISTIK dari vid; `variant` memaksa
                                                    versi tertentu untuk pratinjau                [IMPLEMENTED]
POST   /api/public/landing/{slug}/lead              → lead CRM ber-atribusi + emit lead.created
                                                    (memicu outbox konversi). Idempoten per
                                                    (halaman+telepon+hari) via unique index.
                                                    400 tanpa consent / nomor tak valid;
                                                    honeypot `hp` -> 200 tanpa tulis DB;
                                                    rate limit 30/menit/IP (CGNAT-aware)          [IMPLEMENTED]
POST   /api/public/landing/{slug}/track             → {type:view|cta_click, variant_id} ->
                                                    agregat harian; type lain -> 400              [IMPLEMENTED]
GET    /api/public/media/{id}?thumb=1               → sajikan berkas (read-only, cache 1 hari);
                                                    aset soft-deleted -> 404                      [IMPLEMENTED]
```

---

## 5. ENDPOINT PEMESANAN ONLINE V1 (2026-08-12)

**Aturan yang berlaku untuk SELURUH permukaan ini** (ditegakkan guardrail, bukan konvensi):
harga **selalu** dihitung server — tak satu pun skema permintaan punya field harga
(**INV-BOOK-02**); nominal = integer rupiah; input rusak → **4xx berALASAN** (Bahasa
Indonesia), **tidak pernah 5xx** (INV-5XX-01); teks berbatas panjang (INV-STR-01); endpoint
publik ber-rate-limit per IP dengan ambang yang memperhitungkan CGNAT operator seluler
Indonesia (pengunjung berbagi IP — ambang terlalu ketat menolak pelanggan SAH).

### 5.1 Publik (tanpa login)

| Method | Path | Fungsi |
|--------|------|--------|
| GET | `/api/public/booking/config` | Layanan aktif, tipe unit + harga mulai, rute antar-jemput, `dp_percent`, `mode`, `hold_hours`, kebijakan & ketentuan |
| POST | `/api/public/booking/search` | Cari unit **yang benar-benar bebas** pada rentang waktu → `options[]{vehicle, quote}` + `unavailable[]{…, reason}`. Bentrok = booking aktif atau jendela perawatan |
| POST | `/api/public/booking/quote` | Rincian harga satu unit (langkah tinjau) + validasi `promo_code` |
| POST | `/api/public/booking/promos` | **Daftar promo aktif + kelayakannya** untuk konteks pesanan (`service`, `vehicle_id`, tanggal, `route_id`). Subtotal DIHITUNG ULANG server — klien tidak boleh mengirim angka harga. Respons: `promos[]{code,title,terms[],eligible,discount,reason}` + `eligible_count` |
| POST | `/api/public/booking/submit` | **Buat pesanan** → `{code, token, status, total_amount, dp_amount, hold_expires_at, message}`. `idempotency_key` → klik ganda = 1 pesanan |
| GET | `/api/public/booking/{code}?token=` | Status pesanan + rincian harga + instruksi DP + `countdown_seconds` + riwayat bukti |
| POST | `/api/public/booking/lookup` | Cari pesanan dengan **kode + nomor WhatsApp** (tanpa token) |
| POST | `/api/public/booking/{code}/proof` | **multipart** — unggah bukti transfer (`image`, `token`, `amount`, `sender_name`, `bank`) → masuk Media Library + antrean verifikasi |
| POST | `/api/public/booking/{code}/cancel` | Batalkan pesanan yang belum dikonfirmasi (butuh `token`) |
| POST | `/api/public/booking` | (lama, tetap) permintaan penawaran tanpa unit → booking `pending` + lead CRM |

### 5.2 ERP — verifikasi DP & persetujuan

| Method | Path | RBAC | Fungsi |
|--------|------|------|--------|
| GET | `/api/bookings/payment-proofs?status=` | section `finance` (owner/ops_admin) | Antrean bukti transfer + ringkasan booking terkait |
| POST | `/api/bookings/{id}/proofs/{proof_id}/verify` | section `finance` | Sahkan bukti → `payments` lewat jalur resmi (idempoten `proof:{id}`) → DP cukup ⇒ `hold` **otomatis** `confirmed`. Nominal > sisa tagihan → 400 |
| POST | `/api/bookings/{id}/proofs/{proof_id}/reject` | section `finance` | Tolak + alasan (tampil di halaman status tamu, tamu boleh unggah ulang) |
| POST | `/api/bookings/{id}/approve-hold` | owner/ops_admin | Mode `ops_approval`: setujui permintaan web → `pending` → `hold` + DP diminta (harga dihitung ulang, di dalam mutex + cek bentrok) |

### 5.3 ERP — rute antar-jemput (master data tarif flat)

| Method | Path | RBAC | Fungsi |
|--------|------|------|--------|
| GET | `/api/transfer-routes` | login | Daftar rute (publik hanya yang `active`) |
| POST | `/api/transfer-routes` | owner/ops_admin | Tambah rute + `rates{vehicle_type: rupiah}` |
| PATCH | `/api/transfer-routes/{id}` | owner/ops_admin | Ubah rute/tarif/status aktif |
| DELETE | `/api/transfer-routes/{id}` | owner/ops_admin | Hapus rute (ditolak bila masih dipakai booking aktif) |

### 5.4 Contoh kontrak respons `POST /api/public/booking/search`

```json
{
  "count": 2, "checked": 3,
  "options": [{
    "vehicle": {"id":"veh_…","code":"V-02","name":"Hiace Premio 02","type":"hiace_premio",
                "type_label":"Hiace Premio","capacity":14,"photos":["…"],
                "day_rate":1650000,"price_from":1650000,"rate_basis":"unit"},
    "quote": {"breakdown":[{"label":"Sewa unit (2 hari)","amount":3300000},
                            {"label":"Jasa driver (2 hari)","amount":500000},
                            {"label":"Tol & parkir (estimasi)","amount":400000}],
              "subtotal":4200000,"surcharge_percent":0,"discount":0,
              "total":4200000,"dp_percent":30,"dp_amount":1260000,"days":2},
    "available": true
  }],
  "unavailable": [{"code":"V-01","name":"Hiace Premio 01","reason":"Sudah dipesan pada tanggal itu"}]
}
```

---

## 6. ENDPOINT CMS-CW2 (CMS-05…CMS-09 + defect A1–A3) — 2026-08-17

### Admin — siklus terbit, dua bahasa, analitik (section RBAC `cms`)
```
GET    /api/content/{resource}?status=draft|scheduled|published|all&q=&limit=&offset=
                                              → daftar + `status` & `effective_status` per item
                                                (X-Total-Count/X-Limit/X-Offset)          [IMPLEMENTED]
POST   /api/content/{resource}                → body menerima `status`, `publish_at`,
                                                `translations{en:{…}}`                     [IMPLEMENTED]
PUT    /api/content/{resource}/{id}           → idem (status 'scheduled' TANPA publish_at → 400) [IMPLEMENTED]
POST   /api/content/{resource}/{id}/duplicate → salinan SELALU mulai sebagai draft        [IMPLEMENTED]
POST   /api/content/{resource}/{id}/preview-token
                                              → {token, url, path, expires_at, status}
                                                token 24 jam, hanya membuka 1 dokumen      [IMPLEMENTED]
POST   /api/content/{resource}/translate      → SARAN terjemahan (tidak menyimpan).
                                                AI OFF (keputusan pemilik) → 503 berpesan
                                                "isi manual tetap bisa"                    [IMPLEMENTED]
GET    /api/content/meta/i18n                 → {langs[], default, translatable{}, ai_available} [IMPLEMENTED]
GET    /api/content/meta/promo-options        → {vehicle_types[], services[]} (SSOT: pricing +
                                                booking_flow — FE tidak hardcode enum)     [IMPLEMENTED]
GET    /api/content/analytics/top?limit=      → {overview{tracked,views,leads,bookings,revenue},
                                                rows[{kind,kind_label,slug,title,path,views,
                                                leads,lead_rate,bookings,revenue,last_view_at}],
                                                kinds[]}                                   [IMPLEMENTED]
```

### Admin — funnel ulasan (CMS-07, section RBAC `cms`)
```
GET  /api/reviews/summary            → {count, average, total_published, pending, requests,
                                        submitted, waiting, response_rate, channel}        [IMPLEMENTED]
GET  /api/reviews/requests?status=&limit=&offset=  → daftar permintaan (X-Total-Count)      [IMPLEMENTED]
GET  /api/reviews/eligible-bookings?limit=        → pesanan `completed` yang belum diminta  [IMPLEMENTED]
POST /api/reviews/requests           → {booking_id} → buat/kirim ulang tautan (WA MOCK)     [IMPLEMENTED]
GET  /api/reviews/pending?limit=     → testimoni `approved=false` (antrean moderasi)        [IMPLEMENTED]
POST /api/reviews/{testimonial_id}/moderate → {action: approve|reject, note?}               [IMPLEMENTED]
```

### Publik (tanpa auth)
```
GET  /api/public/packages?lang=id|en&limit=            → hanya yang TAYANG                  [IMPLEMENTED]
GET  /api/public/packages/{slug}?lang=&preview=<token> → 404 bila draft tanpa token;
                                                          `preview:true` + `status` bila token sah [IMPLEMENTED]
GET  /api/public/destinations[/{slug}]?lang=&preview=  → idem                                [IMPLEMENTED]
GET  /api/public/articles[/{slug}]?lang=&preview=      → idem (body HTML sudah tersanitasi)  [IMPLEMENTED]
GET  /api/public/promos?lang=                          → promo aktif + `terms[]` (syarat
                                                         dirangkai dari DATA) + `quota_left`,
                                                         `sold_out`; `used_count`/`id` TIDAK dibocorkan [IMPLEMENTED]
GET  /api/public/testimonials ; GET /api/public/testimonials/summary → agregat rating         [IMPLEMENTED]
POST /api/public/content-view        → {kind, slug, title, path} hitung tampilan
                                       (dedupe 1 IP / 30 menit; IP tidak disimpan)          [IMPLEMENTED]
GET  /api/public/reviews/{token}     → konteks pesanan untuk halaman ulasan                  [IMPLEMENTED]
POST /api/public/reviews/{token}     → {rating 1–5, quote ≥10 char, name?, role?, consent}
                                       → testimoni `approved=false`; token sekali pakai      [IMPLEMENTED]
GET  /api/sitemap.xml                → memuat /packages & /promo + `xhtml:link` hreflang
                                       (id / en / x-default) untuk konten berterjemahan      [IMPLEMENTED]
```

### Catatan kontrak
- `?lang=` dikirim OTOMATIS oleh `services/apiClient` (interceptor) untuk SEMUA GET `/public/*`
  saat pengunjung memilih English → tidak ada halaman publik yang lupa dilokalkan.
- Bahasa tak dikenal (mis. `?lang=xx`) **jatuh ke Indonesia tanpa error**.
- Terjemahan kosong = fallback Indonesia (bukan string kosong).


---

## 7. ENDPOINT CMS-CW3 (CMS-10…CMS-13) — 2026-08-18

### Admin — riwayat versi & pemulihan (section RBAC `cms`)
```
GET    /api/content/{resource}/{id}/versions                  → {rows[], max_versions, total}
                                                                (metadata + changed_fields, TANPA snapshot penuh)
GET    /api/content/{resource}/{id}/versions/{version_id}      → {version{...snapshot}, changed_vs_current[]}
POST   /api/content/{resource}/{id}/versions/{version_id}/restore
                                                              → {ok, restored_from, fields[], item}
                                                                status terbit TIDAK ikut dipulihkan
```

### Admin — Tempat Sampah (retensi 30 hari)
```
DELETE /api/content/{resource}/{id}      → {ok, trashed:true, trash_id, expires_at, retention_days}
GET    /api/content/trash?resource=&limit= → {rows[], stats{total, expired, retention_days}}
POST   /api/content/trash/{id}/restore[?rename=true]
                                          → 200 {ok, item, notes[]} · 409 bentrok slug / sudah dipulihkan
DELETE /api/content/trash/{id}            → buang permanen (beserta riwayat versinya)
```

### Admin — pengalihan URL (301)
```
GET    /api/content/redirects?resource=&limit= → {rows[], stats{total, hits}, prefixes{}}
POST   /api/content/redirects                  → {from_path, to_path} · 400 lingkaran/self/beranda
DELETE /api/content/redirects/{id}             → {ok}
```
Pengalihan `kind:"auto"` DIBUAT SENDIRI oleh `PUT /api/content/{resource}/{id}` saat slug berubah
(respons memuat `redirect_created{from_path,to_path}`).

### Admin — aksi massal
```
POST   /api/content/{resource}/bulk  → {action: publish|unpublish|delete, ids[≤200]}
                                       → 200 {ok, action, done, items[], failed[{id,reason}]}
                                       400 aksi tak dikenal / tanpa item / melebihi batas
```
`publish`/`unpublish` = status terbit (destinations/packages/articles), `approved` (testimonials),
atau `active` (promos). `delete` = pindah ke Tempat Sampah.

### Publik (tanpa auth)
```
GET /api/public/redirect?path=/blog/slug-lama → 200 {from_path, to_path, status:301, resource, kind}
                                                404 bila tidak ada pengalihan
```

### Catatan kontrak
- Path dinormalkan: query & fragment dibuang, garis miring akhir dibuang, huruf besar/kecil slug
  DIPERTAHANKAN (slug case-sensitive di MongoDB).
- Rantai pengalihan diratakan saat pencatatan; `resolve` tetap membawa pengaman `MAX_HOPS` + set
  kunjungan yang sudah dilihat → mustahil berputar.
- SPA tidak bisa mengirim 301 sungguhan: `status: 301` adalah NIAT semantik dan pengalihan
  dijalankan halaman detail publik lewat `useSlugRedirect` (`navigate(..., {replace:true})`).
