> ## ✅ FASE F2 — Pengaturan Integrasi + Pelacakan Situs Publik · SELESAI 2026-08-10
>
> **Backend** `routers/marketing.py`: `GET/PATCH /api/integrations/config[/{provider}]` (Meta & Google),
> `PATCH /api/integrations/consent`, `POST /api/integrations/test/{provider}`,
> `GET /api/public/tracking-config` (PUBLIK, allowlist field ketat), `GET /api/tracking/health`,
> `POST /api/tracking/test-event`, `POST /api/tracking/retry/{id}`. Konfigurasi WhatsApp
> (`/wa/config`) kini juga dapat diakses `marketing_admin` (dulu owner-only).
>
> **Frontend**: halaman `/app/integrations` (3 blok: Meta, Google, WhatsApp + blok Consent) dan
> `/app/tracking` (Kesehatan Pelacakan: ringkasan per provider, daftar percobaan, tombol Kirim
> Event Uji & Coba Lagi). Pelacakan publik: `lib/tracking.js` + `ConsentBanner.jsx` dipasang di
> `PublicLayout`; event funnel terpasang: `page_view/PageView` (1x per URL), `view_item/ViewContent`
> (detail armada & destinasi, anti-ganda), `begin_checkout/InitiateCheckout` (buka form pesan),
> `generate_lead/Lead` + konversi Google Ads pada submit form penawaran & pemesanan dengan
> `event_id` = ID bisnis (dedup pixel↔server).
>
> **Bukti verifikasi mandiri (browser + curl):** RBAC 4 peran (owner/marketing 200, ops/driver 403 di
> semua endpoint integrasi & tracking) · token TIDAK bocor (respons hanya `••••9999`, tanpa ciphertext)
> · `/api/public/tracking-config` tanpa token · banner consent muncul, SEBELUM izin `fbq=false` &
> tag Google belum dimuat, SESUDAH izin `fbevents.js` + `gtag/js?id=...` dimuat dan consent
> `default:denied → update:granted` · event terbukti terpanggil: `PageView`×2 per navigasi berbeda,
> `ViewContent` + `view_item` (value 1.500.000) di detail armada. `gate.sh` **HIJAU 23/23**.
>
> **Catatan jujur:** pengiriman AKHIR ke Meta/Google hanya bisa dipastikan dengan kredensial NYATA
> (Meta Test Events / GA4 DebugView) — saat ini semua provider dalam mode **MOCK/BELUM AKTIF** dan
> diberi label jelas di UI. **QA formal oleh testing agent untuk F2 belum dijalankan** (dilakukan pada
> giliran berikutnya bersama F3).
> **Berikutnya: FASE F3** — konversi server-side otomatis dari event bus (lead.created,
> booking.confirmed, payment.recorded) + worker retry.

---

> ## ✅ FASE F1 (POC) — SELESAI & TERBUKTI 2026-08-10
>
> `python scripts/test_core_ads.py` → **62/62 CEK LULUS** (tanpa kredensial platform, mode uji-kering).
> Bukti ringkas: vault AES-256-GCM (respons publik bebas plaintext & ciphertext) · object storage
> **gambar 1MB + VIDEO 12MB** unggah-unduh identik SHA-256 (~0,5 s) · outbox konversi idempoten
> (8 paralel → 1 dokumen/provider) dgn payload Meta CAPI & Google Data Manager sesuai skema resmi +
> `skipped/failed/dead` berALASAN · 16 tipe blok landing page dgn sanitasi XSS & aturan layak-terbit ·
> peran baru `marketing_admin` sinkron FE↔BE (INV-RBAC-01..05 HIJAU 177 cek).
> `bash scripts/gate.sh` tetap **HIJAU 23/23**. Berkas baru: `backend/services/{secrets_vault,media_store,conversions,landing_blocks}.py`,
> `scripts/test_core_ads.py`; peran+modul baru terdaftar di `permissions_config.py`, `navigationConfig.js`,
> `docs/05_NAVIGATION_MAP.md`, seed `marketing@demo.local`.
> **Berikutnya: FASE F2** (Pengaturan→Integrasi + consent + pemuat tag Pixel/gtag + halaman Marketing).

