# 16 — DEV LIFECYCLE SOP (Pre-Development → Development → Post-Development)

> **Rahaza Travel ERP.** SOP siklus pengembangan agar tiap perubahan **minim-bug by design**,
> konsisten lintas-sesi AI, dan tak mengulang akar masalah (konteks hilang + kode tumbuh).
> Berpasangan dgn `docs/17_BUGHUNT_SOP.md` (bug-hunt), `memory/INVARIANTS.md` (SSOT invariant),
> `docs/15_POSTMORTEM_AND_MITIGATION.md` (pembelajaran).
>
> **Prinsip inti:** *"200/jalan ≠ benar"* — bukti korrektnya adalah **invariant + gate HIJAU**, bukan
> tampilan. Aturan pemaksa: sebelum klaim selesai, `bash scripts/gate.sh` HARUS HIJAU.

---

## Peta ekosistem guardrail (siapa jalan kapan)

```
PRE-DEV  (persiapan)     : scripts/preflight.py        — Definition of Ready + status artefak
DEV      (saat ngoding)  : INVARIANTS-first + guardrail-first (tulis penjaga utk perilaku baru)
POST-DEV (verifikasi)    : scripts/gate.sh             — 20+ gate statik+runtime (WAJIB HIJAU)
DEEP     (audit/rilis)   : scripts/run_forensics.sh    — gate + probe adversarial (bug-hunt)
SSOT                     : memory/INVARIANTS.md        — semua invariant + cara menambah
```

---

## FASE 1 — PRE-DEVELOPMENT (Persiapan / Rules / Mapping)

**Tujuan:** mulai dari konteks penuh, bukan dari nol. Jalankan `python scripts/preflight.py`.

**Definition of Ready (WAJIB terpenuhi sebelum menulis kode):**
1. **Baca SSOT** `memory/INVARIANTS.md` — pahami SEMUA invariant yang berlaku.
2. **Baca** `memory/SESSION_HANDOFF.md` + `memory/BUG_REGISTRY.md` — kondisi terakhir & bug lampau.
3. **Mapping perubahan:** koleksi/entitas & endpoint yang akan disentuh; peran (RBAC) yang terlibat;
   status/state-machine yang berubah.
4. **Kontrak API dulu:** tentukan path (`/api/...`), skema request/response, kode status
   (2xx/4xx) SEBELUM implementasi.
5. **Invariant-relevan:** identifikasi invariant yang berlaku utk perubahan ini
   (auth INV-AUTH-01, race INV-RACE-01/IDENT-01, numeric INV-NUM-01, 5xx INV-5XX-01,
   RBAC INV-RBAC, tarif INV-SET-01, kualitas INV-QUALITY-01).
6. **Rencana pembuktian:** bagaimana perubahan akan DIBUKTIKAN benar (guardrail/test apa).
7. **Definition of Done terukur** (bukan "kelihatan jalan").

---

## FASE 2 — DEVELOPMENT (Saat Ngoding)

**Aturan main:**
- **Invariants-first:** perilaku baru yang berisiko (mutasi, uang, jadwal, auth) → pikirkan
  invariant-nya lebih dulu.
- **Guardrail-first / bersamaan:** bila menambah kelas perilaku baru, tulis penjaganya
  (`scripts/guardrails/verify_*.py`) sekalian — lihat playbook di `docs/15` §6 & `INVARIANTS.md`.
- **Env, bukan hardcode:** `MONGO_URL`, `REACT_APP_BACKEND_URL` selalu dari ENV. Semua route `/api`.
- **Auth deklaratif:** tiap endpoint pakai `Depends(get_current_user/require_role/require_section)`
  kecuali benar-benar publik (daftar di allowlist INV-AUTH-01 + alasan).
- **Anti low-effort (INV-QUALITY-01):** jangan tinggalkan `NotImplementedError` di route,
  `except: pass` senyap, rahasia/URL hardcoded, atau data mock tak-tersanksi.
- **Bound & validasi input:** field numerik uang/kuantitas ber-`ge=0`; koersi angka dibungkus
  try/except → 400; kunci baris (lock) utk jalur reservasi.

---

## FASE 3 — POST-DEVELOPMENT (Verifikasi — WAJIB)

1. **`bash scripts/gate.sh` → HIJAU.** Ini gerbang wajib. Tulis `memory/GATE_RECEIPT.md`.
   Bila MERAH: perbaiki DULU (jangan lanjut / jangan klaim selesai).
2. **Verifikasi perilaku via testing_agent** (bukan hanya curl/inspeksi sendiri) untuk
   fitur/bugfix yang menyentuh API — lihat SOP bug-hunt `docs/17`.
3. **Perbarui SSOT & memori:** `INVARIANTS.md` (bila ada invariant baru + self-test),
   `BUG_REGISTRY.md` (bila ada bug), `SESSION_HANDOFF.md`, `plan.md`.
4. **DEEP (opsional/berkala):** `bash scripts/run_forensics.sh` untuk audit adversarial.

**Definition of Done:**
- [ ] Fungsional sesuai kontrak (2xx benar, 4xx utk input buruk, TIDAK ada 5xx).
- [ ] `gate.sh` HIJAU (0 SKIP untuk cakupan yang berlaku).
- [ ] Invariant baru (jika ada) di-wire + didaftar + **self-test-proven** (MERAH↔HIJAU).
- [ ] testing_agent memverifikasi (untuk perubahan API).
- [ ] Memori/dokumen diperbarui. Tak ada sinyal low-effort (INV-QUALITY-01 HIJAU).

---

## Anti-pattern yang DILARANG
- Klaim "selesai/fixed" tanpa `gate.sh` HIJAU + verifikasi testing_agent.
- "Hijau palsu": gate lolos tanpa benar-benar memeriksa (lihat pelajaran M1 di `docs/15`).
- Menambah guardrail tanpa wiring/registrasi (ditolak INV-META-01).
- Menonaktifkan/melonggarkan penjaga tanpa alasan tertulis di allowlist.
- "Everything is fine" tanpa bukti — lihat SOP bug-hunt untuk sikap adversarial.
