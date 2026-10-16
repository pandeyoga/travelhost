# 18 — ANALISIS FITUR MARKETING END-TO-END & INTEGRASI

> **Dibuat:** 2026-08-10 · **Fase:** persiapan F3–F7 (E29+)
> **Sumber fakta:** audit kode `/app` (bukan asumsi) + playbook resmi Meta Marketing API **v26.0**
> dan Google Ads API **v25** / Data Manager API **v1** (riset 10 Agu 2026).
> **Pemicu:** permintaan user — *"saya lupa menambahkan integrasi Meta Ads, kaitkan dengan Google Ads
> dan Meta Pixel lalu kembangkan; lihat CRM & marketing saat ini, buatkan analisis fitur marketing
> end-to-end yang baik beserta integrasinya."*

---

## 1) Ringkasan eksekutif (5 poin)

1. **Yang paling merugikan hari ini bukan kurangnya fitur, tapi rantai yang terputus.** Sistem sudah
   punya pixel di browser + outbox konversi server-side yang idempoten, **tetapi outbox itu belum
   pernah dipanggil oleh event bus**. Artinya: booking dikonfirmasi & DP masuk — dua konversi paling
   bernilai yang HANYA diketahui backend — tidak pernah sampai ke Meta/Google. Algoritma iklan
   dilatih memakai "form terkirim" saja, jadi ia mengoptimalkan pengisi form, bukan pembeli.
2. **Belum ada integrasi Meta Ads sama sekali** (hanya Meta *Pixel* + *CAPI*). Tidak ada Ad Account,
   tidak ada tarikan biaya/klik (Insights), tidak ada manajemen kampanye, tidak ada audiens.
   Konsekuensinya ROAS di sistem masih memakai **ad-spend yang diketik manual** (`settings.marketing_spend`).
3. **Atribusi berhenti di level channel, bukan level iklan.** `services/attribution.py` sudah rapi
   (gclid/fbclid/ttclid → channel), tapi tidak menyimpan `campaign_id / adset_id / ad_id`. Tanpa itu,
   pertanyaan bisnis yang benar — *"iklan mana yang menghasilkan booking, bukan sekadar lead?"* —
   tidak bisa dijawab.
4. **Jalur iklan paling khas travel Indonesia justru belum tertangkap: Klik-ke-WhatsApp (CTWA).**
   Inbox WA sudah ada, tapi objek `referral` (`ctwa_clid`, `source_id` = ad_id) pada pesan masuk
   dibuang. Padahal itu satu-satunya cara menghubungkan chat WA → iklan → booking.
5. **Rekomendasi urutan (disetujui user):** F3 konversi otomatis → F4 dashboard iklan & ROAS nyata →
   F5 akuisisi lead (Lead Ads + CTWA) → F6 audiens & retargeting → F7 campaign builder (tulis ke
   platform, uang nyata, paling akhir & paling banyak pengaman).

---

## 2) Audit kondisi saat ini (fakta, per file)

