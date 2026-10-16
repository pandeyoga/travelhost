# 🚀 RAHAZA ERP — ANALISIS NILAI BISNIS PER-DOMAIN & RENCANA TRANSFORMASI

> Lensa: **NILAI BISNIS & PENGELOLAAN OPERASI**, bukan sekadar kesehatan teknis (itu di `ERP_ANALYSIS.md`).
> Metodologi: `docs/DEEP_ANALYSIS_PLAYBOOK.md`. Basis: pembacaan kode langsung seluruh router/service/fitur.
> Dokumen pendamping: `plan.md` (overhaul UI/UX website) — keduanya disatukan di §SEQUENCING.

---

## 0. TESIS UTAMA (diagnosis jujur)

Sistem sekarang = **System of Record yang sangat rapi** (mencatat booking/keuangan/GPS dengan disiplin).
Yang Anda minta = **System of Growth & Management** (menggerakkan konversi, mengotomasi operasi, dan
memberi keputusan berbasis data). Gap-nya besar dan terkonsentrasi di **3 lubang strategis**:

1. 🕳️ **CRM pasif, bukan growth engine.** Pipeline + aktivitas manual + WA simulasi. Tidak ada nurturing
   otomatis, lead scoring, SLA, segmentasi, retensi, atau LTV. → Lead masuk lalu "didiamkan" → konversi bocor.
   *(Kritik Anda tepat: CRM saat ini minim nilai bisnis.)*
2. 🕳️ **Tidak ada lapisan Otomasi/Trigger (Event → Aksi).** Semua aksi manual; komunikasi keluar = simulasi.
   Tidak ada "WA masuk → buat lead", "booking confirm → konfirmasi WA", "driver berangkat → notifikasi customer".
3. 🕳️ **BI/Manajemen nyaris kosong.** Dashboard = hitungan mentah + bar-chart entitas. Tidak ada tren omzet,
   funnel konversi, ROI channel, utilisasi armada, AR aging, performa driver, atau forecast. → Manajemen "buta data".

Ketiganya saling mengunci: **WA nyata + Automation Engine** adalah *fondasi* yang menghidupkan CRM growth-engine
DAN mengotomasi operasi DAN memberi sinyal ke BI. Itu sebabnya rencana ini menempatkannya paling awal.

---

## 1. SCORECARD NILAI BISNIS PER-DOMAIN

> Record = kemampuan mencatat · Growth/Mgmt = kemampuan menggerakkan bisnis/keputusan.

| # | Domain | Record | Growth/Mgmt | Lubang bisnis utama |
|---|--------|:--:|:--:|---|
| D1 | Akuisisi & Funnel (Web→Lead→Quote→Booking) | 8 | 4 | Tak ada attribution channel, tak ada auto-nurture, hand-off lambat |
| D2 | **CRM & Customer Lifecycle** | 7 | **2** | Pasif: no scoring/SLA/segmentasi/retensi/LTV/otomasi |
| D3 | **WhatsApp Omnichannel & Automation** | 3 | **1** | Semua simulasi; tak ada in-app WA nyata; tak ada trigger |
| D4 | Booking & Dispatch Operations | 8 | 4 | Tak ada dispatch board, assign-trip, konfirmasi keberangkatan/driver |
| D5 | Fleet & Maintenance (Asset) | 8 | 5 | Tak ada utilisasi/ROI per unit, servis preventif, maintenance→P&L |
| D6 | Finance & Profitability | 8 | 6 | AR collection manual, invoice↔bayar terpisah, no cashflow/forecast |
| D7 | GPS & Service Delivery | 7 | 5 | ETA tak otomatis ke customer; tak ada bukti layanan (POD) |
| D8 | **Business Intelligence & Management** | 3 | **2** | Tak ada exec dashboard/funnel/ROI/forecast/ops-cockpit |
| D9 | People, Access & Driver App | 7 | 5 | Driver web-only, mapping rapuh, audit berlubang |
| D10 | Platform & Integrations | 5 | 3 | Tak ada event bus, integration hub, secret vault, multi-channel |

**Rata-rata Growth/Mgmt ≈ 3.4/10** → inilah ruang nilai bisnis yang belum digarap.

---

## 2. ANALISIS MENDALAM PER-DOMAIN (lensa bisnis)

