# 🔬 PLAYBOOK ANALISIS MENDALAM & KOMPREHENSIF
### Panduan + "Prompt Script" siap-pakai untuk memaksa AI agent (atau manusia) menghasilkan analisis yang dalam, bukan permukaan.

> **Tujuan:** Mengubah analisis dangkal ("global, normatif, menebak") menjadi analisis berbasis bukti,
> point-per-point, sadar batasan, dan langsung dapat dieksekusi.
> **Cara pakai cepat:** lompat ke **Bagian G** (Prompt Script) → isi placeholder → tempel ke AI agent.
> Sisanya (A–F, H) adalah teori, rubrik penilaian, dan template output agar hasilnya konsisten.

---

## A. KAPAN PLAYBOOK INI DIPAKAI
- Sebelum membangun/merombak fitur besar (redesign, integrasi, migrasi, arsitektur baru).
- Saat meminta "analisis" tetapi sering dapat jawaban dangkal/normatif.
- Saat keputusan butuh trade-off (pilih library, pola, prioritas) dan berdampak biaya/waktu.
- Untuk menilai apakah analisis sebuah agent layak dilanjutkan (pakai rubrik Bagian D).

**Tidak perlu** untuk tugas trivial (1–2 langkah, tanpa risiko, tanpa ambiguitas).

---

## B. DOKTRIN KEDALAMAN — 10 PRINSIP NON-NEGOTIABLE
1. **Bukti dulu, opini belakangan.** Dilarang berasumsi. Baca kode/dokumen/data NYATA & buka referensi NYATA dulu.
2. **Telusuri sumber primer.** Codebase asli, file brief/aset, URL referensi, skema DB, log — bukan ingatan/generalisasi.
3. **Telusuri batasan sebelum solusi.** Apa yang TIDAK boleh rusak? Guardrail/aturan? Kontrak API? Konvensi existing?
4. **Ketertelusuran (traceability).** Setiap poin kebutuhan → dipetakan ke solusi konkret → ke fase → ke file.
5. **Spesifik, bukan normatif.** "Pakai grid 12-kolom bento untuk spek armada di `FleetDetail.jsx`", bukan "buat UI modern".
6. **Sintesis komparatif.** Jika ada referensi/kompetitor, ekstrak pola → gabungkan jadi strategi spesifik (mis. blend 30/70).
7. **Manfaatkan aset yang sudah ada.** Hubungkan ide baru ke modul/data existing (jangan bangun ulang yang sudah ada).
8. **Kuantifikasi & benchmark.** Angka, target, budget (mis. LCP < 2s; konversi 2–8%) — bukan kata sifat.
9. **Keputusan ber-trade-off.** Setiap pilihan teknologi/pola: alasan + alternatif + kenapa ditolak.
10. **Artefak + checkpoint.** Hasil = dokumen yang bisa direview (matriks, plan, risiko) + KONFIRMASI sebelum eksekusi.

> Mnemonik 6 tahap: **B-T-K-S-R-A** → **B**ukti → **T**raceability → **K**endala → **S**intesis → **R**encana → **A**rtefak.

---

## C. PIPELINE ANALISIS — 6 TAHAP (lakukan berurutan)

### Tahap 0 — Tangkap Intent & Batasan (sebelum eksplorasi)
- **Aksi:** Baca permintaan mentah TANPA parafrase. Tandai: tujuan bisnis, kriteria sukses, ambiguitas, kata kunci eksplisit
  (warna, versi, library, "jangan…"), bahasa & nada yang diminta.
- **Output:** Daftar tujuan + daftar pertanyaan klarifikasi (ajukan SEBELUM menyelam jika krusial & ambigu).
- **Aturan:** Jangan tentukan hal yang sudah jadi domain user (mis. palet warna) sendiri — TANYAKAN.

