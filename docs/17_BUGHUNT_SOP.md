# 17 — BUG-HUNT SOP (Mekanisme Perburuan Bug — Berulang & Bisa Ditingkatkan)

> **Rahaza Travel ERP.** Mengubah perburuan bug dari "vibe" (respons *"everything is fine"* padahal
> tidak) menjadi **prosedur adversarial yang WAJIB diikuti**, berulang, dan makin tajam seiring waktu.
> Berpasangan: `docs/16_DEV_LIFECYCLE_SOP.md`, `memory/INVARIANTS.md`, `memory/BUG_REGISTRY.md`,
> `docs/15_POSTMORTEM_AND_MITIGATION.md`.
>
> **Versi:** v1 (2026-07-05). **Aturan peningkatan:** tiap kelas bug BARU yang ditemukan → tambah
> ke §2 (matriks serangan) + buat guardrail-nya (INVARIANTS §playbook) → naikkan versi SOP.

---

## §0. Filosofi (WAJIB dipegang)

1. **"200 / aplikasi jalan" BUKAN bukti benar.** Bukti = nilai & invariant terverifikasi.
2. **Sikap adversarial:** tugas hunter adalah **MEMBUKTIKAN ada bug**, bukan membuktikan aman.
   Kirim input terburuk, akses tanpa hak, tekan balapan, langgar state-machine.
3. **Jujur > enak didengar.** Dilarang bilang "aman" tanpa bukti. Nyatakan cakupan yang DIUJI vs
   yang TIDAK, + confidence yang jujur (lihat §5).
4. **Temuan → dijadikan penjaga.** Tiap bug yang ditemukan WAJIB jadi guardrail agar tak kambuh.

---

## §1. Prosedur baku (7 langkah, berulang)

```
1. MAP     — petakan permukaan: endpoint (/openapi.json), peran (owner/ops/driver),
              state-machine, koleksi, jalur reservasi/uang.
2. AUTOMATE— jalankan `bash scripts/run_forensics.sh` (gate + probe adversarial).
3. HUNT    — jalankan testing_agent dgn MATRIKS SERANGAN §2 (template §3).
4. TRIAGE  — pisahkan bug NYATA vs isu-harness; beri severity; catat di BUG_REGISTRY (§4).
5. FIX     — perbaiki akar (bukan gejala) → buat/perkuat guardrail → SELF-TEST (MERAH↔HIJAU).
6. RE-GATE — `bash scripts/gate.sh` HIJAU + testing_agent verifikasi ulang fix.
7. ASSESS  — tulis Honest Assessment (§5): cakupan, sisa risiko, confidence.
```

---

## §2. Matriks Serangan (kelas bug yang WAJIB dicoba)

| # | Kelas serangan | Cara uji | Ekspektasi benar | Invariant terkait |
|---|---|---|---|---|
| A | **Auth bypass** | akses endpoint tanpa token | 401/403, bukan 200 | INV-AUTH-01 |
| B | **RBAC/IDOR** | peran rendah (driver) ke modul manajemen; akses data milik entitas lain | 401/403 | INV-RBAC, fa_rbac_matrix |
| C | **5xx adversarial** | body kosong/tipe-salah/markup/negatif/raksasa/operator-Mongo | 4xx, **tak pernah 5xx** | INV-5XX-01, fa_5xx_fuzz |
| D | **Boundary/numeric** | nilai negatif, 0, sangat besar, non-numerik pd field angka | 4xx / clamp; tak ada nilai absurd | INV-NUM-01, INV-SET-01 |
| E | **Race/TOCTOU** | N request paralel: double-book, dedupe identity, double-submit | tepat 1 sukses; sisanya 409 | INV-RACE-01, INV-IDENT-01 |
| F | **State-machine** | transisi ilegal (mis. complete sebelum confirm) | 4xx (ditolak) | verify_state_machine |
| G | **Idempotency** | ulang operasi berkunci (payment/booking) dgn key sama | tak ada efek ganda | verify_concurrency |
| H | **Cross-entity** | konsistensi lintas entitas (invoice↔booking, stok, saldo) | konsisten | verify_cross_entity |
| I | **Injection/markup** | `<script>`, `& < >`, `${}`, `$where`, unicode | ter-escape, aman | INV-5XX-01, EXPORT-1 |
| J | **Empty/oversized** | payload kosong, string sangat panjang, list bukan-list | 4xx tervalidasi | fa_5xx_fuzz |
| K | **Pagination/query** | limit negatif/raksasa, offset absurd, sort tak dikenal | aman/ter-clamp | (tambah bila perlu) |
| L | **Deploy/secret** | rahasia/URL hardcoded, env tak dipakai | tak ada | INV-QUALITY-01 |

