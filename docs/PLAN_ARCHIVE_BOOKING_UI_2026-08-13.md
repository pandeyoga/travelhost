# Plan — Online Booking Flow (Public Website) + Pricing/Availability Hardening

> **STATUS 2026-08-13 (sesi 4 / KEBERSIHAN DATA + VERIFIKASI ALUR END-TO-END) — SELESAI & TERVERIFIKASI.**
> Repo di-restore dari GitHub ke pod baru. Permintaan user: (1) cek alur dari awal sampai akhir,
> (2) *"ada nama customer aaaaaaaa… itu yang mengganggu"* → seed diperbaiki, **data demo tetap ada**.
> **BUG-0127 ditemukan & ditutup:** penjaga/smoke/POC menulis lewat API sungguhan tetapi hanya
> menghapus dokumen UTAMA — side-effect-nya tidak → **157 dokumen sampah per satu kali `gate.sh`**
> (customer 60.000 karakter "AAAA…", audit 60.016 karakter, percakapan Inbox "Penjaga INV-*"/
> "Smoke Customer", 34 notifikasi hantu, 35/48 event, lead & penawaran ber-karakter NUL, segmen
> "AdvSeg", aset `guard-media-*`, `conversion_events` menumpuk permanen). Semua SENYAP dengan gate
> HIJAU 40/40 — yang menemukan PENGGUNA. Fix: **mesin bersih-bersih bersama**
> `purge_guard_artifacts()` di `scripts/guardrails/_common.py` (cascade penuh + `seed` dikecualikan)
> dipanggil 11 skrip penulis di `finally`; `_clip()` di `backend/services/audit.py`;
> `conversion_events` masuk daftar reset seed. **Guardrail baru INV-CLEAN-01**
> (`verify_no_test_pollution.py` statik+runtime, di-wire PALING AKHIR di gate) + self-test
> **5 mutasi MERAH↔HIJAU**. Alat baru: `scripts/purge_test_pollution.py`, `scripts/db_snapshot.py`.
> **Bukti:** `gate.sh` **HIJAU 42/42 (0 FAIL, 0 SKIP)** **dan database 0 artefak SESUDAH gate** ·
> POC **74/74** & **84/84** · testing agent `iteration_89` (kebersihan data 100% + RBAC 20/20),
> `iteration_90` (alur end-to-end: publik 9 halaman · pemesanan online → hold → bukti DP → ops
> verifikasi → confirmed · keuangan & laporan · 17 modul ERP — semua 100%), `iteration_91`
> (dispatch → keberangkatan → enroute → arrived → driver check-in/out 260 km → completed, 13/13).
> Data demo dipulihkan bersih pasca-uji: 4 customer, BK-0001..BK-0010, 4 armada, 2 sopir, 4 akun.
>
> **STATUS 2026-08-12 (sesi 3 / UI-READABILITY) — Fase 0–7 SELESAI & TERVERIFIKASI.**
> Sesi 3 mengeksekusi 7 permintaan user dari screenshot (keterbacaan mode gelap & di atas foto,
> 3 halaman publik yang "sepi", CTA blog rusak, posisi chat, rename brand **RahazaTrans**) —
> rincian di **Phase 7**. `gate.sh` **HIJAU 40/40** (guardrail baru **INV-THEME-01**),
> `ux_audit --strict` 0 ERROR/0 WARN, testing agent `iteration_86/87/88` (2 ronde terakhir 0 bug).
>
> **STATUS 2026-08-12 (sesi 2 / BOOKING-V2) — Fase 0–6 SELESAI & TERVERIFIKASI.**
> POC `python scripts/test_core_booking_v1.py` **74/74** · `bash scripts/gate.sh` **HIJAU
> (0 FAIL, 0 SKIP)** · `ux_audit --strict` **0 ERROR 0 WARN** · testing agent
> `iteration_83.json` (navbar + STORY H) & `iteration_84.json` (3 fitur baru: backend 100 %, 
> frontend 100 %, 0 bug).
> Sesi 2 menyelesaikan: **STORY H** (toggle "Tayang di web" → sisa verifikasi §0.2 TUNTAS),
> **§0.1 rapikan navbar publik** (14 target klik → 5 menu + 1 aksi utama; header 1 baris,
> 90,75 px), **section beranda "Pesan online dalam 3 langkah"**, **chip "Lanjutkan pesanan"**,
> lalu 3 fitur backlog: **daftar promo di wizard**, **laporan "Hold Hangus"**,
> **rute bandara (katalog tambah-cepat + arah balik, tarif per tipe unit)**.
> Bug baru ditemukan & ditutup: **BUG-0120** (kode rute otomatis simetris `DPS-DPS`).
> Guardrail diperkuat: **INV-BOOK-02** statik kini mengawal SEMUA skema publik (diturunkan
> dari `import` router, bukan daftar manual) — self-test MERAH↔HIJAU.
> Catatan jujur: notifikasi WhatsApp/Meta/Google/GA4 masih **MOCK** (belum ada kredensial);
> tarif rute bandara nyata tetap harus diisi pemilik (sistem sengaja tidak menebak harga).
>
> **STATUS 2026-08-17 (sesi 5 / REQUEST BARU: SITE-WIDE VISUAL PAGE BUILDER) — PLANNING ONLY.**
> User meminta kemampuan **edit SEMUA halaman publik** (Beranda, Tentang, Armada, Destinasi,
> Kontak, Footer, Logo, Typography, cards, dsb) lewat **visual page builder drag-and-drop** ala Wix.
> User eksplisit: **"buatkan plannya saja dulu, jangan eksekusi"**.
>
> **Audit tambahan (tanpa coding) yang mengoreksi asumsi Phase 8 sebelumnya:**
> - Footer **bukan** komponen terpisah: inline di `frontend/src/components/public/PublicLayout.jsx` (baris ~237–278).
>   - Kolom **Kontak** dan bar copyright **sudah dinamis** dari `/public/company` → bukan gap.
>   - Gap nyata: **teks deskripsi brand** masih hardcode + **belum ada sosial media** sama sekali.
>   - Kolom **Jelajahi/Layanan** adalah navigasi fungsional (link route internal) → hanya boleh **show/hide**, bukan teks bebas.
> - Logo publik `frontend/src/components/public/Logo.jsx` adalah SVG monogram hardcode (bukan image upload).
>   `frontend/src/components/public/Preloader.jsx` menduplikasi SVG manual → sebaiknya reuse `Logo.jsx`.
> - Typography belum ada mekanisme global; `font-fraunces` tersebar di banyak heading.
>   Solusi harus lewat CSS variable `--font-heading/--font-body` agar 1 setting berlaku site-wide.
> - `frontend/src/components/cms/ThemeManagerPanel.jsx` sudah mengelola `settings.theme_config`.
>   Keputusan arsitektur diperbaiki: **logo + typography** digabung ke `theme_config` yang sama (bukan `settings.branding` terpisah).
> - RBAC: `backend/permissions_config.py` mengizinkan `landing` untuk `{owner, marketing_admin}` → jadi acuan untuk section baru `site_builder`.

