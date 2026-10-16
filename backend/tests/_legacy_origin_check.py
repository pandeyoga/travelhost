"""Cek edit booking WARISAN (origin di luar master) — sisipkan langsung ke DB lalu PATCH notes."""
import asyncio
import os
import sys

import requests
from dotenv import dotenv_values
from motor.motor_asyncio import AsyncIOMotorClient

env = dotenv_values("/app/backend/.env")
fenv = dotenv_values("/app/frontend/.env")
BASE_URL = fenv["REACT_APP_BACKEND_URL"].rstrip("/")


async def main():
    cli = AsyncIOMotorClient(env["MONGO_URL"])
    db = cli[env["DB_NAME"]]
    src = await db.bookings.find_one({"status": {"$nin": ["cancelled", "completed"]}}, {"_id": 0})
    if not src:
        print("FAIL: tidak ada booking sumber")
        return 1
    doc = dict(src)
    doc["id"] = "bkg_legacy_test_ssot2"
    doc["code"] = "TEST-LEGACY"
    doc["origin"] = "Gudang Warisan Lama"
    doc["notes"] = "TEST_legacy_before"
    await db.bookings.delete_one({"id": doc["id"]})
    await db.bookings.insert_one(doc)

    s = requests.Session()
    tok = s.post(f"{BASE_URL}/api/auth/login",
                 json={"email": "owner@demo.local", "password": "demo12345"}, timeout=30).json()["token"]
    s.headers.update({"Authorization": f"Bearer {tok}", "Content-Type": "application/json"})
    r = s.patch(f"{BASE_URL}/api/bookings/{doc['id']}", json={"notes": "TEST_legacy_after"}, timeout=30)
    print("PATCH notes status:", r.status_code, r.text[:300])
    ok = r.status_code == 200
    if ok:
        after = s.get(f"{BASE_URL}/api/bookings/{doc['id']}", timeout=30).json()
        print("origin sesudah:", after.get("origin"), "| notes:", after.get("notes"))
        ok = after.get("origin") == "Gudang Warisan Lama" and after.get("notes") == "TEST_legacy_after"
    # cleanup
    await db.bookings.delete_one({"id": doc["id"]})
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


sys.exit(asyncio.run(main()))