### D1 — Akuisisi, ADS Integration & Atribusi  ★ (FOKUS REVISI USER)
- **Sekarang:** Web form → lead "new" → CRM; kalkulator harga; quotation→booking. Solid sebagai pipa data.
- **Lubang bisnis:** (a) **tanpa attribution** (source "manual", tak bedakan organic/ads/WA/referral) → tak bisa ukur channel cuan; (b) **belum ada penangkapan lead dari IKLAN** (Meta/Google/TikTok Lead Ads) langsung ke CRM; (c) **hand-off lambat** (tak ada auto-ack saat lead masuk); (d) **data kontak iklan (telp/email) tak ter-capture untuk blasting/remarketing**; (e) tak ada **A/B/funnel tracking**, **GA4/Pixel**, **SEO teknikal**.
- **Target:** setiap lead (web + iklan) **ter-capture otomatis** dgn **atribusi penuh** (source/campaign/utm/gclid/fbclid) + kontak (telp/email + **consent**) tersimpan → **audiens blasting/remarketing**, auto-ack <60 dtk, funnel terukur + **closed-loop ROAS** balik ke platform iklan.
- **Membuka:** konversi naik + **alokasi budget iklan berbasis ROI nyata**.
- **Detail desain:** lihat **§3.5 (Ads/Lead Capture/Atribusi)** & **§3.6 (SEO/Analytics)**; fase khusus **E-ADS** di §4.

### D2 — CRM & Customer Lifecycle  ★ (prioritas kritik Anda)
- **Sekarang:** 6-stage pipeline, auto-assign least-loaded, aktivitas manual, reminder berbasis `trip_date`, convert→customer (dedupe), Contact 360.
- **Lubang bisnis:**
  - **Tidak ada otomasi nurturing** (sequence follow-up H+0/H+1/H+3, reminder DP, winback) — agen harus ingat manual.
  - **Tidak ada lead scoring & SLA** (mana lead panas? mana yang telat direspon?). Tak ada "aging per stage".
  - **Tidak ada segmentasi & lifecycle pelanggan** (prospek→pelanggan baru→loyal→dorman→hilang); tak ada **LTV/RFM**, tak ada **retensi/rebooking**.
  - **Tidak terhubung WA nyata** → percakapan & konteks tidak menyatu; agen kerja di 2 tempat (HP & ERP).
  - **Broadcast = simulasi**, tanpa per-penerima/opt-out/terjadwal.
- **Target:** CRM = **growth engine**: lead scoring + SLA timer + nurturing sequence otomatis (via WA), segmentasi & lifecycle, LTV/RFM, retensi/winback campaign, unified timeline (booking+quote+WA chat) yang actionable.
- **Membuka:** konversi naik, response-time turun, repeat-order naik, agen 1 layar.

### D3 — WhatsApp Omnichannel & Automation Engine  ★ (fondasi)
- **Sekarang:** Inbox multi-admin (web-chat nyata + **WA simulasi**), pesan ditandai "delivered" tapi **tidak terkirim**; broadcast simulasi; notifikasi **in-app saja**. Tak ada trigger WA↔ERP.
- **Lubang bisnis (inti permintaan Anda):**
  - **In-app WA belum nyata** → admin tetap buka HP pribadi; tak ada histori tergabung, tak ada akuntabilitas.
  - **Tidak ada Smart Trigger** (Event→Aksi):
    • Lead web masuk → **auto-ack WA** + assign agen.
    • Quotation terkirim → **kirim PDF/ringkasan via WA**.
    • Booking confirm → **konfirmasi WA + instruksi DP**.
    • Reminder **DP & pelunasan** via WA.
    • **Konfirmasi keberangkatan** H-1/hari-H ke customer (driver+unit+titik jemput+link live-track).
    • **Driver dispatch**: "driver ditugaskan / dalam perjalanan / tiba" → WA customer (+ETA).
    • Trip selesai → **terima kasih + minta ulasan + tawaran rebooking**.
  - **Inbound automation belum ada**: pesan WA masuk → identifikasi/buat lead → auto-reply (jam kerja/menu) → routing → handoff agen; (lanjutan: **AI assistant grounded** ke Pricing/Availability/CMS untuk jawab harga/ketersediaan tanpa halusinasi → bisa **buat draft booking** dari chat).
  - **Tidak ada manajemen template WABA, session-window, opt-in/out, cost-tracking, audit per pesan.**
- **Target arsitektur:** **WhatsApp Adapter (provider-agnostic: `mock | meta_cloud | partner`)** + **Automation/Event Engine** (domain events → rules → actions) yang **idempotent, auditable, configurable**.
- **Membuka:** semua domain lain "hidup"; admin 1 layar; konversi & kepuasan naik; ops tanpa lupa.

### D4 — Booking & Dispatch Operations
- **Sekarang:** create/confirm/cancel/complete + anti double-booking + window perawatan + auto-harga. Tabel + kalender.
- **Lubang bisnis:** (a) **tak ada dispatch board** ("hari ini berangkat apa, siapa sopirnya, unit mana, sudah dikonfirmasi?"); (b) **trip dibuat baru saat checkin** & **koordinat tujuan hilang** (G1) → tak ada penjadwalan/assign trip dari ERP, ETA rapuh; (c) **status `ongoing` phantom** (G2); (d) **tak ada konfirmasi keberangkatan & checklist** (titik jemput, kontak driver) — saat ini hanya notifikasi in-app; (e) tak ada **POD/arrival confirmation**.
- **Target:** **Ops Cockpit "Hari Ini"** + alur **Assign & Jadwalkan Trip** (driver+unit+geocode tujuan) + **konfirmasi keberangkatan otomatis (WA)** + status ongoing nyata + bukti layanan.
- **Membuka:** operasi terkendali, zero "lupa konfirmasi", pengalaman pelanggan premium.

