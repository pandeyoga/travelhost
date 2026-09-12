# 00 — INDEX & READING PROTOCOL
## Travel & Fleet Management Ecosystem — Documentation SSOT

> **Filosofi inti (warisan dari studi guardrails):**
> *"Dokumentasi bukan penegakan. Prosa membusuk. Guardrail yang benar = **kode yang bisa GAGAL (exit ≠ 0)** dan dijalankan otomatis."*
>
> Dokumen di sini adalah **referensi kebenaran (SSOT)**. Penegakan dilakukan oleh **scripts** di `/app/scripts/` yang bisa GAGAL. Bila dokumen ≠ kode berjalan → **kode menang**, lalu perbaiki dokumen.

---

## 📐 ATURAN PALING PENTING

1. **Penamaan kode GENERIK** — dilarang memakai nama brand/perusahaan di kode (koleksi, variabel, endpoint, komponen). Contoh benar: `vehicles`, `bookings`, `drivers`. Contoh salah: `rahazaVehicles`.
2. **Bahasa**: komunikasi ke user = **Bahasa Indonesia**. Kode/variabel = English. Label UI = Bahasa Indonesia. Komentar kode boleh Indonesia.
3. **Kebenaran = GATES**, bukan prosa. Sebelum klaim "selesai", jalankan gate (lihat `12_SOP_AND_DELIVERY.md`).
4. **"HTTP 200 / service running" BUKAN bukti benar** (anti RC-10). Bukti = nilai data benar + invarian terpenuhi + UI merender data.

---

## 🗂️ PETA DOKUMEN

| File | Isi | Kapan dibaca |
|------|-----|--------------|
| `AGENT_START_HERE.md` | **GERBANG TUNGGAL** agent baru (boot sequence + decision tree) | **PALING AWAL, tiap sesi** |
| `PLAYBOOKS.md` | Resep deterministik per tugas (tiap langkah \u2192 script) | Tiap memulai tugas |
| `00_INDEX.md` | File ini — peta + protokol baca | Tiap sesi (Tier 0) |
| `01_PRD.md` | Kebutuhan produk (dari brief) + backlog fitur | Tier 1 |
| `02_ARCHITECTURE.md` | Arsitektur sistem + keputusan teknis | Tier 1 |
| `03_DATA_MODEL.md` | **Entity Registry (SSOT koleksi/skema/invarian)** | Tier 1 (koleksi yang disentuh) |
| `04_API_CONTRACT.md` | Kontrak API kanonik (shape respons, auth) | Tier 0 |
| `05_NAVIGATION_MAP.md` | SSOT navigasi/IA + role matrix + testid | Tier 1 (sebelum tambah halaman) |
| `06_UIUX_STANDARDS.md` | Baseline usability + rujukan `design_guidelines.md` | Tier 0 (frontend) |
| `07_ENGINEERING_GUARDRAILS.md` | Kontrak backend + taksonomi Root-Cause + 3-Gate + DoD | Tier 0 |
| `08_FRONTEND_GUARDRAILS.md` | Kontrak frontend | Tier 0 (frontend) |
| `09_ROADMAP.md` | Roadmap berfase + timeline + dependency | Tier 1 (fase berjalan) |
| `10_CODEBASE_MAP.md` | Peta file & endpoint + batas ukuran file | Tier 0 (cari, jangan baca utuh) |
| `11_AGENT_OPERATING_PROTOCOL.md` | **Minimum AI Agent Response Quality** + honesty + eskalasi | Tier 0 |
| `12_SOP_AND_DELIVERY.md` | SOP workflow + perintah gate + Definition of Done | Tier 0 |
| `13_ARCHITECTURE_BEST_PRACTICES.md` | **Best-practice arsitektur** (realtime, performa/pagination, tech-debt, IA, tech-stack) | Tier 0 |
| `14_ANTI_UNDERDELIVERY_PROTOCOL.md` | **Anti under-deliver** (anti-excuse, assumption ledger, depth standard, delivery manifest) | Tier 0 |
| `/app/design_guidelines.md` | **Design system lengkap** (token, tipografi, komponen, blueprint) | Tier 1 (frontend) |

**Memory (`/app/memory/`):** `SESSION_LOG.md` (log per-sesi), `SESSION_HANDOFF.md` (handoff terakhir), `BUG_REGISTRY.md` (lacak bug \u2192 RC \u2192 gate), `DELIVERY_MANIFEST.md` (kontrak deliverable per fase), `GATE_RECEIPT.md` (bukti gate \u2014 auto-generate), `test_credentials.md` (akun demo — gitignored).

---

## 📖 PROTOKOL BACA BERJENJANG (hemat context window)

> JANGAN baca semua dokumen tiap sesi. Baca berjenjang.

**TIER 0 — WAJIB tiap sesi (ringkas):**
0. **`docs/AGENT_START_HERE.md`** → gerbang tunggal: boot sequence + decision tree (BACA PERTAMA).
1. `bash scripts/load_context.sh` → snapshot service/env/DB/file-size/compliance + handoff terakhir.
2. `07_ENGINEERING_GUARDRAILS.md` — kontrak backend + RC + DoD.
3. `08_FRONTEND_GUARDRAILS.md` — kontrak frontend.
4. `11_AGENT_OPERATING_PROTOCOL.md` — standar kualitas respons & kejujuran.
5. `13_ARCHITECTURE_BEST_PRACTICES.md` — realtime, performa, tech-debt, IA.
6. `14_ANTI_UNDERDELIVERY_PROTOCOL.md` — anti under-deliver (effort & bukti).
7. `10_CODEBASE_MAP.md` — cari file/endpoint (grep, jangan baca utuh).
8. `09_ROADMAP.md` → **fase yang sedang berjalan saja**.

**TIER 1 — SESUAI TUGAS:** `03_DATA_MODEL.md` (hanya koleksi yang disentuh), `04_API_CONTRACT.md`, `05_NAVIGATION_MAP.md`, `01_PRD.md`, `design_guidelines.md`.

**TIER 2 — JARANG:** `02_ARCHITECTURE.md` saat keputusan arsitektural besar; `15_POSTMORTEM_AND_MITIGATION.md` (sumber pembelajaran + acuan mitigasi: root cause sistemik, matriks kelas-bug→guardrail, playbook tambah invariant, confidence jujur); `16_DEV_LIFECYCLE_SOP.md` (SOP siklus dev: pre→dev→post, Definition of Ready/Done); `17_BUGHUNT_SOP.md` (SOP bug-hunt adversarial: matriks serangan, template testing_agent, honest-assessment).

**Verifikasi = GATES**, bukan baca ulang prosa.

---

## 🧭 URUTAN ONBOARDING AGENT BARU
1. **`AGENT_START_HERE.md`** (gerbang + boot sequence) → 2. `bash scripts/load_context.sh` + `cat memory/SESSION_HANDOFF.md` → 3. Tier 0 (`07`,`08`,`11`,`13`,`14`) → 4. `09_ROADMAP.md` (fase berjalan) → 5. buka **`PLAYBOOKS.md`** sesuai tugas → 6. tutup dengan `bash scripts/gate.sh` (receipt hijau).

**Versi:** 1.0 · **Maintainer:** Development Team · **Update:** tiap perubahan struktur dokumen.