---

# Development Plan — FASE F (E29+) Marketing & Ads Platform (Rahaza Travel ERP)

> Status awal (fakta): E27/E28/E28b selesai & terverifikasi; `bash scripts/gate.sh` **HIJAU 23/23**. Fondasi atribusi (`gclid/fbclid/ttclid`) & CRM event bus sudah ada, namun **belum ada Pixel/gtag, belum ada konversi server-side, belum ada dashboard performa API, belum ada campaign builder, belum ada landing page builder advanced + video**, dan belum ada role `marketing_admin`.

---

## 1) Objectives

1. Menutup gap inti: **pelacakan iklan end-to-end** (browser + server) untuk 3 konversi bisnis: **(a) lead terkirim, (b) booking confirmed, (c) DP/payment recorded (IDR)**.
2. Menyediakan **Settings integrasi** (Meta/Google/WhatsApp) **tanpa hardcode**: semua kredensial diinput di UI, disimpan di MongoDB **terenkripsi**, respons API ter-mask.
3. Membangun **dashboard performa iklan** yang bernilai tinggi: gabungkan metrik platform (spend/clicks) + data CRM/booking internal → **ROAS nyata**.
4. Menyediakan **Landing Page Builder (advanced CMS)** + media library (image/video) untuk iklan (dua segmen: **armada** & **destinasi**), cepat di HP, conversion-friendly.
5. Menambahkan kemampuan **campaign management** (Meta + Google) secara aman: default **PAUSED**, `validate_only`, publish eksplisit.
6. Menambahkan **Tracking Health**: tidak ada konversi yang “hilang diam-diam”; semua attempt tercatat + retry.

---

## 2) Implementation Steps

### Phase 1 — Core POC (Isolation) *Wajib lulus sebelum fase 2*
**Core workflow paling riskan:** (1) secret handling + (2) outbox konversi idempoten + (3) object storage media + (4) RBAC role baru.

**User stories (POC)**
1. Sebagai owner, saya ingin menyimpan token Meta/Google/WA secara aman (terenkripsi) sehingga tidak bocor di API response.
2. Sebagai marketing admin, saya ingin menekan “Test event” dan melihat status sukses/gagal tanpa perlu deploy ulang.
3. Sebagai sistem, saya ingin setiap konversi diproses idempoten sehingga tidak ada duplikasi saat retry/paralel.
4. Sebagai editor konten, saya ingin mengunggah gambar/video dan memastikan file tetap ada walau service restart.
5. Sebagai admin, saya ingin memastikan RBAC untuk modul Marketing benar (driver terblokir) sebelum fitur dibangun.

**Deliverables (POC)**
- `scripts/test_core_ads.py` membuktikan 5 hal:
  1) AES-GCM encrypt/decrypt + `mask()` + simpan/baca settings; API response tidak mengandung plaintext.
  2) Emergent object storage: init → PUT/GET image (~1MB) + video (~10–20MB) + hash sama; soft-delete; overwrite.
  3) Outbox konversi: 8 request paralel event_id sama → 1 dokumen (unique index); status pending→failed (tanpa kredensial) **tanpa 5xx**; payload Meta CAPI + Google Data Manager terbentuk (dry-run).
  4) Landing render pipeline: `landing_pages` published → `GET /api/public/landing/{slug}` 200; draft → 404; skema blok tervalidasi.
  5) RBAC role baru: marketing_admin akses sesuai matrix; `verify_rbac_guards.py` HIJAU.
- Tambah guardrail minimal (statik) untuk secret leakage & outbox idempotency (di-wire gate) bila POC menemukan gap.

**Checkpoint:** POC **PASS** + `gate.sh` tetap HIJAU. Stop bila belum lulus.

---

