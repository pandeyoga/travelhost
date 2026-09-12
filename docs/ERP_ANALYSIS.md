# 🏢 ANALISIS MENDALAM ERP — Rahaza Travel (Travel & Fleet Management Ecosystem)

> Metodologi: `docs/DEEP_ANALYSIS_PLAYBOOK.md` (bukti sumber primer + traceability + sadar-kendala + temuan spesifik + NOW/LATER).
> Basis bukti: pembacaan langsung `routers/*`, `services/*`, `features/app/*`, `permissions_config.py`, `server.py`, docs SSOT & 2 audit lama.
> Konteks waktu: pasca **Tahap A (Hardening)** + **Tahap B (Pricing/Quotation/CMS/Identity)**. Audit lama (28–29 Jun) sebagian sudah usang → dokumen ini menyegarkan.
> Legenda severity: 🔴 tinggi · 🟠 sedang · 🟢 rendah/kosmetik.

---

# BAGIAN 1 — ANALISIS GENERAL (lintas-modul)

## 1.1 Arsitektur (bukti)
- **Stack:** React (CRA) `data-surface` ganda (publik sinematik vs app data-dense) + FastAPI (router thin + service) + MongoDB (Motor async).
- **Auth/RBAC:** Bearer `sess_` di koleksi `sessions` (`dependencies.get_current_user`), 3 peran (`owner/ops_admin/driver`) via SSOT `permissions_config.SECTION_ACCESS` + `require_role`/`require_section`.
- **Pola domain konsisten:** `core_utils.new_id(prefix)` (UUID berprefiks), `now_iso()` (UTC), `safe_doc()` (strip `_id`/`password_hash`). Router `/api/*` thin; logika di `services/*`.
- **Invarian (INV) terjaga gate:** INV-1 total booking, INV-2/3 pembayaran, INV-4 anti double-booking, INV-5 profit trip, INV-7 stage lead, INV-8 nomor invoice, INV-19 anti double-convert quotation, INV-21 window perawatan.
- **Hardening (Tahap A) aktif:** `counters` ($inc atomik) untuk BK/INV/QUO, rate-limit + honeypot di `/public/*`, agregasi `$group` (bukan scan penuh) di finance/dashboard/reports, audit log append-only, onboarding.
- **Scheduler:** `server.py._scheduler_loop` jalan tiap 120s → `services.notifications.scan` (idempotent via `dedupe_key`).

## 1.2 Rantai data tanpa-silo (terbukti hidup)
`Lead (web/manual) → CRM pipeline → Quotation (QUO) → Convert → Booking (BK) → [checkin driver] Trip → GPS lokasi/geofence → Expense → Profit trip → Invoice (INV) → Inbox/Notifikasi`. Identity/Dedupe (B4) menyatukan Lead↔Customer↔Quotation↔Conversation via nomor ter-normalisasi (`phone_normalized`) → Contact 360.

## 1.3 Kekuatan umum
1. **Disiplin engineering di atas rata-rata**: gate suite "bisa GAGAL", invarian domain, FK guard di DELETE, RBAC ketat, zero-hardcode, `data-testid` masif.
2. **Konsistensi UI ERP**: `section-card`/`kpi-card`/`DataTable`/`DataStates` (loading/empty/error selalu ada), `tabular-nums`, shadcn `Select`, lucide, recharts.
3. **Keuangan & pricing nyata**: P&L cash-basis + per-trip, AR, invoice PDF/Excel (reportlab/openpyxl, tanpa SDK berbayar), Pricing Engine configurable (1 sumber harga untuk kalkulator/quote/booking).
4. **GPS fungsional gratis** (Leaflet/OSRM) dengan live aggregation (tanpa N+1), geofence auto-status, share-link korporat berbatas waktu.

