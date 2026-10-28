"""Regresi audit ronde 2 (2026-10-28): alur sopir, fee → keuangan, aturan booking ops.

Bagian atas = fungsi murni. Bagian bawah = API + Mongo (backend hidup + seed demo). Data uji
memakai armada/sopir sementara pada 2031+ dan dihapus di akhir modul.
"""
import io
import os
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import requests
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from services.documents import booking_items  # noqa: E402
from services.events import render_template  # noqa: E402
from services.pricing import compute_quote  # noqa: E402

ENV = {**dotenv_values(ROOT / "backend" / ".env"), **os.environ}
API = (ENV.get("REACT_APP_BACKEND_URL") or "http://127.0.0.1:8001").rstrip("/") + "/api"
RULES = {"weekend_surcharge_percent": 20, "holiday_surcharge_percent": 30, "rounding": 1000,
         "day_rates": {"hiace": 1000000}, "driver_fee_per_day": 0, "toll_parking_per_day": 0}


# ------------------------------------------------------------------ fungsi murni
def test_weekend_surcharge_counts_each_rental_day():
    # Rabu 17 Mar 2027 09:00 WIB, 5 hari (Rab–Min) → Sabtu & Minggu kena surcharge.
    q = compute_quote(RULES, vehicle_type="hiace", days=5, when="2027-03-17T02:00:00Z", holidays=[],
                      include_travel=False)
    assert {"label": "Surcharge akhir pekan (2 hari × +20%)", "amount": 400000} in q["breakdown"]
    # Mulai Sabtu 1 hari → hanya hari itu, bukan semua hari.
    q = compute_quote(RULES, vehicle_type="hiace", days=3, when="2027-03-20T02:00:00Z",
                      holidays=["2027-03-22"], include_travel=False)
    labels = {b["label"]: b["amount"] for b in q["breakdown"]}
    assert labels["Surcharge akhir pekan (2 hari × +20%)"] == 400000
    assert labels["Surcharge hari libur (1 hari × +30%)"] == 300000


def test_invoice_items_follow_price_breakdown():
    bk = {"total_amount": 1205000, "price_breakdown": [
        {"label": "Sewa unit (1 hari)", "amount": 1000000},
        {"label": "Jasa driver (1 hari)", "amount": 250000},
        {"label": "Promo X (−Rp 50.000)", "amount": -50000}]}
    items = booking_items(bk)
    assert [i["amount"] for i in items] == [1000000, 250000, -50000, 5000]  # + pembulatan
    assert sum(i["amount"] for i in items) == 1205000


def test_templates_render_iso_as_wib():
    assert render_template("{t}", {"t": "2026-10-28T09:00:00+00:00"}) == "28 Okt 2026 16.00 WIB"


# ------------------------------------------------------------------ API + Mongo
def _login(email):
    try:
        r = requests.post(f"{API}/auth/login", json={"email": email, "password": "demo12345"}, timeout=20)
    except requests.RequestException:
        pytest.skip("backend tidak hidup")
    if r.status_code != 200:
        pytest.skip(f"login {email} gagal ({r.status_code})")
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture(scope="module")
def owner():
    return _login("owner@demo.local")


@pytest.fixture(scope="module")
def db():
    if not ENV.get("MONGO_URL"):
        pytest.skip("MONGO_URL tidak tersedia")
    from pymongo import MongoClient
    return MongoClient(ENV["MONGO_URL"])[ENV.get("DB_NAME", "test_database")]