### D5 — Fleet & Maintenance (Manajemen Aset)
- **Sekarang:** master + dokumen/reminder + window perawatan + sinkron status.
- **Lubang bisnis:** (a) **tak ada utilisasi & ROI per unit** (okupansi %, omzet/unit, biaya/unit); (b) **maintenance cost tak masuk P&L** (G4) → profit per unit semu; (c) tak ada **servis preventif terjadwal** (interval km/bulan) → reaktif; (d) tak ada master bengkel/vendor.
- **Target:** dashboard aset (utilisasi/ROI/biaya per unit), maintenance cost → finance, servis preventif otomatis.
- **Membuka:** keputusan beli/jual/istirahatkan unit berbasis profit nyata.

### D6 — Finance & Profitability
- **Sekarang:** payments (INV-2/3), expenses (INV-5), invoice PDF/Excel (atomik), P&L cash-basis + per-trip, AR.
- **Lubang bisnis:** (a) **AR collection manual** → tak ada reminder tagih otomatis (WA) & aging; (b) **invoice.status terpisah dari pembayaran** (G5); (c) **maintenance cost di luar P&L** (G4); (d) tak ada **cashflow & proyeksi**, tak ada **export PDF laporan**; (e) tak ada DP otomatis ter-link ke konfirmasi booking.
- **Target:** AR collection otomatis (WA reminder + aging), rekonsiliasi invoice↔bayar, P&L komprehensif (incl. maintenance), cashflow & forecast sederhana.
- **Membuka:** piutang turun, profit akurat, kas terprediksi.

### D7 — GPS & Service Delivery
- **Sekarang:** live aggregation, geofence auto-status, ETA OSRM, share-link korporat, `/track/:token`.
- **Lubang bisnis:** (a) **ETA/link live tidak otomatis dikirim ke customer** (padahal aset pembeda!); (b) **dest coords tak tertangkap** (G1) → ETA rapuh; (c) tak ada **POD** (foto/tanda terima), tak ada alert kecepatan/diam; (d) ringkasan trip (jarak/durasi) tak dipersist untuk laporan.
- **Target:** link live-track + ETA otomatis via WA saat berangkat; POD; ringkasan trip tersimpan.
- **Membuka:** kepercayaan korporat, diferensiasi "transparan & terpantau".

### D8 — Business Intelligence & Management  ★
- **Sekarang:** Dashboard = KPI hitungan + reminder + bar-chart entitas (count). Reports = agregat + Excel. **Tidak ada analitik keputusan.**
- **Lubang bisnis:** tak ada **tren omzet/laba/margin**, **funnel konversi per channel + ROI + LTV/CAC**, **utilisasi/okupansi armada**, **AR aging**, **performa driver (on-time, trip, rating)**, **cohort/retensi**, **forecast**, dan **Ops Cockpit "hari ini"** yang actionable.
- **Target:** **BI & Management Cockpit** berlapis: (1) Executive (omzet/laba/utilisasi/AR), (2) Funnel & Channel ROI, (3) Ops Today, (4) Fleet/Driver performance, (5) Retensi & forecast. Semua via MongoDB aggregation (bounded) + recharts + export.
- **Membuka:** manajemen berbasis data — alokasi sumber daya & marketing yang benar.

### D9 — People, Access & Driver App
- **Sekarang:** RBAC 3 peran solid; driver mode **web** (checkin/out); audit sebagian.
- **Lubang bisnis:** (a) **audit berlubang** (user/maintenance/broadcast/login — G3) → akuntabilitas; (b) **mapping driver↔user rapuh** (G10); (c) driver app minim (tanpa jadwal, navigasi, konfirmasi tugas, unggah POD); (d) **keamanan login lemah** (G7) & **tak ada guard last-owner** (G8).
- **Target:** audit penuh, driver workspace (jadwal+navigasi+konfirmasi+POD), hardening auth.
- **Membuka:** akuntabilitas & operasi lapangan yang andal.

### D10 — Platform & Integrations
- **Sekarang:** tak ada event bus/automation, tak ada integration hub/secret vault; notifikasi 1 kanal (in-app); Maps OSRM (Google stub); tak ada GA4/Pixel/Payment.
- **Lubang bisnis:** setiap integrasi nanti dibangun ad-hoc; tak ada fondasi aman untuk kredensial; tak ada multi-channel.
- **Target:** **Integration Hub + secret vault (enkripsi) + Event Bus + Automation Engine** sebagai fondasi semua otomasi & integrasi (WA/Maps/GA4/Payment/email/IG).
- **Membuka:** skalabilitas integrasi & otomasi tanpa utang teknis.

---

