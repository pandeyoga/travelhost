# 15 — POSTMORTEM & MITIGATION (Sumber Pembelajaran + Acuan Mitigasi)

> **Rahaza Travel ERP (FastAPI + React + MongoDB).** Dokumen ini adalah **sumber pembelajaran**
> dari seluruh putaran audit & perbaikan, sekaligus **acuan mitigasi** yang bisa dibaca oleh sesi
> AI / kontributor baru **tanpa konteks sebelumnya**. Baca bersama:
> `memory/INVARIANTS.md` (SSOT invariant), `memory/BUG_REGISTRY.md` (riwayat bug),
> `docs/07_ENGINEERING_GUARDRAILS.md`, `docs/08_FRONTEND_GUARDRAILS.md`.
>
> **Aturan emas:** sebelum klaim "selesai", jalankan `bash scripts/gate.sh` → harus **HIJAU**.

---

## 0. Jawaban jujur: "Zero bug"?

**Tidak.** Yang benar dan bisa dipertanggungjawabkan:

- ✅ **Semua bug yang DIKETAHUI** (seluruh katalog temuan audit §7: O-1, RC-MATRIX-A/B,
  R6-1..R6-5, EXPORT-1, ID-RACE, SET-1, M1) **sudah ditutup** dan **dijaga preventif** oleh
  gate + guardrail yang **self-test-proven**.
- ⚠️ Guardrail mencegah **regresi kelas yang sudah dikenal**. Ia **tidak** bisa menjamin nol
  **kelas baru** yang belum terpikirkan, maupun bug pada **permukaan yang belum diuji**.
- ⚠️ Gap jujur yang tersisa: **real WhatsApp send** (masih MOCK — butuh kredensial Meta WABA),
  **uji beban konkuren tinggi** belum dilakukan, integrasi eksternal **OSRM/geocode** belum
  diuji live penuh.

**Status akurat: "minimum known-bug / near-zero pada permukaan yang teruji" — BUKAN "zero bug".**
Confidence saat ini: **~96%** (naik dari ~78% di awal audit).

---

## 1. Root cause SISTEMIK (kenapa bug berulang)

Audit Putaran 6–12 menyimpulkan bug **bukan** karena fondasi rapuh, melainkan **2 penyebab sistemik**:

1. **Konteks hilang antar-sesi AI.** Tiap sesi baru me-restore repo ke environment baru; aturan
   pengaman yang "diingat" sesi lama tidak otomatis diketahui sesi baru → pola aman tak diterapkan
   konsisten di permukaan baru.
2. **Kode tumbuh (42 router + 43 service).** Endpoint/field baru terus bertambah; pola aman yang
   benar di satu tempat **tidak** ikut ke tempat baru.

Tes lama hanya menguji **happy-path** (coverage 46%) → kelas bug bersembunyi di jalur mutasi &
cabang error yang tak tereksekusi.

**Kesimpulan strategi:** ubah aturan dari *"diingat developer"* → *"DIPAKSA oleh analisis kode"*
(statik + runtime) yang **berjangkar pada SSOT** dan **berjalan otomatis di gate**.

---

## 2. Taksonomi kelas bug yang ditemukan & DITUTUP

| Kelas | Contoh temuan | Root Cause | Status | Invariant penjaga |
|---|---|---|---|---|
| RBAC leakage | O-1 (driver akses modul manajemen) | guard tak konsisten | ✅ ditutup | INV-RBAC-01/02/03 |
| Race / TOCTOU (armada/sopir) | RC-MATRIX-A, R6-1 (double-book) | cek+tulis tak atomik | ✅ ditutup | INV-RACE-01 |
| Nilai negatif | RC-MATRIX-B, R6-2, R6-3 (57 field) | schema tak ber-bound | ✅ ditutup | INV-NUM-01 |
| Crash 5xx input adversarial | EXPORT-1, R6-4, R6-5 | input buruk tak di-handle | ✅ ditutup | INV-5XX-01 |
| Race pembuatan identity | ID-RACE (customer ganda) | dedupe TOCTOU tanpa index unik | ✅ ditutup | INV-IDENT-01 |
| Tarif tak tervalidasi | SET-1 (harga negatif/absurd) | tak ada validasi titik-tulis | ✅ ditutup | INV-SET-01 |
| Guardrail "hijau-palsu" | M1 (gate kontrak tak periksa apa-apa) | tooling ketinggalan pola FE | ✅ ditutup | (fix `verify_api_contract.py`) |
| Guardrail hilang antar-sesi | (preventif) | tak ada meta-cek | ✅ dicegah | INV-META-01 |

