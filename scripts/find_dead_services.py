#!/usr/bin/env python3
"""find_dead_services.py — HYGIENE (report-only): fungsi service publik yang TAK dirujuk.

BUKAN gate (exit selalu 0). Membantu bug-hunt & pemeliharaan: kode mati = permukaan yang
tak teruji / niat yang hilang. Heuristik: untuk tiap `def nama(` (top-level, tak diawali '_')
di `backend/services/*.py`, hitung rujukan `nama` di SELURUH backend. 0 rujukan (di luar
definisinya) → kandidat dead code (verifikasi manual — bisa entrypoint dinamis/registry).
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
SERVICES = BACKEND / "services"
G = "\033[92m"; Y = "\033[93m"; X = "\033[0m"


def main() -> int:
    all_text = {}
    for p in BACKEND.rglob("*.py"):
        if "__pycache__" in p.parts:
            continue
        all_text[p] = p.read_text(encoding="utf-8", errors="ignore")
    dead = []
    for sp in sorted(SERVICES.glob("*.py")):
        if sp.name == "__init__.py":
            continue
        text = all_text.get(sp, "")
        for m in re.finditer(r'^(?:async\s+)?def\s+([a-zA-Z][A-Za-z0-9_]*)\s*\(', text, re.M):
            name = m.group(1)
            if name.startswith("_"):
                continue
            refs = 0
            for p, t in all_text.items():
                cnt = len(re.findall(r'\b' + re.escape(name) + r'\b', t))
                if p == sp:
                    cnt -= 1  # kurangi baris definisi itu sendiri
                refs += cnt
            if refs <= 0:
                dead.append(f"{sp.relative_to(ROOT)}::{name}")
    print("=== find_dead_services (HYGIENE, report-only) ===")
    if dead:
        print(f"  {Y}{len(dead)} fungsi service kandidat TAK-DIRUJUK{X} (verifikasi manual; bisa dead code / dipanggil dinamis):")
        for d in dead:
            print("   ·", d)
    else:
        print(f"  {G}Tak ada kandidat dead service. Bersih.{X}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