## 1.4 Celah & risiko LINTAS-MODUL (general)
- 🔴 **G1 — Coupling Booking↔Trip longgar & koordinat tujuan hilang.** Trip dibuat *lazily* saat `driver/checkin` (bukan saat booking dikonfirmasi/di-assign). Booking hanya simpan `origin/destination` sebagai teks bebas — **tanpa koordinat**; trip turunan set `dest_lat/lng = None`. Akibat: tak ada alur ERP untuk meng-assign trip & ETA "flagship" bergantung input koordinat manual di layar GPS (tidak ada geocoding destinasi).
- 🔴 **G2 — Status booking `ongoing` adalah "phantom state".** `create→confirmed`, `complete→completed`, `cancel→cancelled`. **Tidak ada transisi ke `ongoing`**, padahal dipakai di Dashboard `_ACTIVE`, guard hapus driver, dan scan notifikasi. Booking tidak pernah merefleksikan "sedang berjalan" (hanya Trip yang punya `on_trip`).
- 🔴 **G3 — Cakupan Audit Log tidak merata.** Tercatat: vehicle/driver/customer/payment/expense/invoice/quotation/booking-status. **TIDAK tercatat:** user create/update (ubah peran/sandi — paling sensitif), maintenance CRUD, broadcast send, settings (perlu verifikasi), login/logout. → jejak akuntabilitas berlubang.
- 🟠 **G4 — Maintenance cost di luar P&L.** `services/finance.profit_loss` hanya Σ koleksi `expenses`; `maintenance_records.cost` tidak ikut → biaya operasional understated.
- 🟠 **G5 — Invoice terlepas dari pembayaran.** `invoice.status` (draft/sent/paid) di-set manual, **tidak direkonsiliasi** dengan `booking.payment_status`/`payments`. Risiko invoice "paid" padahal AR masih ada (atau sebaliknya).
- 🟠 **G6 — WhatsApp & notifikasi keluar = SIMULASI.** Inbox reply, broadcast, & reminder hanya in-app/penanda; **tidak terkirim ke nomor pelanggan** (butuh WABA). Reminder **SIM driver belum di-scan** (hanya KIR/pajak/servis).
- 🟠 **G7 — Keamanan auth.** `hash_password` = SHA256 + salt **global statik** (bukan bcrypt/argon2, tanpa per-user salt); **tak ada rate-limit di `/auth/login`** (rate-limit hanya di `/public/*`) → rawan brute-force & offline-cracking; sesi 7 hari tanpa rotasi.
- 🟠 **G8 — Tidak ada proteksi self-lockout/last-owner.** `users.py` mengizinkan owner menonaktifkan/menurunkan peran dirinya/owner terakhir → risiko terkunci dari sistem.
- 🟢 **G9 — Realtime = polling** (Inbox/chat). Latensi beberapa detik (OK untuk MVP).
- 🟢 **G10 — Pemetaan driver→user rapuh** (`user_id` → fallback `phone` → `name`): risiko salah-cocok bila nama kembar.
- 🟢 **G11 — Beberapa baca masih besar tapi bounded** (`bookings/calendar` 1000, P&L `trips` 5000). Aman pada skala sekarang; siapkan pagination saat tumbuh.

## 1.5 Scorecard kematangan (per dimensi)
| Dimensi | Skor | Catatan |
|---|:--:|---|
| Arsitektur & guardrails | 9/10 | Sangat disiplin |
| Integritas data/invarian | 9/10 | INV lengkap; celah `ongoing`/invoice-AR |
| Keuangan & pricing | 8/10 | Kuat; maintenance cost & rekonsiliasi invoice kurang |
| GPS & operasional | 7/10 | Fungsional; coupling trip & koordinat lemah |
| CRM & sales funnel | 8/10 | Lengkap; analytics ROI/source belum |
| Komunikasi (Inbox/Notif) | 6/10 | UI/DB matang; pengiriman nyata = simulasi |
| Keamanan | 6/10 | RBAC kuat; hashing/rate-limit login lemah |
| Auditability | 7/10 | Engine ada; cakupan berlubang |
| UI/UX ERP | 8/10 | Konsisten, data-dense rapi; minim bulk-action/shortcut |
| **Keseluruhan (scope terbangun)** | **🟢 FIT-FOR-PURPOSE** | MVP operasional sehat & terverifikasi |

---

# BAGIAN 2 — ANALISIS KOMPREHENSIF PER-MODUL

> Format tiap modul: **Fungsi (bukti)** · **Kekuatan** · **Celah/Risiko** · **Rekomendasi (NOW/LATER)**.

