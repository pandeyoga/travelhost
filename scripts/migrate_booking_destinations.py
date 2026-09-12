#!/usr/bin/env python3
"""migrate_booking_destinations.py — migrasi RC-E batch 1 (INV-REF-02).

1) Pastikan master `destinations` memuat destinasi OPERASIONAL yang selama ini hanya hidup
   sebagai teks bebas di booking (status 'draft' → tidak tayang di web publik).
2) Normalisasi `bookings.destination` lama ke NAMA KANONIK master (case-insensitive +
   alias pendek warisan: "Bromo" → "Gunung Bromo", "Dieng" → "Dataran Tinggi Dieng").
3) Nilai yang tak bisa dipetakan DIBIARKAN (dilaporkan) — migrasi tidak boleh mengarang data.

Aman dijalankan berulang (idempotent).
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

# Alias warisan → nama kanonik master (hanya untuk data LAMA; jalur tulis baru wajib master).
LEGACY_ALIASES = {
    "bromo": "Gunung Bromo",
    "dieng": "Dataran Tinggi Dieng",
    "jogja": "Yogyakarta",
    "yogya": "Yogyakarta",
}

# Destinasi operasional yang dibuat bila belum ada di master (draft = tak tayang di web).
OPS_DESTINATIONS = ["Bandung", "Jakarta", "Garut", "Pangandaran", "Karimunjawa"]


def now_iso():
    return datetime.now(timezone.utc).isoformat()


async def main():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]

    masters = await db.destinations.find({"deleted": {"$ne": True}},
                                         {"_id": 0, "name": 1, "slug": 1}).to_list(500)
    by_low = {str(m.get("name") or "").strip().lower(): str(m.get("name")).strip() for m in masters}
    for m in masters:
        slug = str(m.get("slug") or "").strip().lower()
        if slug:
            by_low.setdefault(slug, str(m.get("name")).strip())

    created = 0
    for name in OPS_DESTINATIONS:
        if name.lower() in by_low:
            continue
        await db.destinations.insert_one({
            "id": f"dst_{uuid.uuid4().hex[:16]}", "slug": name.lower().replace(" ", "-"),
            "name": name, "region": "", "status": "draft", "source": "ops",
            "description": "Destinasi operasional (dibuat migrasi INV-REF-02).",
            "created_at": now_iso(),
        })
        by_low[name.lower()] = name
        created += 1

    normalized, unmatched = 0, {}
    async for bk in db.bookings.find({}, {"_id": 0, "id": 1, "destination": 1}):
        raw = str(bk.get("destination") or "").strip()
        if not raw:
            continue
        low = raw.lower()
        canon = by_low.get(low) or by_low.get(LEGACY_ALIASES.get(low, "").lower())
        if canon and canon != raw:
            await db.bookings.update_one({"id": bk["id"]}, {"$set": {"destination": canon}})
            normalized += 1
        elif not canon:
            unmatched[raw] = unmatched.get(raw, 0) + 1

    print(f"[MIGRASI INV-REF-02] master ops dibuat={created} · booking dinormalkan={normalized}")
    if unmatched:
        print("Nilai warisan yang TIDAK terpetakan (dibiarkan, tambahkan ke master bila perlu):")
        for k, v in sorted(unmatched.items()):
            print(f"  - '{k}' × {v}")
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