### Phase 2 — V1 App Development (fondasi nyata, tanpa menunggu kredensial)
**User stories (V1)**
1. Sebagai owner/marketing admin, saya bisa mengisi konfigurasi Meta/Google/WhatsApp dari Pengaturan dan melihat indikator “tersimpan” tanpa melihat token mentah.
2. Sebagai marketing admin, saya bisa mengaktif/nonaktifkan tracking publik dan melihat config publik yang aman (tanpa token).
3. Sebagai pengunjung, saya mendapat pilihan consent yang jelas; jika menolak, tidak ada pixel/gtag aktif.
4. Sebagai marketing admin, saya bisa melihat daftar landing page (draft/published), pratinjau, dan publish.
5. Sebagai ops admin, saya bisa melihat dashboard iklan read-only.

**Backend**
- Tambah role `marketing_admin` end-to-end:
  - `permissions_config.ROLES` + `SECTION_ACCESS` + FE `ROLE_MENU_ALLOWLIST` + docs `05_NAVIGATION_MAP.md`.
  - Seed akun demo `marketing@demo.local`.
- Settings baru (MongoDB keyed docs): `meta_ads_config`, `google_ads_config` (+ rapikan `wa_config` di tab Integrasi).
  - Enkripsi AES-GCM (master key via env `SETTINGS_ENCRYPTION_KEY_B64`).
  - API get selalu ter-mask + flag `*_set`.
  - Audit log perubahan settings.
- Endpoint publik aman: `GET /api/public/tracking-config` (hanya ID publik & flags).

**Frontend**
- Menu grup **Marketing**: `Iklan`, `Landing Pages`, `Tracking Health` (owner+marketing_admin; ops read-only dashboard).
- Settings → tab “Integrasi”: form Meta/Google/WA (masked password inputs, tombol “Uji koneksi” stub/dry-run).
- Consent banner (shared state Meta+Google) + wiring `marketing_consent` pada form publik.
- Loader tag runtime (tanpa kredensial dulu):
  - Meta Pixel bootstrap (ID dari `/public/tracking-config`, gated consent).
  - Google tag (gtag.js) runtime; `send_page_view:false`; page_view manual per route.

**End of Phase 2:** panggil `testing_agent_v3` untuk smoke: RBAC role baru + settings masking + consent gating (tanpa token).

---

### Phase 3 — Konversi Server-side + Tracking Health (nilai tertinggi)
**User stories**
1. Sebagai owner, saya ingin lead/booking/payment otomatis tercatat sebagai konversi ke Meta+Google (ketika nanti token diisi).
2. Sebagai marketing admin, saya ingin melihat semua attempt konversi (sukses/gagal) dan alasan gagal.
3. Sebagai marketing admin, saya ingin tombol “Test event” untuk Meta (test_event_code) dan Google (validateOnly) agar setup bisa divalidasi tanpa risiko.
4. Sebagai sistem, saya ingin retry/backoff otomatis dan dead-letter untuk error permanen.
5. Sebagai auditor, saya ingin jaminan tidak ada token muncul di log/response.

**Backend**
- `services/conversions.py` + outbox `conversion_events` (unique {tenant,event_id,provider}).
- Hook ke event bus existing: `lead.created`, `booking.confirmed`, `payment.recorded`.
- Provider:
  - Meta CAPI (httpx async, Graph v25.0, payload sesuai playbook, dedup event_id).
  - Google Data Manager `events:ingest` (validateOnly), fallback legacy upload jika allowlisted.
- UI/endpoint Tracking Health: ringkasan + tabel attempt + resend/test.

**End of Phase 3:** testing agent ronde berikut: event bus → outbox → health UI (mode dry-run bila belum ada token).

---

### Phase 4 — Ads Analytics & Visualisasi (Insights + GAQL cache)
**User stories**
1. Sebagai marketing admin, saya ingin melihat spend/clicks/conversions/ROAS per campaign dengan filter tanggal.
2. Sebagai owner, saya ingin melihat **ROAS nyata** dari booking confirmed/DP yang masuk.
3. Sebagai ops admin, saya ingin dashboard read-only untuk koordinasi operasional.
4. Sebagai marketing admin, saya ingin ekspor PDF/Excel laporan.
5. Sebagai sistem, saya ingin caching harian dan tombol “Tarik sekarang”.

