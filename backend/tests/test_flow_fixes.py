"""Regresi audit flow pembelian · set harga · armada · keuangan (2026-10-28).

Bagian atas = fungsi murni (tanpa server). Bagian bawah = API + Mongo: butuh backend hidup +
seed demo (owner/ops @demo.local, pass demo12345). Semua data uji memakai armada/driver/promo
sementara di tahun 2031+ dan dihapus lagi di akhir modul.
"""
import json
import os
import random
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import requests
from dotenv import dotenv_values
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from core_utils import money  # noqa: E402
from routers.invoices import _compute  # noqa: E402
from schemas import BookingCreate  # noqa: E402
from services import promos  # noqa: E402
from services.booking_flow import hold_fields  # noqa: E402
from services.documents import invoice_paid_portion  # noqa: E402
from services.geo import parse_iso  # noqa: E402
from services.pricing import _surcharge_for_date, compute_quote  # noqa: E402

ENV = {**dotenv_values(ROOT / "backend" / ".env"), **os.environ}
API = (ENV.get("REACT_APP_BACKEND_URL") or "http://127.0.0.1:8001").rstrip("/") + "/api"
RULES = {"weekend_surcharge_percent": 20, "holiday_surcharge_percent": 30, "rounding": 1000,
         "day_rates": {"hiace": 1200000}, "driver_fee_per_day": 250000, "dp_percent": 30}


# ------------------------------------------------------------------ fungsi murni
def test_surcharge_uses_wib_calendar():
    # Sabtu 06:00 WIB = Jumat 23:00 UTC → tetap akhir pekan; Senin 05:00 WIB = Minggu 22:00 UTC.
    assert _surcharge_for_date(RULES, parse_iso("2026-10-30T23:00:00Z"), [])[0] == 20
    assert _surcharge_for_date(RULES, parse_iso("2026-11-01T22:00:00Z"), [])[0] == 0
    assert _surcharge_for_date(RULES, parse_iso("2026-12-24T18:00:00Z"), ["2026-12-25"])[0] == 30


def test_promo_weekend_and_validity_use_wib():
    p = {"code": "W", "discount_type": "amount", "discount_value": 50000, "weekend_only": True}
    kw = dict(subtotal=500000, days=1, vehicle_type="hiace", service="daily_rental")
    assert promos.evaluate(p, start_dt=parse_iso("2026-10-30T23:00:00Z"), **kw) == 50000
    with pytest.raises(promos.PromoError):
        promos.evaluate(p, start_dt=parse_iso("2026-11-01T22:00:00Z"), **kw)
    last_day = {"code": "L", "discount_type": "amount", "discount_value": 1, "valid_until": "2026-10-30"}
    assert promos.evaluate(last_day, now=parse_iso("2026-10-30T16:00:00Z"), **kw) == 1  # 23:00 WIB
    with pytest.raises(promos.PromoError):
        promos.evaluate(last_day, now=parse_iso("2026-10-30T17:30:00Z"), **kw)  # 31 Okt 00:30 WIB


def test_quote_dp_equals_stored_hold_dp():
    q = compute_quote(RULES, vehicle_type="hiace", days=1, when="2026-11-03T02:00:00Z", holidays=[],
                      include_travel=True, day_rate=1205000)
    stored = hold_fields(total=q["total"], dp_percent=30, hold_hours=24, rounding=RULES["rounding"])
    assert stored["dp_amount"] == q["dp_amount"]


def test_invoice_dp_respects_zero_percent_and_caps():
    cfg = {"dp_percent_default": 30}
    calc = _compute({"total_amount": 1000000, "paid_amount": 0, "dp_percent": 0}, cfg, "dp", None, None)
    assert calc["dp_percent"] == 0 and calc["dp_amount"] == 0
    calc = _compute({"total_amount": 1000000, "paid_amount": 0}, cfg, "dp", None, 5_000_000)
    assert calc["dp_amount"] == 1000000  # DP tak boleh melebihi total


