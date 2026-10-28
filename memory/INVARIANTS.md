# INVARIANTS — SSOT invariant guardrail (Layer 3 / VERIFY)

> **Dipulihkan 2026-10-28.** Berkas ini hilang dari repo saat sinkron ulang (folder `memory/`
> hanya berisi `PRD.md`), padahal `scripts/guardrails/verify_guardrail_registry.py` (INV-META-01)
> mewajibkannya → gate MERAH. Isi tabel di bawah **diturunkan langsung** dari deklarasi
> `Guard("INV-…", "…")` di tiap penjaga — bukan ditulis ulang dari ingatan. Rincian kelas bug,
> riwayat, dan cara uji ada di docstring masing-masing berkas penjaga.
>
> Invariant DOMAIN data (INV-1 … INV-23: total booking, status bayar, anti double-booking,
> share token, dll.) tetap ber-SSOT di `docs/03_DATA_MODEL.md` §Invariants dan diperiksa
> `scripts/verify_data_integrity.py`.

## Aturan
1. Penjaga baru (`scripts/guardrails/verify_*.py`) WAJIB: mendeklarasikan `Guard("INV-XXX-NN", …)`,
   ter-wire di `scripts/gate.sh`, dan punya baris di tabel ini (dipaksa INV-META-01).
2. Self-test (`selftest_*.py`) membuktikan penjaga MERAH saat bug disuntikkan; wajib ter-wire juga.
3. Menghapus/melemahkan penjaga = keputusan eksplisit Owner, dicatat di commit — bukan diam-diam.

## Registri penjaga (27 penjaga)
| INV-ID | Invariant | Penjaga | Self-test |
|---|---|---|---|
| **INV-ADS-01** | Penulisan iklan wajib lewat pengaman (validate_only + PAUSED + konfirmasi) | `scripts/guardrails/verify_ads_write_safety.py` | — |
| **INV-5XX-01** | Tidak ada 5xx pada input adversarial (harus 2xx/4xx) | `scripts/guardrails/verify_adversarial_5xx.py` | — |
| **INV-AUD-01** | Sinkron audiens wajib menyaring consent + identitas ter-hash | `scripts/guardrails/verify_audience_consent.py` | — |
| **INV-AUTH-01** | Tiap endpoint router menegakkan auth (kecuali PUBLIC allowlist) | `scripts/guardrails/verify_auth_coverage.py` | — |
| **INV-BOOK-02** | Pemesanan online: hitung ulang server + ketersediaan + mutex, tanpa total klien | `scripts/guardrails/verify_booking_public.py` | `selftest_booking_guards.py` |
| **INV-CMS-01** | Siklus hidup konten CMS aman & pulih (versi · tempat sampah · pengalihan) | `scripts/guardrails/verify_content_lifecycle.py` | `selftest_content_lifecycle.py` |
| **INV-CONV-01** | Event bisnis bernilai terhubung ke outbox konversi + pekerja retry | `scripts/guardrails/verify_conversion_hooks.py` | — |
| **INV-QUALITY-01** | Kualitas kerja minimal AI (anti low-effort) | `scripts/guardrails/verify_effort_quality.py` | — |
| **INV-META-01** | Integritas registri guardrail (semua penjaga ter-wire + terdaftar) | `scripts/guardrails/verify_guardrail_registry.py` | — |
| **INV-IDENT-01** | Pembuatan identity aman-balapan (no duplicate, no 5xx) | `scripts/guardrails/verify_identity_race.py` | — |
| **INV-LP-02** | Template landing page selaras skema blok (tak ada props hilang senyap) | `scripts/guardrails/verify_landing_contract.py` | — |
| **INV-MEDIA-04** | Perilaku Media Library (RBAC, anti-5xx, folder, cache, legacy) runtime | `scripts/guardrails/verify_media_runtime.py` | `selftest_media_runtime.py` |
| **INV-MEDIA-02** | Penyimpanan media aman + URL baca media benar (tak ada gambar 404) | `scripts/guardrails/verify_media_safety.py` | — |
| **INV-MEDIA-03** | Media Library tetap SATU (unified) + folder & cache tidak merusak aset | `scripts/guardrails/verify_media_unified.py` | `selftest_media_unified.py` |
| **INV-CLEAN-01** | Data uji penjaga/smoke wajib dibersihkan total (tak boleh bocor ke ERP) | `scripts/guardrails/verify_no_test_pollution.py` | `selftest_no_test_pollution.py` |
| **INV-NUM-01** | Field numerik uang/kuantitas wajib ber-bound (ge=/gt=) | `scripts/guardrails/verify_numeric_bounds.py` | — |
| **INV-PRICE-02** | Master Harga tunggal — tak ada pintu tulis harga kedua | `scripts/guardrails/verify_price_master.py` | — |
| **INV-PRICE-01** | Harga: tanpa komponen jarak, DP satu sumber, tampil == tersimpan | `scripts/guardrails/verify_pricing_integrity.py` | `selftest_booking_guards.py` |
| **INV-RBAC-01/02/03/04/05** | RBAC berlapis: route FE + endpoint BE + sinkron matrix 2-arah + cakupan data | `scripts/guardrails/verify_rbac_guards.py` | — |
| **INV-RBAC-06** | RBAC runtime: pintu modul + cakupan data per peran | `scripts/guardrails/verify_rbac_runtime.py` | — |
| **INV-REF-01** | Referensi (FK) & pilihan (enum) dari luar wajib divalidasi server | `scripts/guardrails/verify_reference_integrity.py` | — |
| **INV-RACE-01** | Reservasi armada/sopir wajib di-serial (vehicle_lock/driver_lock) | `scripts/guardrails/verify_reservation_locks.py` | — |
| **INV-SEC-02** | Rahasia integrasi & PII tidak bocor (respons, log, hardcode) | `scripts/guardrails/verify_secret_exposure.py` | — |
| **INV-SET-01** | Tarif pricing/settings tervalidasi (tolak negatif/absurd/non-numerik) | `scripts/guardrails/verify_settings_bounds.py` | — |
| **INV-REF-02** | Destinasi booking = relasi ke master destinations (bukan teks bebas) | `scripts/guardrails/verify_ssot_relations.py` | — |
| **INV-STR-01** | Field teks dari luar wajib berbatas panjang (max_length) | `scripts/guardrails/verify_string_bounds.py` | `selftest_booking_guards.py` |
| **INV-THEME-01** | Kontras & pewarisan tema (glass, portal, offset mengapung) | `scripts/guardrails/verify_theme_contrast.py` | `selftest_theme_contrast.py` |

## Catatan per fitur
- **INV-22 (domain) — share token sah**, kini mencakup DUA jenis tautan publik: `trip_shares`
  (tracking) dan `schedule_shares` (jadwal keberangkatan read-only). Token unik lintas jenis;
  aturan 404/403/410 + pencatatan akses ada di SATU tempat: `backend/services/share_links.py`.
  `schedule_shares.expires_at` boleh kosong (= tanpa batas waktu, tetap bisa di-revoke).
  Payload publik jadwal = allowlist `services/schedule_share.public_departure` (tanpa nominal,
  kontak pelanggan, ID internal) — diuji `backend/tests/test_schedule_share.py`; endpoint
  publiknya terdaftar di allowlist INV-AUTH-01 (`verify_auth_coverage.PUBLIC_ENDPOINTS`).
