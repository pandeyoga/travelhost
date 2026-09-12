# 05 — NAVIGATION MAP (SSOT)
## Travel & Fleet Management Ecosystem

> SSOT struktur menu & routing. **Tiap halaman/fitur baru WAJIB dipetakan di sini SEBELUM coding.** Di-cek `scripts/check_nav_map.py`.

---

## 1. PUBLIC SITE (surface=public, tanpa login)
```
/                      Home (hero + trip-finder + sections)
/fleet                 Daftar armada
/fleet/:id             Detail kendaraan
/destinations          Daftar destinasi
/destinations/:slug    Detail destinasi (+ rekomendasi hotel) · dukung `?preview=<token>` (CMS-05)
/packages              **Paket Wisata** (A1) — daftar paket TAYANG. testid: packages-grid ·
                       package-card-{slug} · packages-empty/loading/error · packages-cta-*
/packages/:slug        Detail paket + CTA booking/penawaran · dukung `?preview=<token>` (CMS-05).
                       testid: package-title/price/includes(-empty) · package-book-cta ·
                       package-quote-cta · package-preview-banner
/promo                 **Promo & Penawaran** (A3) — promo aktif + syarat dari DATA + salin kode.
                       testid: promos-grid · promo-card-{CODE} · promo-code-{CODE} ·
                       promo-copy-{CODE} · promo-use-{CODE} (→ /booking?promo=CODE) ·
                       promo-terms-{CODE} · promo-quota-{CODE} · promos-empty
/review/:token         **Halaman ulasan pelanggan** (CMS-07, tautan dari WhatsApp MOCK).
                       testid: review-page · review-stars/review-star-{1..5} · review-quote ·
                       review-name/role/consent · review-submit · review-done · review-invalid
/trip-calculator       Estimator biaya trip
/quotation             Form Request Quotation → leads
/booking               **Pesan Online** — wizard 3 langkah (Cari → Pilih Unit → Data & Konfirmasi)
                       testid: booking-steps · booking-service-{daily_rental|airport_transfer} ·
                       booking-start/end/pax/vehicle-type/route · booking-search-submit ·
                       booking-unit-{vehicleId} + booking-pick-{vehicleId} · booking-results-empty ·
                       booking-name/phone/pickup/consent · booking-submit · booking-quote-total/dp
/booking/status        **Cek Pesanan** — kode+WA atau tautan token; countdown DP, instruksi transfer,
                       unggah bukti, batalkan. testid: booking-status-code · booking-countdown ·
                       booking-bank-{BANK} · booking-proof-file/amount/submit · booking-cancel
/booking/permintaan    Permintaan penawaran tanpa unit (paket wisata/lepas kunci) → booking pending + lead
/lp/:slug              Halaman iklan (Landing Page Builder, header disederhanakan)
/thank-you             Thank-you (retention)
/blog                  Daftar artikel
/blog/:slug            Artikel (isi rich text tersanitasi server / teks polos lama) ·
                       dukung `?preview=<token>` (CMS-05)
/about                 Tentang
/contact               Kontak (+ WhatsApp)
```
Global public: announcement bar, header transparan (nav), WhatsApp floating button, footer.

### 1a. Struktur header publik (SSOT — diubah 2026-08-12, permintaan user "navbar terlalu ramai")

Sebelumnya bar utama memuat 9 menu + 5 utilitas = **14 target klik dalam satu baris**; pada 1920px
label `Pesan Online / Cek Pesanan / Masuk ERP / Pesan Sekarang` sudah **pecah 2 baris**, dan
`Pesan Online` (menu) bersaing dengan `Pesan Sekarang` (tombol) untuk tujuan yang SAMA (`/booking`).

