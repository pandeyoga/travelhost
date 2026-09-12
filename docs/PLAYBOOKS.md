# 📕 PLAYBOOKS — Resep Deterministik (Layer 2 / DO)
## Travel & Fleet Management Ecosystem

> **Aturan:** setiap tugas = 1 playbook. Tiap langkah **menunjuk script spesifik**.
> Tujuan: agent nol-konteks mengerjakan dengan benar **tanpa duplikasi/asumsi/halusinasi**.
> SELALU mulai dengan `preflight.py` (anti-duplikasi) dan SELALU tutup dengan `gate.sh`.

---

## 🔎 LANGKAH-0 WAJIB UNTUK SEMUA PLAYBOOK
```bash
python scripts/preflight.py "<kata-kunci-fitur>"
```
Output menjawab: koleksi/endpoint/komponen **sudah ada?** nama **kanonik**? field sah? → mencegah kamu membuat duplikat atau mengarang nama. **Jika EXISTS → REUSE. Jika NEW → daftarkan sesuai playbook.**

---

## PB-1 — Tambah KOLEKSI DB baru
**Kapan:** domain data benar-benar baru (sudah dipastikan via preflight & `verify_contract.py --list-canonical`).
1. `python scripts/preflight.py <nama>` → pastikan TIDAK ada alias/kanonik yang sama.
2. Update **`docs/03_DATA_MODEL.md`**: tambah ke daftar kanonik + skema field + id-prefix + invarian (bila ada).
3. Tambah nama ke `CANONICAL_COLLECTIONS` di **`scripts/verify_contract.py`** & `CANONICAL` di **`scripts/validate_compliance.py`** & `verify_schema.py` (PREFIX_MAP/SCHEMA).
4. Bila punya invarian domain → tambah `Concept(...)` + cek di **`scripts/verify_data_integrity.py`**.
5. Update `seed_data.py` agar koleksi terisi data realistis yang LULUS invarian.
6. **Gate:** `python scripts/verify_contract.py --all` → `bash scripts/seed_reset.sh` → `python scripts/verify_schema.py`.
> ❗Lupa langkah 3–4 = guardrail "membusuk" (drift tak terdeteksi).

---

## PB-2 — Tambah ENDPOINT API baru
1. `python scripts/preflight.py <nama>` → cek duplicate route & koleksi kanonik.
2. Tulis di **`backend/routers/<domain>.py`** (router **thin**), business logic ke **`services/`**. Prefiks **`/api`**.
3. Pakai `safe_doc()` saat serialisasi; respons **array/objek telanjang**.
4. List endpoint → **WAJIB pagination** (`limit`/`skip` atau `page`) — lihat `13_ARCHITECTURE_BEST_PRACTICES.md` §Performa.
5. Update **`docs/04_API_CONTRACT.md`** + **`docs/10_CODEBASE_MAP.md`**.
6. Tambah ke `CRITICAL_ENDPOINTS` di **`scripts/health_check.py`** bila endpoint penting.
7. **Gate:** `python scripts/verify_api_contract.py` (no duplicate/ghost) → `python scripts/audit_endpoint_sweep.py` (0×5xx) → `python scripts/verify_architecture.py` (pagination/efisiensi).

---

## PB-3 — Tambah HALAMAN / MENU Frontend
1. `python scripts/preflight.py <nama>` + baca **`docs/05_NAVIGATION_MAP.md`** (posisi & role).
2. Tambah menu HANYA via **`frontend/src/config/navigationConfig.js`** (`PAGE_META`, `items`, `ROLE_MENU_ALLOWLIST`).
3. Komponen pakai **shadcn** (`components/ui`), ikon **lucide-react**. WAJIB: loading + empty + error state.
4. WAJIB `data-testid` kebab-case di tiap elemen interaktif & info kritis.
5. Semua call lewat **`services/apiClient.js`**; guard `Array.isArray`.
6. **Gate:** `npx esbuild src/index.js --loader:.js=jsx --bundle --outfile=/dev/null` → `python scripts/check_nav_map.py` → `python scripts/ux_audit.py --strict` → `python scripts/verify_delivery.py` (cegah halaman "ghost"/endpoint "yatim").

---

## PB-4 — Tambah ROLE / PERMISSION
1. Baca **`backend/permissions_config.py`** + matriks role di **`docs/05_NAVIGATION_MAP.md`** (SATU sumber kebenaran izin).
2. Update matriks BE **dan** `ROLE_MENU_ALLOWLIST` FE secara sinkron (cegah RC-9 dua-sumber).
3. **Gate:** `python scripts/verify_api_contract.py` + `testing_agent_v3` (uji akses per role).

---

## PB-5 — Tambah INTEGRASI pihak ke-3
1. **STOP & ASK** ke user (kredensial = trigger kritis, lihat doc 11 §4).
2. Panggil **`integration_playbook_expert_v2`** → dapatkan playbook resmi.
3. Simpan kredensial di **`.env`** (JANGAN di FE, JANGAN hardcode). Untuk LLM → `EMERGENT_LLM_KEY`.
4. Implement sesuai playbook → jalankan checklist playbook → `bash scripts/gate.sh`.

---

## PB-6 — Perbaiki BUG
1. Catat di **`memory/BUG_REGISTRY.md`**: gejala + RC (taksonomi doc 07/08) + gate yang seharusnya menangkap.
2. Self-debug **maks 2×** (baca log, reproduksi minimal). Buntu → `troubleshoot_agent` → `testing_agent_v3` (escalation ladder doc 11 §3).
3. Tulis **regression**: kalau gate yang ada tidak menangkap bug ini → **perkuat gate** (tambah invarian/cek). Guardrail harus tumbuh.
4. **Gate:** `bash scripts/gate.sh` → update status bug di registry jadi `FIXED` + bukti.

---

## PB-7 — TUTUP sebuah FASE (Definition of Done)
1. Buka **`memory/DELIVERY_MANIFEST.md`** → penuhi SEMUA deliverable P0 fase tsb.
2. `python scripts/verify_delivery.py` → 100% deliverable ada, **0 orphan endpoint**.
3. `bash scripts/gate.sh` → semua gate hijau → `memory/GATE_RECEIPT.md`.
4. `testing_agent_v3` 1 putaran → baca laporan → fix semua bug high/medium.
5. Screenshot via **preview URL** (loading/empty/error tampil, angka rapi).
6. Update dokumen SSOT (`01_PRD`, `03_DATA_MODEL`, `05_NAV`, `10_CODEBASE_MAP`) + tandai fase **COMPLETED** di `plan.md` & `09_ROADMAP.md` + isi `SESSION_HANDOFF.md`.
> ❗Fase TIDAK boleh ditandai COMPLETED bila receipt merah atau ada deliverable kurang.

---

## 🔁 PLAYBOOK REVAMP — Mengubah fitur yang SUDAH ada
> Revamp adalah warga kelas-satu (lihat `13` §Revamp). Aman karena gate menangkap regresi.
1. `python scripts/preflight.py <nama>` → temukan SEMUA file/endpoint terdampak (jangan duplikat).
2. Jalankan `bash scripts/gate.sh` **DULU** → simpan baseline receipt (kondisi sebelum ubah).
3. Lakukan perubahan (hormati batas ukuran file & kontrak API).
4. Jalankan `bash scripts/gate.sh` lagi → bandingkan dengan baseline. Tidak boleh ada gate baru yang merah.
5. Update dokumen SSOT terkait + BUG_REGISTRY bila revamp memperbaiki bug.
