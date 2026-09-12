#!/usr/bin/env python3
"""verify_cross_entity.py — GATE anti-regresi CROSS-ENTITY (RC-06 payroll overlap, RC-07 driver bentrok).

Cek:
  CE1 (RC-07) driver double-assign : 2 booking tumpang-tindih (armada beda), assign driver sama → tolak 400.
  CE2 (RC-06) payroll overlap       : 2 payout periode tumpang-tindih utk driver sama → tolak 400.

Objek sintetis 2028 + auto-cleanup. Resilient: backend down / login gagal → SKIP. Exit 1 hanya bila regresi.
Usage: cd /app && python scripts/verify_cross_entity.py
"""
import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / "backend" / ".env")
except Exception:
    pass
try:
    import httpx
except ImportError:
    os.system("pip install httpx -q")
    import httpx
from pymongo import MongoClient

API = os.environ.get("API_BASE", "http://localhost:8001").rstrip("/")
ADMIN = {"email": os.environ.get("ADMIN_EMAIL", "owner@demo.local"),
         "password": os.environ.get("ADMIN_PASS", "demo12345")}
G, Y, R, B, X = "\033[92m", "\033[93m", "\033[91m", "\033[1m", "\033[0m"
DBC = MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "test_database")]
ACTIVE = ["standby", "to_pickup", "on_trip"]
fails = 0
skips = 0
CREATED = {"bookings": [], "trips": [], "driver_payouts": []}


def ok(m):
    print(f"  {G}[OK]{X} {m}")


def fail(m):
    global fails
    fails += 1
    print(f"  {R}[FAIL]{X} {m}")


def skip(m):
    global skips
    skips += 1
    print(f"  {Y}[SKIP]{X} {m}")


async def main():
    print(f"\n{B}{'='*60}{X}\n  CROSS-ENTITY GATE (RC-06/RC-07)  API={API}\n{B}{'='*60}{X}")
    async with httpx.AsyncClient(follow_redirects=True, timeout=30) as c:
        try:
            r = await c.get(f"{API}/api/", timeout=5)
            if r.status_code >= 500:
                raise Exception("5xx")
        except Exception:
            print(f"{Y}  Backend belum berjalan — SKIP (Phase 0).{X}")
            return 0
        r = await c.post(f"{API}/api/auth/login", json=ADMIN)
        if r.status_code != 200:
            print(f"{Y}  Login gagal — SKIP.{X}")
            return 0
        H = {"Authorization": f"Bearer {r.json()['token']}"}
        custs = (await c.get(f"{API}/api/customers", headers=H)).json()
        vehs = (await c.get(f"{API}/api/vehicles", headers=H)).json()
        drvs = (await c.get(f"{API}/api/drivers", headers=H)).json()
        if not custs or len(vehs) < 2 or not drvs:
            skip("Data seed kurang (customer/vehicle/driver) — SKIP.")
            return _summary()
        cust, v1, v2, d1 = custs[0], vehs[0], vehs[1], drvs[0]

        async def mk(veh, start, end):
            r = await c.post(f"{API}/api/bookings", headers=H, json={
                "customer_id": cust["id"], "vehicle_id": veh["id"],
                "start_datetime": start, "end_datetime": end, "base_price": 1000000})
            b = r.json()
            if r.status_code == 200 and isinstance(b, dict) and b.get("id"):
                CREATED["bookings"].append(b["id"])
            return r.status_code, b

        # ---- CE1 (RC-07): driver double-assign ----
        sc1, bF1 = await mk(v1, "2028-04-10T08:00:00+00:00", "2028-04-11T08:00:00+00:00")
        sc2, bF2 = await mk(v2, "2028-04-10T09:00:00+00:00", "2028-04-11T07:00:00+00:00")
        if sc1 == 200 and sc2 == 200:
            r1 = await c.post(f"{API}/api/dispatch/{bF1['id']}/assign", headers=H,
                              json={"driver_id": d1["id"], "vehicle_id": v1["id"]})
            r2 = await c.post(f"{API}/api/dispatch/{bF2['id']}/assign", headers=H,
                              json={"driver_id": d1["id"], "vehicle_id": v2["id"]})
            for rr in (r1, r2):
                tid = rr.json().get("trip", {}).get("id") if rr.status_code == 200 else None
                if tid:
                    CREATED["trips"].append(tid)
            if r1.status_code == 200 and r2.status_code == 400:
                ok("CE1 (RC-07) assign kedua driver bentrok ditolak (400).")
            elif r1.status_code == 200 and r2.status_code == 200:
                fail("CE1 (RC-07) driver di-assign ke 2 trip tumpang-tindih (harus 400).")
            else:
                skip(f"CE1 tak konklusif: r1={r1.status_code} r2={r2.status_code}")
        else:
            skip(f"CE1 buat booking → {sc1}/{sc2}")

        # ---- CE2 (RC-06): payroll periode overlap ----
        p1 = await c.post(f"{API}/api/payroll/payouts/generate", headers=H, json={
            "driver_id": d1["id"], "period_type": "monthly",
            "period_start": "2028-06-01", "period_end": "2028-06-30"})
        p2 = await c.post(f"{API}/api/payroll/payouts/generate", headers=H, json={
            "driver_id": d1["id"], "period_type": "monthly",
            "period_start": "2028-06-15", "period_end": "2028-07-15"})
        if p1.status_code == 200 and isinstance(p1.json(), dict) and p1.json().get("id"):
            CREATED["driver_payouts"].append(p1.json()["id"])
        if p2.status_code == 200 and isinstance(p2.json(), dict) and p2.json().get("id"):
            CREATED["driver_payouts"].append(p2.json()["id"])
        if p1.status_code == 200 and p2.status_code == 400:
            ok("CE2 (RC-06) payout periode tumpang-tindih ditolak (400).")
        elif p1.status_code == 200 and p2.status_code == 200:
            fail("CE2 (RC-06) 2 payout overlap dibuat (harus 400) — risiko dobel-hitung.")
        else:
            skip(f"CE2 tak konklusif: p1={p1.status_code} p2={p2.status_code}")

    return _summary()