## 3. ARSITEKTUR TARGET (yang menghidupkan nilai bisnis)

### 3.1 Event Bus + Automation Engine (jantung)
- **Domain events** dipancarkan dari aksi nyata: `lead.created`, `quotation.sent`, `booking.confirmed`,
  `payment.recorded`, `booking.departure_due`, `trip.driver_assigned`, `trip.started`, `trip.completed`,
  `invoice.overdue`, `doc.expiring`.
- **Rules engine** (configurable di Settings): event → kondisi → actions (`send_wa`, `create_notification`,
  `create_task`, `assign_agent`, `schedule_followup`). **Idempotent** (dedupe_key) + **audit per eksekusi**.
- Koleksi (tanpa melanggar guardrail, kanonik baru terdaftar): `events`, `automation_rules`, `automation_runs`.
- Scheduler existing (`server.py`) diperluas: due-based triggers (departure H-1, AR overdue, nurture steps).

### 3.2 WhatsApp Adapter (provider-agnostic)
- Antarmuka `WhatsAppProvider`: `send_text`, `send_template`, `send_media`, `receive_webhook`.
- Implementasi: `mock` (sekarang/simulasi jujur) · `meta_cloud` (Meta WhatsApp Cloud API — resmi) · `partner` (Wati/Qontak/Twilio).
- **In-app Inbox** (perluas `routers/inbox.py`): channel `whatsapp` nyata, session-window 24 jam, template di luar window,
  status sent/delivered/read dari webhook, opt-in/out, **cost tracking** per percakapan, audit per pesan.
- **Webhook inbound** (`/api/wa/webhook`, publik+verifikasi signature) → identify/create lead/customer (Identity B4) →
  auto-reply (jam kerja/menu) → routing/assign → handoff. (Lanjutan: AI assistant grounded.)

### 3.3 CRM Growth Layer
- **Lead scoring** (sumber, nilai, recency, engagement), **SLA timer** (target respon per stage + alert), **aging board**.
- **Nurturing sequences** (template + delay) via Automation Engine (WA): follow-up, DP reminder, winback.
- **Lifecycle & segmentasi** (prospek/baru/loyal/dorman/hilang), **RFM/LTV**, daftar **retensi & rebooking**.
- **Unified timeline** (booking+quote+WA+notes) actionable di satu drawer.

### 3.4 BI & Management Cockpit
- Pipeline aggregation read-only (`services/analytics.py`): exec KPIs, funnel by source, channel ROI, utilization,
  AR aging, driver/fleet perf, cohort/retention, forecast (moving-avg/linear sederhana). Recharts + export PDF/Excel.
- **Ops Cockpit "Hari Ini"**: keberangkatan hari ini (status konfirmasi), trip aktif, assignment tertunda,
  follow-up jatuh tempo, dokumen kedaluwarsa — semua **actionable** (1 klik → WA/assign/konfirmasi).

### 3.5 Ads Integration, Lead Capture & Atribusi  ★ (fokus revisi)
- **Pola adapter `LeadSource`** (provider-agnostic, **mock-first**): `meta_lead_ads | google_lead_form | tiktok_lead | web_form`. Aktivasi nyata saat kredensial siap (via integration playbook).
- **Ingestion:** Meta Lead Ads (webhook `leadgen` + Graph API tarik field), Google Lead Form (webhook delivery tervalidasi), TikTok Lead Gen (webhook/API), Web form (tangkap `utm_*`,`gclid`,`fbclid`, landing & referrer).
- **Lead diperkaya atribusi** (field baru di `leads`): `source,channel,campaign,adset,ad_id,utm_*,gclid,fbclid,landing_page,consent(opt-in),ad_cost?`. Normalisasi telp/email (Identity B4) + dedupe.
- **Audience & Blasting:** segmen by source/campaign/tag/consent → kampanye **WA broadcast** (E2) + (future) email/IG. Opsi **Custom Audience sync** (unggah hash telp/email) ke Meta/Google untuk retargeting/lookalike *(lanjutan)*.
- **Closed-loop ROAS:** kirim event konversi (lead→quote→booking→won) balik via **Meta CAPI** & **Google offline conversions** (pakai `gclid`/`fbclid`) → iklan optimasi ke booking nyata. **Dashboard marketing:** CPL, conv-rate, CAC, ROAS per campaign (spend via Ads API).
- **Kepatuhan:** simpan `consent`/opt-out; hormati kebijakan data platform.

### 3.6 SEO & Web Analytics  ★ (fokus revisi)
- **On-site (website `plan.md`):** meta dinamis (react-helmet), OpenGraph/Twitter cards, **schema.org JSON-LD** (Organization/LocalBusiness/Product/FAQ/Breadcrumb), `sitemap.xml`, `robots.txt`, canonical, heading/alt semantik, Core Web Vitals (plan.md §10).
- **Analytics:** **GA4** + **Meta Pixel** (+ Google Ads tag), event funnel (view→estimate→lead→quote→booking).
- **Keterbatasan:** frontend CRA **client-rendered** → crawl terbatas. Opsi: (a) **prerender/SSG** halaman publik (react-snap/prerender) untuk markup awal *(dampak tinggi, biaya rendah — rekomendasi)*, atau (b) migrasi SSR (Next.js) *(besar, ditunda)*.

