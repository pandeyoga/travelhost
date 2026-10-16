#!/usr/bin/env python3
"""purge_test_pollution.py — ALAT PERBAIKAN: bersihkan artefak data uji dari database.

Untuk apa
---------
Penjaga (`scripts/guardrails/verify_*.py`) & smoke test menulis data lewat API sungguhan
supaya perilaku server teruji. Sejak BUG-0127 semuanya WAJIB membersihkan diri sendiri
(INV-CLEAN-01). Skrip ini dipakai untuk:

  1. memperbaiki database yang SUDAH kotor dari sesi/rilis lama, dan
  2. dijalankan pengguna kapan pun ia ingin memastikan ERP bebas data hantu.

Yang dihapus HANYA dokumen berpenanda data uji (`GUARD_MARKERS` — mis. "Penjaga INV-",
"Smoke Customer", "Guard Lead ", "guard-media-", nomor `0800000xxx`/`0810000000`) atau field
identitas yang panjangnya di luar batas wajar (`OVERLONG_RULES` — artefak `"A" * 60000`),
BESERTA side-effect-nya: pembayaran/trip/invoice/lokasi, percakapan + pesan Inbox,
notifikasi, event + automation_runs, entri audit, dan aset `guard-media-*`.

Dokumen bersumber `seed` (data demo) TIDAK PERNAH tersentuh — data demo tetap utuh.

Pakai
-----
    python scripts/purge_test_pollution.py            # bersihkan
    python scripts/purge_test_pollution.py --dry-run  # tampilkan saja, jangan hapus
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "guardrails"))
from _common import (G, R, Y, C, B, X, GUARD_MARKERS,  # noqa: E402
                     purge_guard_artifacts, scan_test_pollution)


def main() -> int:
    dry = "--dry-run" in sys.argv
    print(f"{C}{B}BERSIH-BERSIH ARTEFAK DATA UJI (INV-CLEAN-01){X}")
    hits = scan_test_pollution()
    if hits is None:
        print(f"{R}[FAIL]{X} tidak bisa terhubung ke MongoDB (cek MONGO_URL/DB_NAME).")
        return 1
    if not hits:
        print(f"{G}[OK]{X} database sudah bersih — 0 artefak uji "
              f"({len(GUARD_MARKERS)} penanda dipindai).")
        return 0

    by_col = {}
    for h in hits:
        by_col.setdefault(h["collection"], []).append(h)
    print(f"{Y}Ditemukan {len(hits)} dokumen artefak uji:{X}")
    for col, items in sorted(by_col.items()):
        print(f"  - {col}: {len(items)}")
        for i in items[:5]:
            print(f"      {i['id']} \u2192 {i['label']!r}  ({i['reason']})")
        if len(items) > 5:
            print(f"      … dan {len(items) - 5} lagi")

    if dry:
        print(f"\n{Y}--dry-run: tidak ada yang dihapus.{X}")
        return 0

    removed = purge_guard_artifacts()
    sisa = scan_test_pollution() or []
    print(f"\n{G}[OK]{X} {removed} dokumen dihapus (termasuk side-effect: percakapan, pesan, "
          f"notifikasi, event, automation_runs, audit, aset media).")
    if sisa:
        print(f"{R}[FAIL]{X} masih tersisa {len(sisa)} artefak — laporkan (penanda kurang?):")
        for s in sisa[:10]:
            print(f"   {s['collection']}/{s['id']} \u2192 {s['label']!r} ({s['reason']})")
        return 1
    print(f"{G}[OK]{X} verifikasi ulang: 0 artefak uji tersisa. Data demo tetap utuh.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