## M1 — Autentikasi & Sesi  (`routers/auth.py`, `dependencies.py`, `core_utils.py`)
- **Fungsi:** login email+password → token `sess_` (7 hari), `/auth/me`, logout (hapus sesi). Validasi sesi + expiry + status user aktif.
- **Kekuatan:** alur bersih; `safe_doc` tak pernah bocorkan `password_hash` (terverifikasi audit); cek akun nonaktif.
- **Celah:** 🔴 hashing SHA256+salt statik (G7); 🔴 tanpa rate-limit/lockout login (brute-force); 🟠 tanpa rotasi/refresh token & tanpa "logout all"; 🟢 login/logout tak ter-audit.
- **Rekomendasi NOW:** bcrypt/argon2 + per-user salt (migrasi hash on-login), rate-limit `/auth/login` (reuse limiter Tahap A), audit login gagal/berhasil. **LATER:** refresh token + device list + "keluar dari semua sesi".

## M2 — Users & RBAC  (`routers/users.py`, `permissions_config.py`)
- **Fungsi:** CRUD user (owner-only), set peran/status/sandi; SSOT `SECTION_ACCESS` 15 section × 3 peran.
- **Kekuatan:** RBAC deklaratif & dipakai konsisten; email unik; password di-hash saat create/update.
- **Celah:** 🔴 mutasi user **tak ter-audit** (G3); 🟠 **tak ada guard self-lockout/last-owner** (G8); 🟢 tak ada "nonaktifkan vs hapus" (hanya status); tak ada paksa ganti sandi awal.
- **Rekomendasi NOW:** audit create/update user (mask sandi), guard "minimal 1 owner aktif" & larang menurunkan peran diri sendiri. **LATER:** undangan via email, kebijakan sandi, 2FA owner.

## M3 — Dashboard "Control Tower"  (`routers/dashboard.py`, `features/app/Dashboard.jsx`)
- **Fungsi:** KPI role-aware (booking aktif/armada/driver/customer/pemasukan bln/AR/total/lead baru) + reminder dokumen due-soon + booking terbaru + chart entitas + Onboarding + `InfoTip`.
- **Kekuatan:** agregasi `$group` (bukan scan), state lengkap, tabular-nums, tip edukatif, role-filtered.
- **Celah:** 🟠 "Booking Aktif" memakai `ongoing` (G2) → praktis hanya `confirmed`; 🟢 chart "ringkasan entitas" bernilai informatif rendah (count mentah) — bisa diganti tren pemasukan/booking 6 bulan; 🟢 reminder hanya dokumen armada (SIM driver absen, G6).
- **Rekomendasi NOW:** ganti chart count → tren pemasukan & booking; sertakan reminder SIM. **LATER:** widget "tugas hari ini" (keberangkatan/checkin/follow-up) lintas-modul.

## M4 — Bookings & Trip Lifecycle  (`routers/bookings.py`, `trips.py`, `driver.py`, `services/availability.py`, `Bookings.jsx`)
- **Fungsi:** list/calendar/availability/create/edit/confirm/cancel/complete; anti double-booking + window perawatan (400); auto-hitung harga via Pricing Engine bila `base_price≤0`; pembayaran via dialog; trip dibuat saat checkin driver, status trip (standby→to_pickup→on_trip→completed) + geofence.
- **Kekuatan:** proteksi server-side kuat (INV-4/21), kalender warna status, snapshot nama (INV-10), edit terbatas (jaga stabilitas harga).
- **Celah:** 🔴 coupling Booking↔Trip & koordinat tujuan (G1); 🔴 phantom `ongoing` (G2); 🟠 tak ada "assign driver+jadwal trip" dari ERP sebelum checkin; 🟠 create/edit booking tak ter-audit (hanya transisi); 🟢 reschedule (ubah tanggal) tak didukung (harus batal+buat ulang).
- **Rekomendasi NOW:** tambah state `ongoing` (saat checkin/`to_pickup`) + sinkron Dashboard/guard; aksi "Assign & Jadwalkan Trip" (buat trip + set `dest_lat/lng` via map/geocode); audit create/edit. **LATER:** reschedule berpemandu (cek ulang konflik).