def test_non_finite_and_huge_numbers_rejected():
    base = {"customer_id": "c", "vehicle_id": "v", "start_datetime": "x", "end_datetime": "y"}
    for bad in (float("inf"), float("nan"), 1e30):
        with pytest.raises(ValidationError):
            BookingCreate(**base, base_price=bad)
    assert money(float("inf")) == 0  # pertahanan lapis dua: tidak lagi OverflowError → 500


def test_invoice_allocation_per_range():
    dp = {"paid_before": 0, "amount": 300000}
    settle = {"paid_before": 300000, "amount": 700000}
    assert invoice_paid_portion(dp, 1000000) == 300000
    assert invoice_paid_portion(settle, 1000000) == 700000
    assert invoice_paid_portion(settle, 200000) == 0


# ------------------------------------------------------------------ API + Mongo
def _login(email):
    try:
        r = requests.post(f"{API}/auth/login", json={"email": email, "password": "demo12345"}, timeout=20)
    except requests.RequestException:
        pytest.skip("backend tidak hidup")
    if r.status_code != 200:
        pytest.skip(f"login {email} gagal ({r.status_code}) — seed demo belum ada?")
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture(scope="module")
def owner():
    return _login("owner@demo.local")


@pytest.fixture(scope="module")
def ops():
    return _login("ops@demo.local")


@pytest.fixture(scope="module")
def db():
    if not ENV.get("MONGO_URL"):
        pytest.skip("MONGO_URL tidak tersedia")
    from pymongo import MongoClient
    return MongoClient(ENV["MONGO_URL"])[ENV.get("DB_NAME", "test_database")]


@pytest.fixture(scope="module")
def env(db):
    """Armada + driver + promo sementara; semua booking/trip/invoice/payment uji dibersihkan."""
    tag = f"tfx{random.randint(10000, 99999)}"
    now = datetime.now(timezone.utc).isoformat()
    vehicle = {"id": f"veh_{tag}", "name": f"TEST {tag}", "code": tag.upper(), "type": "hiace",
               "plate_number": f"T {random.randint(1000, 9999)} FX", "capacity": 12, "day_rate": 1200000,
               "status": "available", "odometer": 1000.0, "created_at": now}
    driver = {"id": f"drv_{tag}", "name": f"Driver {tag}", "status": "offline", "created_at": now}
    db.vehicles.insert_one(dict(vehicle))
    db.drivers.insert_one(dict(driver))
    customer = db.customers.find_one({}, {"_id": 0, "id": 1})
    if not customer:
        pytest.skip("seed tanpa customer")
    state = {"tag": tag, "vehicle": vehicle, "driver": driver, "customer_id": customer["id"],
             "day": random.randint(0, 2000), "bookings": [], "promos": []}
    yield state
    bids = state["bookings"] + [b["id"] for b in db.bookings.find({"vehicle_id": vehicle["id"]}, {"id": 1})]
    db.bookings.delete_many({"id": {"$in": bids}})
    db.trips.delete_many({"$or": [{"booking_id": {"$in": bids}}, {"vehicle_id": vehicle["id"]}]})
    db.invoices.delete_many({"booking_id": {"$in": bids}})
    db.payments.delete_many({"booking_id": {"$in": bids}})
    db.events.delete_many({"ref_id": {"$in": bids}})
    db.notification_tasks.delete_many({"dedupe_key": {"$regex": "|".join(bids) or "^$"}})
    db.maintenance_records.delete_many({"vehicle_id": vehicle["id"]})
    db.driver_fee_entries.delete_many({"driver_id": driver["id"]})
    db.driver_withdrawals.delete_many({"driver_id": driver["id"]})
    db.driver_payouts.delete_many({"driver_id": driver["id"]})
    db.expenses.delete_many({"$or": [{"driver_id": driver["id"]}, {"booking_id": {"$in": bids}}]})
    db.promos.delete_many({"id": {"$in": state["promos"]}})
    db.vehicles.delete_one({"id": vehicle["id"]})
    db.drivers.delete_one({"id": driver["id"]})


