# 01 — PRODUCT REQUIREMENTS (PRD)
## Travel & Fleet Management Ecosystem

> Sumber: brief transformasi digital sebuah usaha sewa kendaraan premium (Toyota Hiace Premio, Bandung) yang melayani wisata Jawa–Bali & korporat. **Penamaan kode generik (tanpa brand).**

---

## 1. VISI
Mengubah operasi rental tradisional menjadi **ekosistem terintegrasi** (tanpa silo data): satu alur dari **Lead (website)** → **CRM** → **Booking (ERP)** → **alokasi armada/driver** → **GPS tracking** → **pembayaran** → **laporan**.

## 2. PENGGUNA & ROLE
| Role (kode) | Persona | Tujuan utama |
|-------------|---------|--------------|
| `owner` | Pemilik | Control-tower: omset, utilisasi armada, piutang, profit per trip |
| `ops_admin` | Admin Operasional | Booking harian, dispatch, CRM, penagihan |
| `driver` | Driver | Check-in/out trip, kirim lokasi, lihat tugas |
| (publik) | Calon customer | Lihat armada/destinasi, hitung estimasi, minta penawaran |

## 3. MODUL & FITUR

### A. Website Publik (surface: public)
- Home sinematik (hero + trip-finder), value props, preview armada, destinasi populer, testimoni, CTA.
- Fleet (galeri + detail kendaraan: spesifikasi, fasilitas, S&K, FAQ).
- Destinasi (Jawa–Bali) + rekomendasi hotel per destinasi.
- Trip Calculator / Estimator (harga dasar + BBM + tol + uang jalan + overtime).
- Request Quotation (form lead → buat `leads`).
- Thank-You page (retention), WhatsApp floating button.
- Blog/Artikel (SEO), About, Contact.

### B. ERP Internal (surface: app)
- Auth + RBAC + manajemen user.
- Dashboard role-specific (owner/ops_admin/driver).
- Booking Management + **Kalender status warna** (lunas/DP/belum bayar/selesai) + **anti double-booking**.
- Master Armada (`vehicles`): KIR/pajak/servis + reminder.
- Master Driver (`drivers`): SIM, status, histori.
- Customer 360 (`customers`): riwayat, lifetime value.

### C. CRM Internal (WA-ready, tanpa WA live di v1)
- Pipeline kanban (`leads`): new→contacted→quoted→negotiation→won/lost.
- Inbox multi-admin (`conversations`/`messages`).
- Auto-assignment round-robin. Label customer.
- Template + reminder otomatis H-7/H-3/H-1 (`notification_tasks`).
- Broadcast tersegmentasi (`broadcasts`) — struktur disiapkan.

### D. Keuangan & Laporan
- DP/pelunasan (`payments`), pengeluaran BBM/Tol/Uang Jalan (`expenses`).
- Laba-Rugi per trip & bulanan; Piutang/AR; Invoice (`invoices`).
- Export PDF/Excel. Laporan: Laba-Rugi, Piutang, Booking, Armada, Driver, Revenue per trip.

### E. GPS Fleet Tracking
- Driver web app: check-in/out, kirim lokasi (geolocation browser) → `locations`/`trips`.
- Live map semua armada (Leaflet+OSM; swappable Google Maps).
- Status driver (Standby/Menuju Penjemputan/Dalam Perjalanan/Selesai), ETA (OSRM), histori track.
- Maintenance reminders (KIR/pajak/servis) (`maintenance_records`).

## 4. KEPUTUSAN PRODUK (dikonfirmasi user)
- Scope v1: SEMUA modul, dibangun **bertahap**.
- WhatsApp: **internal dulu** (struktur siap WhatsApp Business API).
- GPS: **Leaflet+OSM gratis** default, swappable ke Google Maps (butuh API key user).
- Bahasa UI: Indonesia. Penamaan kode: generik.
- Auth + RBAC dibuat sejak awal.

## 5. NON-FUNCTIONAL
- Mobile-first untuk publik (SEO + Lighthouse). Responsif untuk app.
- Aksesibilitas WCAG AA. Keamanan: RBAC ketat, kredensial di `.env`.
- Modular & scalable (tambah armada/driver/cabang tanpa rewrite).

## 6. BACKLOG / FUTURE (Phase 3+ brief asli)
- Payment gateway online, integrasi akuntansi, aplikasi mobile driver native.
- Multi-cabang, integrasi marketplace (Traveloka dll), loyalty.
- WhatsApp Business API live, Google Maps API, Meta Pixel/GA4.

## 7. OUT OF SCOPE (v1)
- Pengiriman WhatsApp live (butuh WABA). Hardware GPS tracker fisik. Payment gateway.