@pytest.fixture(scope="module")
def env(db):
    tag = f"tfy{random.randint(10000, 99999)}"
    now = datetime.now(timezone.utc).isoformat()
    vehicles = [{"id": f"veh_{tag}{i}", "name": f"TEST {tag}{i}", "code": f"{tag}{i}".upper(), "type": "hiace",
                 "plate_number": f"T {random.randint(1000, 9999)} F{i}", "capacity": 12, "day_rate": 1200000,
                 "status": "available", "odometer": 1000.0, "created_at": now} for i in (1, 2)]
    drivers = [{"id": f"drv_{tag}{i}", "name": f"Sopir {tag}{i}", "status": "offline", "created_at": now,
                "comp": {"enable_base": False, "enable_commission_trip": True, "commission_per_trip": 50000}}
               for i in (1, 2)]
    db.vehicles.insert_many([dict(v) for v in vehicles])
    db.drivers.insert_many([dict(d) for d in drivers])
    customer = db.customers.find_one({}, {"_id": 0, "id": 1})
    if not customer:
        pytest.skip("seed tanpa customer")
    state = {"tag": tag, "vehicles": vehicles, "drivers": drivers, "customer_id": customer["id"],
             "day": random.randint(0, 2000), "bookings": [], "promos": []}
    yield state
    vids, dids = [v["id"] for v in vehicles], [d["id"] for d in drivers]
    bids = state["bookings"] + [b["id"] for b in db.bookings.find({"vehicle_id": {"$in": vids}}, {"id": 1})]
    db.bookings.delete_many({"id": {"$in": bids}})
    db.trips.delete_many({"$or": [{"booking_id": {"$in": bids}}, {"vehicle_id": {"$in": vids}}]})
    for coll in ("invoices", "payments", "payment_proofs"):
        db[coll].delete_many({"booking_id": {"$in": bids}})
    db.events.delete_many({"ref_id": {"$in": bids}})
    db.notification_tasks.delete_many({"$or": [{"booking_id": {"$in": bids}}, {"ref_id": {"$in": bids}}]})
    db.driver_fee_entries.delete_many({"driver_id": {"$in": dids}})
    wids = [w["id"] for w in db.driver_withdrawals.find({"driver_id": {"$in": dids}}, {"id": 1})]
    db.driver_withdrawals.delete_many({"driver_id": {"$in": dids}})
    db.media_assets.delete_many({"source": "withdrawal", "created_at": {"$gte": now}})
    db.driver_payouts.delete_many({"driver_id": {"$in": dids}})
    db.expenses.delete_many({"$or": [{"driver_id": {"$in": dids}}, {"booking_id": {"$in": bids}},
                                     {"withdrawal_id": {"$in": wids}}]})
    db.promos.delete_many({"id": {"$in": state["promos"]}})
    db.vehicles.delete_many({"id": {"$in": vids}})
    db.drivers.delete_many({"id": {"$in": dids}})


def _window(env, days=1, start=None):
    env["day"] += 7
    start = start or datetime(2031, 1, 7, 2, 0, tzinfo=timezone.utc) + timedelta(days=env["day"])
    return start.isoformat(), (start + timedelta(days=days)).isoformat()


def _booking(owner, env, vehicle=0, days=1, base_price=1000000, start=None, **extra):
    s, e = _window(env, days, start)
    r = requests.post(f"{API}/bookings", headers=owner, timeout=30, json={
        "customer_id": env["customer_id"], "vehicle_id": env["vehicles"][vehicle]["id"],
        "start_datetime": s, "end_datetime": e, "base_price": base_price, **extra})
    assert r.status_code == 200, r.text
    env["bookings"].append(r.json()["id"])
    return r.json()


