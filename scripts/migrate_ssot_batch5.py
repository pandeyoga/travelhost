#!/usr/bin/env python3
"""migrate_ssot_batch5.py — bangun master `cities` dari nilai city yang SUDAH ada
di customers/partners (idempotent; nama di-title-case-kan seperlunya, dedupe case-insensitive).

Dipakai saat melanjutkan DB lama (bukan clean-seed). Clean-seed sudah menanam master kota.
Usage: python scripts/migrate_ssot_batch5.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "backend", ".env"))
from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

from core_utils import new_id, now_iso  # noqa: E402


async def main():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    existing = {str(c.get("name") or "").strip().lower()
                async for c in db.cities.find({"deleted": {"$ne": True}}, {"_id": 0, "name": 1})}
    seen, created = set(existing), 0
    for coll in ("customers", "partners", "workshops"):
        async for d in db[coll].find({}, {"_id": 0, "city": 1}):
            name = str(d.get("city") or "").strip()
            low = name.lower()
            if not name or low in seen:
                continue
            seen.add(low)
            await db.cities.insert_one({"id": new_id("cty"), "name": name,
                                        "active": True, "created_at": now_iso()})
            created += 1
    total = await db.cities.count_documents({"deleted": {"$ne": True}})
    print(f"[MIGRATE B5] cities: +{created} baru (total {total})")
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
