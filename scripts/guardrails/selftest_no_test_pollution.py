#!/usr/bin/env python3
"""selftest_no_test_pollution.py — SELF-TEST MUTASI untuk INV-CLEAN-01.

Penjaga yang tak pernah terbukti MENGGIGIT tak bisa dibedakan dari `return 0`. Skrip ini
menyuntikkan pelanggaran NYATA satu per satu, menuntut penjaga **MERAH**, lalu memulihkan
keadaan dan menuntut penjaga **HIJAU** lagi.

Mutasi yang diuji:
  M1 (runtime) — sisipkan customer bernama 60.000 karakter "A" ke database, seperti yang
                 dulu ditinggalkan self-test mutasi INV-STR-01 → penjaga wajib MERAH.
  M2 (runtime) — sisipkan percakapan Inbox "Penjaga INV-BOOK-02" + pesannya → wajib MERAH.
  M3 (runtime) — sisipkan baris audit ber-`summary` 60.016 karakter → wajib MERAH.
  M4 (statik)  — lepas panggilan bersih-bersih dari `verify_string_bounds.py` → wajib MERAH
                 (mencegah seseorang menghapus purge dan gate tetap hijau).
  M5 (statik)  — lepas pemotong `_clip` dari `services/audit.py` → wajib MERAH.

Jalankan: cd /app && python scripts/guardrails/selftest_no_test_pollution.py
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))
from _common import BACKEND, ROOT, mongo_db, G, R, Y, C, B, X  # noqa: E402

GUARD_DIR = ROOT / "scripts" / "guardrails"
GUARD = "verify_no_test_pollution.py"

# Dibaca meta-penjaga INV-META-01: penjaga yang diklaim diuji berkas ini.
COVERS = ["verify_no_test_pollution.py"]

BIG = "A" * 60000


def run_guard():
    proc = subprocess.run([sys.executable, str(GUARD_DIR / GUARD)],
                          capture_output=True, text=True, cwd=str(ROOT))
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def expect(failures, code, desc, mutate, restore):
    """mutate() → penjaga wajib MERAH; restore() → penjaga wajib HIJAU."""
    mutate()
    rc, _out = run_guard()
    restore()
    if rc == 0:
        failures.append(f"{code}: mutasi LOLOS — penjaga tetap HIJAU padahal {desc}.")
        print(f"  {R}\u2717{X} {code} {desc} — penjaga TIDAK menggigit")
    else:
        print(f"  {G}\u2713{X} {code} {desc} — MERAH sesuai harapan")
    rc2, out2 = run_guard()
    if rc2 != 0:
        failures.append(f"{code}: sesudah dipulihkan penjaga MASIH merah — keadaan tidak "
                        f"kembali bersih (periksa manual!). Cuplikan: {out2[-300:]}")
        print(f"  {R}\u2717{X} {code} pemulihan tidak bersih")


def main() -> int:
    print(f"\n{C}{B}SELF-TEST MUTASI — INV-CLEAN-01 (data uji tak boleh bocor ke ERP){X}")
    failures = []
    db, client = mongo_db()
    if db is None:
        print(f"{R}{B}[FAIL]{X} tidak bisa terhubung ke MongoDB — self-test WAJIB jalan "
              f"(SKIP != PASS).")
        return 1

    rc0, out0 = run_guard()
    if rc0 != 0:
        print(f"{R}{B}[FAIL]{X} baseline sudah MERAH sebelum mutasi — bersihkan dulu "
              f"(`python scripts/purge_test_pollution.py`). Cuplikan:\n{out0[-800:]}")
        client.close()
        return 1
    print(f"  {G}\u2713{X} baseline HIJAU (database bersih sebelum mutasi)")

    try:
        # M1 — customer teks raksasa (persis artefak yang dikeluhkan pengguna).
        expect(failures, "M1", "customer bernama 60.000 karakter tertinggal di ERP",
               lambda: db.customers.insert_one(
                   {"id": "cus_selftest_clean01", "name": BIG, "phone": "0899999901",
                    "type": "individual"}),
               lambda: db.customers.delete_many({"id": "cus_selftest_clean01"}))

        # M2 — percakapan Inbox palsu + pesannya.
        def mutate_conv():
            db.conversations.insert_one({"id": "cnv_selftest_clean01",
                                         "contact_name": "Penjaga INV-BOOK-02",
                                         "contact_phone": "0800000202"})
            db.messages.insert_one({"id": "msg_selftest_clean01",
                                    "conversation_id": "cnv_selftest_clean01",
                                    "body": "Halo Penjaga INV-BOOK-02"})

        def restore_conv():
            db.conversations.delete_many({"id": "cnv_selftest_clean01"})
            db.messages.delete_many({"id": "msg_selftest_clean01"})

        expect(failures, "M2", "percakapan Inbox 'Penjaga INV-BOOK-02' tertinggal",
               mutate_conv, restore_conv)

        # M3 — baris audit raksasa.
        expect(failures, "M3", "baris Audit Log ber-summary 60.016 karakter tertinggal",
               lambda: db.audit_logs.insert_one(
                   {"id": "aud_selftest_clean01", "action": "create",
                    "entity_type": "customer", "summary": "Tambah customer " + BIG}),
               lambda: db.audit_logs.delete_many({"id": "aud_selftest_clean01"}))

        # M4 — panggilan bersih-bersih dilepas dari penjaga penulis (statik).
        sb = GUARD_DIR / "verify_string_bounds.py"
        src_sb = sb.read_text()
        anchor_sb = "purge_guard_artifacts"
        if anchor_sb not in src_sb:
            failures.append("M4: jangkar `purge_guard_artifacts` tak ada di "
                            "verify_string_bounds.py — self-test usang.")
            print(f"  {R}\u2717{X} M4 jangkar hilang")
        else:
            expect(failures, "M4", "panggilan bersih-bersih dilepas dari verify_string_bounds",
                   lambda: sb.write_text(src_sb.replace(anchor_sb, "_purge_dimatikan")),
                   lambda: sb.write_text(src_sb))

        # M5 — pemotong panjang summary audit dilepas (statik, sisi produk).
        au = BACKEND / "services" / "audit.py"
        src_au = au.read_text()
        if "_clip" not in src_au:
            failures.append("M5: jangkar `_clip` tak ada di services/audit.py — self-test usang.")
            print(f"  {R}\u2717{X} M5 jangkar hilang")
        else:
            expect(failures, "M5", "pemotong `_clip` dilepas dari services/audit.py",
                   lambda: au.write_text(src_au.replace("_clip", "_tanpa_potong")),
                   lambda: au.write_text(src_au))
    finally:
        client.close()

    print()
    if failures:
        print(f"{R}{B}[FAIL]{X} {len(failures)} masalah self-test:")
        for f in failures:
            print(f"  {R}\u2717{X} {f}")
        print(f"{Y}\u2192 Penjaga wajib MERAH pada tiap mutasi; kalau tidak, perlindungan "
              f"bocor dan data uji akan kembali muncul di ERP pengguna.{X}")
        return 1
    print(f"{G}{B}[PASS]{X} 5 mutasi: penjaga MERAH saat pelanggaran disuntikkan dan HIJAU "
          f"kembali setelah dipulihkan.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
