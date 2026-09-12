#!/usr/bin/env python3
"""
verify_data_integrity.py — POST-SEED INTEGRITY GATE
===================================================
Menangkap bug data yang lolos HTTP 200. WAJIB jalan di DB BERSIH (sesudah seed_reset).
Invarian domain (lihat docs/03_DATA_MODEL.md §3):
  INV-1  booking.total == base_price + Σ add_ons
  INV-2  booking.paid == Σ payments; paid <= total
  INV-3  payment_status derivasi konsisten
  INV-4  ANTI DOUBLE-BOOKING (overlap per vehicle utk status aktif)
  INV-5  trip.profit == revenue - Σ expenses
  INV-6  locations monotonik + lat/lng valid
  INV-7  lead.stage ∈ himpunan sah
  INV-8  number-series unik (bookings.code, invoices.number)
  INV-10 snapshot non-null utk booking confirmed
Usage: cd /app && python scripts/verify_data_integrity.py
Exit 0 = valid. !=0 = INTEGRITY VIOLATION.
"""
import asyncio, os, sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
try:
    from dotenv import load_dotenv; load_dotenv(ROOT / "backend" / ".env")
except Exception: pass
G, Y, R, C, B, X = "\033[92m", "\033[93m", "\033[91m", "\033[96m", "\033[1m", "\033[0m"
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "app_db")
LEAD_STAGES = {"new", "contacted", "quoted", "negotiation", "won", "lost"}
ACTIVE_BOOKING = {"hold", "confirmed", "ongoing"}
results = {"pass": 0, "fail": 0, "warn": 0}


@dataclass
class Concept:
    name: str
    canonical: str
    must_have_data: bool = True
    legacy_must_be_empty: list = field(default_factory=list)


CONCEPTS = [
    Concept("users", "users", True, ["staff", "karyawan"]),
    Concept("vehicles", "vehicles", True, ["cars", "armada", "kendaraan"]),
    Concept("drivers", "drivers", True, ["sopir"]),
    Concept("customers", "customers", True, ["clients", "pelanggan"]),
    Concept("bookings", "bookings", True, ["orders", "pesanan", "reservations"]),
    Concept("leads", "leads", False, ["prospects"]),
    Concept("trips", "trips", False, []),
    Concept("locations", "locations", False, ["gps", "positions"]),
    Concept("payments", "payments", False, ["payment"]),
    Concept("expenses", "expenses", False, ["cost", "biaya"]),
    Concept("invoices", "invoices", False, ["bills", "faktur"]),
    Concept("destinations", "destinations", False, []),
    Concept("settings", "settings", False, ["config"]),
    Concept("lead_activities", "lead_activities", False, []),
    Concept("maintenance_records", "maintenance_records", False, ["maintenance", "servis"]),
    Concept("trip_shares", "trip_shares", False, []),
    Concept("conversations", "conversations", False, ["inbox", "percakapan"]),
    Concept("messages", "messages", False, ["pesan"]),
    Concept("notification_tasks", "notification_tasks", False, ["notifikasi", "reminder"]),
]


def line(tag, color, msg, detail=""):
    print(f"  {color}[{tag}]{X} {msg}" + (f"  {color}{detail}{X}" if detail else ""))


def overlaps(a_start, a_end, b_start, b_end):
    return a_start < b_end and b_start < a_end


async def layer1(db):
    print(f"\n{C}{B}L1/L2 — Rekonsiliasi koleksi (DB clean-seed){X}")
    for c in CONCEPTS:
        n = await db[c.canonical].count_documents({})
        if c.must_have_data and n == 0:
            results["fail"] += 1
            line("FAIL", R, f"{c.name}: '{c.canonical}' KOSONG", "→ seed GAP atau DRIFT")
        else:
            results["pass"] += 1
            line("PASS", G, f"{c.name}: '{c.canonical}' = {n} dok")
        for legacy in c.legacy_must_be_empty:
            ln = await db[legacy].count_documents({})
            if ln > 0:
                results["fail"] += 1
                line("FAIL", R, f"{c.name}: legacy '{legacy}' berisi {ln} dok", "→ DRIFT AKTIF")