Riwayat runtime lama (RC-01..RC-07, INV-1..INV-21) tetap dijaga gate inti
(`verify_state_machine`, `verify_concurrency`, `verify_cross_entity`).

---

## 3. Arsitektur mitigasi — 3 lapis + meta

```
LAPIS 1 — STATIK (selalu jalan, tanpa backend)
  INV-NUM-01  numeric bounds (AST schemas.py)
  INV-RACE-01 reservation locks (auto-discovery write-path)
  INV-RBAC-01/02/03 RBAC (route FE + dep BE + drift matrix)
  M1          FE↔BE contract gate (verify_api_contract.py) — kini NYATA

LAPIS 2 — RUNTIME (butuh backend + auth)
  INV-5XX-01   no-5xx pada input adversarial
  INV-IDENT-01 identity race (N POST paralel → tepat 1)
  INV-SET-01   validasi tarif settings (bad→400, valid→200)
  + health_check, audit_endpoint_sweep, mutation_smoke, state_machine,
    concurrency, cross_entity

LAPIS 3 — META (integritas sistem penjaga)
  INV-META-01  tiap guardrail WAJIB ter-wire di gate.sh + terdaftar di INVARIANTS.md
```

**Orkestrator tunggal:** `scripts/gate.sh` → menulis `memory/GATE_RECEIPT.md`.
**SSOT invariant:** `memory/INVARIANTS.md` (baca ini dulu bila Anda sesi/kontributor baru).

---

## 4. Prinsip anti "HIJAU-PALSU" (pelajaran terpenting dari M1)

Guardrail hanya bernilai bila **benar-benar menangkap pelanggaran**. Karena itu **setiap** penjaga
WAJIB **di-self-test**: *inject pelanggaran → gate MERAH (pesan tepat) → revert → gate HIJAU.*

Pelajaran M1: gate kontrak FE↔BE **lolos selama berbulan-bulan tanpa memeriksa apa pun** karena
regex-nya hanya mencari `axios.`/`fetch(`, padahal FE memakai `apiClient.<m>()`. **0 call
terdeteksi = "hijau palsu".** Setelah diperbaiki: **260 call (167 path) tervalidasi**.
→ **Tiap gate hijau harus dibuktikan bisa MERAH.** (Kini dipaksa juga oleh INV-META-01.)

Bukti self-test (Putaran 12):
- **M1:** sisip `apiClient.get("/route-ngawur")` → MERAH (tunjuk route+file) → revert → HIJAU.
- **INV-IDENT-01:** DROP index `phone_normalized_1` → 8 POST paralel → 2 duplikat → MERAH → recreate → HIJAU.
- **INV-SET-01:** nonaktifkan `_validate_pricing` → 6 tarif buruk 200 senyap → MERAH → revert → HIJAU.
- **INV-META-01:** buat guardrail tanpa wiring/registrasi → MERAH → hapus → HIJAU.

---

## 5. Matriks mitigasi (kelas bug → invariant → penjaga → cara kerja preventif)

