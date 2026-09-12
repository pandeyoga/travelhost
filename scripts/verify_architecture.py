#!/usr/bin/env python3
"""
verify_architecture.py — PERFORMANCE & TECH-DEBT STATIC GATE
============================================================
Menegakkan docs/13_ARCHITECTURE_BEST_PRACTICES.md secara statis (tanpa runtime):
  A1  Unbounded query: .to_list(None) / .to_list(<angka besar>)            (ERROR)
  A2  List endpoint tanpa pagination (limit/skip/page)                      (WARN)
  A3  Potensi N+1: `await db.` di dalam loop `for/while`                    (WARN)
  A4  Kebocoran field sensitif: kembalikan `password_hash` tanpa strip      (ERROR)
  A5  FE: render `.map` tabel besar tanpa pagination/virtualisasi (heuristik)(WARN)
Skip rapi bila backend/frontend belum ada (Phase 0).
Usage: cd /app && python scripts/verify_architecture.py [--strict]
--strict → exit 1 bila ada ERROR.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ROUTERS = ROOT / "backend" / "routers"
SERVICES = ROOT / "backend" / "services"
FEATURES = ROOT / "frontend" / "src" / "features"
G, Y, R, C, B, X = "\033[92m", "\033[93m", "\033[91m", "\033[96m", "\033[1m", "\033[0m"
err = warn = 0


def rel(p):
    return str(p.relative_to(ROOT))


def e(msg):
    global err
    err += 1
    print(f"  {R}[ERROR]{X} {msg}")


def w(msg):
    global warn
    warn += 1
    print(f"  {Y}[WARN]{X} {msg}")


def scan_backend():
    files = []
    for d in (ROUTERS, SERVICES):
        if d.exists():
            files += [f for f in d.rglob("*.py") if "__pycache__" not in str(f)]
    if not files:
        print(f"{Y}  backend routers/services belum ada — skip cek BE (Phase 0).{X}")
        return
    get_pat = re.compile(r'@router\.get\([\'"]([^\'"]+)[\'"]')
    for f in files:
        txt = f.read_text(errors="ignore")
        lines = txt.splitlines()
        # A1 unbounded
        for i, ln in enumerate(lines, 1):
            if re.search(r"\.to_list\(\s*None\s*\)", ln):
                e(f"{rel(f)}:{i} .to_list(None) — query unbounded (pakai limit).")
            m = re.search(r"\.to_list\(\s*(\d{5,})\s*\)", ln)
            if m and int(m.group(1)) > 5000:
                w(f"{rel(f)}:{i} .to_list({m.group(1)}) — batas sangat besar; pertimbangkan pagination.")
        # A4 sensitive leak (heuristik): 'password_hash' disebut di router tanpa pop/exclude/del/projection 0
        if "password_hash" in txt and not re.search(r"(pop\(['\"]password_hash|del .*password_hash|password_hash['\"]?\s*:\s*0|exclude=)", txt):
            w(f"{rel(f)}: menyebut `password_hash` — pastikan TIDAK ikut terkirim ke FE (strip/projection).")
        # A2 list endpoint tanpa pagination (heuristik per fungsi handler GET)
        for m in get_pat.finditer(txt):
            start = m.end()
            block = txt[start:start + 600]
            if "limit" not in block and "page" not in block and "skip" not in block and ".find(" in block:
                w(f"{rel(f)}: GET '{m.group(1)}' tampak list tanpa param pagination (limit/skip/page).")
        # A3 N+1 heuristik
        in_loop = 0
        for ln in lines:
            s = ln.strip()
            if re.match(r"(for|while)\b", s):
                in_loop = 1
            elif in_loop and "await db." in s:
                w(f"{rel(f)}: kemungkinan N+1 (`await db.` di dalam loop) — batukan query ($in/aggregate).")
                in_loop = 0
            elif s and not s.startswith("#") and in_loop and not ln.startswith((" ", "\t")):
                in_loop = 0


def scan_frontend():
    if not FEATURES.exists():
        print(f"{Y}  frontend/features belum ada — skip cek FE (Phase 0).{X}")
        return
    for f in FEATURES.rglob("*.jsx"):
        txt = f.read_text(errors="ignore")
        if re.search(r"<table|<tbody", txt) and ".map(" in txt:
            if not re.search(r"pagination|Pagination|slice\(|page|virtual|InfiniteScroll", txt):
                w(f"{rel(f)}: tabel `.map` tanpa pagination/virtualisasi (risiko render berat).")


def main():
    strict = "--strict" in sys.argv
    print(f"{B}{C}{'='*64}{X}\n{B}  ARCHITECTURE & PERFORMANCE GATE{X}\n{B}{C}{'='*64}{X}")
    print(f"\n{B}BACKEND{X}")
    scan_backend()
    print(f"\n{B}FRONTEND{X}")
    scan_frontend()
    print(f"\n{B}{'='*64}{X}\n  {R}ERROR {err}{X} | {Y}WARN {warn}{X}")
    if err and strict:
        print(f"  {R}{B}ARCH VIOLATION (strict) — perbaiki anti-pattern performa.{X}\n")
        return 1
    if err == 0 and warn == 0:
        print(f"  {G}{B}Tidak ada anti-pattern arsitektur terdeteksi.{X}\n")
    else:
        print(f"  {Y}WARN = backlog tech-debt; file BARU/disentuh sebaiknya 0 ERROR.{X}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