---

## 1) Objectives

### Objectives yang sudah terpenuhi (Phase 0–7)

- Tambahkan **alur pemesanan publik ala Traveloka rentcar/airport transfer**: cari → pilih unit → review → booking dibuat (hold/pending sesuai mode) → instruksi DP + unggah bukti → ops verifikasi → otomatis confirmed.
- Pastikan **harga dihitung ulang di server** (uang = integer rupiah), **tanpa komponen jarak/BBM**, dan harga tampil = harga tersimpan.
- Perbaiki sumber data & relasi agar tidak salah collection/kosong: fleet/availability/pricing/promo/airport routes.
- Perkuat guardrail & gate untuk mencegah regresi (pricing + booking-public invariants).
- Fix temuan LOW: **menu “Media Library” tampil untuk marketing_admin**.
- Fix kebersihan data uji (BUG-0127): tidak ada test pollution; gate 42/42 hijau.

### Objective baru (Phase 8 — 🅿️ PLANNED)

- Bangun **Site-wide Visual Page Builder** untuk **SEMUA halaman publik inti** + elemen global:
  - Halaman inti: **Beranda (/), Tentang (/about), Armada (/fleet), Destinasi (/destinations), Kontak (/contact)**.
  - Elemen global: **Footer** (deskripsi brand + sosial media + toggle kolom nav), **Logo** (image opsional), **Typography** (heading/body font), serta blok-blok kartu/CTA.