def _window(env, days=1):
    """Jendela unik per panggilan (2031+, Selasa 09:00 WIB) supaya uji tidak saling bentrok."""
    env["day"] += 7
    start = datetime(2031, 1, 7, 2, 0, tzinfo=timezone.utc) + timedelta(days=env["day"])
    return start.isoformat(), (start + timedelta(days=days)).isoformat()


def _booking(owner, env, days=1, base_price=1000000, **extra):
    s, e = _window(env, days)
    r = requests.post(f"{API}/bookings", headers=owner, timeout=30, json={
        "customer_id": env["customer_id"], "vehicle_id": env["vehicle"]["id"],
        "start_datetime": s, "end_datetime": e, "base_price": base_price, **extra})
    assert r.status_code == 200, r.text
    env["bookings"].append(r.json()["id"])
    return r.json()


def test_confirm_rejects_cancelled_and_is_idempotent(owner, env):
    bk = _booking(owner, env)
    assert requests.post(f"{API}/bookings/{bk['id']}/confirm", headers=owner, timeout=20).status_code == 200
    requests.post(f"{API}/bookings/{bk['id']}/cancel", headers=owner, json={}, timeout=20)
    r = requests.post(f"{API}/bookings/{bk['id']}/confirm", headers=owner, timeout=20)
    assert r.status_code == 400, "booking batal tidak boleh dihidupkan lagi lewat confirm"


def test_parallel_cancel_posts_refund_once_and_voids_open_invoices(owner, env, db):
    bk = _booking(owner, env)
    r = requests.post(f"{API}/payments", headers=owner, timeout=20,
                      json={"booking_id": bk["id"], "amount": 500000, "type": "dp"})
    assert r.status_code == 200, r.text
    inv = requests.post(f"{API}/invoices", headers=owner, timeout=20,
                        json={"booking_id": bk["id"], "kind": "settlement"})
    assert inv.status_code == 200, inv.text
    body = {"reason": "uji paralel", "refund_amount": 200000, "cancellation_fee": 100000}
    with ThreadPoolExecutor(4) as ex:
        codes = [f.result().status_code for f in [ex.submit(
            requests.post, f"{API}/bookings/{bk['id']}/cancel", headers=owner, json=body, timeout=30)
            for _ in range(4)]]
    assert all(c == 200 for c in codes), codes
    assert db.payments.count_documents({"booking_id": bk["id"], "type": "refund"}) == 1
    fee = list(db.invoices.find({"booking_id": bk["id"], "type": "cancellation_fee"}))
    assert len(fee) == 1 and fee[0]["status"] == "paid"  # ditahan 300rb ≥ denda 100rb
    assert db.invoices.find_one({"id": inv.json()["id"]})["status"] == "void"


def test_unpaid_cancellation_fee_is_not_marked_paid(owner, env, db):
    bk = _booking(owner, env)
    r = requests.post(f"{API}/bookings/{bk['id']}/cancel", headers=owner, timeout=20,
                      json={"reason": "uji", "cancellation_fee": 50000})
    assert r.status_code == 200, r.text
    fee = db.invoices.find_one({"booking_id": bk["id"], "type": "cancellation_fee"})
    assert fee["status"] == "sent" and not fee.get("paid_at")


def test_reschedule_reprices_unless_kept(owner, env):
    bk = _booking(owner, env, days=1, base_price=0)  # harga dari tarif
    s, e = _window(env, days=3)
    r = requests.post(f"{API}/bookings/{bk['id']}/reschedule", headers=owner, timeout=30,
                      json={"start_datetime": s, "end_datetime": e})
    assert r.status_code == 200, r.text
    longer = r.json()
    assert longer["total_amount"] > bk["total_amount"], "3 hari harus lebih mahal dari 1 hari"
    assert longer["base_price"] + sum(a["amount"] for a in longer.get("add_ons") or []) == longer["total_amount"]
    s2, e2 = _window(env, days=1)
    r = requests.post(f"{API}/bookings/{bk['id']}/reschedule", headers=owner, timeout=30,
                      json={"start_datetime": s2, "end_datetime": e2, "reprice": False})
    assert r.status_code == 200 and r.json()["total_amount"] == longer["total_amount"]