| Invariant | Penjaga (file) | Jenis | Cara mencegah regresi otomatis |
|---|---|---|---|
| INV-NUM-01 | `verify_numeric_bounds.py` | statik | Scan AST `schemas.py`; field uang/kuantitas baru tanpa `ge=`/`gt=` → MERAH |
| INV-RACE-01 | `verify_reservation_locks.py` | statik | **Auto-discovery**: fungsi mutasi baru yang panggil conflict-finder wajib pegang lock |
| INV-RBAC-01/02/03 | `verify_rbac_guards.py` | statik | Route FE tanpa `<RoleGuard>` / router sensitif tanpa dep / drift matrix → MERAH |
| INV-5XX-01 | `verify_adversarial_5xx.py` | runtime | Payload adversarial → assert status < 500 |
| INV-IDENT-01 | `verify_identity_race.py` | statik+runtime | Cek index unik + handler DuplicateKey; N POST paralel → tepat 1 |
| INV-SET-01 | `verify_settings_bounds.py` | statik+runtime | Cek `_validate_pricing` ada; PATCH tarif buruk → 400, valid → 200 |
| INV-META-01 | `verify_guardrail_registry.py` | statik-meta | Guardrail tak ter-wire/terdaftar → MERAH (cegah perlindungan mati diam-diam) |

Prinsip pendukung:
- **Allowlist ber-justifikasi:** pengecualian sah harus eksplisit + beralasan di skrip (tak ada yang lolos diam-diam).
- **Auto-discovery > daftar manual:** penjaga menemukan write-path baru sendiri → tak bergantung memori sesi.
- **SSOT tunggal:** `memory/INVARIANTS.md` — 1 file untuk tahu SEMUA aturan + cara menambah.

---

## 6. PLAYBOOK — cara menambah invariant/guardrail baru (untuk sesi berikutnya)

1. Tulis penjaga `scripts/guardrails/verify_<nama>.py`. Gunakan `from _common import Guard`
   dan deklarasikan `Guard("INV-<AREA>-<NN>", "<judul>")` (format WAJIB agar terdeteksi INV-META-01).
   Statik lebih disukai; runtime bila butuh perilaku. Cetak APA + DI MANA + INVARIANT-ID.
2. **Wire** ke `scripts/gate.sh` (blok STATIK atau RUNTIME) dengan `run_gate "guard:<nama> (INV-...)" "python scripts/guardrails/verify_<nama>.py"`.
3. **Daftarkan** baris invariant di tabel `memory/INVARIANTS.md`.
4. **Self-test WAJIB:** buktikan MERAH saat invariant dilanggar, HIJAU saat benar. Catat buktinya
   di `memory/INVARIANTS.md` (bagian anti hijau-palsu).
5. Catat bug (bila ada) di `memory/BUG_REGISTRY.md` (format PB-6).
6. Jalankan `bash scripts/gate.sh` → pastikan HIJAU. INV-META-01 akan menolak bila langkah 2/3 terlewat.

---

## 7. Risiko residual (jujur) & jalan ke ~97%+

| Risiko | Status | Untuk menutup |
|---|---|---|
| Kelas bug BARU (belum terpikir) | inheren | Tambah invariant saat kelas baru ditemukan (playbook §6) |
| Real WhatsApp Meta Cloud send | MOCK | Isi kredensial WABA → uji kirim nyata + webhook |
| Beban konkuren tinggi lintas modul | belum diuji | Load test (mis. k6/locust) pada booking/payment/dispatch |
| OSRM/geocode live | parsial | Uji di environment berjaringan + kredensial |
| Static tripwire berbasis-string | terbatas | (opsional) upgrade ke AST utk anti-komentar |

---

## 8. Referensi cepat

- **Jalankan semua gate:** `bash scripts/gate.sh` → `memory/GATE_RECEIPT.md`.
- **SSOT invariant:** `memory/INVARIANTS.md`.
- **Riwayat bug + regresi:** `memory/BUG_REGISTRY.md`.
- **Laporan audit:** `docs/AUDIT_REPORT_ROUND11.md` (§7 katalog temuan — semua DITUTUP).
- **Handoff sesi:** `memory/SESSION_HANDOFF.md`.
- **Akun demo:** owner@/ops@/driver@demo.local · `demo12345`. WhatsApp = MOCK.
