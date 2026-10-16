# 🔍 AUDIT GAP — Brief Rahaza Travel (Kubus Indonesia) vs Implementasi

Tanggal: 2026-06-29 · Referensi: `Rahaza Travel.docx` (Brief Website & ERP System)
Lingkup audit: membandingkan kebutuhan bisnis pada brief dengan kondisi sistem saat ini
(setelah Tahap A Hardening + Tahap B B1–B4).

> **Status keselarasan keseluruhan: ± 70–75% scope brief.**
> Inti ERP, CRM, Keuangan, GPS (fungsional), dan Website publik **sudah kuat**.
> Gap utama ada pada **3 integrasi eksternal** (WhatsApp Business API, Google Maps,
> Analytics/Ads) + **2 halaman publik** (Paket & Harga) + **SEO/multi-bahasa**.

---

## 1. Ringkasan per Modul

| Modul (Brief) | Status | Catatan |
|---|---|---|
| **Website — Home** (Hero, Armada, Destinasi, Kalkulator, Testimoni) | 🟡 Sebagian | Hero/Armada/Destinasi/Kalkulator/Testimoni ✅. **FAQ ❌**, **logo klien korporat ❌**, **Google Review API ❌** (pakai testimoni internal). |
| **Website — Tentang Kami** | ✅ | Ada. |
| **Website — Halaman Armada + detail** | 🟡 | Detail + spesifikasi ✅. **Foto 360° ❌**. |
| **Website — Paket Wisata (publik)** | ❌ | Data ada (CMS + `/api/public/packages`) tapi **halaman/route publik belum dibuat**. |
| **Website — Harga Sewa (tabel publik)** | ❌ | **Belum ada** halaman tabel harga (Dalam/Luar Kota, Drop-off, Dinas, Wisata). |
| **Website — Blog SEO** | 🟡 | Blog + detail + CMS artikel ✅. **Meta tags/sitemap/keyword struktur ❌**. |
| **Website — Galeri & Kontak** | 🟡 | Kontak (WA/telp/email/maps) ✅, galeri tersebar di Armada/Destinasi; **halaman Galeri khusus 🟡**. |
| **Website — Request Quotation (Lead Capture)** | ✅ | Form lengkap → masuk CRM sebagai lead "new". |
| **Website — Thank You Page (retention)** | ✅ | Ada. |
| **Website — Destinasi + Rekomendasi Hotel** | ✅ | `hotel_recommendations` tersimpan & tampil. |
| **Website — WA Floating + Live Chat** | ✅ | Tombol WA floating global + ChatWidget (web-chat internal) ✅. |
| **Website — Mobile friendly / Modular** | ✅ | Responsif + arsitektur modular. |
| **Website — SEO Friendly** | ❌ | Tidak ada meta description/OG/sitemap/robots/structured data. |
| **Website — GA4 + Meta Pixel + GTM** | ❌ | **Belum terpasang sama sekali.** |
| **Website — Multi-bahasa (ID/EN)** | ❌ | Hanya Bahasa Indonesia. |
| **Website — Landing Page khusus Ads + A/B** | ❌ | Belum ada LP iklan terpisah / A/B. |
| **ERP — Dashboard real-time** | ✅ | KPI booking hari/minggu/bulan, unit aktif, omset. |
| **ERP — Kalender Booking (warna status)** | ✅ | Color-coded (lunas/DP/belum bayar/selesai). |
| **ERP — Detail Booking** | ✅ | Modal lengkap. |
| **ERP — Master Armada (STNK/KIR/Pajak/Servis + reminder)** | ✅ | Reminder dokumen otomatis (bucket urgensi) ✅. |
| **ERP — Master Driver (SIM + reminder)** | 🟡 | Data SIM/masa berlaku ✅, histori ✅. **Reminder SIM otomatis ❌/belum dipastikan**. |
| **ERP — Database Pelanggan 360°** | ✅ | Contact 360 (booking+lead+penawaran+percakapan+timeline) — baru disempurnakan di B4. |
| **ERP — Keuangan (DP/pelunasan, BBM/tol/uang jalan, piutang, P&L, profit/trip)** | ✅ | Lengkap + export PDF/Excel. |
| **ERP — Laporan operasional** | ✅ | Booking/Driver/Armada/Customer/Revenue report. |
| **Modul 1 — WhatsApp Management System** | 🟡→❌ | Inbox multi-admin, auto-assign, label, history, broadcast, reminder **(UI+DB) ✅** — **TAPI integrasi WhatsApp Business API (Meta) BELUM ADA**. Pengiriman pesan WA saat ini **SIMULASI/internal**, bukan terkirim ke nomor pelanggan. |
| **Modul 2 — CRM Lead Management** | ✅ | Pipeline, follow-up, reminder, activities, history, auto-assign, konversi → kuat. Analytics per-source/ROI channel 🟡. |
| **Modul 3 — GPS Fleet Tracking** | 🟡 | Driver mobile (checkin/out/status/lokasi) ✅, live tracking+ETA+history ✅, monitoring owner ✅, akses tracking corporate (share token) ✅. **Pakai Leaflet/OpenStreetMap — brief minta Google Maps** (sudah disiapkan swap via `GOOGLE_MAPS_API_KEY`). |
| **Integrasi — Payment Gateway** | ❌ | Belum (brief = Phase 3/Expansion → wajar ditunda). |
| **Integrasi — Akuntansi / Multi-cabang / Marketplace** | ❌ | Future (Phase 3–4 brief). |