## M5 — Armada / Vehicles  (`routers/vehicles.py`, `Vehicles.jsx`, `VehicleFormDialog.jsx`)
- **Fungsi:** CRUD master + guard DELETE (FK booking) + audit; dokumen KIR/pajak/servis → reminder.
- **Kekuatan:** FK guard, audit, reminder dokumen otomatis (bucket urgensi).
- **Celah:** 🟠 `photos`/galeri/`tour_scenes`/`specs` belum ada di schema (blok fitur 360 website — lihat plan UI/UX Fase 2); 🟢 tak ada histori utilisasi/ROI per unit di detail; 🟢 odometer hanya diperbarui via maintenance complete.
- **Rekomendasi NOW (untuk overhaul web):** tambah field media+360 (lihat `plan.md`). **LATER:** ringkasan utilisasi & profit per unit, riwayat servis di detail armada.

## M6 — Drivers & Surface Driver  (`routers/drivers.py`, `driver.py`, `Drivers.jsx`, `DriverCheckin.jsx`)
- **Fungsi:** CRUD driver (+audit, FK guard), data SIM/expiry/rating; driver mode web: `my-trips`, checkin (buat trip dari booking), checkout.
- **Kekuatan:** alur checkin→trip→update status unit/driver mulus; FK guard hapus.
- **Celah:** 🟠 **reminder SIM otomatis belum ada** (G6); 🟠 pemetaan user↔driver rapuh (G10) — tak ada field `user_id` terisi saat create user driver; 🟢 tak ada beban/jadwal driver (kalender penugasan).
- **Rekomendasi NOW:** tambah sumber reminder SIM ke `notifications.scan`; tautkan `drivers.user_id` saat onboarding driver. **LATER:** kalender penugasan driver + indikator ketersediaan.

## M7 — Customers & Contact 360  (`routers/customers.py`, `services/identity.py`, `Customers.jsx`, `CustomerDetailDialog.jsx`)
- **Fungsi:** CRUD (+dedupe tolak kontak ganda 409, +audit), Contact 360 (booking+lead+quotation+conversation+timeline terpadu via `phone_normalized`), statistik (LTV, jumlah).
- **Kekuatan:** dedupe & auto-link kuat (B4); timeline lintas-entitas; total_spent dari paid_amount.
- **Celah:** 🟢 `lifetime_value`/`total_trips` di dokumen tak selalu sinkron (statistik dihitung on-read; field tersimpan bisa stale); 🟢 tak ada segmentasi (korporat vs individu) lanjut/label; 🟢 W1 lama (tabular-nums) — perlu cek cepat.
- **Rekomendasi NOW:** recompute `lifetime_value/total_trips` saat pembayaran/booking complete (atau hapus field stale, andalkan on-read). **LATER:** label/segmentasi & ekspor kontak.

## M8 — CRM / Leads  (`routers/leads.py`, `services/crm.py`, `Leads.jsx`/`Crm.jsx`, `CrmKanban`, `LeadDetailDrawer`)
- **Fungsi:** pipeline 6-stage (INV-7), list/filter/cari, auto-assign least-loaded, aktivitas timeline, reminder H-7/3/1/overdue, convert→customer (dedupe), pipeline summary (konversi, nilai).
- **Kekuatan:** sangat lengkap; auto-assign adil; identity link; aktivitas tercatat rapi.
- **Celah:** 🟠 **analytics by-source & ROI channel belum ada** (brief minta); 🟠 tak ada SLA/aging per stage (selain reminder trip_date); 🟢 lead tak ter-audit (pakai `lead_activities` — dapat diterima).
- **Rekomendasi NOW:** dashboard konversi per `source` (website/WA/ads/referral) + nilai menang/kalah. **LATER:** SLA respons, skor lead, LTV per source.

