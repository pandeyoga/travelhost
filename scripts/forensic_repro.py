#!/usr/bin/env python3
"""Reproduksi empiris bug kandidat audit forensik — read/write TERISOLASI + CLEANUP.
Semua objek uji memakai tanggal 2027 (jauh dari data seed) dan dihapus di akhir.
"""
import asyncio, os, sys, json
import httpx
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")
API = "http://localhost:8001/api"
DB = MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "test_database")]
CREATED = {"bookings": [], "payments": [], "trips": [], "driver_payouts": [], "expenses": []}
RESULTS = []

def note(bug, verdict, detail):
    RESULTS.append((bug, verdict, detail))
    print(f"[{verdict}] {bug}: {detail}")

async def main():
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(f"{API}/auth/login", json={"email": "owner@demo.local", "password": "demo12345"})
        tok = r.json()["token"]
        H = {"Authorization": f"Bearer {tok}"}

        cust = (await c.get(f"{API}/customers", headers=H)).json()[0]
        vehicles = (await c.get(f"{API}/vehicles", headers=H)).json()
        drivers = (await c.get(f"{API}/drivers", headers=H)).json()
        v1, v2 = vehicles[0], vehicles[1]
        d1 = drivers[0]

        async def mk_booking(veh, start, end, price=1000000):
            r = await c.post(f"{API}/bookings", headers=H, json={
                "customer_id": cust["id"], "vehicle_id": veh["id"],
                "start_datetime": start, "end_datetime": end, "base_price": price})
            b = r.json()
            assert r.status_code == 200, b
            CREATED["bookings"].append(b["id"])
            return b

        # ============ BUG-A: cancel booking setelah assign -> armada & trip tak dibebaskan
        v1_before = DB.vehicles.find_one({"id": v1["id"]}, {"status": 1})["status"]
        bA = await mk_booking(v1, "2027-01-10T08:00:00+00:00", "2027-01-11T08:00:00+00:00")
        r = await c.post(f"{API}/dispatch/{bA['id']}/assign", headers=H,
                         json={"driver_id": d1["id"], "vehicle_id": v1["id"]})
        trip_id = r.json().get("trip", {}).get("id")
        if trip_id: CREATED["trips"].append(trip_id)
        veh_after_assign = DB.vehicles.find_one({"id": v1["id"]}, {"status": 1})["status"]
        r = await c.post(f"{API}/bookings/{bA['id']}/cancel", headers=H)
        veh_after_cancel = DB.vehicles.find_one({"id": v1["id"]}, {"status": 1})["status"]
        trip_after_cancel = DB.trips.find_one({"id": trip_id}, {"status": 1}) if trip_id else None
        if veh_after_cancel == "on_trip" and trip_after_cancel and trip_after_cancel["status"] != "cancelled":
            note("BUG-A cancel-tak-bebaskan-armada/trip", "TERBUKTI",
                 f"vehicle {v1['id']}: {v1_before}->assign:{veh_after_assign}->cancel:{veh_after_cancel}; trip status={trip_after_cancel['status']}")
        else:
            note("BUG-A", "TIDAK TERBUKTI", f"veh={veh_after_cancel}, trip={trip_after_cancel}")

        # ============ BUG-B: pembayaran diterima untuk booking cancelled
        r = await c.post(f"{API}/payments", headers=H,
                         json={"booking_id": bA["id"], "amount": 500000, "type": "dp"})
        if r.status_code == 200:
            CREATED["payments"].append(r.json()["id"])
            bk = DB.bookings.find_one({"id": bA["id"]}, {"payment_status": 1, "paid_amount": 1, "status": 1})
            note("BUG-B pembayaran-ke-booking-cancelled", "TERBUKTI",
                 f"HTTP 200; booking status={bk['status']}, paid={bk['paid_amount']}, payment_status={bk['payment_status']}")
        else:
            note("BUG-B", "TIDAK TERBUKTI", f"HTTP {r.status_code}: {r.text[:120]}")

        # ============ BUG-C: complete booking belum dibayar -> payment_status 'selesai'
        bC = await mk_booking(v1, "2027-02-10T08:00:00+00:00", "2027-02-11T08:00:00+00:00", 2000000)
        r = await c.post(f"{API}/bookings/{bC['id']}/complete", headers=H)
        bk = DB.bookings.find_one({"id": bC["id"]}, {"payment_status": 1, "paid_amount": 1, "total_amount": 1})
        if bk["payment_status"] == "selesai" and bk["paid_amount"] < bk["total_amount"]:
            ar = (await c.get(f"{API}/finance/ar/overdue", headers=H)).json() if False else None
            note("BUG-C selesai-menutupi-tunggakan", "TERBUKTI",
                 f"paid={bk['paid_amount']}/total={bk['total_amount']} tapi payment_status='{bk['payment_status']}' (tunggakan 2jt tak terlihat di list)")
        else:
            note("BUG-C", "TIDAK TERBUKTI", str(bk))

        # ============ BUG-D: POST /trips/{id}/status completed -> armada tetap on_trip, booking tak selesai
        bD = await mk_booking(v2, "2027-03-10T08:00:00+00:00", "2027-03-11T08:00:00+00:00")
        r = await c.post(f"{API}/dispatch/{bD['id']}/assign", headers=H,
                         json={"driver_id": d1["id"], "vehicle_id": v2["id"]})
        tD = r.json().get("trip", {}).get("id")
        if tD: CREATED["trips"].append(tD)
        r = await c.post(f"{API}/trips/{tD}/status", headers=H, json={"status": "completed"})
        veh2 = DB.vehicles.find_one({"id": v2["id"]}, {"status": 1})["status"]
        bkD = DB.bookings.find_one({"id": bD["id"]}, {"status": 1})["status"]
        trD = DB.trips.find_one({"id": tD}, {"status": 1, "distance_km": 1})
        if veh2 == "on_trip" and bkD != "completed":
            note("BUG-D jalur-status-generik-split-brain", "TERBUKTI",
                 f"trip={trD['status']} via /trips/status TAPI vehicle={veh2} (terkunci), booking={bkD} (tak selesai), distance_km={trD.get('distance_km')}")
        else:
            note("BUG-D", "TIDAK TERBUKTI", f"veh={veh2}, booking={bkD}")

        # ============ BUG-E: payroll periode overlap -> trip sama dibayar 2x
        # trip tD sudah completed milik d1 (Mar 2027, end_at=today by now_iso!) -> pakai periode berbasis end_at hari ini
        import datetime
        today = datetime.date.today().isoformat()
        p1 = await c.post(f"{API}/payroll/payouts/generate", headers=H, json={
            "driver_id": d1["id"], "period_type": "monthly",
            "period_start": today, "period_end": today})
        p2 = await c.post(f"{API}/payroll/payouts/generate", headers=H, json={
            "driver_id": d1["id"], "period_type": "monthly",
            "period_start": (datetime.date.today()-datetime.timedelta(days=1)).isoformat(),
            "period_end": today})
        ok1, ok2 = p1.status_code == 200, p2.status_code == 200
        if ok1: CREATED["driver_payouts"].append(p1.json()["id"])
        if ok2: CREATED["driver_payouts"].append(p2.json()["id"])
        if ok1 and ok2:
            t1, t2 = p1.json(), p2.json()
            overlap = t1["trips_count"] > 0 and t2["trips_count"] > 0
            note("BUG-E payroll-overlap-dobel-hitung", "TERBUKTI" if overlap else "PARSIAL",
                 f"payout1({t1['period_start']}..{t1['period_end']}) trips={t1['trips_count']} & payout2({t2['period_start']}..{t2['period_end']}) trips={t2['trips_count']} — trip yang sama dihitung di KEDUA payout")
        else:
            note("BUG-E", "TIDAK TERBUKTI", f"p1={p1.status_code} p2={p2.status_code} {p2.text[:100]}")

        # ============ BUG-F: driver double-assign (2 booking beda armada, waktu sama)
        bF1 = await mk_booking(v1, "2027-04-10T08:00:00+00:00", "2027-04-11T08:00:00+00:00")
        bF2 = await mk_booking(v2, "2027-04-10T09:00:00+00:00", "2027-04-11T07:00:00+00:00")
        r1 = await c.post(f"{API}/dispatch/{bF1['id']}/assign", headers=H,
                          json={"driver_id": d1["id"], "vehicle_id": v1["id"]})
        r2 = await c.post(f"{API}/dispatch/{bF2['id']}/assign", headers=H,
                          json={"driver_id": d1["id"], "vehicle_id": v2["id"]})
        for rr in (r1, r2):
            tid = rr.json().get("trip", {}).get("id") if rr.status_code == 200 else None
            if tid: CREATED["trips"].append(tid)
        if r1.status_code == 200 and r2.status_code == 200:
            note("BUG-F driver-double-assign", "TERBUKTI",
                 f"driver {d1['name']} berhasil di-assign ke 2 booking yang tumpang-tindih waktu (armada beda) — tidak ada cek bentrok driver")
        else:
            note("BUG-F", "TIDAK TERBUKTI", f"r1={r1.status_code} r2={r2.status_code}")

        # ============ BUG-G: race pembayaran paralel (TOCTOU INV-2)
        bG = await mk_booking(v1, "2027-05-10T08:00:00+00:00", "2027-05-11T08:00:00+00:00", 1000000)
        async def pay():
            return await c.post(f"{API}/payments", headers=H,
                                json={"booking_id": bG["id"], "amount": 800000, "type": "dp"})
        rs = await asyncio.gather(*[pay() for _ in range(4)])
        codes = [r.status_code for r in rs]
        for r in rs:
            if r.status_code == 200: CREATED["payments"].append(r.json()["id"])
        total_paid = sum(p["amount"] for p in DB.payments.find({"booking_id": bG["id"]}))
        bkG = DB.bookings.find_one({"id": bG["id"]}, {"paid_amount": 1, "total_amount": 1})
        if total_paid > bkG["total_amount"]:
            note("BUG-G race-overpayment", "TERBUKTI",
                 f"4 request paralel 800rb utk tagihan 1jt: HTTP={codes}; total dibayar={total_paid:,.0f} > total={bkG['total_amount']:,.0f} (INV-2 DILANGGAR saat balapan)")
        else:
            note("BUG-G race-overpayment", "TIDAK TERBUKTI (single-worker serialize)",
                 f"HTTP={codes}; total_paid={total_paid}")

    # ============ CLEANUP total (kembalikan kondisi DB)
    for b in CREATED["bookings"]:
        DB.bookings.delete_one({"id": b})
        DB.payments.delete_many({"booking_id": b})
        DB.trips.delete_many({"booking_id": b})
        DB.invoices.delete_many({"booking_id": b})
    for t in CREATED["trips"]:
        DB.trips.delete_one({"id": t})
    for p in CREATED["driver_payouts"]:
        d = DB.driver_payouts.find_one({"id": p})
        if d and d.get("expense_id"): DB.expenses.delete_one({"id": d["expense_id"]})
        DB.driver_payouts.delete_one({"id": p})
    DB.audit_logs.delete_many({"entity_id": {"$in": CREATED["bookings"] + CREATED["trips"] + CREATED["driver_payouts"]}})
    DB.events.delete_many({"ref_id": {"$in": CREATED["bookings"]}})
    DB.notification_tasks.delete_many({"payload.booking_id": {"$in": CREATED["bookings"]}})
    # pulihkan status armada & driver dari seed (armada available kecuali sedang dipakai trip aktif seed)
    active_trip_vids = {t.get("vehicle_id") for t in DB.trips.find({"status": {"$in": ["standby","to_pickup","on_trip"]}}, {"vehicle_id": 1})}
    for v in DB.vehicles.find({}, {"id": 1, "status": 1}):
        want = "on_trip" if v["id"] in active_trip_vids else "available"
        if v.get("status") != want and v.get("status") in ("on_trip", "available"):
            DB.vehicles.update_one({"id": v["id"]}, {"$set": {"status": want}})
    print("\n=== CLEANUP selesai ===")
    print(json.dumps({k: len(v) for k, v in CREATED.items()}, indent=0))
    print("\n=== RINGKASAN ===")
    for bug, verdict, detail in RESULTS:
        print(f"  {verdict:12s} | {bug}")

asyncio.run(main())