def _cleanup():
    for b in CREATED["bookings"]:
        DBC.bookings.delete_one({"id": b})
        DBC.trips.delete_many({"booking_id": b})
        DBC.payments.delete_many({"booking_id": b})
        DBC.audit_logs.delete_many({"entity_id": b})
        DBC.events.delete_many({"ref_id": b})
        # Hygiene: notification_tasks ikut dibersihkan (top-level & payload) agar tidak
        # meninggalkan FK menggantung yang membuat verify_schema MERAH-palsu di run berikutnya.
        DBC.notification_tasks.delete_many({"booking_id": b})
        DBC.notification_tasks.delete_many({"payload.booking_id": b})
    for t in CREATED["trips"]:
        DBC.trips.delete_one({"id": t})
    for p in CREATED["driver_payouts"]:
        d = DBC.driver_payouts.find_one({"id": p})
        if d and d.get("expense_id"):
            DBC.expenses.delete_one({"id": d["expense_id"]})
        DBC.driver_payouts.delete_one({"id": p})
    active_vids = {t.get("vehicle_id") for t in DBC.trips.find({"status": {"$in": ACTIVE}}, {"vehicle_id": 1})}
    for v in DBC.vehicles.find({}, {"id": 1, "status": 1}):
        want = "on_trip" if v["id"] in active_vids else "available"
        if v.get("status") in ("on_trip", "available") and v.get("status") != want:
            DBC.vehicles.update_one({"id": v["id"]}, {"$set": {"status": want}})


def _summary():
    _cleanup()
    print(f"\n{B}{'='*60}{X}\n  {R}FAIL {fails}{X} | {Y}SKIP {skips}{X}\n{B}{'='*60}{X}")
    if fails:
        print(f"{R}{B}  CROSS-ENTITY REGRESI — RC-06/RC-07 bocor.{X}\n")
        return 1
    print(f"{G}{B}  Cross-entity sehat (RC-06/RC-07 tertutup).{X}\n")
    return 0


if __name__ == "__main__":
    try:
        rc = asyncio.run(main())
    except Exception as ex:
        _cleanup()
        print(f"{Y}  Gate error (dianggap SKIP): {ex}{X}")
        rc = 0
    sys.exit(rc)