## M9 — Quotations (Penawaran)  (`routers/quotations.py`, `services/quotations.py`, `services/pricing.py`, `Quotations.jsx`)
- **Fungsi:** lifecycle draft→sent→accepted→converted/rejected; item auto via Pricing Engine atau manual; nomor QUO atomik; PDF; convert→booking (cek konflik/maintenance, dedupe customer, update lead→won, INV-19 anti double-convert); audit + log aktivitas lead.
- **Kekuatan:** funnel terhubung (lead↔quote↔booking), proteksi konversi, PDF, snapshot harga.
- **Celah:** 🟠 `valid_until` **tidak ditegakkan** (penawaran kedaluwarsa masih bisa accept/convert); 🟠 `accept` boleh dari `draft` (lewati `sent`) — longgar; 🟠 tak ada pengiriman penawaran (email/WA) — manual unduh PDF; 🟢 tak ada versi/revisi penawaran.
- **Rekomendasi NOW:** tegakkan kedaluwarsa (tolak/auto-`expired`), perketat transisi accept hanya dari `sent`. **LATER:** kirim PDF via WA/email + e-acceptance link publik.

## M10 — Inbox / Conversations  (`routers/inbox.py`, `Inbox.jsx`, `public.chat`)
- **Fungsi:** percakapan multi-admin (web-chat + WA simulasi), thread, status pesan (sent/delivered/read), assign agen, catatan internal (tak bocor ke pelanggan — terverifikasi), filter (unassigned/mine/all), unread.
- **Kekuatan:** pemisahan internal/eksternal aman, assign & status, integrasi web-chat publik (token).
- **Celah:** 🟠 pengiriman keluar = simulasi (G6, butuh WABA); 🟢 realtime = polling (G9); 🟢 tak ada SLA/queue antar-agen, tak ada lampiran/template balasan cepat.
- **Rekomendasi NOW:** template balasan cepat + indikator SLA. **LATER:** WABA nyata (adapter mock|real), websocket/SSE, lampiran media.

## M11 — Broadcasts  (`routers/broadcasts.py`)
- **Fungsi:** segmentasi audiens dari `leads` (stage/source), buat draft, kirim (SIMULASI: set `sent` + hitung penerima).
- **Kekuatan:** struktur segmentasi siap; recipients dihitung dari segmen nyata.
- **Celah:** 🟠 `scheduled_at` disimpan tapi **tak ada scheduler yang mengirim terjadwal**; 🟠 tak ada record per-penerima/status kirim; 🟠 tak ada audit; 🔴(untuk go-live) tanpa WABA = tidak terkirim.
- **Rekomendasi NOW:** catat audit + tandai jelas "simulasi" di UI. **LATER:** WABA + eksekusi terjadwal + log per-penerima + opt-out.

## M12 — Notifications & Reminder Engine  (`routers/notifications.py`, `services/notifications.py`, scheduler)
- **Fungsi:** scan idempotent (dokumen armada, follow-up lead, keberangkatan booking ≤24j) → `notification_tasks`; visibilitas per-peran; read/dismiss/read_all; bell + badge.
- **Kekuatan:** idempotensi (`dedupe_key`), targeting peran/agen, scheduler 120s, in-app center rapi.
- **Celah:** 🟠 **kanal hanya in-app** (G6) — bukan WA/email/push; 🟠 **SIM driver tak di-scan**; 🟢 tak ada preferensi notifikasi per-user.
- **Rekomendasi NOW:** tambah sumber SIM driver. **LATER:** kanal WA/email + preferensi per-user + digest harian.

## M13 — Finance (Payments/Expenses/Invoices/P&L/AR)  (`routers/payments.py|expenses.py|invoices.py|finance.py`, `services/finance.py`, `services/exporter.py`, `Finance.jsx`)
- **Fungsi:** catat pembayaran (INV-2/3, audit), pengeluaran berkategori (recompute profit trip INV-5, audit), invoice dari booking (nomor atomik reset tahunan, PDF/Excel, audit), P&L cash-basis + per-trip + per-kategori, AR via pipeline.
- **Kekuatan:** agregasi server-side, export pure-python, audit pada mutasi, KPI rapi (tabular-nums, periode selektor).
- **Celah:** 🟠 **maintenance cost tak masuk P&L** (G4); 🟠 **invoice.status terlepas dari pembayaran** (G5) — tak ada rekonsiliasi/auto-paid saat lunas; 🟢 P&L "revenue" cash-basis vs total accrual booking bisa membingungkan tanpa label; 🟢 tak ada export PDF P&L (hanya invoice PDF; laporan Excel).
- **Rekomendasi NOW:** sertakan biaya maintenance ke pengeluaran/P&L; auto-set invoice `paid` saat booking lunas (atau tampilkan badge sinkron AR↔invoice). **LATER:** jurnal kas/bank, multi-metode rekonsiliasi, export PDF laporan.