def test_assign_rejects_sold_and_maintenance_vehicle(owner, env, db):
    bk = _booking(owner, env)
    vid, did = env["vehicle"]["id"], env["driver"]["id"]
    try:
        db.vehicles.update_one({"id": vid}, {"$set": {"status": "sold"}})
        r = requests.post(f"{API}/dispatch/{bk['id']}/assign", headers=owner, timeout=30,
                          json={"driver_id": did, "vehicle_id": vid})
        assert r.status_code == 400, r.text
        db.vehicles.update_one({"id": vid}, {"$set": {"status": "available"}})
        db.maintenance_records.insert_one({
            "id": f"mnt_{env['tag']}", "vehicle_id": vid, "status": "scheduled", "title": "uji",
            "start_date": bk["start_datetime"], "end_date": bk["end_datetime"],
            "scheduled_date": bk["start_datetime"][:10], "created_at": bk["start_datetime"]})
        r = requests.post(f"{API}/dispatch/{bk['id']}/assign", headers=owner, timeout=30,
                          json={"driver_id": did, "vehicle_id": vid})
        assert r.status_code == 400 and "perawatan" in r.text, r.text
    finally:
        db.vehicles.update_one({"id": vid}, {"$set": {"status": "available"}})
        db.maintenance_records.delete_many({"vehicle_id": vid})


def test_trip_completion_keeps_held_vehicle_and_cannot_reopen(owner, env, db):
    bk = _booking(owner, env)
    vid, did = env["vehicle"]["id"], env["driver"]["id"]
    r = requests.post(f"{API}/dispatch/{bk['id']}/assign", headers=owner, timeout=30,
                      json={"driver_id": did, "vehicle_id": vid, "driver_fee_rate": 100000})
    assert r.status_code == 200, r.text
    trip = r.json()["trip"]
    assert "origin_lat" in trip and "origin_lng" in trip  # titik jemput disimpan utk geofence
    db.vehicles.update_one({"id": vid}, {"$set": {"status": "maintenance"}})  # unit ditarik bengkel
    try:
        with ThreadPoolExecutor(3) as ex:
            codes = [f.result().status_code for f in [ex.submit(
                requests.post, f"{API}/trips/{trip['id']}/status", headers=owner,
                json={"status": "completed"}, timeout=30) for _ in range(3)]]
        assert all(c == 200 for c in codes), codes
        assert db.vehicles.find_one({"id": vid})["status"] == "maintenance"
        assert db.driver_fee_entries.count_documents({"trip_id": trip["id"]}) == 1
        r = requests.post(f"{API}/trips/{trip['id']}/status", headers=owner, json={"status": "on_trip"}, timeout=20)
        assert r.status_code == 400, "trip selesai tidak boleh mundur ke on_trip"
    finally:
        db.vehicles.update_one({"id": vid}, {"$set": {"status": "available"}})


def test_checkin_and_pod_rejected_on_cancelled_booking(owner, env):
    bk = _booking(owner, env)
    vid, did = env["vehicle"]["id"], env["driver"]["id"]
    trip = requests.post(f"{API}/dispatch/{bk['id']}/assign", headers=owner, timeout=30,
                         json={"driver_id": did, "vehicle_id": vid}).json()["trip"]
    requests.post(f"{API}/bookings/{bk['id']}/cancel", headers=owner, json={}, timeout=20)
    r = requests.post(f"{API}/driver/checkin", headers=owner, json={"trip_id": trip["id"]}, timeout=20)
    assert r.status_code == 400, r.text
    r = requests.post(f"{API}/dispatch/trips/{trip['id']}/pod", headers=owner,
                      data={"recipient_name": "x"}, timeout=20)
    assert r.status_code == 400, r.text
    r = requests.post(f"{API}/dispatch/trips/{trip['id']}/enroute", headers=owner, timeout=20)
    assert r.status_code == 400, r.text