---

## 4. RENCANA TRANSFORMASI BERFASE (E0–E7 + E-ADS)

> Setiap fase: outcome bisnis · kerja backend/frontend/integrasi · jaga `gate.sh` 10/10 · `testing_agent_v3`.
> Hindari koleksi baru bila bisa; yang perlu (events/automation_rules/automation_runs/wa_messages) didaftarkan di guardrail/docs.

### ✅ E0 — Hardening Kepercayaan (cepat, prasyarat) · **SELESAI & TERVERIFIKASI 2026-06-30**
Tutup lubang integritas/keamanan agar otomasi aman dibangun: **G2** state `ongoing`, **G3** audit penuh
(user/maintenance/broadcast/settings/login), **G7** bcrypt+rate-limit login, **G8** guard last-owner.
*Outcome:* fondasi tepercaya & akuntabel.

> **Bukti penutupan E0:**
> - **G7** — `core_utils.hash_password` → **bcrypt** (`$2b$12$`), `verify_password` mendukung bcrypt + legacy SHA256
>   dengan **migrasi transparan** saat login berhasil; `auth.login` diberi **rate-limit berbasis-kegagalan**
>   (`services/ratelimit.py`: 8 gagal per IP+email / 5 mnt → 429; login sukses membersihkan budget).
> - **G3** — audit ditambahkan: `auth` (login/login_failed/login_blocked/login_denied/logout), `users` (create/update,
>   sandi tak pernah masuk audit), `maintenance` (create/update/complete/delete), `broadcasts` (create/send),
>   `drivers` (delete). (`settings`/`vehicles`/`bookings`/dll sudah ada sebelumnya.)
> - **G8** — `users.update_user`: larang ubah-peran/nonaktifkan **diri sendiri** + guard **minimal 1 owner aktif**.
> - **G2** — booking `ongoing` kini NYATA: driver **checkin** → booking `confirmed`→`ongoing`; **checkout** →
>   `completed` (+`payment_status=selesai`, INV-3). Dashboard `_ACTIVE` & guard hapus driver konsisten.
> - **Verifikasi:** `bash scripts/gate.sh` = **HIJAU 10/10** (`memory/GATE_RECEIPT.md`); `testing_agent_v3`
>   (iter 29) = **0 bug kritis**, 48/51 E0-suite (3 sisanya = ekspektasi pesan, perilaku benar). Kredensial uji:
>   `memory/test_credentials.md`. **Berikutnya: E1** (Event Bus + Automation Engine + WhatsApp Adapter mock + Inbox upgrade).

### ✅ E1 — Event Bus + Automation Engine + WhatsApp Adapter (mock) + In-App Inbox upgrade  ★ · **SELESAI 2026-06-30**
Bangun event bus, rules engine (configurable), adapter WA (`mock` dulu), perluas Inbox jadi channel WA nyata-ready
(session-window, template, status, cost, audit).
*Outcome:* fondasi otomasi & "in-app WA" siap; trigger dapat diuji dengan mock.
> **Bukti penutupan E1:** Koleksi kanonik baru `events`/`automation_rules`/`automation_runs` (terdaftar di gate + `docs/03`).
> `services/events.py` (Event Bus, `emit()` idempotent+defensif), `services/automation.py` (rules engine: kondisi→aksi
> send_wa/create_notification/create_task/assign_agent/schedule_followup, idempotent dedupe rule:event + audit run),
> `services/whatsapp.py` (provider-agnostic: MockProvider aktif + MetaCloudProvider **stub E6**, cost tracking, session-window 24j,
> auto-reply jam kerja, opt-in/out, webhook publik verify+ingest+signature). Event dipancarkan dari aksi nyata
> (lead.created, quotation.sent, booking.confirmed, payment.recorded, trip.started/completed, booking.departure_due,
> invoice.overdue, doc.expiring, wa.inbound). UI: menu **Otomasi** (monitoring KPI/Aturan/Eksekusi/Event) + konfigurasi
> rules & WA di **Pengaturan** + Inbox WA (sesi/biaya/template/opt + tombol "Simulasi WA Masuk"). Seed 8 aturan AKTIF.
> POC `test_core_e1.py` **23/23 PASS**; `gate.sh` HIJAU; delivery **15/15 P0**. **Berikutnya: E-ADS / E2.**