| Kapabilitas | Status | Bukti di kode |
|---|---|---|
| Vault kredensial AES-256-GCM + mask response | ✅ ADA | `backend/services/secrets_vault.py`, `routers/marketing.py` |
| Halaman Integrasi (Meta Pixel, Google/GA4, WhatsApp) | ✅ ADA | `frontend/src/features/app/Integrations.jsx` |
| Consent banner + pemuat pixel/gtag runtime (Consent Mode v2) | ✅ ADA | `frontend/src/lib/tracking.js`, `components/public/ConsentBanner.jsx` |
| Outbox konversi idempoten (unique `provider+event_key`, retry/backoff/dead) | ✅ ADA | `backend/services/conversions.py` |
| **Outbox tersambung ke event bus** | ❌ **TIDAK** | `rg "conversions" backend` → hanya diimpor `routers/marketing.py`. `lead.created` / `booking.confirmed` / `payment.recorded` tidak memanggil `enqueue()` |
| **Worker retry konversi** | ❌ TIDAK | `dispatch_pending()` ada tapi tak pernah dijadwalkan |
| Meta CAPI payload | ⚠️ PERLU KOREKSI | `api_version` default **v25.0** (harus v26.0), tanpa `appsecret_proof`, tanpa dukungan `ctwa_clid` / `action_source=business_messaging` |
| Google Data Manager payload | ⚠️ **SALAH FIELD** | `operatingAccount.product` (harus `accountType`), `consent: "CONSENT_GRANTED"` (harus `GRANTED`), tanpa `encoding: "HEX"`, tanpa `destinationReferences` |
| Atribusi channel (utm/gclid/fbclid/ttclid, first+last touch) | ✅ ADA | `backend/services/attribution.py` |
| Atribusi **level iklan** (campaign_id/adset_id/ad_id) | ❌ TIDAK | tidak ada field-nya di lead |
| **Meta Ads API** (akun, Insights, kampanye, audiens) | ❌ TIDAK ADA | — |
| **Google Ads API** (GAQL Insights, kampanye, Customer Match) | ❌ TIDAK ADA | hanya OAuth refresh untuk Data Manager |
| Biaya iklan | ⚠️ MANUAL | `services/analytics.py::set_marketing_spend` (`settings.marketing_spend`) |
| ROAS / CPL / CAC per channel | ✅ ADA (basis manual) | `analytics.channels_roi` |
| ROAS per **kampanye/adset/iklan** | ❌ TIDAK | butuh Insights + atribusi ad-level |
| Lead Ads | ⚠️ MOCK | `services/ads.py` hanya mem-parse payload; tanpa verifikasi `X-Hub-Signature-256`, tanpa fetch `/{leadgen_id}`, tanpa backfill |
| **CTWA (Klik-ke-WhatsApp)** | ❌ TIDAK | `routers/whatsapp.py::inbound` mengabaikan `messages[].referral` |
| CRM: pipeline, skor+SLA, RFM/LTV, segmen, sequence, kampanye WA | ✅ KUAT | `routers/leads.py`, `growth.py`, `campaigns.py`, `features/app/Crm.jsx` (7 tab) |
| **Segmen CRM → audiens platform** (Custom Audience / Customer Match) | ❌ TIDAK | segmen hanya dipakai broadcast WA internal |
| Landing Page Builder + media (video) | ⚠️ FONDASI | `services/landing_blocks.py`, `media_store.py` ada (POC F1); belum ada editor & render publik |
| RBAC `marketing_admin` | ✅ ADA | `permissions_config.py`, `navigationConfig.js` |
| Halaman Kesehatan Pelacakan | ✅ ADA | `features/app/TrackingHealth.jsx` |

**Kesimpulan audit:** fondasi (kredensial aman, consent, outbox, CRM) **sudah bagus**. Yang hilang
adalah **dua ujung rantai**: (a) mengirim konversi bernilai ke platform secara otomatis, dan
(b) menarik biaya + identitas iklan dari platform agar bisa dihitung untung/rugi per iklan.

---

## 3) Cetak biru marketing end-to-end yang seharusnya