---

## 2. Daftar GAP Terprioritas

### 🔴 P0 — Inti scope brief belum terpenuhi
1. **Integrasi WhatsApp Business API (Meta Cloud API)** — jantung "Modul Baru 1". Saat ini seluruh
   channel WA (inbox, reminder DP/H-7/H-3/H-1, notifikasi booking, broadcast) **hanya simulasi internal**,
   belum benar-benar mengirim ke WhatsApp pelanggan. Brief menempatkan ini di **Phase 1 (Launch)**.
   → Butuh: kredensial Meta WABA (Phone Number ID, Permanent Token), persetujuan template, dan OPEX per-percakapan.
2. **Halaman publik "Paket Wisata"** + **"Harga Sewa"** — bagian struktur website wajib & funnel konversi.
   Data & API sudah ada; tinggal membangun halaman + routing publik.
3. **SEO teknis + Tracking marketing (GA4, Meta Pixel, GTM)** — brief memposisikan website sebagai
   "mesin lead generation 24/7" yang bergantung pada SEO + paid ads tracking. Saat ini belum ada sama sekali.

### 🟠 P1 — Penting untuk paritas brief
4. **Google Maps integration** (swap dari OSM) untuk GPS live + ETA (sudah disiapkan titik swap-nya).
5. **Multi-bahasa (Indonesia & Inggris)** di website publik.
6. **Reminder SIM driver otomatis** (lengkapi paritas dengan reminder dokumen armada).
7. **Home enhancements**: section **FAQ**, **logo klien korporat** (social proof), **Google Review API**.
8. **CRM analytics**: dashboard konversi & ROI per-source (website/WA/ads/referral/marketplace), LTV report.

### 🟡 P2 — Nilai tambah / future (sebagian = Phase 3–4 brief)
9. Landing Page khusus Ads + A/B testing.
10. Foto 360° armada + halaman Galeri khusus.
11. Payment Gateway online (transfer/CC/e-wallet).
12. Integrasi akuntansi, arsitektur multi-cabang, integrasi marketplace (Traveloka/Tokopedia), loyalty.
13. Driver mobile sebagai aplikasi terpisah (saat ini mode web checkin).

---

## 3. Catatan Penting (Kebutuhan Kredensial & Biaya)
- **WhatsApp Business API** & **Google Maps API** memerlukan **kredensial nyata dari user** + biaya OPEX
  (sesuai lampiran brief: WA ± Rp3.000/percakapan, Google Maps pay-as-you-use). Integrasi kode bisa
  disiapkan, namun aktivasi penuh butuh akun/billing pelanggan.
- **GA4 / Meta Pixel / GTM** memerlukan ID properti dari user (gratis untuk dipasang).
- Item infrastruktur brief (SSL, Cloud VPS, backup) berada di luar lingkup kode aplikasi (di-handle platform/deploy).

---

## 4. Rekomendasi Urutan Pengerjaan (usulan)
1. **Quick wins website** (P0 #2 + sebagian P1 #7): Halaman Paket Wisata + Harga Sewa + FAQ + logo klien.
2. **SEO + Analytics foundation** (P0 #3): meta/OG/sitemap + slot GA4/Pixel/GTM (ID dari user).
3. **WhatsApp Business API** (P0 #1): integrasi nyata (butuh kredensial Meta) — mengaktifkan reminder & broadcast.
4. **Google Maps swap** (P1 #4) + **Reminder SIM** (P1 #6) + **Multi-bahasa** (P1 #5).
5. **CRM analytics & ROI channel** (P1 #8), lalu item P2 sesuai roadmap.