| Lapis | Isi | `data-testid` |
|-------|-----|----------------|
| Bar pengumuman (paling atas) | teks area layanan · **chip "Lanjutkan pesanan BK-00xx"** (dari `localStorage` `rahaza_bookings`) · **Promo** · **Cek Pesanan** · nomor telepon · **Masuk ERP** · **pemilih bahasa ID/EN** | `public-announcement-bar` · `resume-booking-chip` · `public-nav-promo` · `public-nav-booking-status` · `nav-phone-cta` · `public-nav-login` · `lang-switch` (+ `lang-switch-id` / `lang-switch-en`) |
| Menu utama (6) | Beranda · Armada · Destinasi (mega) · **Paket** · Kalkulator · Blog | `public-nav-home` · `public-nav-fleet` · `public-nav-destinations` · `public-nav-packages` · `public-nav-trip-calculator` · `public-nav-blog` |
| Aksi | **1 tombol utama "Pesan Online"** (gradien) + ganti tema + WhatsApp (sekunder, outline) | `nav-booking-cta` · `nav-theme-switch` · `nav-whatsapp-cta` |
| Drawer ponsel | grup 1 = 6 menu utama (`mnav-<id>`) + **baris bahasa** (`public-mobile-lang`); **grup 2 "Layanan & Bantuan"** = Pesan Online · Cek Pesanan · **Promo** · Minta Penawaran · Tentang · Kontak · Masuk ERP (`mnav-booking`, `mnav-booking-status`, `mnav-promo`, `mnav-quotation`, `mnav-about`, `mnav-contact`, `mnav-login`) + aksi `mnav-booking-cta` / `mnav-whatsapp` | `public-mobile-menu` · `public-mobile-lang` · `public-mobile-help-group` |
| Footer | Jelajahi: Armada · Destinasi · **Paket Wisata** · **Promo** · Kalkulator · Blog — Layanan: Pesan Online · Cek Status Pesanan · Minta Penawaran · **Tentang Kami** · **Kontak** · Konsol Internal | `footer-nav-packages` · `footer-nav-promo` · `public-nav-booking` · `footer-nav-booking-status` · `public-nav-about` · `public-nav-contact` · `footer-nav-login` |
| Bar bawah ponsel | ikon Kalkulator + **Pesan Online** (utama) + WhatsApp | `sticky-cta-calc` · `sticky-cta-booking` · `sticky-cta-wa` |

Aturan yang WAJIB dipertahankan:
1. `Tentang` & `Kontak` **tetap** ada di `sitemap.xml` (`backend/routers/seo.py`) dan tetap ditaut
   footer → crawlability tidak turun walau keluar dari menu.
2. `data-testid` lama **DIPINDAH, tidak dihapus** (`public-nav-about`, `public-nav-contact`,
   `public-nav-booking`, `public-nav-booking-status`, `public-nav-login`, `nav-booking-cta`,
   `nav-phone-cta`) supaya laporan uji lama tetap valid.
3. `/lp/:slug` (`isLanding`) tetap **menyembunyikan seluruh menu DAN utilitas bar pengumuman** —
   halaman iklan berbayar hanya boleh punya satu tindakan (INV-LP).
4. Beranda punya section **`home-booking-steps`** ("Pesan online dalam 3 langkah") dengan angka DP
   & lama hold dari `/public/booking/config` (bukan hardcode) + `home-cta-booking`.
5. **Header WAJIB tetap SATU baris.** Terukur 2026-08-17 = **91,25 px** pada 1920px (bar pengumuman
   29,75 px + baris menu 61,5 px) setelah "Paket" masuk menu & pemilih bahasa masuk bar utilitas.
   `--header-h: 90px` di `index.css` adalah SSOT offset elemen mengapung (ChatWidget) — bila header
   diubah lagi, ukur ulang dan sesuaikan token itu (INV-THEME-01).
6. **CMS-06 (dua bahasa):** pemilih bahasa hanya mengganti bahasa **isi publik** (`?lang=` dikirim
   otomatis oleh `services/apiClient`) + label kerangka (`lib/i18n.js`). `?lang=` pada URL adalah
   sumber kebenaran tertinggi (disinkronkan tiap navigasi SPA) supaya tautan English yang dibagikan
   tetap English. Halaman `/lp/:slug` memakai `i18n:false` (tanpa hreflang).

