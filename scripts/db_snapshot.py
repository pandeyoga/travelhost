#!/usr/bin/env python3
"""db_snapshot.py — cetak jumlah dokumen per koleksi (alat bantu verifikasi INV-CLEAN-01).

Dipakai untuk membuktikan klaim "data uji tidak menumpuk": ambil snapshot SESUDAH seed bersih,
jalankan gate/POC, lalu bandingkan. Angka WAJIB kembali sama — kalau bertambah, ada skrip uji
yang meninggalkan jejak (lihat memory/INVARIANTS.md → INV-CLEAN-01).

Pakai:
    python scripts/db_snapshot.py                 # cetak snapshot
    python scripts/db_snapshot.py --save nama     # simpan ke /tmp/snap_nama.json
    python scripts/db_snapshot.py --diff nama     # bandingkan dengan snapshot tersimpan
"""
import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / "backend" / ".env")
except Exception:  # noqa: BLE001
    pass

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

G, Y, R, X = "\033[92m", "\033[93m", "\033[91m", "\033[0m"


async def counts():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    out = {}
    for col in sorted(await db.list_collection_names()):
        out[col] = await db[col].count_documents({})
    client.close()
    return out


def main() -> int:
    now = asyncio.run(counts())
    args = sys.argv[1:]
    if "--save" in args:
        name = args[args.index("--save") + 1]
        Path(f"/tmp/snap_{name}.json").write_text(json.dumps(now, indent=1))
        print(f"{G}[OK]{X} snapshot '{name}' disimpan ({sum(now.values())} dokumen).")
        return 0
    if "--diff" in args:
        name = args[args.index("--diff") + 1]
        path = Path(f"/tmp/snap_{name}.json")
        if not path.exists():
            print(f"{R}[FAIL]{X} snapshot '{name}' tidak ada.")
            return 1
        before = json.loads(path.read_text())
        keys = sorted(set(before) | set(now))
        drift = [(k, before.get(k, 0), now.get(k, 0)) for k in keys
                 if before.get(k, 0) != now.get(k, 0)]
        if not drift:
            print(f"{G}[OK]{X} TIDAK ADA selisih vs snapshot '{name}' "
                  f"({sum(now.values())} dokumen) — data uji tidak menumpuk.")
            return 0
        print(f"{Y}[SELISIH]{X} vs snapshot '{name}':")
        for k, b, a in drift:
            arrow = f"{R}+{a - b}{X}" if a > b else f"{Y}{a - b}{X}"
            print(f"   {k}: {b} → {a}  ({arrow})")
        return 1
    for k, v in now.items():
        print(f"{k}: {v}")
    print(f"TOTAL: {sum(now.values())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