- Builder harus:
  1. Memakai pola builder yang sudah ada (Landing Builder) dengan **preview WYSIWYG** desktop/mobile.
  2. Mendukung **blok reusable** (hero, value props, FAQ, CTA band, dst).
  3. **Aman**: situs tidak pernah blank/500 (fallback default blocks; blok tak dikenal di-skip).
  4. Menjaga standar desain: typography/font lewat **whitelist** + CSS variable global.
- **Tidak ada implementasi di sesi ini**: hanya rencana.

---

## 2) Implementation Steps

### Phase 0 — Quick Fix (UI) — ✅ SELESAI

User stories:
1. Sebagai marketing_admin, saya melihat menu **Media Library** di navigasi “Konten Web”.
2. Sebagai marketing_admin, saya bisa membuka `/app/media` dari menu tanpa mengetik URL.
3. Sebagai ops_admin, navigasi tidak berubah/pecah.
4. Sebagai driver, menu Media Library tetap tidak muncul.
5. Sebagai QA, perubahan tidak mengganggu gate/guideline FE.

Steps:
- Audit sumber nav/section mapping FE (AppShell/menu builder + permissions/sections).
- Pastikan section `media` termasuk untuk role marketing_admin (frontend + backend permission_config bila perlu).
- Re-run minimal FE smoke + gate.

---

### Phase 1 — Core POC (Isolated) — `scripts/test_core_booking_v1.py` — ✅ SELESAI (74/74)

Core = “search availability + server-side pricing + booking state machine + concurrency safety”.

User stories:
1. Sebagai tamu publik, saya hanya melihat **unit yang benar-benar available** untuk tanggal yang dipilih.
2. Sebagai tamu, harga yang saya lihat adalah harga final yang tersimpan di booking (tidak bisa ditamper).
3. Sebagai sistem, 8–16 request paralel pada unit+waktu sama menghasilkan **tepat 1 booking sukses**.
4. Sebagai owner, saya bisa memilih mode **hold_dp** atau **ops_approval** via Settings.
5. Sebagai ops_admin, verifikasi pembayaran mengubah booking hold → confirmed otomatis.

POC steps (backend-only, tanpa UI):
- Tambah model Settings baru `booking_flow` (mode, hold_hours, approval_hours, payment_instructions, bank_accounts/QRIS).
- Tambah field fleet canonical:
  - `vehicles.day_rate` (override per unit, integer rupiah)
  - `vehicles.web_published` (bool)
- Buat **availability search** function (services): filter vehicles yang:
  - `web_published==true`, `ownership==owned`, status allowed
  - tidak bentrok booking aktif (hold/confirmed/ongoing) + tidak bentrok maintenance
- Pricing v2 (services):
  - Input: vehicle_id|vehicle_type, start/end (days), trip_date(start), promo_code(optional)
  - Base per hari = `vehicles.day_rate` jika ada else `pricing_rules.day_rates[type]`
  - **Hapus komponen jarak/BBM** dari compute
  - Surcharge weekend/holiday tetap ada (settings.operational.holidays)
  - Promo tervalidasi server
  - Output: breakdown + total + dp_amount (single DP source)