## 2. APP (surface=app, login required)
```
SHELL: Sidebar (grouped, role-filtered) + TopBar + (optional) Right Detail Panel

🏠 Beranda (Dashboard)        — role-specific (owner/ops_admin/driver)
   ├─ Tab **Ringkasan** — KPI operasional + pengingat dokumen + booking terbaru + grafik entitas (semua role).
   └─ Tab **BI Cockpit** (E4, owner/ops_admin) — Exec KPI (+delta), Sales Funnel, Channel mix/ROAS (ad-spend manual), Fleet ROI, Driver performance, AR aging, Retensi/Cohort, Forecast moving-average. Range 30/90/365/kustom + pembanding periode lalu. Export PDF/Excel.
🗓️ Booking
   ├─ **Panel "Bukti Transfer Menunggu Verifikasi"** (owner/ops_admin; section `finance`) — antrean
   │    bukti DP dari pemesanan online. Aksi: Lihat bukti · isi nominal diterima ·
   │    **Verifikasi & Catat** (→ `payments` → `hold` otomatis `confirmed`) · **Tolak** + alasan.
   │    testid: payment-proofs-panel · proofs-count · proof-{id} · proof-view-{id} ·
   │    proof-amount-{id} · proof-verify-{id} · proof-reject-{id}
   ├─ Daftar Booking (tabel; badge status `Hold (Menunggu DP)` untuk pesanan web menunggu DP,
   │    tombol **ACC + Minta DP** `booking-approve-hold-{id}` pada mode `ops_approval`)
   ├─ Kalender (color-coded payment status)
   └─ Detail Booking (panel: timeline + pembayaran)
🚦 Dispatch (dispatch)        — E3: Ops Cockpit "Hari Ini". KPI (Berangkat/Perlu Assign/Perlu Konfirmasi/Sedang Jalan/Selesai) + tabel keberangkatan. Aksi: Assign driver+unit (geocode tujuan via Nominatim → perbaiki G1), Konfirmasi keberangkatan (WA), Berangkat/Tiba (status driver→customer, WA), POD (Bukti Layanan: foto+penerima+catatan, lokal).
🚐 Armada (vehicles)          — master + reminder KIR/pajak/servis
👤 Driver (drivers)            — master + SIM + histori
📇 Customer 360 (customers)
🗂️ Referensi Jemput & Destinasi (masterdata) — Master Data SSOT (INV-REF-02): kelola TITIK JEMPUT
   (`pickup_points`) & DESTINASI sisi ops. Ganti nama = CASCADE ke booking/lead/penawaran;
   nonaktif = hilang dari selector form (data lama utuh). Owner + ops_admin.
💬 CRM
   ├─ Pipeline (kanban)
   ├─ Skor & SLA (Scoreboard: lead scoring + SLA/aging + recompute)
   ├─ RFM/LTV (customer RFM + lifecycle segment chips)
   ├─ Segmen (segment builder: audience lead/customer + criteria, preview count/reachable)
   ├─ Sequence (nurturing steps + enable + enroll dari segmen + enrollments)
   ├─ Campaign (broadcast WA tersegmentasi: pilih segmen/template/pesan → kirim → stats + recipients)  [E2]
   └─ Reminder (H-7/H-3/H-1)
   (Inbox = menu terpisah · "Broadcast" lama DIGANTI tab "Campaign" sejak E2)
⚡ Otomasi (automation)       — E1: Event Bus + Automation Engine + WhatsApp Adapter (mock). Monitoring: Aturan · Riwayat Eksekusi · Event Stream. Konfigurasi rules + WA di Pengaturan.
🧾 Penawaran (quotations)     — Quotation Lifecycle (B2): lead → QUO → kirim/terima → konversi → booking (+ PDF)
📰 Konten Web (cms)           — Light CMS (B3 + CMS-CW2). 8 tab: **Destinasi · Paket · Artikel ·
   Testimoni · Promo · Ulasan · Analitik · Tema Situs** (`content-tab-<id>`).
   ├─ Daftar konten: pencarian (`content-search`), **filter status terbit** (`content-status-filter`
   │    + `content-status-opt-{all|published|scheduled|draft}`, hanya destinasi/paket/artikel),
   │    badge status `Tayang|Terjadwal|Draft` + badge **EN** bila punya terjemahan, urutan
   │    (`content-pos-*`), **tautan pratinjau bertoken** (`content-preview-token-{id}`, hanya konten
   │    belum tayang), buka halaman publik (`content-preview-{id}`), duplikat, edit, hapus,
   │    "Muat lebih banyak" (`content-load-more`).
   ├─ Dialog konten (`content-form-dialog`) 3 tab: **Indonesia** (`cf-tab-id`) · **English**
   │    (`cf-tab-en` → `cf-en-panel`, `cf-en-{field}`, `cf-en-copy-{field}`, `cf-en-clear-{field}`) ·
   │    **Terbit** (`cf-tab-publish` → `cf-status` + `cf-status-opt-{draft|scheduled|published}`,
   │    `cf-publish-at`, `cf-preview-token`/`cf-preview-open`/`cf-preview-copy`).
   │    Artikel memakai **editor rich text** (`cf-rte-body` + `cf-rte-body-tool-*`,
   │    `cf-rte-body-html-toggle`, `cf-rte-body-convert`). Promo memakai field ATURAN
   │    (`cf-valid_from`, `cf-min_days`, `cf-min_amount`, `cf-vehicle_types`, `cf-services`,
   │    `cf-weekend_only`, `cf-max_uses`) + `cf-used_count` read-only.
   ├─ Tab **Ulasan** (CMS-07, `reviews-panel`) — KPI (`reviews-kpi-*`), antrean moderasi
   │    (`review-approve-{id}` / `review-reject-{id}`), pesanan selesai belum diminta
   │    (`review-send-{bookingId}`, WhatsApp **MOCK**), permintaan terkirim (`review-copy-{id}`,
   │    `review-open-{id}`).
   └─ Tab **Analitik** (CMS-08, `content-analytics-panel`) — KPI (`ca-kpi-*`), peringkat konten
        (`ca-table`, `ca-row-{kind}-{slug}`), filter jenis (`ca-kind-filter`), ekspor CSV (`ca-export`).
💰 Keuangan
   ├─ Pembayaran (DP/Pelunasan)
   ├─ Pengeluaran (BBM/Tol/Uang Jalan)
   ├─ Laba-Rugi per trip
   ├─ Piutang (AR)
   └─ Invoice (+ export PDF/Excel)
📊 Laporan (reports)
📍 GPS Tracking (live map + side list + detail)
   └─ Driver Check-in (mobile view)
📣 Marketing & Iklan (FASE F/E29)
   ├─ Iklan (ads) — dashboard performa Meta/Google (spend/CTR/CPL/ROAS) + ROAS NYATA dari booking terkonfirmasi; kelola kampanye (mulai PAUSED)
   ├─ Landing Page (landing) — Landing Page Builder (advanced CMS) berbasis blok; 2 segmen: fokus ARMADA & fokus DESTINASI; publik di /lp/{slug}
   ├─ Kesehatan Pelacakan (tracking) — outbox konversi server-side (Meta CAPI + Google Data Manager): sukses/gagal/dilewati + kirim event uji
   └─ Integrasi API (integrations) — kredensial Meta/Google/WhatsApp diinput dari UI, tersimpan TERENKRIPSI (tidak hardcoded)
🔧 Maintenance (reminders)
⚙️ Admin
   ├─ Manajemen User (users · RBAC) — CRUD akun ERP + peran (owner-only)
   ├─ Pengaturan (settings) — perusahaan · tarif harga (`day_rates`, `dp_percent` = SATU sumber DP) ·
   │    operasional/hari libur · WhatsApp/otomasi · **Alur Pemesanan Online** (`BookingFlowPanel`:
   │    mode `hold_dp`/`ops_approval`, batas jam hold & SLA ACC, jendela pesan, layanan aktif,
   │    rekening/QRIS + instruksi DP, kebijakan pembatalan) · **Rute Antar-Jemput Bandara**
   │    (`TransferRoutesPanel`: CRUD rute + tarif FLAT per tipe unit)
   └─ Jejak Audit (auditlog · audit_logs · owner-only)
```