```
                    ┌──────────── 1. IKLAN (Meta / Google) ────────────┐
                    │  Lead Ads   │  Traffic → LP  │  Klik-ke-WhatsApp │
                    └──────┬──────┴────────┬───────┴─────────┬─────────┘
   penanda klik:    leadgen webhook   fbclid/gclid/utm    ctwa_clid + ad_id
                           │                │                  │
                           ▼                ▼                  ▼
              ┌────────────────── 2. TANGKAP (ERP) ──────────────────┐
              │ /api/public/webhooks/meta/leads │ form LP/penawaran │
              │ /api/public/wa/webhook (referral)                   │
              └───────────────────────┬─────────────────────────────┘
                                      ▼
              3. LEAD di CRM  ── ber-atribusi AD-LEVEL (campaign/adset/ad + click id)
                 auto-assign · skor · SLA · sequence nurturing · WA ack
                                      ▼
              4. PENAWARAN (quotation) → 5. BOOKING confirmed → 6. DP / pelunasan
                                      │
                 ┌────────────────────┴────────────────────┐
                 ▼ (kirim balik / feedback loop)           ▼ (tarik / pull)
   7. KONVERSI SERVER-SIDE                    8. INSIGHTS PLATFORM
      Meta CAPI  (Lead / Purchase)               Meta Ads Insights (spend/clicks/actions)
      Google Data Manager (events:ingest)        Google Ads GAQL (cost_micros/clicks/conv)
      + GA4 Measurement Protocol                 → cache `ads_metrics_daily`
                 └────────────────────┬────────────────────┘
                                      ▼
              9. RUANG KEPUTUSAN — "Dashboard Iklan"
                 biaya platform  ⨯  booking & pendapatan NYATA (dari ERP)
                 = CPL · CAC · ROAS per kampanye/adset/iklan · lead→booking rate
                                      ▼
              10. TINDAKAN: jeda iklan boncos · naikkan budget pemenang ·
                  sinkron audiens (retargeting & Lookalike) · duplikasi iklan juara
```

**Prinsip yang dipegang:**

- **Satu ID konversi untuk browser & server** (`lead_<id>`, `booking_<id>`, `payment_<id>`) → Meta
  men-dedup, tidak ada penghitungan ganda. Sudah benar di `conversions.event_key()`.
- **Uang tidak boleh bergerak tanpa perintah manusia.** Setiap tulis ke platform default
  `PAUSED` + `validate_only` dulu + publish eksplisit + audit.
- **Tidak ada konversi hilang diam-diam.** Semua percobaan tercatat di outbox dengan alasan gagal.
- **Consent-first.** Tanpa izin pengunjung: tak ada pixel; tanpa `marketing_consent`: kontak tidak
  ikut audiens.
- **Mata uang tidak diasumsikan IDR.** Akun iklan bisa USD/SGD — currency wajib dibaca dari akun
  (`act_<id>?fields=currency` / `customer.currency_code`) dan `cost_micros ÷ 1.000.000`.

---

## 4) Gap prioritas (dampak uang vs usaha)

| # | Gap | Dampak bisnis | Usaha | Fase |
|---|-----|---------------|-------|------|
| G1 | Konversi booking & DP tidak dikirim ke platform | **SANGAT TINGGI** — algoritma salah optimasi, biaya per booking membengkak | S | **F3** |
| G2 | Tidak ada worker retry | Tinggi — konversi gagal sekali langsung hilang | S | **F3** |
| G3 | Payload Google Data Manager salah nama field | Tinggi — semua kiriman akan ditolak saat kunci diisi | XS | **F3** |
| G4 | Meta versi v25.0 & tanpa `appsecret_proof` | Sedang — risiko ditolak/deprecated | XS | **F3** |
| G5 | Biaya iklan manual, tak ada Insights | **SANGAT TINGGI** — tidak tahu iklan mana yang untung | M | **F4** |
| G6 | Atribusi tidak sampai level iklan | Tinggi — ROAS per iklan mustahil | M | **F4** |
| G7 | CTWA tidak tertangkap | Tinggi (jalur utama travel ID) | S | **F5** |
| G8 | Lead Ads masih mock (tanpa signature/fetch/backfill) | Tinggi — lead bisa hilang/dipalsukan | M | **F5** |
| G9 | Segmen CRM tidak bisa jadi audiens | Sedang-tinggi — retargeting & Lookalike tak jalan | M | **F6** |
| G10 | Tidak bisa jeda/naikkan budget dari ERP | Sedang — keputusan lambat, harus buka Ads Manager | M | **F7** |
| G11 | Belum ada campaign builder | Sedang | L | **F7** |
| G12 | Landing Page Builder belum ada UI | Sedang | L | F8 (setelah ini) |

---

