#!/usr/bin/env python3
"""migrate_booking_v1.py — migrasi IDEMPOTEN untuk pemesanan online (database yang sudah jalan).

Seed bersih (`scripts/seed_data.py`) sudah menulis field baru, tetapi database produksi/demo
yang sudah berisi data harus diselaraskan tanpa kehilangan apa pun. Skrip ini boleh dijalankan
berulang kali; setiap langkah hanya menyentuh dokumen yang belum punya nilai.

Yang dikerjakan:
  1. vehicles.day_rate        ← price_from (bila > 0) atau tarif tipe dari pricing_rules.
                                Alasan: harga yang TAMPIL di web dulu berasal dari price_from
                                sementara tagihan memakai tarif tipe → dua angka berbeda.
  2. vehicles.publish_to_web  ← True untuk unit milik sendiri; False untuk unit mitra.
                                Field ini sudah ada di seed tetapi TIDAK pernah dibaca siapa pun;
                                sekarang jadi penentu resmi katalog & pemesanan online.
  3. packages.destination_id  ← dicocokkan dari nama destinasi (relasi nyata, sekali saja).
  4. promos.*                 ← field syarat yang belum ada diisi nilai netral (tidak mengubah
                                perilaku promo lama: tanpa syarat = tidak ada batasan tambahan).
  5. settings.pricing_rules   ← buang `fuel_per_km` (komponen jarak sudah dihapus dari mesin)
                                dan samakan `dp_percent` dengan `pricing_defaults` (satu sumber).
  6. settings.booking_flow    ← dibuat dengan nilai default bila belum ada.

Jalankan: cd /app && python scripts/migrate_booking_v1.py
"""
import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / "backend" / ".env")
except Exception:  # pragma: no cover
    pass

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

G, Y, C, B, X = "\033[92m", "\033[93m", "\033[96m", "\033[1m", "\033[0m"

PROMO_DEFAULTS = {
    "valid_from": "", "min_days": 0, "min_amount": 0, "vehicle_types": [],
    "services": [], "weekend_only": False, "max_uses": 0, "used_count": 0,
}


async def main():
    client = AsyncIOMotorClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
    db = client[os.environ.get("DB_NAME", "test_database")]
    from services.booking_flow import DEFAULT_FLOW
    from services.pricing import resolve_day_rate

    print(f"\n{C}{B}MIGRASI PEMESANAN ONLINE (idempoten){X}\n")
    rules_doc = await db.settings.find_one({"key": "pricing_rules"}, {"_id": 0})
    rules = (rules_doc or {}).get("value") or {}

    # 1 + 2 — tarif resmi per unit & flag tayang web
    n_rate = n_pub = 0
    async for v in db.vehicles.find({}, {"_id": 0}):
        patch = {}
        if not v.get("day_rate"):
            price_from = v.get("price_from")
            try:
                marketing = int(round(float(price_from or 0)))
            except (TypeError, ValueError):
                marketing = 0
            patch["day_rate"] = marketing if marketing > 0 else resolve_day_rate(
                rules, vehicle=v)[0]
            n_rate += 1
        if v.get("publish_to_web") is None:
            patch["publish_to_web"] = str(v.get("ownership") or "owned") == "owned"
            n_pub += 1
        if patch:
            await db.vehicles.update_one({"id": v["id"]}, {"$set": patch})
    print(f"  {G}[1]{X} vehicles.day_rate diisi: {n_rate}")
    print(f"  {G}[2]{X} vehicles.publish_to_web diisi: {n_pub}")

    # 3 — relasi paket → destinasi
    by_name = {d.get("name"): d.get("id") for d in
               await db.destinations.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(500)}
    n_pkg = 0
    async for pkg in db.packages.find({}, {"_id": 0, "id": 1, "destination": 1,
                                          "destination_id": 1}):
        if pkg.get("destination_id"):
            continue
        dst_id = by_name.get(pkg.get("destination"))
        if dst_id:
            await db.packages.update_one({"id": pkg["id"]},
                                        {"$set": {"destination_id": dst_id}})
            n_pkg += 1
    print(f"  {G}[3]{X} packages.destination_id ditautkan: {n_pkg}")

    # 4 — syarat promo sebagai data
    n_promo = 0
    async for pr in db.promos.find({}, {"_id": 0}):
        patch = {k: v for k, v in PROMO_DEFAULTS.items() if pr.get(k) is None}
        if patch:
            await db.promos.update_one({"id": pr["id"]}, {"$set": patch})
            n_promo += 1
    print(f"  {G}[4]{X} promos dilengkapi field syarat: {n_promo}")

    # 5 — bersihkan aturan harga + satu sumber DP
    pd_doc = await db.settings.find_one({"key": "pricing_defaults"}, {"_id": 0})
    pd = (pd_doc or {}).get("value") or {}
    dp = rules.get("dp_percent", pd.get("dp_percent", 30))
    new_rules = {k: v for k, v in rules.items() if k != "fuel_per_km"}
    new_rules["dp_percent"] = dp
    await db.settings.update_one({"key": "pricing_rules"},
                                {"$set": {"key": "pricing_rules", "value": new_rules}},
                                upsert=True)
    if pd:
        pd["dp_percent"] = dp
        await db.settings.update_one({"key": "pricing_defaults"},
                                    {"$set": {"key": "pricing_defaults", "value": pd}})
    print(f"  {G}[5]{X} pricing_rules: fuel_per_km dibuang, dp_percent disamakan = {dp}%")

    # 6 — konfigurasi alur booking
    existing = await db.settings.find_one({"key": "booking_flow"}, {"_id": 0})
    if not existing:
        await db.settings.update_one({"key": "booking_flow"},
                                    {"$set": {"key": "booking_flow",
                                              "value": dict(DEFAULT_FLOW)}}, upsert=True)
        print(f"  {G}[6]{X} settings.booking_flow dibuat (mode={DEFAULT_FLOW['mode']})")
    else:
        print(f"  {Y}[6]{X} settings.booking_flow sudah ada — tidak diubah")

    print(f"\n{G}{B}  MIGRASI SELESAI.{X}\n")
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