def _assign(owner, env, bk, driver=0, vehicle=0, fee=None):
    body = {"driver_id": env["drivers"][driver]["id"], "vehicle_id": env["vehicles"][vehicle]["id"]}
    if fee:
        body["driver_fee_rate"] = fee
    r = requests.post(f"{API}/dispatch/{bk['id']}/assign", headers=owner, json=body, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["trip"]


def _status(owner, trip_id, status):
    return requests.post(f"{API}/trips/{trip_id}/status", headers=owner, json={"status": status}, timeout=30)


def test_driver_steps_follow_phase_order(owner, env, db):
    bk = _booking(owner, env)
    trip = _assign(owner, env, bk)
    vid = env["vehicles"][0]["id"]
    assert db.vehicles.find_one({"id": vid})["status"] == "available", "assign tidak boleh membuat unit on_trip"
    # Belum berangkat: selesai / tiba / POD ditolak.
    assert requests.post(f"{API}/driver/checkout", headers=owner, json={"trip_id": trip["id"]}, timeout=20).status_code == 400
    assert requests.post(f"{API}/dispatch/trips/{trip['id']}/arrived", headers=owner, timeout=20).status_code == 400
    assert requests.post(f"{API}/dispatch/trips/{trip['id']}/pod", headers=owner, data={"recipient_name": "x"},
                         timeout=20).status_code == 400
    # Berangkat lewat tombol ops → booking 'ongoing', WA enroute, unit dipakai, notifikasi ops.
    assert requests.post(f"{API}/dispatch/trips/{trip['id']}/enroute", headers=owner, timeout=20).status_code == 200
    assert db.bookings.find_one({"id": bk["id"]})["status"] == "ongoing"
    assert db.vehicles.find_one({"id": vid})["status"] == "on_trip"
    assert db.events.count_documents({"type": "trip.enroute", "ref_id": bk["id"]}) == 1
    assert db.notification_tasks.find_one({"dedupe_key": f"trip-started:{trip['id']}"})
    assert _status(owner, trip["id"], "standby").status_code == 400  # tidak boleh mundur
    assert _status(owner, trip["id"], "on_trip").status_code == 200
    t = db.trips.find_one({"id": trip["id"]})
    assert t.get("enroute_at") and t.get("start_at")  # timeline: berangkat jemput & penumpang naik
    # POD dari Dispatch TIDAK menyelesaikan trip lagi.
    r = requests.post(f"{API}/dispatch/trips/{trip['id']}/pod", headers=owner, data={"recipient_name": "Budi"}, timeout=20)
    assert r.status_code == 200 and r.json()["status"] == "on_trip", r.text
    r = requests.post(f"{API}/driver/checkout", headers=owner, timeout=20,
                      json={"trip_id": trip["id"], "odometer_end": 900})
    assert r.status_code == 400, "odometer akhir < odometer armada harus ditolak"
    requests.post(f"{API}/driver/checkin", headers=owner, json={"trip_id": trip["id"], "odometer_start": 1000}, timeout=20)
    r = requests.post(f"{API}/driver/checkout", headers=owner, timeout=20,
                      json={"trip_id": trip["id"], "odometer_end": 990})
    assert r.status_code == 400, "odometer akhir < awal harus ditolak"
    r = requests.post(f"{API}/driver/checkout", headers=owner, json={"trip_id": trip["id"], "odometer_end": 1170}, timeout=20)
    assert r.status_code == 200 and r.json()["distance_km"] == 170, r.text
    # Checkout ulang pada trip selesai tidak menimpa km/odometer.
    r = requests.post(f"{API}/driver/checkout", headers=owner, json={"trip_id": trip["id"], "odometer_end": 5000}, timeout=20)
    assert r.status_code == 200 and r.json()["distance_km"] == 170
    assert db.vehicles.find_one({"id": vid})["odometer"] == 1170


def test_reassign_driver_moves_trip(owner, env, db):
    bk = _booking(owner, env)
    trip = _assign(owner, env, bk, driver=0)
    r = requests.patch(f"{API}/bookings/{bk['id']}", headers=owner, json={"driver_id": env["drivers"][1]["id"]}, timeout=20)
    assert r.status_code == 200, r.text
    assert db.trips.find_one({"id": trip["id"]})["driver_id"] == env["drivers"][1]["id"]
    assert _status(owner, trip["id"], "on_trip").status_code == 200
    r = requests.patch(f"{API}/bookings/{bk['id']}", headers=owner, json={"driver_id": env["drivers"][0]["id"]}, timeout=20)
    assert r.status_code == 400, "sopir tidak boleh diganti di tengah perjalanan"


def test_driver_only_sees_own_trips(db):
    drv = _login("driver@demo.local")
    r = requests.get(f"{API}/trips", headers=drv, timeout=20)
    assert r.status_code == 200
    user = db.users.find_one({"email": "driver@demo.local"}, {"_id": 0, "id": 1})
    me = db.drivers.find_one({"user_id": user["id"]}, {"_id": 0, "id": 1}) if user else None
    assert all(t.get("driver_id") == (me or {}).get("id") for t in r.json())
    assert all("revenue" not in t for t in r.json())
    other = db.trips.find_one({"driver_id": {"$ne": (me or {}).get("id")}}, {"_id": 0, "id": 1})
    if other:
        assert requests.get(f"{API}/trips/{other['id']}", headers=drv, timeout=20).status_code == 404


def test_complete_requires_started_confirmed_booking(owner, env):
    future = _booking(owner, env)
    r = requests.post(f"{API}/bookings/{future['id']}/complete", headers=owner, timeout=20)
    assert r.status_code == 400 and "belum dimulai" in r.text
    hold = _booking(owner, env, require_dp=True)
    r = requests.post(f"{API}/bookings/{hold['id']}/complete", headers=owner, timeout=20)
    assert r.status_code == 400 and "DP" in r.text


def test_reject_stores_reason_and_returns_promo(owner, env, db):
    promo_id = f"pro_{env['tag']}"
    env["promos"].append(promo_id)
    db.promos.insert_one({"id": promo_id, "code": env["tag"].upper(), "used_count": 1, "max_uses": 5,
                          "discount_type": "amount", "discount_value": 1000, "active": False})
    hold = _booking(owner, env, require_dp=True)
    db.bookings.update_one({"id": hold["id"]}, {"$set": {"promo_id": promo_id}})
    r = requests.post(f"{API}/bookings/{hold['id']}/reject", headers=owner, json={"reason": "Unit penuh"}, timeout=20)
    assert r.status_code == 200, r.text
    assert db.bookings.find_one({"id": hold["id"]})["cancellation_reason"] == "Unit penuh"
    assert db.promos.find_one({"id": promo_id})["used_count"] == 0
    paid = _booking(owner, env, require_dp=True)
    requests.post(f"{API}/payments", headers=owner, json={"booking_id": paid["id"], "amount": 10000, "type": "dp"}, timeout=20)
    assert requests.post(f"{API}/bookings/{paid['id']}/reject", headers=owner, json={}, timeout=20).status_code == 400


def test_cancel_requires_retained_money_to_match_fee(owner, env, db):
    bk = _booking(owner, env)
    requests.post(f"{API}/payments", headers=owner, json={"booking_id": bk["id"], "amount": 500000, "type": "dp"}, timeout=20)
    r = requests.post(f"{API}/bookings/{bk['id']}/cancel", headers=owner, timeout=20,
                      json={"cancellation_fee": 300000, "refund_amount": 100000})
    assert r.status_code == 400 and "200.000" in r.text, r.text  # saran refund = 500rb − 300rb
    db.payment_proofs.insert_one({"id": f"ppf_{env['tag']}", "booking_id": bk["id"], "status": "pending"})
    r = requests.post(f"{API}/bookings/{bk['id']}/cancel", headers=owner, timeout=20,
                      json={"cancellation_fee": 300000, "refund_amount": 200000})
    assert r.status_code == 400 and "bukti" in r.text.lower()


def test_fee_is_accrued_on_trip_and_settled_by_withdrawal(owner, env, db):
    bk = _booking(owner, env, start=datetime.now(timezone.utc) - timedelta(hours=3))
    trip = _assign(owner, env, bk, driver=1, vehicle=1, fee=150000)
    assert _status(owner, trip["id"], "on_trip").status_code == 200
    assert _status(owner, trip["id"], "completed").status_code == 200
    exp = db.expenses.find_one({"trip_id": trip["id"], "source": "driver_fee"})
    assert exp and exp["amount"] == 150000 and exp["paid"] is False and exp["vehicle_id"] == env["vehicles"][1]["id"]
    assert db.trips.find_one({"id": trip["id"]})["profit"] is not None  # laba trip ikut fee sopir
    assert requests.delete(f"{API}/expenses/{exp['id']}", headers=owner, timeout=20).status_code == 400
    # Payroll: trip ber-fee tidak diberi komisi/trip lagi.
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    r = requests.post(f"{API}/payroll/payouts/generate", headers=owner, timeout=20, json={
        "driver_id": env["drivers"][1]["id"], "period_type": "monthly",
        "period_start": f"{month}-01", "period_end": f"{month}-28"})
    assert r.status_code == 200, r.text
    assert r.json()["commission_trip"] == 0 and r.json()["fee_trips_count"] == 1
    # Pencairan: tidak membuat expense baru, melunasi akrual, tercatat di arus kas.
    did = env["drivers"][1]["id"]
    r = requests.post(f"{API}/driver/fees/withdraw", headers=owner, timeout=20, json={
        "driver_id": did, "amount": 150000, "bank_name": "BCA", "account_number": "123", "account_name": "Uji"})
    assert r.status_code == 200, r.text
    before = db.expenses.count_documents({"driver_id": did})
    png = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
           b"\x00\x00\x00\rIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82")
    r = requests.post(f"{API}/payroll/withdrawals/{r.json()['id']}/pay", headers=owner, timeout=30,
                      files={"proof": ("bukti.png", io.BytesIO(png), "image/png")})
    assert r.status_code == 200, r.text
    assert db.expenses.count_documents({"driver_id": did}) == before, "pencairan tidak boleh membuat expense dobel"
    assert db.expenses.find_one({"id": exp["id"]})["paid"] is True
    cf = requests.get(f"{API}/finance/cashflow?months=1&horizon=1", headers=owner, timeout=30).json()
    assert cf["months"][-1]["cash_out"] >= 150000


def test_finance_header_matches_profit_and_loss(owner):
    s = requests.get(f"{API}/finance/summary", headers=owner, timeout=30).json()
    pl = requests.get(f"{API}/finance/pl-full", headers=owner, timeout=30).json()
    assert s["profit"] == pl["profit"] and s["expenses"] == pl["total_cost"]


def test_public_status_rules(owner, env, db):
    hold = _booking(owner, env, require_dp=True)
    token = f"tok{env['tag']}"
    db.bookings.update_one({"id": hold["id"]}, {"$set": {"public_token": token}})
    db.payment_proofs.insert_one({"id": f"ppf_{env['tag']}h", "booking_id": hold["id"], "status": "pending",
                                  "created_at": datetime.now(timezone.utc).isoformat()})
    r = requests.get(f"{API}/public/booking/{hold['code']}?token={token}", timeout=20)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["dp_required"] is True and body["can_cancel"] is False and body["cancel_blocked_reason"]