## 5) Matriks integrasi (versi & endpoint yang dipakai)

| Provider | API & versi | Dipakai untuk | Endpoint utama | Mode kering |
|---|---|---|---|---|
| Meta | **Graph/Marketing API v26.0** | konversi server-side | `POST /{dataset_id}/events` | `test_event_code` |
| Meta | v26.0 | metrik iklan | `GET /act_<id>/insights` (+`async=true` untuk rentang besar) | degrade `not_configured` |
| Meta | v26.0 | metadata akun (currency/timezone) | `GET /act_<id>?fields=currency,timezone_name,name,account_status` | idem |
| Meta | v26.0 | kampanye/adset/creative/ad | `POST /act_<id>/campaigns|adsets|adcreatives|ads` | **`execution_options:["validate_only"]` + `status:PAUSED`** |
| Meta | v26.0 | audiens | `POST /act_<id>/customaudiences`, `/{id}/users`, subtype `LOOKALIKE` | dry-run internal |
| Meta | v26.0 | Lead Ads | webhook `leadgen` + `GET /{leadgen_id}` + `GET /{form_id}/leads` | simulator payload bertanda tangan |
| Meta | WhatsApp Cloud API | CTWA | `messages[].referral.ctwa_clid` → CAPI `user_data.ctwa_clid`, `action_source=business_messaging` | simulasi inbound |
| Google | **Ads API v25** | metrik iklan | `POST /v25/customers/{cid}/googleAds:searchStream` (GAQL) | degrade `not_configured` |
| Google | Ads API v25 | kampanye/budget/adgroup/RSA/keyword | `:mutate` + **`validateOnly:true` + `partialFailure:true`** | wajib validate dulu |
| Google | Ads API v25 | Customer Match (legacy) | `userLists:mutate` + `offlineUserDataJobs:create/addOperations/run` | `validateOnly` |
| Google | **Data Manager API v1** | konversi offline / ECL | `POST datamanager.googleapis.com/v1/events:ingest` | **`validateOnly:true`** |
| Google | GA4 Measurement Protocol | event server-side | `POST /mp/collect` · validasi `/debug/mp/collect` | endpoint debug |
| Google | OAuth 2.0 | token | `POST oauth2.googleapis.com/token` (scope `adwords` + `datamanager`) | — |

**Izin/scope yang harus user siapkan nanti:** Meta System User token dengan `ads_read`,
`ads_management`, `business_management`, `leads_retrieval` (+ Page token untuk baca lead),
`whatsapp_business_messaging`. Google: developer token (level Basic/Standard), OAuth client +
refresh token dengan scope `.../auth/adwords` dan `.../auth/datamanager`.

---

## 6) Model data yang ditambahkan

| Koleksi | Isi | Catatan kunci |
|---|---|---|
| `conversion_events` (ada) | outbox konversi | + field `channel`, `action_source`, `identifiers.ctwa_clid` |
| `ads_accounts` | cache metadata akun iklan | `provider`, `account_id`, `currency`, `timezone`, `name`, `status`, `synced_at` |
| `ads_entities` | kampanye/adset/ad hasil sinkron | `provider`, `level`, `entity_id`, `parent_id`, `name`, `status`, `objective`, `daily_budget` |
| `ads_metrics_daily` | metrik harian per entitas | unique `(provider, level, entity_id, date)` → idempoten saat tarik ulang; simpan `spend_micros` + `currency` mentah |
| `ads_sync_runs` | jejak tarikan | `provider`, `range`, `rows`, `status`, `error`, `usage_headers` |
| `ad_touches` | klik iklan yang teridentifikasi | `click_id` (gclid/fbclid/ctwa_clid), `provider`, `campaign_id/adset_id/ad_id`, `lead_id` |
| `audience_syncs` | riwayat sinkron audiens | `segment_id`, `provider`, `audience_id`, `matched`, `consent_filtered`, `status` |
| `platform_leads` | lead mentah dari Lead Ads | unique `leadgen_id` → dedup pengiriman ganda webhook |
| **`leads` (perluasan)** | atribusi ad-level | `ad_campaign_id`, `ad_adset_id`, `ad_id`, `ad_platform`, `click_id`, `ctwa_clid` |

