#!/usr/bin/env python3
"""selftest_theme_contrast.py — SELF-TEST MUTASI untuk INV-THEME-01.

Penjaga statik mudah "terasa ada" padahal regexnya tidak pernah cocok dengan kode nyata.
Skrip ini menyuntikkan tiap kelas bug yang benar-benar pernah terjadi (satu per satu),
menuntut penjaga MERAH, lalu mengembalikan berkasnya dan menuntut HIJAU kembali.

Jalankan: cd /app && python scripts/guardrails/selftest_theme_contrast.py
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))
from _common import FRONTEND, ROOT, G, R, C, B, X  # noqa: E402

GUARD_DIR = ROOT / "scripts" / "guardrails"
SRC = FRONTEND / "src"

# Dibaca meta-penjaga INV-META-01: klaim "sudah di-self-test" tidak boleh tanpa bukti.
COVERS = ["verify_theme_contrast.py"]

GUARD = "verify_theme_contrast.py"

# (kode, berkas, teks_asli, teks_mutasi, dampak yang dicegah)
MUTATIONS = [
    ("T01", SRC / "features" / "public" / "BlogDetail.jsx",
     '        <Reveal className="mt-10">',
     '        <Reveal className="mt-10 bg-gradient-to-br from-primary to-[color:var(--primary)]">',
     "gradient memakai token triplet → background dibuang browser, teks putih di kertas putih"),
    ("T02", SRC / "index.css",
     'hsla(var(--glass-bg-strong, 210 30% 99% / 0.94)) 100%) !important;',
     'hsla(0 0% 100% / 0.94) 100%) !important;',
     "dialog dipaku putih untuk semua mode → teks putih hilang di mode gelap"),
    ("T03", SRC / "context" / "ThemeContext.js",
     'root.setAttribute("data-surface", "public");',
     '// root.setAttribute("data-surface", "public");',
     "konten Radix yang di-portal tidak mewarisi tema → dialog/dropdown terang di situs gelap"),
    ("T04", SRC / "styles" / "public-themes.css",
     '[data-surface="public"][data-theme="azure"].dark {',
     '[data-surface="public"][data-theme="azure"]:not(*).dark {',
     "blok gelap preset tidak cocok untuk <html> → mode gelap memakai palet terang"),
    ("T05", SRC / "components" / "public" / "ChatWidget.jsx",
     'className="fixed right-4 flex h-12 w-12 items-center justify-center rounded-full',
     'className="fixed bottom-24 right-4 flex h-12 w-12 items-center justify-center rounded-full',
     "offset chat kembali hardcode → panel menembus header pada viewport pendek"),
    ("T06", SRC / "index.css",
     '  --refraction-opacity: 0.22;\n  --refraction-blend: soft-light;',
     '  --surface-on-hero: var(--card) / 0.93;\n  --refraction-opacity: 0.22;'
     '\n  --refraction-blend: soft-light;',
     "komposisi token tema di :root → nilainya tidak ikut mode gelap (kartu terang, teks putih)"),
    ("T07", SRC / "index.css",
     '    mix-blend-mode: var(--refraction-blend);',
     '    mix-blend-mode: screen;',
     "refraksi `screen` kembali menyapu label/placeholder di atas foto terang"),
]


def run_guard():
    proc = subprocess.run([sys.executable, str(GUARD_DIR / GUARD)],
                          capture_output=True, text=True, cwd=str(ROOT))
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def main() -> int:
    print(f"\n{C}{B}SELF-TEST MUTASI — penjaga kontras & pewarisan tema (INV-THEME-01){X}")
    failures = []

    rc0, _ = run_guard()
    if rc0 != 0:
        print(f"  {R}✗{X} penjaga sudah MERAH sebelum mutasi — perbaiki pelanggaran nyata dulu.")
        return 1

    for code, path, original, mutated, impact in MUTATIONS:
        if not path.exists():
            failures.append(f"{code}: berkas {path.name} tidak ada — self-test usang.")
            print(f"  {R}✗{X} {code} berkas hilang: {path.name}")
            continue
        src = path.read_text()
        if original not in src:
            failures.append(f"{code}: jangkar mutasi tak ditemukan di {path.name} — self-test "
                            f"usang (kode berubah, mutasi harus diperbarui).")
            print(f"  {R}✗{X} {code} jangkar hilang di {path.name}")
            continue
        path.write_text(src.replace(original, mutated, 1))
        rc, out = run_guard()
        path.write_text(src)
        if rc == 0:
            failures.append(f"{code}: penjaga tetap HIJAU padahal bug disuntikkan → {impact}.")
            print(f"  {R}✗{X} {code} LOLOS penjaga (perlindungan bocor): {impact}")
        else:
            print(f"  {G}✓{X} {code} {impact} — MERAH sesuai harapan")
        rc_back, _ = run_guard()
        if rc_back != 0:
            failures.append(f"{code}: setelah revert penjaga masih MERAH — berkas tidak pulih.")
            print(f"  {R}✗{X} {code} tidak pulih setelah revert")

    if failures:
        print(f"\n{R}{B}[FAIL]{X} {len(failures)} masalah pada pembuktian penjaga:")
        for f in failures:
            print(f"  {R}✗{X} {f}")
        return 1
    print(f"\n{G}{B}[PASS]{X} {len(MUTATIONS)} mutasi: penjaga MERAH saat bug disuntikkan dan "
          f"HIJAU kembali setelah revert.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