def test_odometer_never_decreases_for_ops(owner, ops, env):
    vid = env["vehicle"]["id"]
    r = requests.patch(f"{API}/vehicles/{vid}", headers=ops, json={"odometer": 10}, timeout=20)
    assert r.status_code == 400, r.text
    r = requests.patch(f"{API}/vehicles/{vid}", headers=owner, json={"odometer": 1000}, timeout=20)
    assert r.status_code == 200, r.text


def test_invoice_amount_capped_and_status_transitions(owner, env):
    bk = _booking(owner, env)
    r = requests.post(f"{API}/invoices", headers=owner, timeout=20,
                      json={"booking_id": bk["id"], "kind": "full", "amount": bk["total_amount"] + 1})
    assert r.status_code == 400, r.text
    inv = requests.post(f"{API}/invoices", headers=owner, timeout=20,
                        json={"booking_id": bk["id"], "kind": "full"}).json()
    assert set(inv["next_status"]) == {"sent", "void"}
    assert requests.patch(f"{API}/invoices/{inv['id']}", headers=owner, json={"status": "partial"},
                          timeout=20).status_code == 400


def test_reconciliation_allocates_payments_per_invoice(owner, env):
    bk = _booking(owner, env)
    dp = requests.post(f"{API}/invoices", headers=owner, timeout=20,
                       json={"booking_id": bk["id"], "kind": "dp", "dp_percent": 30}).json()
    requests.post(f"{API}/payments", headers=owner, timeout=20,
                  json={"booking_id": bk["id"], "amount": dp["amount"], "type": "dp"})
    st = requests.post(f"{API}/invoices", headers=owner, timeout=20,
                       json={"booking_id": bk["id"], "kind": "settlement"}).json()
    requests.post(f"{API}/payments", headers=owner, timeout=20,
                  json={"booking_id": bk["id"], "amount": st["amount"], "type": "settlement"})
    rec = requests.get(f"{API}/finance/reconciliation", headers=owner, timeout=30)
    assert rec.status_code == 200, rec.text
    mine = {i["invoice_id"]: i for i in rec.json()["items"] if i["booking_id"] == bk["id"]}
    assert mine[dp["id"]]["recon_status"] == "lunas" and mine[dp["id"]]["paid"] == dp["amount"]
    assert mine[st["id"]]["recon_status"] == "lunas"


def test_hold_expiry_respects_pending_proof_and_releases_promo(owner, env, db):
    past = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    promo_id = f"pro_{env['tag']}"
    env["promos"].append(promo_id)
    db.promos.insert_one({"id": promo_id, "code": env["tag"].upper(), "discount_type": "amount",
                          "discount_value": 1000, "max_uses": 5, "used_count": 1, "active": False})
    s, e = _window(env)
    base = {"customer_id": env["customer_id"], "vehicle_id": env["vehicle"]["id"], "status": "hold",
            "start_datetime": s, "end_datetime": e, "hold_expires_at": past, "total_amount": 1000000,
            "paid_amount": 0, "created_at": past}
    pending, plain = f"bk_{env['tag']}_p", f"bk_{env['tag']}_n"
    env["bookings"] += [pending, plain]
    db.bookings.insert_many([{**base, "id": pending, "code": "TP", "proof_status": "pending"},
                             {**base, "id": plain, "code": "TN", "promo_id": promo_id}])
    r = requests.post(f"{API}/notifications/scan", headers=owner, timeout=60)
    assert r.status_code == 200, r.text
    assert db.bookings.find_one({"id": pending})["status"] == "hold", "bukti DP pending tak boleh hangus"
    assert db.bookings.find_one({"id": plain})["status"] == "cancelled"
    assert db.promos.find_one({"id": promo_id})["used_count"] == 0, "kuota promo harus kembali"


