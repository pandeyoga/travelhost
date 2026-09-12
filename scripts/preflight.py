#!/usr/bin/env python3
"""preflight.py — PRE-DEV readiness (Definition of Ready). Report + WARN, TAK mem-block.

Dijalankan SEBELUM menulis kode fitur baru. Memastikan konteks & artefak siap agar tak
mengulang AKAR MASALAH (konteks hilang antar-sesi). Mencetak status artefak + checklist.
Bagian dari SOP: docs/16_DEV_LIFECYCLE_SOP.md.
"""
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
G = "\033[92m"; Y = "\033[93m"; C = "\033[96m"; B = "\033[1m"; X = "\033[0m"

ARTIFACTS = [
    ("plan.md", "Rencana & fase aktif"),
    ("memory/INVARIANTS.md", "SSOT invariant (BACA DULU!)"),
    ("memory/SESSION_HANDOFF.md", "Status sesi terakhir & item terbuka"),
    ("memory/BUG_REGISTRY.md", "Riwayat bug + regresi"),
    ("docs/16_DEV_LIFECYCLE_SOP.md", "SOP siklus dev (pre+post)"),
    ("docs/17_BUGHUNT_SOP.md", "SOP bug-hunt (adversarial)"),
]
CHECKLIST = [
    "Baca memory/INVARIANTS.md — pahami SEMUA invariant yang berlaku.",
    "Baca memory/SESSION_HANDOFF.md — tahu kondisi terakhir & item terbuka.",
    "Petakan koleksi/entitas & endpoint baru yang akan disentuh.",
    "Identifikasi invariant RELEVAN dgn perubahan (auth? race? numeric? 5xx? RBAC?).",
    "Tentukan kontrak API (path /api, request/response) SEBELUM implementasi.",
    "Rencanakan guardrail/test utk fitur baru (post-dev WAJIB bisa dibuktikan).",
    "Definition of Ready: kriteria selesai jelas & terukur (bukan 'kelihatan jalan').",
]


def main() -> int:
    warn = 0
    print(f"{C}{B}=== PRE-DEV PREFLIGHT (Definition of Ready) ==={X}")
    print(f"\n{B}Artefak konteks:{X}")
    for rel, desc in ARTIFACTS:
        ok = (ROOT / rel).exists()
        tag = (G + "ADA" + X) if ok else (Y + "HILANG" + X)
        print(f"  [{tag}] {rel} — {desc}")
        if not ok:
            warn += 1
    print(f"\n{B}Lingkungan:{X}")
    try:
        code = urllib.request.urlopen("http://localhost:8001/api/", timeout=5).status
        print(f"  [{G}UP{X}] backend ({code})")
    except Exception as e:  # noqa: BLE001
        print(f"  [{Y}DOWN{X}] backend — {e}")
        warn += 1
    print(f"\n{B}Checklist kesiapan (konfirmasi manual SEBELUM ngoding):{X}")
    for i, c in enumerate(CHECKLIST, 1):
        print(f"  {i}. [ ] {c}")
    print(f"\n{B}Setelah ngoding →{X} `bash scripts/gate.sh` (HIJAU) lalu (deep) `bash scripts/run_forensics.sh`.")
    verdict = (Y + f"⚠ {warn} artefak/lingkungan perlu perhatian." if warn else G + "✓ Konteks & lingkungan siap.") + X
    print(f"\n{verdict}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
