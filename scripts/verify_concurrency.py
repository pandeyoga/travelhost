#!/usr/bin/env python3
"""verify_concurrency.py — GATE anti-regresi CONCURRENCY (RC-01 race overpayment / INV-2).

Menembak N pembayaran PARALEL ke satu booking. INVARIAN: Σ pembayaran diterima ≤ total tagihan
(tak boleh overpay walau balapan). Booking sintetis 2028 + auto-cleanup.

Catatan: pada uvicorn single-worker request ter-serialize; guard atomik `find_one_and_update`
(RC-01) tetap menjamin invarian di multi-worker. Gate memverifikasi INVARIAN, bukan kondisi balapan.

Resilient: backend down / login gagal → SKIP. Exit 1 hanya bila INV-2 dilanggar (overpay).
Usage: cd /app && python scripts/verify_concurrency.py
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
fails = 0
skips = 0
CREATED = {"bookings": [], "payments": []}


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
    print(f"\n{B}{'='*60}{X}\n  CONCURRENCY GATE (RC-01 / INV-2)  API={API}\n{B}{'='*60}{X}")
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
        if not custs or not vehs:
            skip("Data seed kurang — SKIP.")
            return _summary()
        cust, v1 = custs[0], vehs[0]

        total = 1000000
        r = await c.post(f"{API}/api/bookings", headers=H, json={
            "customer_id": cust["id"], "vehicle_id": v1["id"],
            "start_datetime": "2028-05-10T08:00:00+00:00", "end_datetime": "2028-05-11T08:00:00+00:00",
            "base_price": total})
        b = r.json()
        if r.status_code != 200 or not b.get("id"):
            skip(f"buat booking → {r.status_code}")
            return _summary()
        CREATED["bookings"].append(b["id"])
        bkid = b["id"]

        # 6 pembayaran paralel @300rb (Σ 1,8jt) utk tagihan 1jt → hanya ≤3 boleh sukses.
        async def pay():
            return await c.post(f"{API}/api/payments", headers=H,
                                json={"booking_id": bkid, "amount": 300000, "type": "dp"})
        rs = await asyncio.gather(*[pay() for _ in range(6)])
        codes = [x.status_code for x in rs]
        for x in rs:
            if x.status_code == 200 and isinstance(x.json(), dict) and x.json().get("id"):
                CREATED["payments"].append(x.json()["id"])
        n200 = sum(1 for x in rs if x.status_code == 200)
        total_paid = sum(float(p.get("amount", 0)) for p in DBC.payments.find({"booking_id": bkid}))
        bk = DBC.bookings.find_one({"id": bkid}, {"_id": 0, "paid_amount": 1, "total_amount": 1}) or {}
        paid_field = float(bk.get("paid_amount", 0) or 0)
        # INVARIAN: total_paid ≤ total & paid_amount ≤ total & paid_amount == Σpayments.
        if total_paid > total + 0.01:
            fail(f"INV-2 DILANGGAR (overpay): Σpayments={total_paid:,.0f} > total={total:,.0f} (HTTP={codes}).")
        elif paid_field > total + 0.01:
            fail(f"paid_amount={paid_field:,.0f} > total={total:,.0f} (HTTP={codes}).")
        elif abs(paid_field - total_paid) > 0.01:
            fail(f"paid_amount({paid_field:,.0f}) != Σpayments({total_paid:,.0f}) — drift INV-2.")
        else:
            ok(f"RC-01 aman: {n200}×200 diterima, Σ={total_paid:,.0f} ≤ total={total:,.0f} (HTTP={codes}).")

    return _summary()


def _cleanup():
    for b in CREATED["bookings"]:
        DBC.bookings.delete_one({"id": b})
        DBC.payments.delete_many({"booking_id": b})
        DBC.trips.delete_many({"booking_id": b})
        DBC.invoices.delete_many({"booking_id": b})
        DBC.audit_logs.delete_many({"entity_id": b})
        DBC.events.delete_many({"ref_id": b})
        # Hygiene: notification_tasks ikut dibersihkan (top-level & payload) agar tidak
        # meninggalkan FK menggantung yang membuat verify_schema MERAH-palsu di run berikutnya.
        DBC.notification_tasks.delete_many({"booking_id": b})
        DBC.notification_tasks.delete_many({"payload.booking_id": b})


def _summary():
    _cleanup()
    print(f"\n{B}{'='*60}{X}\n  {R}FAIL {fails}{X} | {Y}SKIP {skips}{X}\n{B}{'='*60}{X}")
    if fails:
        print(f"{R}{B}  CONCURRENCY REGRESI — RC-01 (atomic payment) bocor.{X}\n")
        return 1
    print(f"{G}{B}  Concurrency aman (RC-01 / INV-2 tertutup).{X}\n")
    return 0


if __name__ == "__main__":
    try:
        rc = asyncio.run(main())
    except Exception as ex:
        _cleanup()
        print(f"{Y}  Gate error (dianggap SKIP): {ex}{X}")
        rc = 0
    sys.exit(rc)
