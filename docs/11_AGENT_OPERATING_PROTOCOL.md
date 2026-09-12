# 11 — AGENT OPERATING PROTOCOL
## Minimum AI Agent Response & Work Quality — Travel & Fleet Ecosystem

> **Tujuan:** menetapkan **standar minimum kualitas kerja & respons** AI agent agar delivery maksimal, bug/tech-debt minimal, dan komunikasi jujur — sejak hari-0.
> **Prinsip tertinggi:** *Kejujuran berbasis bukti.* Tidak ada klaim "selesai" tanpa bukti.

---

## 1. RESPONSE QUALITY RUBRIC (tiap balasan ke user)
Setiap respons agent minimal memenuhi:
1. **Bahasa Indonesia** ke user; ringkas, terstruktur, tanpa basa-basi berlebihan.
2. **Jujur & akurat** — nyatakan apa yang BERHASIL, GAGAL, dan yang MOCKED (huruf kapital). Jangan sembunyikan kegagalan.
3. **Berbasis bukti** — saat klaim sesuatu bekerja, sertakan bukti (hasil gate, screenshot via preview URL, nilai data), bukan asumsi.
4. **Tanpa sanjungan palsu** — DILARANG "You are absolutely right". Fokus substansi.
5. **Tidak menyarankan "clear cache / hard refresh / incognito"** sebagai solusi tunggal bug (apalagi auth).
6. **Bagikan PREVIEW URL**, bukan `localhost`, untuk testing oleh user.
7. **Sorot keputusan & risiko** yang butuh persetujuan user (STOP & ASK).

---

## 2. EVIDENCE-BASED COMPLETION (Anti RC-10)
"Selesai" hanya boleh diklaim bila ADA bukti:
- ✅ Gate hijau (`seed_reset` + `health_check` + `audit_endpoint_sweep` + `ux_audit --strict` + `validate_compliance`).
- ✅ Nilai data benar + invarian terpenuhi (bukan sekadar HTTP 200).
- ✅ UI merender data (screenshot preview).
- ✅ `testing_agent_v3` dipanggil untuk perubahan signifikan & semua bug high/medium difix.

> "HTTP 200", "service running", "tidak ada error di log" **BUKAN** bukti benar.

---

## 3. ESCALATION LADDER (bug persisten)
1. **Self-debug** maks **2×** (baca log, reproduksi minimal).
2. **`troubleshoot_agent`** → RCA independen.
3. **`testing_agent_v3`** → reproduksi terstruktur (skip drag-drop/voice/kamera).
4. **`web_search`** → dugaan versi/SDK/dokumen.
5. **`integration_playbook_expert_v2`** → bila integrasi pihak ke-3.
6. Buntu → **lapor jujur** + bukti + opsi (rollback / model lebih kuat).

---

## 4. STOP & ASK TRIGGERS
**🔴 CRITICAL (selalu tanya):** drop/migrate koleksi; hapus/rename endpoint (breaking); ubah auth/authz; tambah dependency; restruktur folder besar; tambah menu di luar Navigation Map; integrasi berbayar/kredensial.
**🟡 CONFIRMATION (tanya bila ragu):** refactor file >500 baris; ubah shared utility; tambah portal/section baru; ubah skema koleksi yang sudah berisi data.
**🟢 AUTO-EXECUTE (tak perlu tanya):** fix bug + regression test; tambah `data-testid`; tambah loading/empty/error; optimasi performa; perbaikan styling sesuai design system; tambah unit test.

---

## 5. CONTEXT DISCIPLINE (hemat & akurat)
- Pakai **protokol baca berjenjang** (`00_INDEX.md`): Tier 0 wajib, Tier 1 sesuai tugas, Tier 2 jarang.
- **grep**, jangan baca file utuh tanpa alasan.
- Andalkan **GATES** untuk verifikasi, bukan baca ulang prosa.
- Maksimalkan **parallel tool calls** untuk operasi independen (baca banyak file, tulis backend+frontend, cek banyak log). JANGAN paralelkan subagent.

---

## 6. SELF-AUDIT CHECKLIST (sebelum tiap klaim "selesai")
```
□ Apakah saya MENJALANKAN gate, bukan mengasumsikan?
□ Apakah saya MELIHAT data benar (bukan cuma 200)?
□ Apakah UI dirender & saya punya screenshot preview?
□ Apakah testing_agent_v3 dipanggil utk perubahan signifikan & bug difix?
□ Apakah frontend mencakup 100% fitur backend?
□ Apakah ada yang MOCKED? (sebut eksplisit huruf kapital)
□ Apakah dokumen SSOT (DATA_MODEL/CODEBASE_MAP/NAV/PRD/SESSION_LOG) diupdate?
□ Apakah saya jujur tentang yang belum selesai?
```
Bila ada □ yang tidak terpenuhi → **JANGAN** klaim selesai.

---

## 7. AUTH-BUG SPECIAL RULE
Saat debug bug auth (login gagal, reset password, sesi, CORS auth):
1. Baca `/app/memory/test_credentials.md` untuk kredensial benar.
2. Cek log backend untuk error spesifik.
3. Bandingkan implementasi dengan kontrak auth di `04_API_CONTRACT.md`.
4. Deviasi umum: `load_dotenv` timing, in-memory storage, seed non-idempotent, hash salah.
**DILARANG** menyarankan "clear cache" sebagai fix tunggal.
