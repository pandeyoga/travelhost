#!/usr/bin/env python3
"""selftest_booking_guards.py — SELF-TEST MUTASI untuk INV-PRICE-01 / INV-BOOK-02 / INV-STR-01.

Kenapa file ini ada: penjaga yang tak pernah terbukti MENGGIGIT tak bisa dibedakan dari
`return 0`. Skrip ini menyuntikkan bug NYATA satu per satu (mutasi), menjalankan penjaga yang
bersangkutan, dan menuntut penjaga itu **MERAH**; lalu kode dikembalikan dan penjaga wajib
**HIJAU** lagi. Kalau ada mutasi yang lolos (penjaga tetap hijau), file ini MERAH — artinya
perlindungan itu bocor.

Jalankan: cd /app && python scripts/guardrails/selftest_booking_guards.py
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))
from _common import BACKEND, ROOT, G, R, Y, C, B, X, purge_guard_artifacts  # noqa: E402

GUARD_DIR = ROOT / "scripts" / "guardrails"

# Penjaga yang dibuktikan file ini (dibaca meta-penjaga INV-META-01 supaya klaim "sudah
# di-self-test" tidak bisa dipalsukan: tiap berkas di bawah WAJIB ada + ter-wire di gate.sh,
# dan WAJIB punya minimal satu mutasi di MUTATIONS).
COVERS = [
    "verify_pricing_integrity.py",
    "verify_booking_public.py",
    "verify_string_bounds.py",
]

# (kode, penjaga, file, teks_asli, teks_mutasi, dampak yang dicegah)
MUTATIONS = [
    ("P01", "verify_pricing_integrity.py", BACKEND / "services" / "pricing.py",
     '        core = int(round(rate * days))',
     '        core = int(round(rate * days)) + int(_num(rules.get("fuel_per_km")) * _num(distance_km))',
     "komponen BBM×jarak kembali ke harga → pengunjung menentukan harganya sendiri"),
    ("P02", "verify_pricing_integrity.py", BACKEND / "services" / "booking_search.py",
     '        dp_percent = await get_dp_percent(db)',
     '        dp_percent = int(((await db.settings.find_one({"key": "pricing_defaults"},'
     ' {"_id": 0})) or {}).get("value", {}).get("dp_percent") or 30)',
     "DP dibaca dari dokumen settings kedua → DP web ≠ DP tagihan ops"),
    ("B01", "verify_booking_public.py", BACKEND / "schemas_booking.py",
     '    marketing_consent: Optional[bool] = False',
     '    total_amount: Optional[float] = 0\n    marketing_consent: Optional[bool] = False',
     "skema publik menerima total dari klien → pesan Rp 1 lewat curl"),
    ("B02", "verify_booking_public.py", BACKEND / "services" / "booking_public.py",
     '            async with vehicle_lock(db, doc["vehicle_id"]):\n'
     '                await assert_free(db, doc["vehicle_id"], start_iso, end_iso)\n'
     '                await db.bookings.insert_one(dict(doc))',
     '            await assert_free(db, doc["vehicle_id"], start_iso, end_iso)\n'
     '            await db.bookings.insert_one(dict(doc))',
     "penulisan reservasi keluar dari mutex → satu unit bisa dijual dua kali"),
    ("S01", "verify_string_bounds.py", BACKEND / "schemas.py",
     '    name: str = Field(min_length=1, max_length=120)\n    phone: Optional[str] ='
     ' Field(default="", max_length=24)\n    email: Optional[str] = Field(default="",'
     ' max_length=160)\n    type: Optional[str] = Field(default="individual", max_length=40)',
     '    name: str = Field(min_length=1)\n    phone: Optional[str] = ""\n'
     '    email: Optional[str] = ""\n    type: Optional[str] = "individual"',
     "field teks customer tanpa batas → nama 60.000 karakter tersimpan & merusak tabel/PDF/WA"),
]


def run_guard(script: str):
    proc = subprocess.run([sys.executable, str(GUARD_DIR / script)],
                          capture_output=True, text=True, cwd=str(ROOT))
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def wait_backend_reload():
    """Uvicorn --reload butuh sesaat setelah file backend berubah."""
    subprocess.run(["sleep", "6"], check=False)


def main() -> int:
    print(f"\n{C}{B}SELF-TEST MUTASI — penjaga pemesanan online (INV-PRICE-01/INV-BOOK-02/"
          f"INV-STR-01){X}")
    failures = []
    exercised = {script for _, script, *_ in MUTATIONS}
    for claimed in COVERS:
        if claimed not in exercised:
            failures.append(f"{claimed}: diklaim di COVERS tetapi TIDAK punya mutasi — klaim "
                            f"'sudah di-self-test' tanpa bukti.")
            print(f"  {R}✗{X} {claimed} diklaim tanpa mutasi")
    for code, script, path, original, mutated, impact in MUTATIONS:
        src = path.read_text()
        if original not in src:
            failures.append(f"{code}: jangkar mutasi tak ditemukan di {path.name} — self-test "
                            f"usang (kode berubah, mutasi harus diperbarui).")
            print(f"  {R}✗{X} {code} jangkar hilang di {path.name}")
            continue
        path.write_text(src.replace(original, mutated, 1))
        wait_backend_reload()
        rc, out = run_guard(script)
        path.write_text(src)
        wait_backend_reload()
        if rc == 0:
            failures.append(f"{code}: mutasi LOLOS — {script} tetap HIJAU padahal {impact}.")
            print(f"  {R}✗{X} {code} {impact} — penjaga TIDAK menggigit")
        else:
            print(f"  {G}✓{X} {code} {impact} — MERAH sesuai harapan")
        rc2, _ = run_guard(script)
        if rc2 != 0:
            failures.append(f"{code}: setelah revert, {script} MASIH merah — kode tidak "
                            f"kembali bersih (periksa manual!).")
            print(f"  {R}✗{X} {code} revert tidak bersih")
    # INV-CLEAN-01 — WAJIB: saat mutasi aktif, penjaga sengaja BERHASIL menulis data buruk
    # (mis. S01 melepas `max_length` → customer bernama 60.000 karakter TERSIMPAN). Dokumen itu
    # dulu tak pernah dihapus sehingga muncul di ERP pengguna sebagai "AAAAAA…" (BUG-0127).
    left = purge_guard_artifacts()
    if left:
        print(f"  {G}✓{X} bersih-bersih pasca-mutasi: {left} dokumen artefak uji dihapus")
    print()
    if failures:
        print(f"{R}{B}[FAIL]{X} {len(failures)} masalah self-test:")
        for f in failures:
            print(f"  {R}✗{X} {f}")
        print(f"{Y}→ Penjaga wajib MERAH pada tiap mutasi; kalau tidak, perlindungan bocor.{X}")
        return 1
    print(f"{G}{B}[PASS]{X} {len(MUTATIONS)} mutasi: semua penjaga MERAH saat bug disuntikkan "
          f"dan HIJAU kembali setelah revert.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