- Endpoint POC (minimal):
  - `POST /api/public/booking/search`
  - `POST /api/public/booking/create`
  - `POST /api/public/booking/upload-proof`
  - `POST /api/bookings/{id}/approve` (ops_approval)
  - `POST /api/bookings/{id}/verify-proof` (ops)
  - `POST /api/public/booking/status` (code+phone)
- Implement **POC script** untuk memverifikasi 10 poin Fase 1.

---

### Phase 2 — V1 App Development (Backend + Frontend) — ✅ SELESAI

User stories (public):
1. Sebagai tamu, saya memilih layanan **Sewa Harian** dan melihat daftar unit available + harga per unit.
2. Sebagai tamu, saya memilih layanan **Airport Transfer** dan melihat harga flat per rute.
3. Sebagai tamu, setelah booking dibuat saya melihat halaman **Instruksi DP + countdown** dan bisa unggah bukti.
4. Sebagai tamu, saya bisa cek status booking dengan **kode + nomor WA** (tanpa akun).
5. Sebagai tamu, saya menerima WA/notifikasi sesuai event (requested/confirmed).

User stories (ERP/ops):
1. Sebagai ops_admin, saya melihat booking source=public dan status (pending/hold/confirmed).
2. Sebagai ops_admin, saya bisa approve (mode ops_approval) dan mengubah pending→hold.
3. Sebagai ops_admin, saya bisa memverifikasi bukti bayar dan otomatis mencatat payment.
4. Sebagai owner, saya mengatur `booking_flow`.
5. Sebagai owner, saya mengatur tarif per unit (`day_rate`) dan toggle `web_published`.

---

### Phase 3 — Guardrails + Regression + Gate — ✅ SELESAI

- Guardrail: **INV-PRICE-01**, **INV-BOOK-02**.
- Self-test mutasi + wiring ke `gate.sh`.
- `gate.sh` hijau.

---

### Phase 4 — Docs + Handoff — ✅ SELESAI

- Update `docs/03_DATA_MODEL.md`, `docs/04_API_CONTRACT.md`, `docs/05_NAVIGATION_MAP.md`.
- Update memory docs + bug registry.

---

### Phase 5 — Rapikan Navbar Publik + Onboarding Pemesanan — ✅ SELESAI

---

### Phase 6 — 3 Fitur Backlog (promo list + hold hangus report + airport routes) — ✅ SELESAI

---

### Phase 7 — Readability + Kedalaman Halaman Publik + Rename Brand — ✅ SELESAI

---

### Phase 8 — **Site-wide Visual Page Builder (ala Wix) untuk semua halaman publik** — 🅿️ PLANNED (BELUM DIEKSEKUSI)

> **Aturan sesi ini:** hanya rencana. Tidak ada perubahan kode, migrasi, atau eksekusi gate.

#### Phase 8.0 — Arsitektur & Scope Lock (Design Doc) — 🅿️ PLANNED

**User stories**
1. Sebagai maintainer, halaman inti situs memakai storage terpisah dari `landing_pages` agar workflow iklan (publish/readiness/A-B test) tidak mencemari situs utama.
2. Sebagai owner, saya mengedit halaman inti tanpa konsep publish terpisah: **simpan = langsung tayang** di route fixed.
3. Sebagai QA, saya punya kontrak jelas tentang footer: link navigasi (Jelajahi/Layanan) hanya bisa **show/hide**, bukan teks bebas.
4. Sebagai desainer sistem, typography global bisa diubah dari ERP tetapi dibatasi **whitelist font** (agar konsistensi desain terjaga).