**Kunci join untuk ROAS nyata:**
`ads_metrics_daily.entity_id` ⟷ `leads.ad_campaign_id/ad_adset_id/ad_id` ⟷ `bookings.lead_id`
→ `payments`. Untuk web-traffic tanpa ad_id, fallback ke `utm_campaign` (nama kampanye) yang
dicocokkan ke `ads_entities.name`.

---

## 7) Tiga jalur atribusi (dan cara masing-masing ditutup)

1. **Lead Ads (form di dalam Facebook/IG).** Tidak ada kunjungan web → tidak ada `fbclid`.
   Atribusi datang dari webhook: `campaign_id`, `adgroup_id` (=adset), `ad_id`, `form_id`.
   → simpan di `platform_leads` + `leads.ad_*`. Konversi balik pakai CAPI dengan
   `action_source="system_generated"`/`website` + hash email/telepon dari `field_data`.
2. **Traffic ke website / landing page.** Sudah berjalan separuh: `fbclid`/`gclid` + UTM ditangkap.
   Yang ditambah: simpan **`fbc`/`fbp` cookie** & `ad_id` bila tersedia di URL (`utm_content`
   biasanya diisi `{{ad.id}}` di Meta / `{creative}` di Google) → `ad_touches`.
3. **Klik-ke-WhatsApp (CTWA).** Pesan masuk membawa
   `referral{source_type:"ad", source_id:<ad_id>, ctwa_clid, source_url, headline}`.
   → buat/gabung lead dengan channel `meta_ads`, simpan `ctwa_clid` **tanpa di-hash**, dan saat
   booking/DP terjadi kirim CAPI `action_source="business_messaging"`,
   `messaging_channel:"whatsapp"`, `user_data.ctwa_clid` + `whatsapp_business_account_id`.

---

## 8) Keamanan & pengaman belanja (karena ERP akan boleh MENULIS iklan)

| Pengaman | Aturan |
|---|---|
| **Interlock 2 langkah** | Semua create/update wajib lulus `validate_only` dulu; tombol "Terbitkan" terpisah |
| **Default PAUSED** | Kampanye/adset/ad selalu dibuat `PAUSED`, tidak pernah langsung `ACTIVE` |
| **Konfirmasi ketik** | Mengaktifkan iklan / menaikkan budget wajib ketik ulang nama objek |
| **Batas budget harian** | Nilai maksimum yang diizinkan disimpan di pengaturan; di atasnya ditolak ERP (bukan platform) |
| **RBAC** | Mutasi iklan: `owner` + `marketing_admin` saja. `ops_admin` hanya baca dashboard. `driver` tidak melihat menu |
| **Audit** | Setiap validate/publish/pause/budget tercatat di Jejak Audit (aktor, payload ter-redaksi, request id) |
| **Rahasia** | Token hanya di server (AES-256-GCM). Browser hanya menerima `••••9999`. `appsecret_proof` dihitung server |
| **Tanpa kredensial** | Semua endpoint mengembalikan `not_configured` / `skipped` + alasan — **tidak pernah 5xx** |
| **Consent** | Kontak tanpa `marketing_consent=true` **tidak** pernah masuk audiens; hitung & tampilkan "tersaring karena tanpa izin" |

**Guardrail baru yang akan di-wire ke `scripts/gate.sh`:**
`INV-CONV-01` (setiap event bisnis bernilai wajib punya hook enqueue + outbox idempoten),
`INV-ADS-01` (semua pemanggil write platform wajib melewati helper dry-run & default PAUSED),
`INV-SEC-02` (tidak ada plaintext token/PII di response & log),
`INV-AUD-01` (sinkron audiens wajib melewati filter consent).