### Tahap 1 — Kumpulkan Bukti (primary sources)
- **Aksi:** Eksplor codebase (struktur folder, file inti, pola, konvensi); baca dokumen/brief/aset; crawl URL referensi;
  cek skema DB & kontrak API; jalankan/lihat keadaan saat ini (screenshot/log).
- **Output:** Ringkasan "Apa yang SUDAH ADA & bagaimana cara kerjanya" + temuan mengejutkan.
- **Tool umum:** baca file (bulk), glob/grep, crawl web, analisis dokumen, screenshot, baca log.
- **Kualitas:** Kutip lokasi konkret (path/baris/endpoint). Jika belum baca, jangan klaim.

### Tahap 2 — Bedah Kebutuhan → Traceability Matrix (point-by-point)
- **Aksi:** Pecah permintaan jadi poin atomik. Untuk TIAP poin: status saat ini → akar masalah → solusi spesifik → fase.
- **Output:** **Tabel ketertelusuran** (lihat template F1). Tidak boleh ada poin user yang tidak terpetakan.

### Tahap 3 — Petakan Kendala & Arsitektur
- **Aksi:** Identifikasi guardrail/CI, hal yang wajib tetap utuh, kontrak API, batas teknologi, biaya, keamanan, RBAC,
  performa, aksesibilitas. Tentukan strategi agar perubahan AMAN (mis. "tanpa koleksi DB baru").
- **Output:** Daftar kendala + "strategi kepatuhan" + dampak ke desain solusi.

### Tahap 4 — Sintesis & Strategi
- **Aksi:** Gabungkan bukti+referensi jadi arah konkret. Lakukan: sintesis komparatif, leverage aset existing,
  keputusan ber-trade-off (riset bila perlu), kuantifikasi/benchmark, dan pemisahan NOW vs LATER beralasan.
- **Output:** Keputusan arsitektur + **decision log** (F2) + strategi blend/prioritas.

### Tahap 5 — Rencana Bertahap + Risiko + Kuantifikasi
- **Aksi:** Susun fase eksekusi (tujuan, file backend/frontend, dependensi, testing, pemetaan ke poin user).
  Tambah tabel risiko+mitigasi, budget performa, NOW/LATER, dan kesiapan instrumentasi (testid/analytics).
- **Output:** **Rencana berfase** (F3) + **tabel risiko** (F4).

### Tahap 6 — Artefak + Checkpoint + Iterasi
- **Aksi:** Tulis artefak yang bisa direview (mis. `design_guidelines.md`, `plan.md`, matriks). Ajukan KONFIRMASI
  dengan pertanyaan berpilihan (a/b/c). Jangan koding sebelum disetujui. Iterasi jika user minta lebih dalam.
- **Output:** Artefak final + ringkasan keputusan + pertanyaan GO/revisi.

---

## D. DEFINITION OF DONE — RUBRIK PENILAIAN (skor 0–100)
Beri nilai analisis sebelum dilanjutkan. **Lulus ≥ 85.**

| Kriteria | Bobot | Lulus bila… |
|----------|------:|-------------|
| Berbasis bukti (sumber primer dibaca & dikutip) | 20 | Ada kutipan path/endpoint/URL nyata, bukan asumsi |
| Ketertelusuran point-by-point | 20 | Setiap poin user terpetakan ke solusi+fase |
| Sadar kendala/guardrail | 15 | Risiko "merusak existing" diidentifikasi + strategi aman |
| Spesifik & dapat dieksekusi | 15 | Sebut file/komponen/endpoint konkret, bukan normatif |
| Trade-off & alternatif | 10 | Keputusan teknologi disertai alasan + opsi yang ditolak |
| Kuantifikasi/benchmark | 5 | Ada angka/target (perf, konversi, dll) |
| Leverage aset existing | 5 | Menghubungkan ke modul/data yang sudah ada |
| NOW vs LATER beralasan | 5 | Prioritas + alasan penundaan jelas |
| Artefak + checkpoint | 5 | Dokumen review + pertanyaan konfirmasi, tidak langsung koding |