## M14 — Reports  (`routers/reports.py`, `services/reports.py`, `Reports.jsx`)
- **Fungsi:** ringkasan agregat (tren/kategori/status/top-customer/utilisasi) + export Excel; section `reports` (owner/ops).
- **Kekuatan:** read-only, agregasi, export.
- **Celah:** 🟢 hanya Excel (tanpa PDF/print), 🟢 belum ada filter dimensi (per-armada/per-driver/per-source) mendalam, 🟢 belum ada penjadwalan/email laporan.
- **Rekomendasi LATER:** filter dimensi + export PDF + kirim laporan terjadwal.

## M15 — GPS Tracking  (`routers/locations.py|trips.py|shares.py`, `services/geofence.py|osrm.py|geo.py|maps.py`, `GpsTracking.jsx`, `LiveMap`)
- **Fungsi:** ingest lokasi (validasi koordinat, timestamp server INV-6, geofence auto-status), live per-armada (aggregation + stale/offline + moving/idle), histori/playback, ETA (OSRM + fallback haversine), share-link korporat (expiry/revoke/access count) + `/track/:token` publik.
- **Kekuatan:** flagship; tanpa N+1; gratis (Leaflet/OSRM); geofence; berbagi aman.
- **Celah:** 🔴 ETA bergantung `dest_lat/lng` yang **tak tertangkap dari booking** (G1) — tak ada geocoding destinasi; 🟠 Google Maps masih stub (brief minta); 🟢 tak ada speeding/idle alert, tak ada riwayat ringkas per-trip (jarak total/durasi) yang dipersist.
- **Rekomendasi NOW:** geocode destinasi booking → isi `dest_lat/lng` trip; persist ringkasan trip (jarak/durasi). **LATER:** swap Google Maps (kunci user), alert kecepatan/diam, replay timeline.

## M16 — Maintenance  (`routers/maintenance.py`, `services/maintenance.py`, `Maintenance.jsx`)
- **Fungsi:** jadwal/riwayat servis, window perawatan blok availability (INV-21), reminder KIR/pajak/servis (H-30/14/7/overdue), sinkron status armada (maintenance↔available), complete set `last_service_date`/odometer.
- **Kekuatan:** integrasi availability (INV-21), sinkron status unit, reminder bucket.
- **Celah:** 🟠 **CRUD maintenance tak ter-audit** (G3); 🟠 **cost tak masuk P&L** (G4); 🟢 tak ada jadwal servis berkala otomatis (interval km/bulan).
- **Rekomendasi NOW:** audit maintenance + alirkan cost ke finance. **LATER:** servis preventif terjadwal (interval), vendor/bengkel master.

## M17 — CMS / Content  (`routers/content.py`, `ContentManager.jsx`, `ContentFormDialog.jsx`)
- **Fungsi:** CRUD 5 resource (destinations/packages/articles/testimonials/promos) via SSOT `SCHEMAS`, whitelist field per-resource, role `cms` (owner/ops).
- **Kekuatan:** form generik berbasis schema, role-gated.
- **Celah:** 🟠 tanpa galeri/360 builder/live-preview/multi-theme (lihat `plan.md` Fase 5); 🟠 **armada tak dikelola di CMS** (master data via Vehicles); 🟢 tanpa draft/publish & versioning konten.
- **Rekomendasi:** lihat `plan.md` (overhaul UI/UX Fase 5). **LATER:** draft/publish + audit konten.

## M18 — Settings & Pricing Engine  (`routers/settings.py`, `services/pricing.py`, `Settings.jsx`)
- **Fungsi:** profil perusahaan, harga & kebijakan (DP/min-sewa/pembatalan), **Pricing Rules** configurable (tarif per tipe, driver/BBM/tol, surcharge weekend/libur, DP, rounding), kalender operasional (jam + hari libur). Owner-only.
- **Kekuatan:** 1 sumber harga untuk kalkulator publik/quote/booking; granular; form rapi.
- **Celah:** 🟠 perubahan settings perlu dipastikan ter-audit (G3); 🟢 tak ada validasi nilai (mis. surcharge 0–100); 🟢 belum ada `theme_config` (akan ditambah di overhaul).
- **Rekomendasi NOW:** audit perubahan settings + validasi rentang. **LATER:** `theme_config` multi-theme (plan UI/UX).