- Meta Insights puller (async report bila besar) + cache `ads_metrics_daily`.
- Google GAQL SearchStream + cache.
- Gabungkan dengan CRM/booking internal via attribution mapping (gclid/fbclid + landing/campaign identifiers).
- Pertahankan input manual ad-spend sebagai fallback.

---

### Phase 5 — Landing Page Builder (advanced CMS) + Media Library
**User stories**
1. Sebagai marketing admin, saya bisa membuat landing page dari template segmen Armada/Destinasi.
2. Sebagai marketing admin, saya bisa drag-reorder blok, edit konten, upload media, dan preview mobile.
3. Sebagai pengunjung, landing page cepat terbuka dan CTA jelas (Booking/WA) dengan UTM diteruskan.
4. Sebagai marketing admin, lead dari landing page otomatis masuk CRM dengan atribusi.
5. Sebagai owner, hanya role berwenang yang bisa publish/unpublish.

- Backend: `landing_pages` + `media_assets` + upload via Emergent object storage.
  - Video: dukung file kecil (≤50MB) + Range/caching; video besar via embed URL.
- Frontend editor 3 kolom: blocks + live preview + settings panel; templates ≥3 per segmen.
- Public render: `/lp/:slug` + `GET /api/public/landing/{slug}` + submit lead.

---

### Phase 6 — Lead ingest platform (Meta Lead Ads + Google Lead Form)
- Implement webhook real (verify + signature) + worker fetch historical + dedup + mapping per form.
- UI mapping field & rekonsiliasi.

---

### Phase 7 — Campaign management (Meta + Google) *fase akhir*
- Meta campaign/adset/ad/creative: default PAUSED + validate_only; publish eksplisit; status review.
- Google budget/campaign/adgroup/keyword/RSA: validate_only + partial_failure; publish eksplisit.
- Integrasi target URL ke landing page builder.

---

### Phase 8 — Hardening & Final Verification
- Guardrails baru (wired gate + self-test): INV-SEC-01, INV-CONV-01, INV-TRACK-01, INV-LP-01, INV-MEDIA-01.
- Update SSOT docs (Data Model, API Contract, UI/UX standards, Nav map).
- `testing_agent_v3` lintas 4 role + `gate.sh` HIJAU.

---

## 3) Next Actions (Immediate)

1. Buat desain SSOT RBAC untuk role `marketing_admin` + section Marketing (ads/landing/tracking/settings-integrations) lalu update docs/05_NAVIGATION_MAP.md draft.
2. Rancang model settings terenkripsi (AES-GCM) + mask response (re-use pola `wa_config`).
3. Tulis `scripts/test_core_ads.py` (POC) + skema koleksi baru (`conversion_events`, `media_assets`, `landing_pages`).
4. Tambah wiring minimal di `gate.sh` untuk menjalankan POC script (sebagai runtime gate baru) setelah disetujui.
5. Presentasikan hasil POC PASS ke user untuk persetujuan lanjut Phase 2.

---

## 4) Success Criteria

- **POC PASS**: kelima bukti POC lulus; tidak ada 5xx; idempotency outbox terbukti; object storage OK.
- **Secrets aman**: token/secret/refresh token tidak pernah muncul plaintext di API response/log; semua tersimpan terenkripsi.
- **RBAC**: owner+marketing_admin dapat mengelola integrasi/landing; ops read-only analytics; driver tidak melihat menu marketing.
- **Tracking**: lead/booking/payment menghasilkan event browser+server (mode test/dry-run tanpa token) dan semua attempt terlihat di Tracking Health.
- **Analytics**: dashboard dapat menampilkan metrik platform + ROAS nyata (dengan cache, filter rentang, export).
- **Landing pages**: bisa dibuat/publish dari template, cepat dibuka di mobile, CTA mempertahankan atribusi; lead masuk CRM.
- **Quality bar**: `bash scripts/gate.sh` tetap **HIJAU**, dan testing agent tiap fase lulus tanpa regresi E27/E28/E28b.
