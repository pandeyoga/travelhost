# GUARDRAILS — Executable Gate Suite
## Travel & Fleet Management Ecosystem

Kumpulan **guardrail yang bisa GAGAL** (exit ≠ 0) untuk mencegah bug data, drift FE↔BE,
5xx, dan utang UX. Baca dulu: `docs/07_ENGINEERING_GUARDRAILS.md`, `docs/08_FRONTEND_GUARDRAILS.md`,
`docs/06_UIUX_STANDARDS.md`.

## Urutan pemakaian (sebelum `finish`)
```bash
cd /app
# CARA TERMUDAH (orkestrator tunggal) \u2014 jalankan SEMUA gate + tulis receipt:
bash scripts/gate.sh                      # \u2192 memory/GATE_RECEIPT.md (WAJIB hijau)

# Sebelum membangun fitur (anti-duplikasi/asumsi):
python scripts/preflight.py "<kata-kunci>"

# Manual (bila perlu granular):
bash scripts/load_context.sh             # snapshot kondisi (awal sesi)
bash scripts/seed_reset.sh               # seed bersih + [GATE] contract+api_contract+integrity
python scripts/verify_schema.py          # field-level + FK + id-prefix
python scripts/health_check.py           # ISI endpoint kritis (bukan cuma 200)
python scripts/audit_endpoint_sweep.py   # sweep SEMUA GET /api \u2192 5xx
python scripts/mutation_smoke.py         # alur TULIS (create\u2192bayar\u2192status, anti double-booking)
python scripts/verify_architecture.py    # performa/tech-debt (pagination, N+1, unbounded)
python scripts/verify_delivery.py        # anti under-deliver (manifest + orphan endpoint)
python scripts/ux_audit.py --strict      # baseline UX
python scripts/validate_compliance.py    # file-size, naming, docs, /api, env, testid
```

## Daftar script
| Script | Fungsi | Exit≠0 saat |
|--------|--------|------------|
| `gate.sh` | **ORKESTRATOR**: jalankan semua gate berurutan + tulis `memory/GATE_RECEIPT.md` | ada gate (non-skip) gagal |
| `preflight.py` | **ANTI-DUPLIKASI**: cek koleksi/endpoint/komponen sudah ada + nama kanonik | (alat bantu, selalu 0) |
| `load_context.sh` | Snapshot service/env/DB/file-size/compliance + handoff | (laporan) |
| `seed_reset.sh` | Seed bersih + jalankan [GATE] contract+api_contract+integrity | seed/gate gagal |
| `seed_data.py` | Isi DB dengan akun demo + data minimal realistis | error seed |
| `verify_contract.py` | Nama koleksi kanonik vs terlarang (`db.x` & `db["x"]`) | ada koleksi terlarang |
| `verify_schema.py` | **Field-level + FK referential integrity + id-prefix** (DB clean-seed) | FK menggantung / prefix salah / tipe salah |
| `verify_api_contract.py` | Duplicate route + FE call→route exist + FE field ⊆ BE response | drift FE↔BE |
| `verify_data_integrity.py` | Invarian domain (double-booking, payment_status, profit, lokasi, lead stage) | invarian dilanggar |
| `verify_architecture.py` | **Performa/tech-debt**: unbounded query, pagination, N+1, kebocoran field | `--strict` & ada ERROR |
| `verify_delivery.py` | **ANTI UNDER-DELIVER**: manifest completeness (P0) + orphan endpoint (BE tanpa FE) | P0 kurang / ada orphan |
| `health_check.py` | Login + sweep endpoint kritis, cek jumlah item | ada FAIL/5xx |
| `audit_endpoint_sweep.py` | Hit SEMUA GET /api (resolve path param) → 5xx | ada 5xx |
| `mutation_smoke.py` | **Alur TULIS**: create→bayar→status + uji anti double-booking | 5xx / invarian rusak pasca-tulis |
| `ux_audit.py` | Baseline UX (loading/empty/chart/tabular-nums/testid) | `--strict` & ada ERROR |
| `validate_compliance.py` | file-size, debug print, duplicate endpoint, forbidden collection, hardcode, testid, docs, /api, env | pelanggaran kritis |
| `check_nav_map.py` | Navigasi vs 05_NAVIGATION_MAP.md | inkonsistensi |