**Keputusan arsitektur (berbasis audit, tanpa coding)**
- Reuse engine yang sudah ada di **Landing Page Builder** (`/app/landing`): preview desktop/mobile, daftar blok, media library, editor blok.
- Halaman iklan (`/lp/:slug`) tetap menggunakan `landing_pages`.
- Halaman inti situs menggunakan collection baru `site_pages` dan `site_footer`.
- **Branding & typography digabung ke `settings.theme_config`** (yang sudah ada): tambah `logo_url`, `heading_font`, `body_font`.

**Catatan soal drag-and-drop**
- Engine existing memakai reorder tombol naik/turun (setara fungsional). Drag-native opsional dan menambah scope (library baru).

**Deliverable (dokumen, bukan kode)**
- Kontrak data `site_pages/site_footer/theme_config`.
- Whitelist blok per `page_key` (lihat Phase 8.2).
- Aturan fallback anti-blank.
- Urutan rollout yang disarankan: **Kontak → Tentang → Armada → Beranda → Footer/Branding terakhir**.

---

#### Phase 8.1 — Backend: Model & API — 🅿️ PLANNED

**File BARU (direncanakan)**
- `backend/routers/site_pages.py` — router baru untuk halaman inti & footer.
- (opsional) `backend/services/site_pages_defaults.py` — default blocks per page_key untuk fallback.

**File DIMODIFIKASI (direncanakan)**
- `backend/server.py` — `app.include_router(site_pages.router)`.
- `backend/permissions_config.py` — tambah section baru:
  - `SECTION_ACCESS["site_builder"] = {"owner", "marketing_admin"}`
- Router/settings backend yang mengelola `/api/settings` — extend schema `theme_config`:
  - tambah `logo_url`, `heading_font`, `body_font`.

**Collection baru (MongoDB)**
- `site_pages` — satu dokumen per `page_key` tetap (tidak bisa create page bebas):
  - `page_key ∈ {home, about, fleet_index, destinations_index, contact}`
  - schema:
    ```json
    {
      "id": "...",
      "page_key": "home",
      "blocks": [
        {"id":"blk_...","type":"home_hero","hidden":false,"device":"all","props":{}}
      ],
      "updated_at": "...",
      "updated_by": "user_id/email"
    }
    ```
- `site_footer` — singleton:
  - schema:
    ```json
    {
      "id": "footer",
      "brand_description": "...",
      "social_links": [{"platform":"instagram","url":"https://..."}],
      "nav_columns_visibility": {"jelajahi": true, "layanan": true},
      "updated_at": "...",
      "updated_by": "..."
    }
    ```

**Endpoint internal (ERP, butuh login + role `site_builder`)**
- `GET /api/site-pages/{page_key}`
- `PATCH /api/site-pages/{page_key}` — body `{blocks}`; validasi schema per blok.
- `GET /api/site-footer`
- `PATCH /api/site-footer`
- `PATCH /api/settings` — menerima tambahan `theme_config.logo_url/heading_font/body_font`.

**Endpoint publik (tanpa login)**
- `GET /api/public/site-pages/{page_key}` — **wajib fallback** ke default blocks bila dokumen kosong/absen.
- `GET /api/public/site-footer` — fallback default footer bila singleton belum ada.

**Validasi & hardening**
- Sanitasi string / rich-text (anti-XSS).
- Batas panjang text per field (mencegah layout rusak seperti bug data 60k char).
- Validasi URL untuk `logo_url` dan `social_links[].url`.
- Tolak `page_key` di luar whitelist (404/422).

---

#### Phase 8.2 — Block Library: Whitelist per halaman + Props Schema — 🅿️ PLANNED

> Fokus Phase 8 adalah memindahkan *konten hardcode* jadi data-driven blok; bukan mengganti seluruh sumber data entity yang sudah dinamis (armada/destinasi/testimoni) kecuali bagian yang memang hardcode.

**Whitelist blok per `page_key` (kontrak anti-kekacauan)**