## M19 — Audit Log  (`routers/audit_logs.py`, `services/audit.py`)
- **Fungsi:** viewer append-only (owner-only), filter entity/action/cari, before/after.
- **Kekuatan:** append-only, tanpa endpoint tulis API, filter berguna.
- **Celah:** 🔴 **cakupan berlubang** (G3: user/maintenance/broadcast/login); 🟢 tak ada export & retensi/rotasi.
- **Rekomendasi NOW:** lengkapi cakupan ke semua aksi sensitif. **LATER:** export + kebijakan retensi.

## M20 — Onboarding & In-App Help  (`routers/onboarding.py`, `services/onboarding.py`, `OnboardingChecklist`, `InfoTip`)
- **Fungsi:** checklist per-peran (status derived dari data nyata + manual + dismiss/reset), tip in-app pada KPI.
- **Kekuatan:** menurunkan friksi pengguna baru, derivasi otomatis.
- **Celah:** 🟢 cakupan tip terbatas, tak ada tur produk/empty-state edukatif di semua modul.
- **Rekomendasi LATER:** product tour ringan + empty-state ber-aksi di tiap modul.

---

# BAGIAN 3 — BACKLOG PERBAIKAN TERPRIORITAS (usulan, evidence-based)

### 🔴 P0 — Integritas & keamanan inti
1. **G2** Tambah state booking `ongoing` (saat checkin/`to_pickup`) + sinkron Dashboard/guard/scan. *(hapus phantom state)*
2. **G1** Tangkap koordinat tujuan (geocode) di booking→trip agar ETA/GPS andal + alur "Assign & Jadwalkan Trip" di ERP.
3. **G3** Lengkapi Audit Log: user mgmt, maintenance, broadcast, settings, login. *(akuntabilitas)*
4. **G7** Keamanan auth: bcrypt/argon2 + rate-limit `/auth/login` + audit login.
5. **G8** Guard last-owner/self-lockout di Users.

### 🟠 P1 — Kelengkapan domain & paritas brief
6. **G4** Maintenance cost → masuk pengeluaran/P&L.
7. **G5** Rekonsiliasi Invoice↔Pembayaran (auto-`paid` saat lunas / badge sinkron).
8. **G6** Reminder **SIM driver** otomatis + tandai jelas channel WA = simulasi.
9. **M8** CRM analytics by-source & ROI channel; **M9** tegakkan kedaluwarsa & perketat transisi quotation.
10. **M10/M11** Template balasan + audit broadcast + label "simulasi".

### 🟢 P2 — Nilai tambah / skala (banyak = roadmap Tier C brief)
11. WABA nyata (adapter), Google Maps swap, GA4/Pixel, Payment Gateway, object-storage media, SSR/SEO.
12. Bulk action + pagination lanjutan + shortcut keyboard; export PDF laporan; product tour.
13. Reschedule booking berpemandu; kalender penugasan driver; servis preventif terjadwal; segmentasi customer.

> **Aturan eksekusi:** tiap perubahan backend WAJIB jaga `bash scripts/gate.sh` HIJAU 10/10 + sinkron `docs/03,04,05` + `testing_agent_v3`. Hindari koleksi DB baru bila bisa (tempel field di koleksi kanonik).

---

## Lampiran — Apa yang BERUBAH sejak audit lama (28–29 Jun)
- Audit lama menandai sebagai gap: Audit Log, Atomic Counters, Rate-limit publik, Pagination, Onboarding (Tahap A) **dan** Pricing Engine, Quotation lifecycle, CMS, Identity (Tahap B). **Semua kini SUDAH ADA** (terverifikasi di kode). Dokumen ini fokus pada **celah tersisa & yang baru terlihat pasca-Tahap B** (G1–G11 di atas).

_Versi 1.0 · Analisis oleh Neo · basis: pembacaan kode langsung + gate/audit SSOT._