async def layer_invariants(db):
    print(f"\n{C}{B}L4 — Invarian domain{X}")
    bookings = await db.bookings.find({}, {"_id": 0}).to_list(5000)
    payments = await db.payments.find({}, {"_id": 0}).to_list(20000)
    pay_by_booking = {}
    for p in payments:
        pay_by_booking.setdefault(p.get("booking_id"), 0.0)
        pay_by_booking[p.get("booking_id")] += float(p.get("amount", 0) or 0)

    # INV-1 total
    v1 = []
    for b in bookings:
        base = float(b.get("base_price", 0) or 0)
        addons = sum(float(a.get("amount", 0) or 0) for a in (b.get("add_ons") or []))
        if abs(base + addons - float(b.get("total_amount", 0) or 0)) > 0.01:
            v1.append(b.get("code", b.get("id")))
    _report("INV-1 total_amount == base + Σ add_ons", v1, len(bookings))

    # INV-2 paid == Σ payments; paid <= total
    v2 = []
    for b in bookings:
        paid_field = float(b.get("paid_amount", 0) or 0)
        paid_sum = pay_by_booking.get(b.get("id"), 0.0)
        total = float(b.get("total_amount", 0) or 0)
        if abs(paid_field - paid_sum) > 0.01 or paid_field > total + 0.01:
            v2.append(b.get("code", b.get("id")))
    _report("INV-2 paid_amount == Σ payments & <= total", v2, len(bookings))

    # INV-3 payment_status derivation (RC-02: sinyal FINANSIAL murni; status operasional terpisah)
    v3 = []
    for b in bookings:
        paid = float(b.get("paid_amount", 0) or 0); total = float(b.get("total_amount", 0) or 0)
        ps = b.get("payment_status")
        if paid <= 0:
            expected = "belum_bayar"
        elif paid >= total and total > 0:
            expected = "lunas"
        else:
            expected = "dp"
        if ps and ps != expected:
            v3.append(f"{b.get('code', b.get('id'))}({ps}!={expected})")
    _report("INV-3 payment_status konsisten", v3, len(bookings))

    # INV-11 money integral (RC-11): uang disimpan sebagai bilangan bulat rupiah (bebas drift float)
    def _fractional(v):
        try:
            return abs(float(v) - round(float(v))) > 1e-9
        except (TypeError, ValueError):
            return False

    _exp = await db.expenses.find({}, {"_id": 0}).to_list(20000)
    _inv = await db.invoices.find({}, {"_id": 0}).to_list(20000)
    _mnt = await db.maintenance_records.find({}, {"_id": 0}).to_list(20000)
    _dpo = await db.driver_payouts.find({}, {"_id": 0}).to_list(20000)
    _trp = await db.trips.find({}, {"_id": 0}).to_list(20000)
    money_map = {
        "bookings": (bookings, ["total_amount", "paid_amount", "base_price"]),
        "payments": (payments, ["amount"]),
        "expenses": (_exp, ["amount"]),
        "invoices": (_inv, ["amount"]),
        "maintenance_records": (_mnt, ["cost"]),
        "driver_payouts": (_dpo, ["total", "gross", "bonus_total", "deduction_total",
                                  "base_salary", "commission_trip", "commission_pct",
                                  "allowance_km", "total_revenue"]),
        "trips": (_trp, ["revenue", "profit"]),
    }
    v_money = []
    money_total = 0
    for coll, (docs, fields) in money_map.items():
        money_total += len(docs)
        for d in docs:
            for f in fields:
                val = d.get(f)
                if val is not None and _fractional(val):
                    v_money.append(f"{coll}.{d.get('code', d.get('number', d.get('id')))}.{f}={val}")
    _report("INV-11 money integral (rupiah)", v_money, money_total)

    # INV-4 anti double-booking
    v4 = []
    by_vehicle = {}
    for b in bookings:
        if b.get("status") in ACTIVE_BOOKING and b.get("vehicle_id"):
            by_vehicle.setdefault(b["vehicle_id"], []).append(b)
    for vid, bks in by_vehicle.items():
        bks_sorted = [x for x in bks if x.get("start_datetime") and x.get("end_datetime")]
        for i in range(len(bks_sorted)):
            for j in range(i + 1, len(bks_sorted)):
                a, c2 = bks_sorted[i], bks_sorted[j]
                if overlaps(a["start_datetime"], a["end_datetime"], c2["start_datetime"], c2["end_datetime"]):
                    v4.append(f"{vid}:{a.get('code')}×{c2.get('code')}")
    _report("INV-4 ANTI double-booking (no overlap per vehicle)", v4, len(by_vehicle))

    # INV-5 trip profit
    trips = await db.trips.find({}, {"_id": 0}).to_list(5000)
    expenses = await db.expenses.find({}, {"_id": 0}).to_list(20000)
    exp_by_trip = {}
    for e in expenses:
        exp_by_trip.setdefault(e.get("trip_id"), 0.0)
        exp_by_trip[e.get("trip_id")] += float(e.get("amount", 0) or 0)
    v5 = []
    for t in trips:
        if t.get("profit") is None: continue
        rev = float(t.get("revenue", 0) or 0); ex = exp_by_trip.get(t.get("id"), 0.0)
        if abs(float(t.get("profit", 0) or 0) - (rev - ex)) > 0.5:
            v5.append(t.get("id"))
    _report("INV-5 trip.profit == revenue - Σ expenses", v5, len(trips))

    # INV-6 locations monotonic + range
    locs = await db.locations.find({}, {"_id": 0}).to_list(50000)
    by_trip = {}
    for l in locs:
        by_trip.setdefault(l.get("trip_id"), []).append(l)
    v6 = []
    for tid, pts in by_trip.items():
        ts = [p.get("timestamp") for p in pts if p.get("timestamp")]
        if ts != sorted(ts): v6.append(f"{tid}(ts)")
        for p in pts:
            lat = p.get("lat"); lng = p.get("lng")
            if lat is None or lng is None or not (-90 <= float(lat) <= 90) or not (-180 <= float(lng) <= 180):
                v6.append(f"{tid}(coord)"); break
    _report("INV-6 locations monotonik + lat/lng valid", v6, len(by_trip))

    # INV-7 lead stage
    leads = await db.leads.find({}, {"_id": 0}).to_list(5000)
    v7 = [l.get("id") for l in leads if l.get("stage") and l.get("stage") not in LEAD_STAGES]
    _report("INV-7 lead.stage ∈ himpunan sah", v7, len(leads))

    # INV-8 number-series unik
    codes = [b.get("code") for b in bookings if b.get("code")]
    invs = await db.invoices.find({}, {"_id": 0}).to_list(5000)
    inums = [i.get("number") for i in invs if i.get("number")]
    dup = []
    if len(codes) != len(set(codes)): dup.append("bookings.code")
    if len(inums) != len(set(inums)): dup.append("invoices.number")
    _report("INV-8 number-series unik", dup, len(codes) + len(inums))

    # INV-10 snapshot non-null utk confirmed
    v10 = []
    for b in bookings:
        if b.get("status") in (ACTIVE_BOOKING | {"completed"}):
            if not b.get("customer_name") or not b.get("vehicle_name"):
                v10.append(b.get("code", b.get("id")))
    _report("INV-10 snapshot (customer/vehicle name) terisi", v10, len(bookings))

    # INV-21 maintenance window memblok booking aktif (no overlap per vehicle)
    maint = await db.maintenance_records.find({}, {"_id": 0}).to_list(5000)
    win_by_vehicle = {}
    for m in maint:
        if m.get("status") in {"scheduled", "in_progress"} and m.get("vehicle_id") \
                and m.get("start_date") and m.get("end_date"):
            win_by_vehicle.setdefault(m["vehicle_id"], []).append(m)
    v21 = []
    for vid, wins in win_by_vehicle.items():
        active_bks = [b for b in by_vehicle.get(vid, []) if b.get("start_datetime") and b.get("end_datetime")]
        for w in wins:
            for b in active_bks:
                if overlaps(w["start_date"], w["end_date"], b["start_datetime"], b["end_datetime"]):
                    v21.append(f"{vid}:{w.get('id')}×{b.get('code')}")
    _report("INV-21 maintenance window tak overlap booking aktif", v21, len(win_by_vehicle))

    # INV-22 share token aktif sah (unik, tak kedaluwarsa, tak dibatalkan)
    shares = await db.trip_shares.find({}, {"_id": 0}).to_list(5000)
    now_dt = datetime.now(timezone.utc)
    v22 = []
    tokens = [s.get("token") for s in shares if s.get("token")]
    if len(tokens) != len(set(tokens)):
        v22.append("token-duplikat")
    for s in shares:
        if s.get("revoked"):
            continue
        exp = s.get("expires_at")
        try:
            e = datetime.fromisoformat(str(exp).replace("Z", "+00:00")) if exp else None
            if e and e.tzinfo is None:
                e = e.replace(tzinfo=timezone.utc)
        except Exception:
            e = None
        if not s.get("token") or e is None or e <= now_dt:
            v22.append(s.get("id"))
    _report("INV-22 share token aktif sah", v22, len(shares))

    # INV-23 message.conversation_id selalu rujuk conversation sah (tak ada pesan yatim)
    convo_ids = set(c.get("id") for c in await db.conversations.find({}, {"_id": 0, "id": 1}).to_list(5000))
    msgs = await db.messages.find({}, {"_id": 0, "id": 1, "conversation_id": 1}).to_list(20000)
    v23 = [m.get("id") for m in msgs if m.get("conversation_id") not in convo_ids]
    _report("INV-23 message.conversation_id rujuk conversation sah", v23, len(msgs))

    # INV-24 payroll-finance (E11): total/gross konsisten + expense akrual/kas sinkron
    payouts = await db.driver_payouts.find({}, {"_id": 0}).to_list(5000)
    exp_by_id = {e["id"]: e for e in await db.expenses.find(
        {"category": "gaji_driver"}, {"_id": 0}).to_list(5000)}
    v24 = []
    for p in payouts:
        gross = round(float(p.get("base_salary") or 0) + float(p.get("commission_trip") or 0)
                      + float(p.get("commission_pct") or 0) + float(p.get("allowance_km") or 0), 2)
        total = round(gross + float(p.get("bonus_total") or 0) - float(p.get("deduction_total") or 0), 2)
        if abs(float(p.get("gross") or 0) - gross) > 0.5 or abs(float(p.get("total") or 0) - total) > 0.5:
            v24.append(f"{p.get('id')}:math"); continue
        if p.get("status") in ("approved", "paid") and float(p.get("total") or 0) > 0:
            exp = exp_by_id.get(p.get("expense_id"))
            if not exp:
                v24.append(f"{p.get('id')}:no-expense"); continue
            if p.get("status") == "paid" and not exp.get("paid"):
                v24.append(f"{p.get('id')}:expense-not-paid")
    _report("INV-24 payroll akrual/kas sinkron dgn Finance", v24, len(payouts))

    # INV-25 REFERENTIAL INTEGRITY — FK tak menggantung (blind-spot gate lama; ditambah pasca audit forensik).
    veh_ids = set(await db.vehicles.distinct("id"))
    drv_ids = set(await db.drivers.distinct("id"))
    cust_ids = set(await db.customers.distinct("id"))
    partner_ids = set(await db.partners.distinct("id"))
    bk_ids = set(b.get("id") for b in bookings)
    trip_ids = set(t.get("id") for t in trips)
    ref = []
    for b in bookings:
        if b.get("vehicle_id") and b["vehicle_id"] not in veh_ids:
            ref.append(f"bk:{b.get('code')}->veh")
        if b.get("customer_id") and b["customer_id"] not in cust_ids:
            ref.append(f"bk:{b.get('code')}->cust")
        if b.get("status") in ACTIVE_BOOKING and b.get("driver_id") and b["driver_id"] not in drv_ids:
            ref.append(f"bk:{b.get('code')}->drv")
    for t in trips:
        if t.get("booking_id") and t["booking_id"] not in bk_ids:
            ref.append(f"trip:{t.get('id')}->bk")
        if t.get("vehicle_id") and t["vehicle_id"] not in veh_ids:
            ref.append(f"trip:{t.get('id')}->veh")
    for p in payments:
        if p.get("booking_id") and p["booking_id"] not in bk_ids:
            ref.append(f"pay:{p.get('id')}->bk")
    for e in _exp:
        if e.get("trip_id") and e["trip_id"] not in trip_ids:
            ref.append(f"exp:{e.get('id')}->trip")
        if e.get("booking_id") and e["booking_id"] not in bk_ids:
            ref.append(f"exp:{e.get('id')}->bk")
    for s in await db.subcharters.find({}, {"_id": 0}).to_list(20000):
        if s.get("partner_id") and s["partner_id"] not in partner_ids:
            ref.append(f"sub:{s.get('id')}->partner")
        if s.get("booking_id") and s["booking_id"] not in bk_ids:
            ref.append(f"sub:{s.get('id')}->bk")
    _report("INV-25 referential integrity (no dangling FK)", ref, len(bookings) + len(trips))

    # INV-26 STATE consistency: vehicle.status 'on_trip' <-> ada trip aktif (blind-spot gate lama).
    ACTIVE_TRIP = {"standby", "to_pickup", "on_trip"}
    active_trip_veh = set(t.get("vehicle_id") for t in trips if t.get("status") in ACTIVE_TRIP)
    vehicles_all = await db.vehicles.find({}, {"_id": 0}).to_list(5000)
    stv = []
    for v in vehicles_all:
        if v.get("status") == "on_trip" and v["id"] not in active_trip_veh:
            stv.append(f"{v.get('code')}:on_trip-tanpa-trip")
        if v["id"] in active_trip_veh and v.get("status") not in ("on_trip", "maintenance"):
            stv.append(f"{v.get('code')}:trip-tapi-{v.get('status')}")
    _report("INV-26 vehicle.status sinkron dgn trip aktif", stv, len(vehicles_all))


def _report(name, violations, total):
    if violations:
        results["fail"] += 1
        line("FAIL", R, f"{name}: {len(violations)} pelanggaran", str(violations[:5]))
    else:
        results["pass"] += 1
        line("PASS", G, f"{name} ({total} diperiksa)")


async def run():
    print(f"\n{B}{'='*60}{X}\n  DATA INTEGRITY GATE  (DB: {DB_NAME})\n{B}{'='*60}{X}")
    try:
        from motor.motor_asyncio import AsyncIOMotorClient
    except ImportError:
        os.system("pip install motor -q")
        from motor.motor_asyncio import AsyncIOMotorClient
    db = AsyncIOMotorClient(MONGO_URL)[DB_NAME]
    await layer1(db)
    await layer_invariants(db)
    print(f"\n{B}{'='*60}{X}\n  {G}PASS {results['pass']}{X} | {Y}WARN {results['warn']}{X} | {R}FAIL {results['fail']}{X}\n{B}{'='*60}{X}")
    if results["fail"]:
        print(f"{R}{B}  INTEGRITY VIOLATION — perbaiki sebelum lanjut.{X}\n"); return 1
    print(f"{G}{B}  Semua invarian valid.{X}\n"); return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(run()))