### 🟡 E-ADS — Akuisisi: Integrasi Ads, Lead Capture & Atribusi  ★ · **SEBAGIAN (mock-first) SELESAI 2026-06-30**
Adapter `LeadSource` (mock-first) + webhook Meta/Google/TikTok Lead Ads + capture UTM/gclid/fbclid di web;
perkaya `leads` dgn atribusi + consent; **audiens blasting** (telp/email) → kampanye WA (pakai E1/E2);
**dashboard marketing** (CPL/conv/CAC/ROAS, mock→nyata saat creds); **closed-loop** Meta CAPI / Google offline conv.
SEO/GA4/Pixel di sisi web (lihat `plan.md`).
*Outcome:* setiap rupiah iklan terukur; lead + kontak ter-capture & siap di-blast.
> **Bukti (mock-first, tanpa key):** `services/attribution.py` (derive_channel UTM/gclid/fbclid/ttclid + first/last touch), `services/ads.py` (`create_ad_lead` + parse envelope Meta `field_data`); `routers/public.py` → `POST /api/public/lead-ads/{provider}` (mock) + form Quotation kirim atribusi+consent; `analytics.channels_roi` dikelompokkan per **channel** (CPL/CAC/ROAS) tampil di BI Cockpit (ChannelsCard + kolom Menang/CAC); `segments` kriteria `channel`/`marketing_consent` (blasting via Campaign E2); FE `utils/attribution.js` + LeadDetailDrawer (panel Atribusi+Consent). POC `test_core_eads_e6.py` **35/35 PASS**; `gate.sh` HIJAU (P0 8/8); `testing_agent_v3` iter 37.
> **MASIH MENUNGGU KEY/ID:** koneksi NYATA platform Ads (akun + token), **closed-loop** Meta CAPI / Google offline-conversions, dan GA4/Meta Pixel di web (butuh Measurement ID/Pixel ID — gratis dari user).

### ✅ E2 — CRM Growth Engine  ★ (jawaban kritik Anda) · **SELESAI & TERVERIFIKASI 2026-06-30**
Lead scoring + SLA + aging board; nurturing sequences (WA via E1); segmentasi & lifecycle; RFM/LTV; retensi/winback;
unified timeline. Broadcast jadi kampanye nyata (segmen+terjadwal+per-penerima+opt-out).
*Outcome:* CRM = mesin konversi & retensi (bukan CRUD).
> **Bukti penutupan E2:** Koleksi `segments`/`sequences`/`sequence_enrollments`/`campaigns`/`campaign_recipients`; `services/growth.py` (scoring 0–100 + band, SLA respons, RFM/LTV+lifecycle, scan_sla/scan_rfm→event), `services/segments.py`, `services/sequences.py`, `services/campaigns.py`; `routers/growth.py` + `routers/campaigns.py` (`/api/crm/{scoreboard,aging,rfm,recompute,growth-config,segments,sequences,campaigns}`). UI: 7 tab CRM (Pipeline · Skor&SLA · RFM · Segmen · Sequence · Campaign · Reminder), tab Broadcast lama DIHAPUS→Campaign. POC `test_core_e2.py` PASS; `gate.sh` HIJAU 10/10; `testing_agent_v3` iter 33 = Backend 100% (59/59) + Frontend 100% (0 bug). WA = **MOCK**. **Berikutnya: E3.**

### ✅ E3 — Dispatch & Komunikasi Operasi  ★ · **SELESAI & TERVERIFIKASI 2026-06-30**
Ops Cockpit "Hari Ini"; **Assign & Jadwalkan Trip** (driver+unit+geocode tujuan → perbaiki G1); status `ongoing` nyata;
**Trigger WA**: konfirmasi booking, **konfirmasi keberangkatan H-1/hari-H**, **notifikasi driver→customer (ditugaskan / dalam perjalanan / tiba)**,
selesai→ulasan+rebooking. POD (Bukti Layanan lokal: foto+penerima+catatan, disajikan via `/api/uploads`). *(Link live-track ke customer DITUNDA — menunggu Customer Portal.)*
*Outcome:* operasi terkonfirmasi otomatis, pengalaman pelanggan premium.
> POC `test_core_e3.py` **14/14 PASS** (live Nominatim geocode + 4 trigger WA baru + idempotency). `gate.sh` HIJAU 10/10; delivery **11/11 P0**; `testing_agent_v3` iter 34 = Backend 100% (26/26) + Frontend 100% (0 bug) + RBAC OK. WA = **MOCK** (aktif nyata di E6). **Berikutnya: E4 (BI & Management Cockpit) — menunggu instruksi user.**