## 3. ROLE ACCESS MATRIX
> **FASE F (E29):** ditambahkan peran **`marketing_admin`** (pemilik kanal akuisisi) + 4 modul
> Marketing. Kolomnya sengaja eksplisit agar tidak ada asumsi tersembunyi.

| Section | owner | ops_admin | marketing_admin | driver |
|---|:---:|:---:|:---:|:---:|
| Beranda | ✅ (control tower) | ✅ (ops) | ✅ | ✅ (driver) |
| Booking | ✅ Full | ✅ Full | ❌ | 👁️ trip miliknya |
| Kalender Keberangkatan (calendar) | ✅ Full | ✅ Full | ❌ | ❌ |
| Dispatch | ✅ Full | ✅ Full | ❌ | ❌ |
| Ruang Kerja Driver (driver-workspace) | ✅ Full | ✅ Full | ❌ | ✅ (tugasnya sendiri) |
| Armada | ✅ Full | ✅ Full | ❌ | 👁️ read |
| Driver | ✅ Full | ✅ Full | ❌ | 👁️ profil sendiri |
| Customer 360 | ✅ | ✅ | ✅ | ❌ |
| Referensi Jemput & Destinasi (masterdata) | ✅ Full | ✅ Full | ❌ | ❌ |
| CRM | ✅ | ✅ | ✅ | ❌ |
| Otomasi (automation) | ✅ Full | ✅ (monitoring) | ❌ | ❌ |
| Penawaran (quotations) | ✅ | ✅ | ❌ | ❌ |
| Inbox (inbox) | ✅ | ✅ | ✅ | ❌ |
| Konten Web (cms) | ✅ | ✅ | ✅ | ❌ |
| Media Library (media) | ✅ | ✅ | ✅ | ❌ |
| Keuangan | ✅ Full | ✅ (input) | ❌ | ❌ |
| Laporan | ✅ Full | 👁️ terbatas | ❌ | ❌ |
| GPS Tracking | ✅ | ✅ | ❌ | ✅ (kirim lokasi/check-in) |
| Maintenance | ✅ | ✅ | ❌ | 👁️ read |
| Iklan (ads) | ✅ Full | 👁️ read-only | ✅ Full | ❌ |
| Landing Page (landing) | ✅ Full | ❌ | ✅ Full | ❌ |
| Kesehatan Pelacakan (tracking) | ✅ | ❌ | ✅ | ❌ |
| Integrasi API (integrations) | ✅ | ❌ | ✅ | ❌ |
| Admin (User/Settings) | ✅ Full | ❌ | ❌ | ❌ |