| page_key | Blok yang diizinkan | Catatan sumber data |
|---|---|---|
| `home` | `home_hero`, `booking_steps`, `value_props`, `stats_band`, `featured_fleet`, `featured_destinations`, `testimonials_grid`, `trust_signals`, `faq_accordion`, `cta_band` | Migrasi dari konstanta hardcode di `Home.jsx` (HERO, chips, VALUE_PROPS, TRUST, FAQS) |
| `about` | `hero_simple`, `stats_band`, `about_values`, `cta_band` | Migrasi dari `About.jsx` |
| `fleet_index` | `hero_simple`, `standards_list`, `faq_accordion`, `cta_band` | Grid armada tetap dari `/public/fleet`; yang dipindah hanya STANDARDS + FAQ |
| `destinations_index` | `hero_simple`, `cta_band` | Grid destinasi tetap dari `/public/destinations` |
| `contact` | `hero_simple`, `contact_channels`, `cta_band` | Channel kontak tetap dari `/public/company`; blok ini mengatur tampil/urutan/presentasi |

**Skema props untuk tipe blok baru**

- `home_hero`
  ```json
  {
    "eyebrow": "...",
    "title": "...",
    "subtitle": "...",
    "image_url": "https://...",
    "chips": ["Driver berpengalaman", "CHSE / KIR"],
    "cta_primary": {"label": "Minta Penawaran", "to": "/quotation"},
    "cta_secondary": {"label": "Halaman Kalkulator", "to": "/trip-calculator"}
  }
  ```

- `value_props` / `about_values` / `trust_signals`
  ```json
  {
    "items": [
      {"icon_key": "ShieldCheck", "title": "Armada Terawat", "description": "...", "tag": "Kelaikan terjaga"}
    ]
  }
  ```
  - `icon_key` harus dari whitelist ikon `lucide-react` yang didukung (bukan upload ikon bebas).

- `stats_band`
  ```json
  {
    "items": [
      {"key": "fleet", "value": 12, "suffix": "+", "label": "Armada"}
    ]
  }
  ```

- `faq_accordion`
  ```json
  {
    "eyebrow": "FAQ",
    "title": "Pertanyaan yang sering diajukan",
    "items": [{"q": "...", "a": "..."}]
  }
  ```

- `standards_list`
  ```json
  {
    "items": [{"title": "KIR aktif", "description": "..."}]
  }
  ```

- `contact_channels`
  - Props minimal (umumnya hanya konfigurasi tampilan), tetapi sumber nilai (telp/WA/email/alamat) tetap dari `/public/company`.

**Footer (data-driven sebagian)**
- Editable:
  - `brand_description` (text)
  - `social_links[]` (platform + url)
  - `nav_columns_visibility` (toggle show/hide kolom Jelajahi/Layanan)
- Tetap hardcode (demi integritas navigasi):
  - daftar link & tujuan untuk kolom Jelajahi/Layanan (route internal).

---

#### Phase 8.3 — Frontend: Editor “Page Builder Situs” + Public Renderer — 🅿️ PLANNED

**File BARU (direncanakan)**
- `frontend/src/features/app/SiteBuilder.jsx`
- `frontend/src/components/app/sitebuilder/SitePageEditor.jsx`
- `frontend/src/components/app/sitebuilder/SiteBlockForm.jsx`
- `frontend/src/components/app/sitebuilder/SiteFooterEditor.jsx`
- `frontend/src/components/app/sitebuilder/BrandingTypographyPanel.jsx`
- `frontend/src/components/public/SiteBlockRenderer.jsx`

**File DIMODIFIKASI (direncanakan)**
- `frontend/src/App.js`
  - route `/app/site-builder` dengan `<RoleGuard section="site-builder">`.
- `frontend/src/config/navigationConfig.js`
  - tambah menu `site-builder` di grup "Konten Web".
  - tambah allowlist role: `owner`, `marketing_admin`.