### ✅ E4 — BI & Management Cockpit  ★ · **SELESAI & TERVERIFIKASI 2026-06-30**
Executive dashboard (tab di Beranda) + sales funnel + channel-ROI/CPL/CAC (ad-spend manual `settings.marketing_spend`) + utilisasi & ROI per unit + AR aging + performa driver + retensi/cohort + forecast moving-average. Range 30/90/365/kustom + pembanding periode lalu. Export PDF + Excel.
*Outcome:* manajemen berbasis data.
> POC `test_core_e4.py` **20/20 PASS** (KPI+delta, funnel monotonic, channel ROAS/CPL math, AR aging==outstanding, fleet ROI, retensi 0..1, forecast MA, ad-spend round-trip). `gate.sh` HIJAU 10/10; delivery **15/15 P0**; `testing_agent_v3` iter 35 = Backend fungsional 100% (10 'gagal' = timeout infra uji RBAC driver; curl driver=403 ~2.4ms), Frontend 100% (0 bug), RBAC OK. *(ROAS berbayar nyata penuh menanti E-ADS; saat ini channel-revenue diatribusikan dari nilai lead won.)* **Berikutnya: E5 (Finance Automation) — menunggu instruksi user.**

### ✅ E5 — Finance Automation · **SELESAI & TERVERIFIKASI 2026-06-30**
Maintenance cost → P&L (G4); rekonsiliasi invoice↔bayar (G5); **AR collection otomatis (WA reminder + aging)**;
cashflow & proyeksi; export PDF/Excel laporan.
*Outcome:* piutang turun, profit akurat.
> **Bukti penutupan E5:** `services/finance_automation.py` (pl_full incl. perawatan total+per-unit [G4]; reconciliation invoice↔pembayaran + `sync_invoice_statuses` paid/partial/sent idempotent [G5]; cashflow bulanan + proyeksi moving-average; ar_overdue + send_ar_reminder/bulk via event `invoice.overdue`→Automation→WA mock; assemble_finance_report) + `services/finance_export.py` (PDF reportlab + Excel openpyxl); `routers/finance.py` extend (`/finance/pl-full,/reconciliation,/reconciliation/sync,/cashflow,/ar/overdue,/ar/{id}/remind,/ar/remind-all,/export`); `invoices.py` VALID_STATUS += `partial`. UI: tab Keuangan jadi 6 (+ **Rekonsiliasi** + **Arus Kas**), Laba-Rugi pakai pl-full (perawatan+per-unit), export PDF/Excel, reminder AR (per-baris + Ingatkan Semua). POC `test_core_e5.py` **19/19 PASS**; `gate.sh` HIJAU 10/10 (0 orphan); delivery **12/12 P0**; `testing_agent_v3` iter 36 = Backend 100% (70/70) + Frontend 100% (0 bug) + RBAC OK (driver 403). WA = **MOCK** (aktif nyata di E6). **Berikutnya: E-ADS / E6 / E7 — menunggu instruksi user.**