> **Penegakan matriks ini (WAJIB 3 lapis — pelajaran RBAC-CAL-01, E28).** Satu lapis saja tidak cukup:
> 1. **FE menu/route** — `ROLE_MENU_ALLOWLIST` di `frontend/src/config/navigationConfig.js` + `<RoleGuard section="...">` di `App.js`.
> 2. **BE pintu modul** — section terdaftar di `backend/permissions_config.SECTION_ACCESS` **dan** endpoint memakai `Depends(require_section("<section>"))`.
> 3. **BE cakupan data (row-level)** — untuk baris "👁️ miliknya" (Booking & Driver bagi peran driver) query WAJIB disaring lewat `backend/services/rbac_scope.py`.
>
> Guardrail `scripts/guardrails/verify_rbac_guards.py` memaksa ketiganya (INV-RBAC-01..05) dan
> membandingkan matriks FE↔BE **dua arah**, sehingga modul BARU tidak bisa lolos diam-diam.
>
> **Kalender Keberangkatan** sengaja ❌ untuk driver: halaman itu permukaan manajemen
> (buat keberangkatan, setujui/tolak permintaan publik, tugaskan sopir, ekspor jadwal seluruh
> armada, panel risiko "Perlu Perhatian" lintas armada) — setara Dispatch. Driver memakai
> **Ruang Kerja Driver** (`/app/driver-workspace`) untuk tugasnya sendiri.

## 4. data-testid NAV (konvensi)
```
nav-group-{domain}      mis. nav-group-keuangan
nav-{module}            mis. nav-bookings, nav-gps, nav-crm
tab-{module}-{tab}      mis. tab-bookings-calendar
public-nav-{link}       mis. public-nav-fleet, public-nav-quotation
```

**Dispatch (E3) testid:** `dispatch-page`, `dispatch-summary`, `disp-stat-{total|assign|confirm|ongoing|completed}`, `dispatch-today-btn`, `dispatch-tomorrow-btn`, `dispatch-date`, `dispatch-list`, `dispatch-row-{id}`, `dispatch-assign-{id}`, `dispatch-confirm-{id}`, `dispatch-enroute-{id}`, `dispatch-arrived-{id}`, `dispatch-pod-{id}`; dialog `assign-dialog` (`assign-driver`/`assign-vehicle`/`assign-save`), `pod-dialog` (`pod-photo-btn`/`pod-recipient`/`pod-note`/`pod-save`).

## 5. ATURAN KEDALAMAN & ANTI-PATTERN
- Maks 4 level: Grup (L1) → Menu (L2) → Tab/Panel (L3) → Modal (L4).
- Jangan menu redundan; jangan halaman duplikat per role (gunakan konten kondisional).
- Perubahan besar nav → STOP & ASK + update dokumen ini dulu.

**Changelog:** v1.0 — struktur awal public + app. · v1.1 (E3) — menu **Dispatch** (Ops Cockpit) ditambah di grup Operasional (owner/ops_admin). · v1.2 (E16) — menu **Pinjam Armada** (partners · sub-charter) ditambah di grup Operasional (owner/ops_admin).


## CMS — tab di halaman `/app/cms` (SSOT tab, bukan menu navigasi)

| Tab | testid | Isi |
|---|---|---|
| Destinasi · Paket · Artikel · Testimoni · Promo | `content-tab-<resource>` | daftar CRUD + aksi massal + riwayat versi |
| Ulasan | `content-tab-reviews` | moderasi ulasan → testimoni (CMS-07, WA MOCK) |
| Analitik | `content-tab-analytics` | konten → lead → pesanan → omzet (CMS-08) |
| **Pengalihan** | `content-tab-redirects` | **CMS-12** pengalihan URL 301 (auto saat slug diubah + manual) |
| Tema Situs | `content-tab-theme` | preset warna & mode situs publik |

Aksi lintas-tab: `content-trash-open` (Tempat Sampah, CMS-11) · `content-history-<id>` (riwayat
versi, CMS-10) · `content-bulk-bar` dengan `content-bulk-publish|unpublish|delete` (CMS-13).