---

## E. ANTI-PATTERN (CIRI ANALISIS DANGKAL) → PENANGKAL
| Ciri dangkal | Penangkal |
|--------------|-----------|
| "Buat UI modern & menarik" (normatif) | Sebut pola+komponen+file spesifik (Bagian C/F) |
| Menebak isi kode/dokumen | Baca sumber primer dulu (Tahap 1) |
| Lewatkan beberapa poin permintaan | Wajib Traceability Matrix lengkap (F1) |
| Abaikan hal yang bisa rusak | Tahap 3 (kendala/guardrail) wajib |
| Pilih library tanpa alasan | Decision log + trade-off (F2) |
| Tidak ada angka | Tambah benchmark/budget (Prinsip 8) |
| Langsung koding | Artefak + checkpoint dulu (Tahap 6) |
| Generik, tak terkait konteks | Leverage aset existing + sintesis komparatif |
| Berhenti di permukaan saat diminta "lebih dalam" | Iterasi: tambah riset tren + benchmark + tie-in |

---

## F. TEMPLATE OUTPUT (salin & isi)

### F1. Traceability Matrix
| # | Kebutuhan (poin user) | Kondisi saat ini (bukti) | Akar masalah | Solusi spesifik (file/komponen) | Fase |
|---|------------------------|--------------------------|--------------|----------------------------------|------|

### F2. Decision Log
| Keputusan | Opsi dipertimbangkan | Dipilih | Alasan | Alternatif ditolak (kenapa) |
|-----------|----------------------|---------|--------|-----------------------------|

### F3. Rencana Berfase
```
FASE n — <judul> (Status: NOT STARTED)
  Tujuan:
  Backend: <schema/router/docs/guardrail>
  Frontend: <komponen + halaman>
  Dependensi/lib:
  Testing: <esbuild/screenshot/testing_agent>
  Maps ke poin user: #...
```

### F4. Tabel Risiko & Mitigasi
| Risiko | Dampak | Kemungkinan | Mitigasi |
|--------|--------|-------------|----------|

### F5. NOW vs LATER
- **SEKARANG:** … (alasan dampak tinggi/biaya rendah)
- **DITUNDA:** … (alasan: butuh kredensial/biaya/perf/di luar scope) + kesiapan agar mudah dikerjakan nanti

---

## G. 🧰 PROMPT SCRIPT SIAP-PAKAI (copy-paste ke AI agent)
> Isi bagian `{…}`. Tempel utuh. Prompt ini "memaksa" agent melalui 6 tahap & melarang koding dini.