def test_parallel_withdrawals_cannot_exceed_balance(owner, env, db):
    did = env["driver"]["id"]
    db.driver_fee_entries.insert_one({"id": f"dfe_{env['tag']}", "driver_id": did, "trip_id": f"trp_{env['tag']}",
                                      "amount": 100000, "status": "earned"})
    available = requests.get(f"{API}/driver/fees?driver_id={did}", headers=owner, timeout=20).json()["available"]
    body = {"driver_id": did, "amount": available // 2 + 1, "bank_name": "BCA", "account_number": "123",
            "account_name": "Uji"}  # dua pengajuan sekaligus pasti melebihi saldo
    with ThreadPoolExecutor(5) as ex:
        codes = [f.result().status_code for f in [ex.submit(
            requests.post, f"{API}/driver/fees/withdraw", headers=owner, json=body, timeout=30)
            for _ in range(5)]]
    assert codes.count(200) == 1, codes
    wid = db.driver_withdrawals.find_one({"driver_id": did, "status": "requested"})["id"]
    db.driver_withdrawals.update_one({"id": wid}, {"$set": {"status": "paid"}})
    r = requests.post(f"{API}/payroll/withdrawals/{wid}/reject", headers=owner, json={"reason": "telat"}, timeout=20)
    assert r.status_code == 400 and db.driver_withdrawals.find_one({"id": wid})["status"] == "paid"


def test_parallel_payout_approve_creates_one_expense(owner, env, db):
    pid = f"po_{env['tag']}"
    db.driver_payouts.insert_one({"id": pid, "driver_id": env["driver"]["id"], "driver_name": "uji",
                                  "status": "draft", "total": 250000, "period_start": "2031-01-01",
                                  "period_end": "2031-01-31"})
    with ThreadPoolExecutor(4) as ex:
        [f.result() for f in [ex.submit(requests.post, f"{API}/payroll/payouts/{pid}/approve",
                                        headers=owner, timeout=30) for _ in range(4)]]
    assert db.expenses.count_documents({"payout_id": pid}) == 1


def test_settings_patch_merges_and_rejects_infinity(owner, db):
    before = db.settings.find_one({"key": "pricing_rules"}, {"_id": 0})
    try:
        rules = (before or {}).get("value") or {}
        r = requests.patch(f"{API}/settings", headers=owner, timeout=20,
                           json={"pricing_rules": {"rounding": rules.get("rounding", 1000)}})
        assert r.status_code == 200, r.text
        assert r.json()["pricing_rules"].get("day_rates") == rules.get("day_rates"), "PATCH sebagian menghapus tarif"
        raw = '{"pricing_rules": {"weekend_surcharge_percent": Infinity}}'
        r = requests.patch(f"{API}/settings", headers={**owner, "Content-Type": "application/json"},
                           data=raw, timeout=20)
        assert r.status_code in (400, 422), r.text
    finally:
        if before:
            db.settings.replace_one({"key": "pricing_rules"}, before)


def test_booking_api_rejects_infinity(owner, env):
    s, e = _window(env)
    raw = json.dumps({"customer_id": env["customer_id"], "vehicle_id": env["vehicle"]["id"],
                      "start_datetime": s, "end_datetime": e}).rstrip("}") + ', "base_price": Infinity}'
    r = requests.post(f"{API}/bookings", headers={**owner, "Content-Type": "application/json"}, data=raw, timeout=20)
    assert r.status_code == 422, r.text


def test_reports_summary_follows_period(owner):
    r = requests.get(f"{API}/reports/summary?period=2001-01", headers=owner, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["period"] == "2001-01"
    assert data["revenue_total"] == 0 and data["expense_total"] == 0
    assert data["revenue_by_month"][-1]["month"] == "2001-01"
