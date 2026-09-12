#!/usr/bin/env python3
"""migrate_ssot_batch2.py — migrasi INV-REF-02 batch 2 (titik jemput + destinasi lead).

1) Bangun master `pickup_points` dari nilai `bookings.origin` lama yang non-kosong
   (plus baris umum), lalu normalisasi origin lama ke NAMA KANONIK master.
2) Normalisasi `leads.destination` lama ke nama kanonik master `destinations`
   (case-insensitive + alias warisan). Nilai yang tak terpetakan DIBIARKAN & dilaporkan
   (lead inbound publik memang boleh di luar master — batas sistem).

Idempotent — aman dijalankan berulang.
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "backend", ".env"))
from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

LEGACY_DEST_ALIASES = {"bromo": "Gunung Bromo", "dieng": "Dataran Tinggi Dieng",
                       "jogja": "Yogyakarta", "yogya": "Yogyakarta"}
BASE_PICKUPS = ["Bandung", "Jakarta", "Bandara Soekarno-Hatta", "Stasiun Bandung"]


def now_iso():
    return datetime.now(timezone.utc).isoformat()


async def main():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]

    # --- 1) master pickup_points dari origin lama + baris umum ---
    existing = {str(p.get("name", "")).strip().lower(): str(p.get("name", "")).strip()
                async for p in db.pickup_points.find({"deleted": {"$ne": True}}, {"_id": 0, "name": 1})}
    created = 0
    candidates = list(BASE_PICKUPS) + [o for o in await db.bookings.distinct("origin") if o and str(o).strip()]
    for raw in candidates:
        name = str(raw).strip()
        if name.lower() in existing:
            continue
        await db.pickup_points.insert_one({"id": f"pkp_{uuid.uuid4().hex[:16]}",
                                           "name": name, "created_at": now_iso()})
        existing[name.lower()] = name
        created += 1

    norm_origin = 0
    async for bk in db.bookings.find({}, {"_id": 0, "id": 1, "origin": 1}):
        raw = str(bk.get("origin") or "").strip()
        canon = existing.get(raw.lower()) if raw else None
        if raw and canon and canon != bk.get("origin"):
            await db.bookings.update_one({"id": bk["id"]}, {"$set": {"origin": canon}})
            norm_origin += 1

    # --- 2) normalisasi destinasi lead ke master destinations ---
    dest_by_low = {}
    async for d in db.destinations.find({"deleted": {"$ne": True}}, {"_id": 0, "name": 1, "slug": 1}):
        nm = str(d.get("name") or "").strip()
        if nm:
            dest_by_low[nm.lower()] = nm
            slug = str(d.get("slug") or "").strip().lower()
            if slug:
                dest_by_low.setdefault(slug, nm)

    norm_lead, unmatched = 0, {}
    async for ld in db.leads.find({}, {"_id": 0, "id": 1, "destination": 1}):
        raw = str(ld.get("destination") or "").strip()
        if not raw:
            continue
        canon = dest_by_low.get(raw.lower()) or dest_by_low.get(
            LEGACY_DEST_ALIASES.get(raw.lower(), "").lower())
        if canon and canon != raw:
            await db.leads.update_one({"id": ld["id"]}, {"$set": {"destination": canon}})
            norm_lead += 1
        elif not canon:
            unmatched[raw] = unmatched.get(raw, 0) + 1

    print(f"[MIGRASI INV-REF-02 b2] pickup_points dibuat={created} · origin dinormalkan={norm_origin} "
          f"· destinasi lead dinormalkan={norm_lead}")
    if unmatched:
        print("Destinasi lead di luar master (dibiarkan — inbound publik):")
        for k, v in sorted(unmatched.items()):
            print(f"  - '{k}' × {v}")
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