- Halaman publik:
  - `frontend/src/features/public/Home.jsx`
  - `frontend/src/features/public/About.jsx`
  - `frontend/src/features/public/Fleet.jsx` (bagian index)
  - `frontend/src/features/public/Destinations.jsx` (index)
  - `frontend/src/features/public/Contact.jsx`
  - tujuan: render bagian konten hardcode via `SiteBlockRenderer` dari `/public/site-pages/{page_key}`.
- `frontend/src/components/public/PublicLayout.jsx`
  - Footer: ambil `brand_description`, `social_links`, `nav_columns_visibility` dari `/public/site-footer`.
- `frontend/src/components/public/Logo.jsx`
  - dukung `logoUrl` opsional (render `<img>` jika ada; fallback SVG monogram jika kosong).
- `frontend/src/components/public/Preloader.jsx`
  - reuse `Logo.jsx` (hilangkan duplikasi SVG manual) agar logo custom juga muncul di preloader.
- `frontend/src/index.css`
  - tambah CSS variables `--font-heading`, `--font-body`.
  - arahkan kelas heading yang sekarang memakai `font-fraunces` menjadi menggunakan variable (agar 1 setting theme_config berlaku site-wide tanpa refactor besar).
- `frontend/src/components/cms/ThemeManagerPanel.jsx`
  - extend UI: input `logo_url` + dropdown `heading_font`/`body_font` (whitelist) + publish via `PATCH /api/settings`.

**UX Editor (reuse pola LandingBuilder)**
- Panel kiri: list blok (reorder naik/turun; opsi hidden per blok; tambah blok via select)
- Tengah: preview desktop/mobile (renderer sama dengan publik)
- Panel kanan: form blok terpilih + MediaLibrary untuk gambar

---

#### Phase 8.4 — Migrasi & Rollout (No Visual Regression) — 🅿️ PLANNED

**Tujuan:** saat fitur aktif, tampilan publik **identik** dengan versi hardcode.

**Skrip migrasi (direncanakan)**
- `scripts/migrate_site_pages_seed.py`
  - mengisi `site_pages` & `site_footer` dari konstanta hardcode saat ini:
    - `Home.jsx`: HERO, chips, VALUE_PROPS, TRUST, FAQS, CTA.
    - `About.jsx`: seluruh konten.
    - `Fleet.jsx`: STANDARDS + FAQ.
    - `Contact.jsx`: teks heading/CTA.
    - `PublicLayout.jsx`: `brand_description` (footer).

**Urutan rollout disarankan (minim risiko):**
1. `contact` (paling kecil)
2. `about`
3. `fleet_index`
4. `home` (paling kompleks)
5. Footer + Logo + Typography terakhir (karena berdampak ke semua halaman termasuk `/lp/:slug`).

**Fallback selama transisi:**
- Jika fetch `site-pages` gagal, renderer menggunakan default blocks sehingga halaman tidak blank.

---

#### Phase 8.5 — Guardrails & Testing — 🅿️ PLANNED

**Guardrail baru (mengikuti konvensi proyek)**
- **INV-SITEBUILDER-01** — *No-blank public pages*:
  - Endpoint publik `GET /api/public/site-pages/{page_key}` & `GET /api/public/site-footer` tidak boleh menyebabkan halaman kosong/500.
  - Self-test mutasi MERAH↔HIJAU: hapus dokumen `site_pages`/`site_footer` → API tetap 200 dengan default.
- **INV-SITEBUILDER-02** — *Whitelist blok per halaman*:
  - `PATCH /api/site-pages/{page_key}` menolak blok tipe yang tidak diizinkan untuk page_key tersebut.
  - Self-test: injeksi blok ilegal harus gagal 422.
- **INV-THEME-01 (perluasan)**:
  - Pastikan setting font baru (`heading_font/body_font`) tidak melanggar kontrak kontras/tema yang sudah dijaga.