## Aturan emas
1. Verifikasi di **DB bersih** (`seed_reset`) — DB kotor menutupi drift.
2. "200 / running" **bukan** bukti benar — cek **nilai** & **invarian**.
3. Tambah fitur ⇒ tambah Concept/endpoint/koleksi ke gate terkait (lihat `docs/07` §7).
4. Jangan klaim hijau palsu (RC-10). FAIL disengaja = catat sebagai keputusan owner.

## Variabel lingkungan
- `MONGO_URL`, `DB_NAME` → dari `backend/.env` (auto via `load_dotenv`).
- `API_BASE` (default `http://localhost:8001`), `ADMIN_EMAIL`, `ADMIN_PASS` bisa di-override.

---

## Kebersihan data uji (INV-CLEAN-01 — BUG-0127)

Penjaga & smoke test SENGAJA menulis lewat API sungguhan supaya perilaku server benar-benar
teruji. Konsekuensinya mereka WAJIB membersihkan jejaknya **beserta side-effect** (percakapan
Inbox, notifikasi, event, automation_runs, entri audit, bukti bayar + asetnya, outbox konversi).
Mesin bersih-bersihnya terpusat di `scripts/guardrails/_common.py`:

| Fungsi / berkas | Peran |
|---|---|
| `_common.GUARD_MARKERS` · `GUARD_PHONE_PREFIXES` | **SSOT konvensi identitas data uji.** Nama dokumen uji WAJIB berawalan salah satu penanda (mis. `Penjaga INV-…`), nomor kontak WAJIB `0800000xxx` (guardrail) atau `0810000000` (smoke). |
| `_common.purge_guard_artifacts(verbose=, extra_markers=, extra_phones=, extra_ids=)` | Hapus artefak uji + cascade penuh. Panggil di blok `finally`. Idempotent, tak pernah raise. Dokumen bersumber `seed` DIKECUALIKAN. |
| `_common.scan_test_pollution(...)` | Deteksi tanpa menghapus (dipakai penjaga). |
| `scripts/guardrails/verify_no_test_pollution.py` | **Penjaga INV-CLEAN-01.** Statik: tiap skrip penulis wajib memanggil mesin purge + `services/audit.py` wajib punya `_clip`. Runtime: 40 koleksi operasional wajib 0 artefak. Dijalankan PALING AKHIR di `gate.sh`. |
| `scripts/guardrails/selftest_no_test_pollution.py` | 5 mutasi MERAH↔HIJAU (bukti penjaga menggigit). |
| `scripts/purge_test_pollution.py` | **Alat perbaikan manual.** `--dry-run` untuk melihat saja. Aman: data demo tetap utuh. |
| `scripts/db_snapshot.py` | `--save <nama>` lalu `--diff <nama>` — bukti bahwa data uji tidak menumpuk. Drift `sessions` & audit `login` sesudah gate itu WAJAR (penjaga memang login). |

**Kalau Anda menambah skrip yang menulis data uji:** daftarkan di `WRITERS` pada
`verify_no_test_pollution.py`, pakai penanda dari `GUARD_MARKERS`, dan panggil
`purge_guard_artifacts()` di `finally`. Tanpa itu gate langsung MERAH.

⚠️ **MEMBATALKAN booking BUKAN membersihkan** — booking sengaja tidak punya endpoint DELETE
(catatan keuangan), jadi pesanan uji yang hanya di-`cancel` tetap terlihat pengguna. Hapus lewat
mesin purge.