---

## 9) Roadmap yang disepakati

| Fase | Judul | Hasil yang user lihat |
|---|---|---|
| **F3** | Konversi otomatis + worker retry | Lead/booking/DP otomatis masuk daftar konversi; halaman Kesehatan Pelacakan hidup; koreksi payload Meta v26 & Data Manager |
| **F4** | Meta Ads + Google Ads Insights & **Dashboard Iklan** | Tabel biaya/klik/konversi per kampanye→adset→iklan disandingkan booking & pendapatan nyata = ROAS asli; tombol "Tarik sekarang"; atribusi ad-level |
| **F5** | Akuisisi lead: Lead Ads webhook nyata + CTWA | Lead dari iklan FB/IG & chat WA dari iklan masuk CRM otomatis lengkap dengan nama iklannya |
| **F6** | Audiens & retargeting | Segmen CRM → Custom Audience Meta + Customer Match Google + Lookalike, dengan filter consent |
| **F7** | Campaign builder (tulis penuh) | Buat kampanye/adset/iklan (termasuk CTWA) dari ERP: validasi dulu, PAUSED, terbitkan manual, jeda/ubah budget |

**Definisi selesai per fase:** `bash scripts/gate.sh` HIJAU · `testing_agent_v3` lulus 4 peran ·
tanpa kredensial tetap 0 error 5xx · dokumen SSOT (`03_DATA_MODEL`, `04_API_CONTRACT`,
`05_NAVIGATION_MAP`) diperbarui.

---

## 10) KPI yang wajib terlihat di Dashboard Iklan

1. **Biaya** (per hari / kampanye / adset / iklan) dalam mata uang akun **dan** IDR (bila akun non-IDR, dengan kurs tercatat).
2. **Lead** masuk (dari ERP, bukan dari platform) · **CPL** = biaya ÷ lead.
3. **Booking confirmed** ber-atribusi · **CAC** = biaya ÷ booking.
4. **Pendapatan nyata** (booking confirmed + DP diterima) · **ROAS** = pendapatan ÷ biaya.
5. **Lead → Booking rate** per iklan (menemukan iklan yang ramai lead tapi tak pernah jadi).
6. **Status kesehatan pelacakan**: % konversi terkirim sukses, jumlah `skipped/failed/dead` + alasan.
7. **Peringatan otomatis**: iklan dengan biaya > X tanpa booking dalam N hari → sarankan jeda.

---

## 11) Koreksi teknis wajib pada kode saat ini (dikerjakan di F3)

| Berkas | Sekarang | Harus |
|---|---|---|
| `services/conversions.py` | `api_version` default `v25.0` | `v26.0` (tetap bisa di-override dari UI) |
| `services/conversions.py` | Meta tanpa `appsecret_proof` | tambahkan bila `app_secret` ada |
| `services/conversions.py` | `operatingAccount.product` | `operatingAccount.accountType` |
| `services/conversions.py` | `consent: CONSENT_GRANTED/DENIED` | `GRANTED` / `DENIED` |
| `services/conversions.py` | tanpa `encoding` | `"encoding": "HEX"` di root payload |
| `services/conversions.py` | tanpa `destinationReferences` | tiap event menunjuk `reference` destinasi |
| `services/conversions.py` | tanpa jalur CTWA | dukung `action_source=business_messaging` + `ctwa_clid` |
| `routers/whatsapp.py` | `referral` diabaikan | tangkap → `ad_touches` + `leads.ctwa_clid` |
| `services/attribution.py` | hanya channel | + `campaign_id/adset_id/ad_id`, `fbc/fbp` |
| `routers/marketing.py` | provider Meta hanya pixel | + `ad_account_id`, `dataset_id`, `waba_id`, `system_user_token`, `page_token`, `lead_verify_token` |

---

*Dokumen ini adalah SSOT analisis marketing. Perubahan arah marketing wajib memperbarui berkas ini
lebih dulu, lalu `plan.md`.*