**Testing plan (setelah implementasi, bukan sekarang)**
- `testing_agent_v3`:
  1. Validasi 5 halaman inti render normal (tanpa blank) sebelum dan sesudah migrasi.
  2. Verifikasi footer: deskripsi brand berasal dari `site_footer`; kontak tetap dari `/public/company`.
  3. Edit via ERP: tambah/reorder/hide blok + simpan → refresh halaman publik → perubahan terlihat.
  4. Edit logo_url + font heading/body → cek perubahan di navbar, footer, dan preloader.
  5. Pastikan `/lp/:slug` tidak rusak oleh perubahan footer/branding.
- Gate:
  - Wire guardrail ke `scripts/gate.sh` (target tetap **0 FAIL, 0 SKIP**).
- RBAC regression:
  - `driver` dan `ops_admin` tidak bisa akses `/app/site-builder` dan endpoint PATCH terkait (403/redirect).

**Dokumentasi (setelah implementasi)**
- `docs/03_DATA_MODEL.md` (site_pages, site_footer, theme_config fields baru)
- `docs/04_API_CONTRACT.md` (endpoint internal & publik Phase 8.1)
- `docs/05_NAVIGATION_MAP.md` (menu baru + RBAC section site_builder)

---

## 3) Next Actions (sisa backlog setelah Fase 0–7 selesai)

0. ✅ **SELESAI 2026-08-13 — Kebersihan data uji (BUG-0127) + verifikasi alur end-to-end.**
1. 🅿️ **Phase 8 — Site-wide Visual Page Builder** (plan detail dibuat; menunggu izin user untuk eksekusi).
2. **Uji beban konkuren tinggi (load test)** — belum pernah dijalankan (P1 lama).
3. **Kredensial nyata** WhatsApp Cloud / Meta Ads / Google Ads / GA4 → semua LIVE-READY tapi MOCK.
4. **Promo di halaman publik non-wizard** — `/promo` khusus + kartu promo di beranda belum ada.
5. **Notifikasi ops untuk hold hangus** — laporan ada; dorongan proaktif (WA/email) belum dibuat.

---

## 4) Success Criteria

### Sudah terpenuhi (Phase 0–7)

- Phase 0: marketing_admin melihat menu Media Library; driver tetap tidak.
- Phase 1 (POC): `python scripts/test_core_booking_v1.py` PASS 100% (termasuk concurrency).
- Phase 2: public booking 2 produk berjalan end-to-end; upload proof; ops verify → confirmed.
- Phase 3: `bash scripts/gate.sh` HIJAU 0 FAIL 0 SKIP + invariants terdaftar; E2E PASS.
- Phase 4: docs & handoff lengkap.

### Target Phase 8 (acceptance tests yang presisi)

1. **Editor tersedia & RBAC benar**
   - Owner dan marketing_admin melihat menu **Konten Web → Page Builder Situs**.
   - Role lain (ops_admin/driver) tidak bisa akses halaman maupun endpoint PATCH (403/redirect).
2. **5 halaman inti bisa diedit tanpa ubah kode**
   - Konten hardcode yang dulu ada di `Home.jsx/About.jsx/Fleet.jsx/Contact.jsx` sekarang berasal dari `site_pages` dan dapat diubah lewat editor.
3. **Footer global bisa diedit dengan batasan aman**
   - `brand_description` dan `social_links` berubah via editor dan tampil di semua halaman publik.
   - Link "Jelajahi"/"Layanan" tetap route-locked; hanya bisa show/hide kolom.
4. **Logo & typography bersifat global**
   - `theme_config.logo_url` mengubah logo di navbar + footer + preloader (fallback ke SVG bila kosong).
   - `theme_config.heading_font/body_font` mengubah font heading/body site-wide via CSS variable.
5. **Tidak ada halaman blank/500**
   - Guardrail `INV-SITEBUILDER-01` memastikan default fallback selalu tersedia.
   - `gate.sh` tetap hijau (0 FAIL, 0 SKIP) setelah fitur diimplementasikan.
