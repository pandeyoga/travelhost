# 14 — ANTI-UNDER-DELIVERY & EFFORT PROTOCOL
## Travel & Fleet Management Ecosystem

> **Status:** TIER 0 (wajib, prioritas tertinggi untuk perilaku agent).
> **Latar:** pain-point owner — agent AI sering **tidak memberi effort penuh**, mengerjakan setengah-setengah, lalu berdalih *"konteks kurang"*. Dokumen ini **melarang** itu dan menyediakan mekanisme yang **bisa diverifikasi mesin** (`verify_delivery.py` + `gate.sh` + `DELIVERY_MANIFEST.md`).
> **Prinsip:** *Effort itu wajib & terukur. "Selesai" = deliverable lengkap + bukti, bukan klaim.*

---

## 1. ⛔ ANTI-EXCUSE CLAUSE (paling penting)
DALIL berikut **DILARANG** dipakai untuk berhenti atau menurunkan kualitas:
- ❌ "Konteks/instruksi kurang" → maka aku kerjakan seadanya / berhenti.
- ❌ "Mungkin maksud user begini" lalu mengerjakan yang paling mudah saja.
- ❌ "HTTP 200 / tidak ada error" dianggap bukti selesai (RC-10).

**YANG WAJIB dilakukan saat informasi terasa kurang:**
1. **Gali dulu** dari sumber yang ADA: dokumen referensi, file yang diberikan, `docs/`, codebase (`preflight.py`, grep). *Mayoritas "konteks kurang" sebenarnya "belum dibaca".*
2. Bila benar ada celah keputusan → tulis **ASSUMPTION LEDGER** (lihat §3) **lalu tetap maju** dengan asumsi paling masuk akal, ditandai jelas.
3. Hanya **STOP & ASK** untuk hal yang **kritis & tak bisa diasumsikan** (kredensial, biaya, breaking change, pilihan produk besar) — dengan **pertanyaan bernomor + opsi**, bukan pertanyaan terbuka malas.
> Berhenti diam-diam tanpa ledger / tanpa pertanyaan = **pelanggaran berat**.

---

## 2. 📏 DEPTH STANDARD — Standar Kedalaman per Jenis Tugas
Under-deliver paling sering terjadi karena kerja **dangkal**. Baseline minimum:

### A. Tugas ANALISIS (mis. "analisis dokumen/referensi ini")
WAJIB menghasilkan, **tanpa diminta dua kali**:
- Pembedahan terstruktur per-bagian (bukan ringkasan 3 kalimat).
- **≥ 8 temuan konkret** + implikasi untuk proyek.
- Identifikasi **kontradiksi, risiko, celah, dan asumsi tersembunyi**.
- Referensi silang ke kebutuhan/komponen nyata (apa artinya untuk arsitektur/data/UI).
- Rekomendasi actionable + langkah berikutnya.
> Acuan kualitas: seandainya owner adalah konsultan senior yang membayar mahal — apakah ini layak? Jika tidak → perdalam.

### B. Tugas BUILD (fitur)
- Backend + Frontend + seed + states (loading/empty/error) + `data-testid` → **satu kesatuan**, bukan backend saja.
- Tidak meninggalkan **orphan endpoint** (BE tanpa UI) atau **ghost page** (UI tanpa data).
- Lulus `verify_delivery.py` + `gate.sh`.

### C. Tugas DEBUG
- RCA sampai akar (petakan ke RC), bukan tambal gejala. Tulis di `BUG_REGISTRY.md`.
- Tambah/menguatkan gate agar bug **tak terulang**.

### D. Tugas DESIGN/UI
- Ikuti `design_guidelines.md` + `06_UIUX_STANDARDS.md` sepenuhnya. Bukan UI "datar" asal jadi (RC-F8).

---

## 3. 🧾 ASSUMPTION LEDGER (template wajib saat info kurang)
Alih-alih berhenti, tulis ini di balasan lalu lanjut bekerja:
```
ASUMSI YANG SAYA AMBIL (agar tetap maju):
1. [Asumsi] — alasan: [...] — risiko bila salah: [...] — mudah diubah? [ya/tidak]
2. ...
YANG SAYA BUTUH DIKONFIRMASI (hanya yang kritis):
1. [pertanyaan bernomor + opsi a/b/c]
RENCANA: saya lanjut membangun X dengan asumsi di atas; bila (1) berbeda, dampak terbatas pada [file/area].
```

---

## 4. 📦 DELIVERY MANIFEST (mengubah "effort" jadi terukur)
Setiap fase punya **kontrak deliverable** di `memory/DELIVERY_MANIFEST.md`: daftar konkret & **bisa dihitung** (endpoint apa saja, halaman apa saja, min jumlah testid, seed count, invarian yang harus lulus, screenshot wajib).
- **`verify_delivery.py`** membaca manifest fase aktif → menghitung **completeness %** + menandai item kurang & orphan endpoint.
- **Exit ≠ 0** bila ada deliverable P0 yang belum ada → mustahil "klaim selesai" saat masih bolong.
> Manifest = janji yang ditagih mesin. Ini benteng utama anti under-deliver.

---

## 5. ✅ EVIDENCE-BASED COMPLETION (sejajar doc 11 §2)
"Selesai" hanya sah bila SEMUA ada:
- `memory/GATE_RECEIPT.md` **hijau** (dari `bash scripts/gate.sh`).
- `verify_delivery.py` → completeness 100% deliverable P0, 0 orphan.
- Nilai data benar + invarian lulus (bukan cuma 200).
- Screenshot preview URL menunjukkan UI benar.
- `testing_agent_v3` dijalankan utk perubahan signifikan; bug high/medium difix.
- Laporan **jujur**: sebut yang MOCKED/limitasi (HURUF KAPITAL).

---

## 6. 🧮 SELF-AUDIT EFFORT (sebelum tiap balasan "selesai")
```
□ Apakah aku sudah MENGGALI semua sumber yang ADA sebelum bilang "kurang konteks"?
□ Apakah kedalaman kerjaku memenuhi DEPTH STANDARD (§2) untuk jenis tugas ini?
□ Apakah ada deliverable yang aku diam-diam lewati? (cek DELIVERY_MANIFEST)
□ Apakah verify_delivery.py & gate.sh hijau (bukan asumsi)?
□ Apakah aku menulis Assumption Ledger alih-alih berhenti?
□ Apakah aku jujur soal yang belum selesai / MOCKED?
```
Ada □ tak terpenuhi → **JANGAN** klaim selesai; perbaiki atau lapor jujur.

---

## 7. ESKALASI (bukan menyerah)
Buntu ≠ berhenti. Tangga: self-debug 2× → `troubleshoot_agent` → `testing_agent_v3` → `web_search` → `integration_playbook_expert_v2` → lapor jujur + opsi (rollback/model lebih kuat) + bukti. **DILARANG** mengklaim selesai tanpa bukti, **DILARANG** menyerah diam-diam.
