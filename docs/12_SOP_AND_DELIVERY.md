# 12 — SOP & DELIVERY STANDARD
## Travel & Fleet Management Ecosystem

> Standar **cara kerja (SOP)** + **definisi pengiriman (Delivery / Definition of Done)**.

---

## 1. SOP DEVELOPMENT WORKFLOW (per fitur/fase)
```
1. PLAN     → baca Tier 0 + fase berjalan (09_ROADMAP). Pastikan koleksi/endpoint belum ada (Gate A).
2. CONTRACT → daftarkan koleksi/skema baru di 03_DATA_MODEL + verify_contract; tentukan posisi nav (05).
3. BUILD    → backend (router thin + service) lalu frontend (shadcn + states + testid). Hormati 07 & 08.
4. SEED     → seed_data.py mengikuti KONTRAK API (bukan sebaliknya).
5. GATE     → jalankan semua gate (§3). Perbaiki FAIL.
6. TEST     → testing_agent_v3 untuk perubahan signifikan; fix semua bug high/medium.
7. DOC      → update CODEBASE_MAP, NAVIGATION_MAP, DATA_MODEL, PRD, SESSION_LOG, plan.md.
8. DELIVER  → finish dengan ringkasan jujur (sebut MOCKED/limitasi bila ada).
```

---

## 2. PERINTAH GATE (jalankan dari `/app`)
```bash
bash scripts/load_context.sh             # snapshot kondisi sistem (awal sesi)
bash scripts/seed_reset.sh               # seed bersih + [GATE] contract+api_contract+integrity
python scripts/health_check.py           # ISI endpoint kritis
python scripts/audit_endpoint_sweep.py   # sweep semua GET /api → 5xx
python scripts/ux_audit.py --strict      # baseline UX (file disentuh wajib 0 ERROR)
python scripts/verify_api_contract.py    # FE↔BE (duplicate route, ghost endpoint, field drift)
python scripts/validate_compliance.py    # file-size, naming, docs, /api prefix, env, testid
python scripts/check_nav_map.py          # navigasi vs map (bila menyentuh nav)
```

---

## 3. DELIVERY STANDARD — DEFINITION OF DONE

### Per-perubahan
- [ ] Gate A–C hijau (atau FAIL dicatat sebagai keputusan owner).
- [ ] 0 endpoint 5xx baru; invarian valid di seed bersih.
- [ ] FE = 100% fitur BE (tidak ada endpoint yatim, tidak ada fitur BE tanpa UI).
- [ ] `data-testid` lengkap; loading/empty/error ada; `tabular-nums` untuk angka.
- [ ] Linter bersih; tidak ada `console.log`/`print` debug; tidak ada TODO/FIXME baru.
- [ ] Dokumen SSOT diupdate.

### Per-fase (exit criteria)
- [ ] Semua user story fase terpenuhi & terverifikasi.
- [ ] `testing_agent_v3` dijalankan; laporan dibaca; semua bug high/medium difix.
- [ ] Screenshot preview menunjukkan UI benar (loading/empty/error, angka rapi).
- [ ] `09_ROADMAP.md` & `plan.md` fase ditandai COMPLETED; `SESSION_HANDOFF.md` diisi.

---

## 4. SEVERITY & RESPONS
| Level | Definisi | Respons |
|-------|----------|---------|
| **P0** | Core rusak (login/booking/peta down) | Hentikan fitur lain, fix minimal, verifikasi core, RCA |
| **P1** | Fitur penting rusak, ada workaround | Bugfix + test komprehensif |
| **P2** | Bug minor, UX terganggu tapi fungsional | Bugfix standar |
| **P3** | Enhancement / nice-to-have | Masuk backlog `01_PRD.md` |

---

## 5. PEMICU UPDATE DOKUMEN
| Dokumen | Update saat |
|---------|-------------|
| `01_PRD.md` | Fitur selesai / backlog berubah |
| `03_DATA_MODEL.md` | Koleksi/field/invarian baru |
| `05_NAVIGATION_MAP.md` | Menu/halaman baru |
| `10_CODEBASE_MAP.md` | File/endpoint/komponen baru |
| `SESSION_LOG.md` | Akhir tiap sesi |
| `plan.md` / `09_ROADMAP.md` | Status task / fase berubah |

---

## 6. KONVENSI COMMIT (ringan, opsional bila pakai git)
```
feat: tambah modul booking calendar
fix: koreksi derivasi payment_status (RC-17)
refactor: pecah server.py → routers/bookings.py
docs: update DATA_MODEL untuk koleksi trips
test: invariant anti double-booking
```

---

## 7. PENAMAAN GENERIK (WAJIB)
Kode TIDAK memuat nama brand. Koleksi/endpoint/komponen pakai istilah domain umum:
`vehicles, drivers, customers, leads, bookings, trips, locations, payments, expenses, invoices, conversations, messages, notification_tasks, broadcasts, maintenance_records, destinations, articles, testimonials, users, sessions, settings, audit_logs`.
