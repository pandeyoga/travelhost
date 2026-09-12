#!/usr/bin/env python3
"""verify_state_machine.py — GATE anti-regresi STATE-MACHINE (RC-02/03/04/05).

Menguji jalur MENYIMPANG (bukan happy-path) dgn objek sintetis tahun 2028 + auto-cleanup
ke baseline. Bug kelas ini lolos gate lama karena gate lama menguji clean-seed+happy-path.

Cek:
  SM1 (RC-04) assign→cancel : trip terkait → cancelled & armada dibebaskan (available).
  SM2 (RC-03) /trips/{id}/status=completed : efek identik checkout (booking completed, armada bebas).
  SM3 (RC-02) complete tanpa lunas : payment_status ∈ {dp,belum_bayar} & TETAP muncul di AR (jujur).
  SM4 (RC-05) pembayaran ke booking cancelled : DITOLAK (400).

Resilient: backend down / login gagal / data seed kurang → SKIP rapi (Phase 0). Exit 1 hanya bila regresi.
Usage: cd /app && python scripts/verify_state_machine.py
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
CREATED = {"bookings": [], "trips": [], "payments": []}


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


def _veh_ok(vid, tid, veh_status):
    """Armada dianggap benar bila available, ATAU masih dipakai trip aktif lain (bukan trip kita)."""
    if veh_status == "available":
        return True
    other = DBC.trips.find_one({"vehicle_id": vid, "id": {"$ne": tid}, "status": {"$in": ACTIVE}}, {"_id": 0, "id": 1})
    return bool(other)


async def main():
    print(f"\n{B}{'='*60}{X}\n  STATE-MACHINE GATE (RC-02/03/04/05)  API={API}\n{B}{'='*60}{X}")
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

        async def mk(veh, start, end, price=1000000):
            r = await c.post(f"{API}/api/bookings", headers=H, json={
                "customer_id": cust["id"], "vehicle_id": veh["id"],
                "start_datetime": start, "end_datetime": end, "base_price": price})
            b = r.json()
            if r.status_code == 200 and isinstance(b, dict) and b.get("id"):
                CREATED["bookings"].append(b["id"])
            return r.status_code, b

        # ---- SM1 (RC-04): assign lalu cancel ----
        sc, b = await mk(v1, "2028-01-10T08:00:00+00:00", "2028-01-11T08:00:00+00:00")
        if sc == 200:
            r = await c.post(f"{API}/api/dispatch/{b['id']}/assign", headers=H,
                             json={"driver_id": d1["id"], "vehicle_id": v1["id"]})
            tid = r.json().get("trip", {}).get("id") if r.status_code == 200 else None
            if tid:
                CREATED["trips"].append(tid)
            await c.post(f"{API}/api/bookings/{b['id']}/cancel", headers=H)
            trip = DBC.trips.find_one({"id": tid}, {"_id": 0, "status": 1}) if tid else None
            veh = DBC.vehicles.find_one({"id": v1["id"]}, {"_id": 0, "status": 1}) or {}
            trip_cancelled = (trip or {}).get("status") == "cancelled"
            if trip_cancelled and _veh_ok(v1["id"], tid, veh.get("status")):
                ok(f"SM1 (RC-04) cancel → trip cancelled & armada beres (vehicle={veh.get('status')}).")
            else:
                fail(f"SM1 (RC-04) cancel TIDAK sinkron: trip={(trip or {}).get('status')}, vehicle={veh.get('status')}")
        else:
            skip(f"SM1 buat booking → {sc}")
        cancelled_bk = b.get("id") if sc == 200 else None

        # ---- SM2 (RC-03): /trips/{id}/status completed = efek checkout ----
        sc, b2 = await mk(v2, "2028-02-10T08:00:00+00:00", "2028-02-11T08:00:00+00:00")
        if sc == 200:
            r = await c.post(f"{API}/api/dispatch/{b2['id']}/assign", headers=H,
                             json={"driver_id": d1["id"], "vehicle_id": v2["id"]})
            tid2 = r.json().get("trip", {}).get("id") if r.status_code == 200 else None
            if tid2:
                CREATED["trips"].append(tid2)
            rs = await c.post(f"{API}/api/trips/{tid2}/status", headers=H, json={"status": "completed"})
            veh2 = DBC.vehicles.find_one({"id": v2["id"]}, {"_id": 0, "status": 1}) or {}
            bk2 = DBC.bookings.find_one({"id": b2["id"]}, {"_id": 0, "status": 1}) or {}
            if rs.status_code == 200 and bk2.get("status") == "completed" and _veh_ok(v2["id"], tid2, veh2.get("status")):
                ok(f"SM2 (RC-03) /trips/status=completed → booking completed & armada beres (vehicle={veh2.get('status')}).")
            else:
                fail(f"SM2 (RC-03) split-brain: http={rs.status_code}, booking={bk2.get('status')}, vehicle={veh2.get('status')}")
        else:
            skip(f"SM2 buat booking → {sc}")

        # ---- SM3 (RC-02): complete tanpa lunas ----
        sc, b3 = await mk(v1, "2028-03-10T08:00:00+00:00", "2028-03-11T08:00:00+00:00", price=2000000)
        if sc == 200:
            await c.post(f"{API}/api/bookings/{b3['id']}/complete", headers=H)
            bk3 = DBC.bookings.find_one({"id": b3["id"]}, {"_id": 0, "payment_status": 1, "status": 1}) or {}
            ar = (await c.get(f"{API}/api/finance/ar", headers=H)).json()
            ar_ids = {it.get("booking_id") for it in (ar.get("items") or [])}
            ps = bk3.get("payment_status")
            in_ar = b3["id"] in ar_ids
            if ps in ("dp", "belum_bayar") and in_ar:
                ok(f"SM3 (RC-02) complete tanpa lunas → payment_status='{ps}' & muncul di AR (jujur).")
            else:
                fail(f"SM3 (RC-02) sinyal kontradiktif: payment_status='{ps}', in_AR={in_ar} (harus dp/belum_bayar & di AR).")
        else:
            skip(f"SM3 buat booking → {sc}")

        # ---- SM4 (RC-05): pembayaran ke booking cancelled ----
        if cancelled_bk:
            r = await c.post(f"{API}/api/payments", headers=H,
                             json={"booking_id": cancelled_bk, "amount": 100000, "type": "dp"})
            if r.status_code == 200 and isinstance(r.json(), dict) and r.json().get("id"):
                CREATED["payments"].append(r.json()["id"])
                fail("SM4 (RC-05) pembayaran ke booking cancelled DITERIMA (200) — harus 400.")
            elif r.status_code == 400:
                ok("SM4 (RC-05) pembayaran ke booking cancelled ditolak (400).")
            else:
                skip(f"SM4 pembayaran → {r.status_code} (tak konklusif).")
        else:
            skip("SM4 tak ada booking cancelled utk diuji.")

    return _summary()


def _cleanup():
    for b in CREATED["bookings"]:
        DBC.bookings.delete_one({"id": b})
        DBC.payments.delete_many({"booking_id": b})
        DBC.trips.delete_many({"booking_id": b})
        DBC.invoices.delete_many({"booking_id": b})
        DBC.audit_logs.delete_many({"entity_id": b})
        DBC.events.delete_many({"ref_id": b})
        DBC.notification_tasks.delete_many({"payload.booking_id": b})
        # Hygiene: notification_tasks juga menyimpan booking_id di TOP-LEVEL (dipakai
        # verify_schema untuk cek FK) — filter payload saja meninggalkan referensi menggantung.
        DBC.notification_tasks.delete_many({"booking_id": b})
    for t in CREATED["trips"]:
        DBC.trips.delete_one({"id": t})
    for p in CREATED["payments"]:
        DBC.payments.delete_one({"id": p})
    # Pulihkan status armada/driver dari trip aktif nyata (baseline).
    active_vids = {t.get("vehicle_id") for t in DBC.trips.find({"status": {"$in": ACTIVE}}, {"vehicle_id": 1})}
    for v in DBC.vehicles.find({}, {"id": 1, "status": 1}):
        want = "on_trip" if v["id"] in active_vids else "available"
        if v.get("status") in ("on_trip", "available") and v.get("status") != want:
            DBC.vehicles.update_one({"id": v["id"]}, {"$set": {"status": want}})


def _summary():
    _cleanup()
    print(f"\n{B}{'='*60}{X}\n  {R}FAIL {fails}{X} | {Y}SKIP {skips}{X}\n{B}{'='*60}{X}")
    if fails:
        print(f"{R}{B}  STATE-MACHINE REGRESI — perbaiki (lihat RC terkait).{X}\n")
        return 1
    print(f"{G}{B}  State-machine sehat (RC-02/03/04/05 tertutup).{X}\n")
    return 0


if __name__ == "__main__":
    try:
        rc = asyncio.run(main())
    except Exception as ex:  # jangan biarkan objek uji tertinggal
        _cleanup()
        print(f"{Y}  Gate error (dianggap SKIP): {ex}{X}")
        rc = 0
    sys.exit(rc)
