# Rahaza Travel ERP — PRD / Catatan Lanjutan (E1)

## Problem statement asli
Lanjutkan development repo https://github.com/pandeyoga/travelhost. Cek penyimpanan foto galeri/media, error,
gambar tidak terload, stabilitas sistem. (Sesi ini fokus ke bug yang dilaporkan user via screenshot.)

## Arsitektur
FastAPI (backend/, routers + services) · React CRA + shadcn (frontend/) · MongoDB. ERP di /app/*, situs publik di /.
Deploy: Caddy (deploy/render_caddyfile.sh) — ERP bisa di subdomain terpisah (ERP_DOMAIN → `redir / /app/login`).
Seed demo: `python scripts/seed_data.py` (owner/ops/marketing/driver @demo.local, pass demo12345).

## Yang dikerjakan 12 Sep 2026
1. Setup repo di /app, deps terpasang (emergentintegrations/litellm pin konflik → di-skip dari install, tidak dipakai runtime).
2. CMS → Halaman: dari 3 → 9 halaman (home, about, contact, fleet, destinations, packages, promo, blog, trip-calculator);
   6 halaman baru punya section `page_hero` via komponen `CmsPageHero`.
3. Pratinjau CMS menampilkan ERP (bukan situs) saat ERP di subdomain: iframe kini pakai base URL situs publik
   (Pengaturan Situs → `site_url`, fallback env PUBLIC_SITE_URL) + postMessage cross-origin via `?pbOrigin=`.
4. Manajemen User: peran `marketing_admin` tampil di dropdown; edit user, reset sandi, nonaktifkan, hapus
   (DELETE /api/users/{id} dgn guard diri sendiri & owner terakhir).
5. Master Driver: field Status & Rating manual dihapus (status otomatis dari trip). Tambah tautan akun login
   (drivers.user_id): pilih akun driver yang ada / buat akun baru; kolom "Akun Login"; GET /api/drivers/accounts.
6. Master Armada: dropdown status operasional diganti "Status Unit" (Aktif/Nonaktif); on_trip/maintenance otomatis
   dan ditolak backend bila dikirim dari master data. Verifikasi sinkronisasi trip/maintenance/publik OK.
Testing: test_reports/iteration_3.json & iteration_4.json — semua lulus.

## Yang dikerjakan (sesi lanjutan, sinkron ulang dari github.com/hatacavaya/travel)
Sesi sebelumnya (iteration_5, lulus): edit+hapus lengkap untuk CRM Leads, Penawaran, Pengeluaran.
Sesi ini — audit semua halaman list, dilengkapi yang masih kurang (iteration_6, lulus 10/10 backend, 3/3 flow UI):
1. CRM → Broadcast: PATCH/DELETE /api/broadcasts/{id} (edit hanya draft/failed; hapus dilarang saat 'sending');
   UI tombol edit (dialog sama, judul "Edit Broadcast") & hapus (ConfirmDialog `broadcast-delete-confirm`).
2. Keuangan → Invoice: PATCH /api/invoices/{id} kini menerima amount/due_at/notes/terms (selain status; nominal
   dikunci bila paid/void); DELETE hanya draft/void. UI `InvoiceEditDialog` + tombol hapus untuk Draft/Batal.
3. Mitra → Order Sub-charter: DELETE /api/subcharters/{id} untuk status requested/cancelled (confirmed/settled → 400);
   UI tombol hapus `sc-delete-<id>`.
Halaman yang sudah lengkap/by-design (tidak diubah): Bookings (state machine batal, bukan hapus), Master Data
(nonaktif/gabung SSOT), Users, Drivers, Vehicles, Customers, Maintenance, Workshops, Service Types, Partners,
Segments, Sequences, Campaigns, Add-on, Transfer Routes, Landing Pages, CMS.
Catatan RBAC: marketing_admin memang punya akses section 'crm' (termasuk broadcast) per permissions_config.py.

## Impor konten situs (zip foto dari user) — iteration_7 lulus 11/11
- `content_import/assets/` (7 MB, ikut repo): foto destinasi (Bandung/Bromo/Yogyakarta/Pangandaran), kartu beranda,
  22 foto galeri tamu (auto-crop dari artboard PNG 6401px), 5 hero crop. Sumber zip & folder `src/` di-gitignore.
- `scripts/import_content.py` (idempoten; `--dry-run`, `--force-media`, `--skip-testimonials`): unggah ke Media Library
  (folder "Konten Situs"), upsert 4 destinasi + copywriting lengkap (intro, sorotan berfoto, itinerary, rute, FAQ, hotel,
  SEO), Beranda (hero + section baru `gallery`), page_hero 8 halaman, 3 testimoni tamu (avatar demo pravatar dinonaktifkan).
- Section Page Builder baru `gallery` (backend whitelist + `PhotoGalleryGrid` + Lightbox); detail destinasi kini
  menampilkan galeri & gambar sorotan.
- VPS: `deploy/Dockerfile.backend` menyalin skrip + assets; jalankan `bash deploy/import_content.sh` setelah `update.sh`
  (lihat deploy/README.md §3b).
- Folder Video & Unit Armada di zip kosong — foto armada belum ada (masih unsplash demo).

## Backlog / P1
- Audit penyimpanan foto Media Library (permintaan awal user): cek media_store.py (disk lokal), URL gambar, orphan.
- Rating driver: belum ada sumber data (ulasan per driver) — field disembunyikan; bisa dihitung dari testimoni/trip.
- FAQ/CTA per halaman daftar (fleet/destinations) belum bisa di-override dari builder (hanya hero).

## Sesi 12 Sep 2026 (lanjut) — bug: video tidak bisa dipilih/diunggah ke Media Library
Akar masalah: `accept="image/*,video/*"` mengandalkan registri MIME OS — di Windows (tanpa QuickTime) .mov/.webm tidak
dikenali sehingga file explorer menyembunyikannya; dan bila terpilih pun browser mengirim `application/octet-stream`
yang ditolak backend ("Tipe berkas tidak didukung").
Perbaikan:
1. frontend/src/components/media/mediaApi.js: `ACCEPT_IMAGE`/`ACCEPT_VIDEO`/`ACCEPT_ALL`/`acceptFor(kind)` (ekstensi + MIME eksplisit).
   MediaBrowser: input unggah mengikuti tab aktif (Semua/Foto/Video). MediaDetailPanel: input "Ganti berkas" mengikuti jenis aset.
2. backend/services/media_store.py: `resolve_content_type(content_type, filename)` → tebak MIME dari ekstensi bila kosong/generik;
   dukung `.m4v`/`video/x-m4v`. Dipakai di routers/media.py (upload & replace) dan routers/landing.py.
Testing: test_reports/iteration_8.json — backend 8/8 & UI lulus.

## Backlog
- P1: Galeri (GalleryManager / lp-gallery) masih khusus foto (`pickKind="image"`) — dukung video bila diperlukan (butuh render <video> di halaman publik).
- P2: `GET /api/public/media/{id}` belum mendukung HTTP Range (seek video besar).
- P2: Thumbnail/poster otomatis untuk video (saat ini ikon Film).
