#!/usr/bin/env python3
"""
ux_audit.py — UX Baseline Enforcer
==================================
Mengubah docs/06_UIUX_STANDARDS.md jadi cek EXECUTABLE. Scan frontend/src/features
+ components (kecuali components/ui = shadcn primitives).

  E1  Tabel data tanpa LOADING state            (ERROR)
  E2  Tabel data tanpa EMPTY state              (ERROR)
  E3  Chart (recharts) tanpa EMPTY-state guard  (ERROR)
  E4  <ResponsiveContainer> tanpa initialDimension (ERROR)
      -> mencegah kembalinya warning konsol recharts "width(-1) and height(-1) of chart
         should be greater than 0" saat chart dirender di parent yang belum terukur
         (mis. di dalam tab non-aktif). Baseline P1 sesi E28: 0 warning terbukti bersih.
  W1  Uang tanpa `tabular-nums`                  (WARN)
  W2  Native <select>                            (WARN)
  W3  >=3 tombol tanpa data-testid               (WARN)
  W4  Chart tanpa <Tooltip>                       (WARN)

Usage:
  python scripts/ux_audit.py            # ringkasan (exit 0)
  python scripts/ux_audit.py --strict   # exit 1 bila ada ERROR (gate)
  python scripts/ux_audit.py --file features/app/Bookings.jsx
"""
import argparse, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "frontend" / "src"
SCAN_DIRS = [SRC / "features", SRC / "components"]
G, Y, R, C, B, X = "\033[92m", "\033[93m", "\033[91m", "\033[96m", "\033[1m", "\033[0m"
FORM_HINTS = ("Form", "Modal", "Dialog", "Drawer", "Editor", "Create", "Edit",
              "Wizard", "Panel", "Uploader", "Field", "Input", "Login", "Hero", "Nav", "Footer")


def rel(p):
    return str(p.relative_to(SRC))


def analyze(path):
    t = path.read_text(encoding="utf-8", errors="ignore")
    findings = []
    is_form = any(h in path.name for h in FORM_HINTS)
    renders_rows = bool(re.search(r'<table', t) or re.search(r'\.map\(\s*\(?\w+', t))
    has_table = bool(re.search(r'<table|<tbody|role=["\']table', t)) or (
        renders_rows and re.search(r'<tr|<td|grid|divide-y', t))
    has_loading = bool(re.search(r'loading|isLoading|Skeleton|Spinner|Loader|animate-pulse', t, re.I))
    has_empty = bool(re.search(r'length\s*===?\s*0|length\s*<\s*1|!\w+\.length|'
                               r'No\s|Belum ada|Tidak ada|Kosong|empty|Empty', t))
    if has_table and not is_form:
        if not has_loading:
            findings.append(("ERROR", "E1", "Tabel/list data tanpa LOADING state"))
        if not has_empty:
            findings.append(("ERROR", "E2", "Tabel/list data tanpa EMPTY state"))
    if re.search(r'from\s+["\']recharts["\']|<(Line|Area|Pie|Radar)Chart\b|<BarChart[\s>]', t):
        if not has_empty:
            findings.append(("ERROR", "E3", "Chart tanpa EMPTY-state guard"))
        if 'Tooltip' not in t:
            findings.append(("WARN", "W4", "Chart tanpa <Tooltip>"))
    n_rc = len(re.findall(r'<ResponsiveContainer\b', t))
    if n_rc:
        n_init = len(re.findall(r'initialDimension', t))
        if n_init < n_rc:
            findings.append(("ERROR", "E4", f"{n_rc - n_init} <ResponsiveContainer> tanpa "
                                            "initialDimension (picu warning recharts width/height -1)"))
    if re.search(r'formatCurrency|Rp\s|currency', t) and 'tabular-nums' not in t:
        findings.append(("WARN", "W1", "Tampilan uang tanpa class `tabular-nums`"))
    # W2 dinilai pada KODE saja: baris komentar (// ... atau * ...) dikecualikan supaya
    # dokumentasi yang menyebut elemen native tidak menghasilkan temuan palsu.
    code_only = "\n".join(ln for ln in t.splitlines() if not re.match(r'\s*(//|/\*|\*)', ln))
    if re.search(r'<select[\s>]', code_only):
        findings.append(("WARN", "W2", "Native <select> — gunakan Select (shadcn)"))
    n_btn = len(re.findall(r'<(button|Button)\b', t))
    n_testid = len(re.findall(r'data-testid', t))
    if n_btn >= 3 and n_testid == 0:
        findings.append(("WARN", "W3", f"{n_btn} tombol, 0 data-testid"))
    return findings


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--file")
    args = ap.parse_args()
    if not SRC.exists():
        print(f"{Y}frontend/src belum ada — skip UX audit (Phase 0).{X}")
        return 0
    files = []
    if args.file:
        files = [SRC / args.file]
    else:
        for d in SCAN_DIRS:
            if d.exists():
                for f in d.rglob("*.jsx"):
                    if "/ui/" in str(f).replace("\\", "/"):
                        continue
                    files.append(f)
                for f in d.rglob("*.js"):
                    if "/ui/" in str(f).replace("\\", "/"):
                        continue
                    files.append(f)
    files = sorted(set(files))
    total_err = total_warn = 0
    err_files = []
    print(f"\n{B}{C}UX BASELINE AUDIT ({len(files)} file){X}\n")
    for f in files:
        fnd = analyze(f)
        if not fnd:
            continue
        errs = [x for x in fnd if x[0] == "ERROR"]
        warns = [x for x in fnd if x[0] == "WARN"]
        total_err += len(errs); total_warn += len(warns)
        if errs:
            err_files.append(rel(f))
        head = f"{R}●{X}" if errs else f"{Y}○{X}"
        print(f"{head} {B}{rel(f)}{X}")
        for sev, code, msg in fnd:
            c = R if sev == "ERROR" else Y
            print(f"    {c}[{sev} {code}]{X} {msg}")
    print(f"\n{B}{'='*60}{X}")
    print(f"  {R}ERROR {total_err}{X}  |  {Y}WARN {total_warn}{X}  (di {len(files)} file)")
    print(f"{B}{'='*60}{X}")
    if total_err:
        print(f"\n  {R}{B}{len(err_files)} file melanggar baseline UX.{X}")
        print("  File lama = backlog; file BARU/disentuh WAJIB lolos.\n")
    else:
        print(f"\n  {G}{B}Tidak ada pelanggaran ERROR baseline UX.{X}\n")
    return 1 if (args.strict and total_err) else 0


if __name__ == "__main__":
    sys.exit(main())