### 🟡 E6 — Aktivasi WhatsApp NYATA + go-live otomasi  · **PREP SELESAI 2026-06-30 (menunggu kredensial WABA)**
Tukar adapter `mock → meta_cloud/partner` (butuh kredensial), submit template, cost tracking, opt-in/out compliance.
*Outcome:* semua trigger E1–E5 mengirim WA sungguhan.
> **Prep tanpa key (siap-colok):** `MetaCloudProvider` kini KIRIM NYATA via Graph API (`httpx`, default `v21.0`, gagal rapi tanpa kredensial — tidak pernah raise); `POST /api/wa/test-send` (owner) pakai provider aktif; Settings → WhatsApp: field Phone Number ID/Verify Token/Access Token/App Secret/**API Version**, badge **'Siap kirim'**, tombol **Test Kirim** (5b: kirim nyata). Webhook verify+signature sudah ada (E1). **Aktivasi NYATA tinggal isi kredensial WABA + submit template Meta.**

### ⏳ E7 — Lanjutan (skala & cerdas)
AI assistant WA grounded (**Claude/Anthropic API LANGSUNG**, anti-halusinasi via Pricing/Availability/CMS) → buat draft booking;
**Customer Portal + live-track link** (akun pelanggan); Google Maps swap; Payment Gateway (Midtrans);
multi-channel (email/IG); Custom-Audience sync lanjutan; object storage media.
*(GA4/Meta Pixel/Ads & SEO sudah dimajukan ke E-ADS + website.)*

---

## 5. SEQUENCING GABUNGAN (ERP transformation + Website overhaul `plan.md`)

Website = **mesin akuisisi** (atas funnel); ERP transformation = **mesin konversi & operasi** (bawah funnel).
Keduanya komplementer. Usulan urutan berdampak tertinggi:

```
1) E0 (Hardening cepat)                          ← prasyarat tepercaya
2) Website Fase 1 + SEO/GA4/Pixel (akuisisi)     ← naikkan jumlah & kualitas lead
3) E1 (Automation+WA mock) + E-ADS (capture lead iklan + atribusi + audiens blasting)  ← FOKUS MARKETING
4) E2 (CRM Growth)                               ← konversi + retensi (DAMPAK TERBESAR)
5) E3 (Dispatch + konfirmasi WA, tanpa live-link customer)  ‖  Website Fase 2 (Armada+360)
6) E4 (BI: incl. marketing/ROAS) + E5 (Finance automation)  ‖  Website Fase 3–5
7) E6 (WA & Ads NYATA go-live) → E7 (AI Claude / Customer Portal+live-link / Maps / Payment)
```

*(Bisa diparalelkan: tim "growth" garap Website+CRM; ketika kredensial WA siap, aktifkan E6.)*

---

## 6. ✅ KEPUTUSAN FINAL (TERKUNCI)

1. **WhatsApp = Meta WhatsApp Cloud API (resmi, langsung)** sebagai target produksi — DI ATAS pola **adapter**.
2. **Mulai MOCK-FIRST.** Kredensial WABA belum siap → seluruh otomasi dibangun & diuji dengan provider `mock`;
   aktivasi `meta_cloud` nyata dilakukan di **E6** saat kredensial siap (saya bantu prosesnya nanti).
3. **BI = modul PENUH** (Executive + Funnel/Channel-ROI/LTV + Ops-Today + Fleet/Driver + Retensi/Forecast).
4. **AI Assistant WA = YA**, memakai **Claude (Anthropic API) LANGSUNG** — **TIDAK memakai library/ key Emergent**.
   → perlu **`ANTHROPIC_API_KEY`** milik Anda saat fase AI (E7). Grounded ke Pricing/Availability/CMS (anti-halusinasi).
5. **Urutan = PARALEL** (rekomendasi): jalur Website + jalur ERP (E0 → E1/E2 …) sesuai kapasitas.
6. **REVISI USER:** Live-track link ke CUSTOMER + Customer Portal **DITUNDA** (E7/future, saat ada akun pelanggan).
   **Fokus sekarang = MARKETING (Ads integration, lead capture, atribusi, blasting + SEO) & OPERASIONAL.**

> Kepatuhan integrasi: WhatsApp Cloud API, Anthropic Claude, Google Maps, Payment Gateway WAJIB lewat
> **integration playbook** sebelum implementasi; kredensial dikumpulkan dari Anda lebih dulu.
> Pola **adapter** + **mock-first** memungkinkan mulai SEKARANG tanpa menunggu kredensial.

---

## 7. 🎯 RENCANA EKSEKUSI FINAL & SPRINT-1

### 7.1 Urutan Master Gabungan (terkunci)
```
SPRINT 1  → [ERP] E0 Hardening  +  [WEB] Fase 1 (Home immersive + estimator) + SEO/GA4/Pixel
SPRINT 2  → [ERP] E1 Automation Engine + WA Adapter(mock) + In-app WA Inbox
SPRINT 3  → [ERP] E-ADS Ads Integration + Lead Capture + Atribusi + Audiens Blasting   ← FOKUS MARKETING
SPRINT 4  → [ERP] E2 CRM Growth Engine (scoring/SLA/nurturing/segmentasi/LTV)          ← jawaban kritik CRM
SPRINT 5  → [ERP] E3 Dispatch + Konfirmasi WA (booking/keberangkatan/driver)  ‖  [WEB] Fase 2 Armada+360
SPRINT 6  → [ERP] E4 BI (incl. ROAS marketing) + E5 Finance Automation  ‖  [WEB] Fase 3–5
SPRINT 7  → [ERP] E6 Aktivasi WA & Ads NYATA → E7 AI(Claude langsung)/Customer Portal/Maps/Payment
```
`‖` = dapat diparalelkan.

### 7.2 SPRINT-1 — rincian tugas (siap eksekusi setelah GO)
**Jalur A — ERP E0 (Hardening, backend):**
- G2: tambah state booking `ongoing` (di-set saat trip `to_pickup`/checkin) + sinkron Dashboard `_ACTIVE`, guard hapus driver, scan notifikasi.
- G3: lengkapi Audit Log → `users` (create/update, mask sandi), `maintenance` (CRUD/complete), `broadcasts` (send), `settings` (patch), `auth` (login sukses/gagal, logout).
- G7: ganti `hash_password` → bcrypt/argon2 (+migrasi on-login transparan) + rate-limit `/auth/login` (reuse limiter Tahap A).
- G8: guard "minimal 1 owner aktif" + larang turunkan-peran/nonaktifkan diri sendiri.
- Sinkron `docs/03,04,05`; jalankan `bash scripts/gate.sh` (target 10/10); `testing_agent_v3` (regресi auth/booking/audit).

**Jalur B — WEBSITE Fase 1** (lihat `plan.md` §Fase 1): token multi-theme + font + logo + navbar/footer glass + Framer Motion + preloader + Home dirombak + `TripEstimatorInline` + endpoint `GET /api/public/theme`.

### 7.3 Definition of Done Sprint-1
- ERP: gate 10/10, audit lengkap untuk aksi sensitif, login aman & ter-rate-limit, tak ada regresi (testing agent hijau).
- Web: Home premium responsif (light/dark + ganti preset), estimator inline berfungsi, esbuild bersih, screenshot OK.

---

_Versi 1.2 (revisi: fokus Ads/SEO/marketing + operasional; live-track customer & Customer Portal ditunda) · oleh Neo._
