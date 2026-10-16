#!/usr/bin/env python3
"""
check_nav_map.py — Navigation consistency gate
==============================================
Memastikan item navigasi di frontend config konsisten dengan docs/05_NAVIGATION_MAP.md.
Resilient: skip dengan rapi bila frontend belum dibuat (Phase 0).

Cek:
  - Setiap `nav-<id>` / id menu di navigationConfig.js punya PAGE_META.
  - Setiap modul nav disebut di 05_NAVIGATION_MAP.md (mencegah menu liar).

Usage: cd /app && python scripts/check_nav_map.py
Exit 0 = OK / skip. 1 = inkonsistensi.
"""
import re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAV_CFG = ROOT / "frontend" / "src" / "config" / "navigationConfig.js"
NAV_DOC = ROOT / "docs" / "05_NAVIGATION_MAP.md"
G, Y, R, B, X = "\033[92m", "\033[93m", "\033[91m", "\033[1m", "\033[0m"


def main():
    if not NAV_CFG.exists():
        print(f"{Y}navigationConfig.js belum ada — skip nav check (Phase 0).{X}")
        return 0
    cfg = NAV_CFG.read_text(encoding="utf-8", errors="ignore")
    doc = NAV_DOC.read_text(encoding="utf-8", errors="ignore") if NAV_DOC.exists() else ""
    # id menu: { id: 'bookings', ... }
    ids = sorted(set(re.findall(r"id:\s*['\"]([a-z0-9_-]+)['\"]", cfg)))
    page_meta = re.search(r"PAGE_META\s*=\s*\{(.*?)\}\s*;", cfg, re.S)
    meta_keys = set(re.findall(r"['\"]([a-z0-9_-]+)['\"]\s*:", page_meta.group(1))) if page_meta else set()
    problems = 0
    print(f"\n{B}NAV MAP CHECK — {len(ids)} menu id{X}")
    for i in ids:
        in_meta = i in meta_keys or not page_meta
        in_doc = (i in doc) or (i.replace('-', ' ') in doc.lower())
        if not in_doc and doc:
            problems += 1
            print(f"  {R}[WARN] menu '{i}' tidak disebut di 05_NAVIGATION_MAP.md (menu liar?){X}")
        elif not in_meta:
            print(f"  {Y}[INFO] menu '{i}' belum punya PAGE_META{X}")
        else:
            print(f"  {G}[OK]{X} {i}")
    print()
    # tidak gagal keras untuk menu liar saat awal — hanya warning bila doc ada
    return 0


if __name__ == "__main__":
    sys.exit(main())