```
PERAN: Kamu analis senior. Lakukan ANALISIS MENDALAM & KOMPREHENSIF, BUKAN ringkasan permukaan.
BAHASA JAWABAN: {bahasa, mis. Indonesia}.
ATURAN KERAS:
- Dilarang berasumsi. Baca SUMBER PRIMER dulu (kode/dokumen/URL/skema/data) lalu KUTIP lokasinya (path/baris/endpoint/URL).
- Jangan menentukan hal yang merupakan preferensi pemilik (mis. palet warna, brand) sendiri — TANYAKAN dulu.
- JANGAN mulai implementasi/koding. Output tahap ini = ANALISIS + ARTEFAK + PERTANYAAN KONFIRMASI.

KONTEKS:
- Problem statement (mentah, jangan diparafrase): {tempel apa adanya}
- Referensi/kompetitor (URL): {url1, url2, …}
- Tech stack & batasan: {stack, guardrail/CI, hal yang tidak boleh rusak, RBAC, performa, dll}
- Aset/dokumen tersedia: {brief, file, kredensial, dataset}

LANGKAH WAJIB (lakukan berurutan, tampilkan hasil tiap langkah):
1) INTENT & AMBIGUITAS: daftar tujuan bisnis, kriteria sukses, kata kunci eksplisit, dan pertanyaan klarifikasi.
2) BUKTI: eksplor codebase/dokumen/URL; ringkas "yang SUDAH ADA & cara kerjanya" + temuan penting (dengan kutipan lokasi).
3) TRACEABILITY MATRIX: pecah problem jadi poin atomik; tiap poin → kondisi kini → akar masalah → solusi spesifik (file/komponen) → fase. (TIDAK boleh ada poin terlewat.)
4) KENDALA & ARSITEKTUR: guardrail/kontrak/hal-yang-tak-boleh-rusak + STRATEGI KEPATUHAN agar perubahan aman.
5) SINTESIS & KEPUTUSAN: sintesis komparatif referensi → strategi konkret; leverage aset existing; decision log (opsi+alasan+alternatif ditolak); benchmark/kuantifikasi; NOW vs LATER beralasan.
6) RENCANA BERFASE + RISIKO: fase (tujuan, file backend/frontend, dependensi, testing, maps ke poin) + tabel risiko/mitigasi + budget performa.
7) ARTEFAK & CHECKPOINT: tulis artefak yang dapat direview (mis. design_guidelines.md, plan.md) lalu ajukan PERTANYAAN BERPILIHAN (1,2,3 dengan opsi a/b/c) untuk persetujuan. Tunggu GO sebelum eksekusi.

SEBELUM SELESAI — SELF-CHECK (jawab jujur, perbaiki bila ada "Tidak"):
[ ] Sudah baca sumber primer & mengutip lokasinya?
[ ] Semua poin user terpetakan di matriks?
[ ] Risiko "merusak existing" + strategi aman sudah ada?
[ ] Solusi spesifik (sebut file/komponen), bukan normatif?
[ ] Ada trade-off + alternatif yang ditolak?
[ ] Ada angka/benchmark?
[ ] Menghubungkan ke aset/modul existing?
[ ] NOW vs LATER jelas + alasan?
[ ] Sudah membuat artefak + pertanyaan konfirmasi, dan TIDAK mulai koding?

JIKA pengguna berkata "kurang dalam": tambahkan riset tren terbaru + benchmark industri + lebih banyak tie-in aset existing + perinci tiap poin lebih detail; jangan ulang hal yang sama.
```

### G2. "One-liner" penegas (tambahkan bila agent tetap dangkal)
```
Naikkan kedalaman: untuk SETIAP klaim, sertakan bukti (kutipan path/endpoint/URL) + solusi spesifik (nama file/komponen) +
trade-off + angka. Hapus semua kalimat normatif tanpa bukti. Lengkapi Traceability Matrix sampai tidak ada poin terlewat.
```

---

## H. CONTOH PENERAPAN (studi kasus Rahaza Travel — ringkas)
- **Bukti:** baca `Home/Fleet/Destination/Blog/ContentManager.jsx`, `routers/{public,content,vehicles,settings}.py`,
  `schemas.py`, `scripts/gate.sh` + verifier; crawl kudanil.com & travelsos.co.uk; analisis brief `.docx`.
- **Traceability:** 9 kritik user → tabel solusi→fase (lihat `plan.md` §1).
- **Kendala:** guardrail `gate.sh` → strategi "tanpa koleksi DB baru; field di koleksi kanonik; tema di settings".
- **Sintesis:** blend 30% Kudanil / 70% TravelSOS; multi-theme glass; trade-off Framer Motion vs GSAP (pilih Framer).
- **Leverage existing:** GPS→peta rute; WA reminder→remarketing; data CHSE/KIR→trust badge; availability→urgensi jujur.
- **Kuantifikasi:** konversi 2–8%, abandonment >80%, budget LCP <2s.
- **Artefak:** `design_guidelines.md` + `plan.md` (§8 premium layer, §9 konversi, §10 performa) + checkpoint a/b/c.

---

_Versi 1.0 — dokumen hidup. Perbarui rubrik/anti-pattern saat menemukan pola baru._
