# 🚦 AGENT START HERE — Gerbang Tunggal (Layer 1 / BOOT)
## Travel & Fleet Management Ecosystem

> **Untuk SIAPA:** kamu, AI agent yang baru masuk dengan **NOL konteks**.
> **Tujuan file ini:** membuatmu produktif & BENAR dalam < 5 menit, tanpa menebak,
> tanpa duplikasi, tanpa halusinasi. **Baca file ini SAMPAI HABIS sebelum menyentuh kode.**
>
> Aturan #1: *Kebenaran = output script (GATES), bukan klaim.* Kalau ragu → jalankan script, jangan berasumsi.

---

## ⛔ 3 HAL YANG DILARANG KERAS
1. **DILARANG menulis kode bisnis sebelum** menyelesaikan "BOOT SEQUENCE" di bawah.
2. **DILARANG berdalih "konteks kurang" lalu berhenti / menurunkan kualitas.** Lihat `14_ANTI_UNDERDELIVERY_PROTOCOL.md`. Kalau kurang info → tulis *Assumption Ledger* atau ajukan pertanyaan bernomor, **lalu tetap maju**.
3. **DILARANG klaim "selesai" tanpa `GATE_RECEIPT.md` hijau** (dihasilkan `scripts/gate.sh`).

---

## 🥾 BOOT SEQUENCE (jalankan berurutan, copy-paste)
```bash
cd /app
# 1) Snapshot kondisi sistem (service, env, jumlah dok DB, file-size, compliance, handoff terakhir)
bash scripts/load_context.sh

# 2) Cek handoff sesi sebelumnya (apa yang sudah/ belum selesai)
cat memory/SESSION_HANDOFF.md

# 3) Lihat fase yang sedang berjalan SAJA (jangan baca semua roadmap)
sed -n '/IN PROGRESS/,/^## PHASE/p' docs/09_ROADMAP.md
```
Lalu baca **TIER 0** (ringkas): `07_ENGINEERING_GUARDRAILS.md`, `08_FRONTEND_GUARDRAILS.md`, `11_AGENT_OPERATING_PROTOCOL.md`, `13_ARCHITECTURE_BEST_PRACTICES.md`, `14_ANTI_UNDERDELIVERY_PROTOCOL.md`.

> Detail protokol baca berjenjang: `00_INDEX.md`. **Jangan** baca seluruh dokumen tiap sesi.

---

## 🧭 DECISION TREE — "Saya mau melakukan X, mulai dari mana?"
Setiap aksi WAJIB lewat **PLAYBOOK** yang menunjuk script spesifik. Buka `docs/PLAYBOOKS.md`.

| Saya mau... | Langkah pertama (ANTI-DUPLIKASI) | Playbook | Gate penutup |
|-------------|----------------------------------|----------|--------------|
| Tambah **koleksi DB** | `python scripts/preflight.py <nama>` → cek sudah ada/alias terlarang | PB-1 | `verify_contract.py` + `verify_schema.py` |
| Tambah **endpoint API** | `python scripts/preflight.py <nama>` → cek duplikat route | PB-2 | `verify_api_contract.py` + `audit_endpoint_sweep.py` |
| Tambah **halaman/menu FE** | `python scripts/preflight.py <nama>` + baca `05_NAVIGATION_MAP.md` | PB-3 | `check_nav_map.py` + `ux_audit.py --strict` |
| Tambah **role/permission** | baca `permissions_config.py` + `05_NAVIGATION_MAP.md` | PB-4 | `verify_api_contract.py` + testing_agent |
| Tambah **integrasi pihak-3** | panggil `integration_playbook_expert_v2` | PB-5 | playbook checklist |
| **Perbaiki bug** | catat di `memory/BUG_REGISTRY.md` + petakan ke RC (doc 07) | PB-6 | `gate.sh` + regression |
| **Tutup sebuah fase** | penuhi `memory/DELIVERY_MANIFEST.md` fase itu | PB-7 | `gate.sh` (semua hijau) |

---

## ✅ SEBELUM "SELESAI" — SATU PERINTAH
```bash
bash scripts/gate.sh          # menjalankan SEMUA gate berurutan → menulis memory/GATE_RECEIPT.md
cat memory/GATE_RECEIPT.md    # WAJIB hijau. Kalau ada FAIL → perbaiki, jangan klaim selesai.
```
Receipt **merah / tidak ada** = pekerjaan **BELUM** selesai. Titik.

---

## 🗺️ PETA SINGKAT REPO
```
docs/   → SSOT (acuan). 00_INDEX = peta. AGENT_START_HERE (ini) = gerbang. PLAYBOOKS = resep.
scripts/→ GATES (penegak). gate.sh = orkestrator tunggal. preflight.py = anti-duplikasi.
memory/ → SESSION_HANDOFF, SESSION_LOG, BUG_REGISTRY, DELIVERY_MANIFEST, GATE_RECEIPT, test_credentials.
backend/→ FastAPI (routers thin + services). frontend/ → React + shadcn (dual-surface).
```

## 🔑 KONTRAK YANG TAK BOLEH DILANGGAR (hafalkan)
- Penamaan **generik** (tanpa brand). Koleksi **kanonik** (lihat `03_DATA_MODEL.md`).
- Auth: `POST /api/auth/login` → `{"token":"sess_...","user":{...}}`. Field = **`token`**.
- List endpoint → **ARRAY telanjang**. Detail/dashboard → **objek telanjang**. Tanpa envelope.
- Semua route prefiks **`/api`**. ID = UUID berprefiks via `new_id()`. Waktu = ISO UTC via `now_iso()`.
- FE selalu lewat `services/apiClient.js`; guard `Array.isArray`. `data-testid` wajib.
- **JANGAN** ubah `.env` (`MONGO_URL`, `REACT_APP_BACKEND_URL`). Paket FE via **`yarn`** (bukan npm).

**Versi:** 1.0 · Baca ulang bagian DECISION TREE setiap memulai tugas baru.