> Kelas baru ditemukan? Tambahkan baris di sini + buat guardrailnya.

---

## §3. Template tugas testing_agent (salin & isi)

```
original_problem_statement: <konteks + kredensial demo owner/ops/driver @demo.local:demo12345, prefix /api>
features_or_bugs_to_test:
  - [Auth] endpoint X tanpa token -> 401/403 (bukan 200)
  - [RBAC] driver ke GET /api/<manajemen> -> 403 ; owner -> 200
  - [5xx] POST /api/<...> body {markup/negatif/tipe-salah} -> 4xx (BUKAN 500)
  - [Race] 8x paralel POST /api/<...> identik -> tepat 1 sukses, sisanya 409
  - [State] transisi ilegal -> 4xx
  - [Regresi] jalur normal happy-path tetap 2xx
testing_type: backend only (atau both bila FE berubah)
agent_to_agent_context_note: fokus STATUS CODE (no 5xx) + semantik 4xx/409 + happy-path.
  Jangan ubah kode produksi. Lewati drag/drop/upload/voice/camera.
mocked_api: WhatsApp = MOCK by design.
```

---

## §4. Format entri BUG_REGISTRY (tiap temuan)

```
### <ID> — <judul singkat> — <FIXED/OPEN> <tanggal>
- Gejala        : apa yang salah (status/perilaku)
- Root Cause    : akar (bukan gejala)
- Gate penangkap: guardrail/probe mana yang (kini) menangkap
- Perbaikan     : ringkas fix + file
- Regression    : bukti self-test guardrail (MERAH↔HIJAU)
- Status        : FIXED (bukti: gate + testing_agent iter-N)
```

---

## §5. Honest Assessment (WAJIB di akhir hunt — anti "everything is fine")

Jawab jujur, jangan dilebih-lebihkan:
- **Yang DIUJI:** modul/endpoint/kelas-serangan mana yang benar-benar dicoba.
- **Yang TIDAK diuji:** permukaan yang belum tersentuh (sebut eksplisit).
- **Temuan:** daftar bug + severity; berapa sudah ditutup + dijaga.
- **Confidence (%):** angka + alasan. Ingat: guardrail cegah regresi kelas DIKENAL;
  **tak menjamin nol kelas BARU**.
- **Sisa risiko:** mis. integrasi ber-kredensial (WA real), uji beban tinggi, kelas belum terpikir.

> Contoh kalimat jujur: *"16/16 backend lolos untuk kelas A–L pada modul X–Z; TIDAK menguji beban
> konkuren tinggi & WA real (MOCK). Confidence ~96% — minimum known-bug, BUKAN zero-bug."*

---

## §6. Kapan menjalankan
- **Tiap fitur/bugfix menyentuh API** → minimal langkah 3+6 (testing_agent verifikasi).
- **Audit berkala / sebelum rilis besar** → seluruh 7 langkah + `run_forensics.sh`.
- **Saat curiga** ("kok mencurigakan") → langsung matriks §2 pada area itu.

## §7. Cara meningkatkan SOP ini
1. Temukan kelas bug baru → tambah ke §2.
2. Buat guardrail statik/runtime → wire ke `gate.sh`, daftar di `INVARIANTS.md`, self-test.
3. Bila perlu, tambah probe di `forensic/` + panggil dari `run_forensics.sh`.
4. Naikkan versi SOP + catat perubahan.
