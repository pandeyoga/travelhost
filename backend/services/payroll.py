"""services/payroll.py — Driver Payroll / HR Lite (E11 Phase C).

Kompensasi driver *fully-configurable* (embedded di dokumen `drivers.comp`) + generator
akrual payout per periode dari trip SELESAI + integrasi Finance (expenses kategori
`gaji_driver`).

Keputusan bisnis (dari user):
  - Kompensasi per driver: gaji pokok bulanan + komisi/trip + %revenue + uang jalan/km,
    masing-masing punya toggle aktif.
  - Sumber revenue untuk komisi %: CONFIGURABLE per driver — `trip` (trip.revenue) atau
    `booking` (total_amount booking terkait). Default `trip`.
  - Periode: configurable (bulanan/mingguan/per-trip).
  - Finance: expense dibuat SEKALI saat payout DISETUJUI (akrual masuk P&L), lalu ditandai
    LUNAS saat payout DIBAYAR (realisasi kas). Tidak dobel-hitung.
  - Bonus & potongan: baris manual bebas (label + nominal, boleh banyak).
"""
from core_utils import money, new_id, now_iso

DEFAULT_COMP = {
    "base_salary_monthly": 0.0,
    "commission_per_trip": 0.0,
    "commission_pct_revenue": 0.0,   # dalam persen, mis. 5 = 5%
    "allowance_per_km": 0.0,
    "revenue_base": "trip",          # trip | booking
    "enable_base": True,
    "enable_commission_trip": False,
    "enable_commission_pct": False,
    "enable_allowance_km": False,
}
PERIOD_TYPES = ("monthly", "weekly", "per_trip")
# Faktor gaji pokok terhadap periode (gaji pokok = bulanan).
_BASE_FACTOR = {"monthly": 1.0, "weekly": round(7.0 / 30.0, 4), "per_trip": 0.0}


def get_comp(driver: dict) -> dict:
    """Gabungkan konfigurasi kompensasi driver dengan default (aman untuk driver lama)."""
    comp = dict(DEFAULT_COMP)
    raw = (driver or {}).get("comp") or {}
    for k in DEFAULT_COMP:
        if raw.get(k) is not None:
            comp[k] = raw[k]
    # koersi numerik
    for k in ("base_salary_monthly", "commission_per_trip", "commission_pct_revenue", "allowance_per_km"):
        try:
            comp[k] = float(comp[k] or 0)
        except (TypeError, ValueError):
            comp[k] = 0.0
    if comp.get("revenue_base") not in ("trip", "booking"):
        comp["revenue_base"] = "trip"
    for k in ("enable_base", "enable_commission_trip", "enable_commission_pct", "enable_allowance_km"):
        comp[k] = bool(comp.get(k))
    return comp


def _in_period(trip: dict, start: str, end: str) -> bool:
    """True bila tanggal trip (end_at→start_at→created_at) berada di [start, end] (inklusif)."""
    stamp = trip.get("end_at") or trip.get("start_at") or trip.get("created_at") or ""
    d = str(stamp)[:10]
    if not d:
        return False
    return start <= d <= end


async def _period_trips(db, driver_id: str, start: str, end: str):
    trips = await db.trips.find(
        {"driver_id": driver_id, "status": "completed"}, {"_id": 0}
    ).sort("created_at", -1).to_list(5000)
    return [t for t in trips if _in_period(t, start, end)]


async def _revenue_for(db, trips, revenue_base: str) -> float:
    if revenue_base == "booking":
        ids = list({t.get("booking_id") for t in trips if t.get("booking_id")})
        totals = {}
        if ids:
            rows = await db.bookings.find(
                {"id": {"$in": ids}}, {"_id": 0, "id": 1, "total_amount": 1}
            ).to_list(5000)
            totals = {b["id"]: float(b.get("total_amount") or 0) for b in rows}
        return money(sum(totals.get(t.get("booking_id"), 0.0) for t in trips))
    # default: trip.revenue
    return money(sum(float(t.get("revenue") or 0) for t in trips))


def compute_totals(payout: dict) -> dict:
    """Hitung ulang gross/bonus/potongan/total dari komponen + baris manual. Idempotent."""
    gross = money(
        float(payout.get("base_salary") or 0)
        + float(payout.get("commission_trip") or 0)
        + float(payout.get("commission_pct") or 0)
        + float(payout.get("allowance_km") or 0))
    bonus_total = money(sum(float(b.get("amount") or 0) for b in payout.get("bonuses") or []))
    deduction_total = money(sum(float(d.get("amount") or 0) for d in payout.get("deductions") or []))
    total = money(gross + bonus_total - deduction_total)
    payout["gross"] = gross
    payout["bonus_total"] = bonus_total
    payout["deduction_total"] = deduction_total
    payout["total"] = total
    return payout


async def build_accrual(db, driver: dict, period_type: str, start: str, end: str,
                        bonuses=None, deductions=None, notes: str = "") -> dict:
    """Rakit dokumen payout DRAFT (akrual) dari trip selesai + konfigurasi kompensasi driver."""
    comp = get_comp(driver)
    trips = await _period_trips(db, driver["id"], start, end)
    trips_count = len(trips)
    total_km = round(sum(float(t.get("distance_km") or 0) for t in trips), 1)
    total_revenue = await _revenue_for(db, trips, comp["revenue_base"])

    base_salary = money(comp["base_salary_monthly"] * _BASE_FACTOR.get(period_type, 1.0)) if comp["enable_base"] else 0
    commission_trip = money(comp["commission_per_trip"] * trips_count) if comp["enable_commission_trip"] else 0
    commission_pct = money(total_revenue * comp["commission_pct_revenue"] / 100.0) if comp["enable_commission_pct"] else 0
    allowance_km = money(comp["allowance_per_km"] * total_km) if comp["enable_allowance_km"] else 0

    payout = {
        "id": new_id("dpo"),
        "driver_id": driver["id"], "driver_name": driver.get("name"),
        "period_type": period_type, "period_start": start, "period_end": end,
        "trips_count": trips_count, "total_km": total_km, "total_revenue": total_revenue,
        "revenue_base": comp["revenue_base"],
        "base_salary": base_salary, "commission_trip": commission_trip,
        "commission_pct": commission_pct, "allowance_km": allowance_km,
        "bonuses": list(bonuses or []), "deductions": list(deductions or []),
        "notes": notes or "",
        "status": "draft",
        "approver_id": None, "approver_name": None, "approved_at": None, "paid_at": None,
        "expense_id": None,
        "snapshot_comp": comp,
        "created_at": now_iso(), "updated_at": now_iso(),
    }
    return compute_totals(payout)


async def create_payout_expense(db, payout: dict):
    """Buat expense akrual (kategori gaji_driver) saat payout disetujui. Return expense_id | None."""
    if float(payout.get("total") or 0) <= 0:
        return None
    exp = {
        "id": new_id("exp"),
        "booking_id": None, "trip_id": None,
        "category": "gaji_driver",
        "amount": money(payout["total"]),
        "note": f"Payroll {payout.get('driver_name')} · {payout.get('period_start')}—{payout.get('period_end')}",
        "payout_id": payout["id"], "driver_id": payout.get("driver_id"),
        "paid": False, "paid_at": None,
        "created_at": now_iso(),
    }
    await db.expenses.insert_one(exp)
    return exp["id"]


async def summary(db) -> dict:
    """KPI payroll: jumlah per status + total akrual (approved+paid) & total dibayar."""
    rows = await db.driver_payouts.find({}, {"_id": 0, "status": 1, "total": 1}).to_list(5000)
    by_status = {"draft": 0, "approved": 0, "paid": 0}
    accrued = 0.0
    paid_total = 0.0
    for r in rows:
        st = r.get("status", "draft")
        by_status[st] = by_status.get(st, 0) + 1
        amt = float(r.get("total") or 0)
        if st in ("approved", "paid"):
            accrued += amt
        if st == "paid":
            paid_total += amt
    return {
        "count": len(rows), "by_status": by_status,
        "accrued_total": round(accrued, 2), "paid_total": round(paid_total, 2),
    }


async def bulk_generate(db, period_type: str, start: str, end: str, driver_ids=None) -> dict:
    """Generate payout DRAFT untuk banyak driver sekaligus. Lewati yang sudah punya payout
    pada periode sama. Return {created:[...], skipped:[...]}."""
    q = {} if not driver_ids else {"id": {"$in": list(driver_ids)}}
    drivers = await db.drivers.find(q, {"_id": 0}).to_list(5000)
    created, skipped = [], []
    for drv in drivers:
        # RC-06: lewati bila sudah ada payout periode TUMPANG-TINDIH (bukan exact-match).
        dup = await db.driver_payouts.find_one({
            "driver_id": drv["id"],
            "period_start": {"$lte": end},
            "period_end": {"$gte": start},
        }, {"_id": 1})
        if dup:
            skipped.append({"driver_id": drv["id"], "driver_name": drv.get("name")})
            continue
        payout = await build_accrual(db, drv, period_type, start, end)
        await db.driver_payouts.insert_one(dict(payout))
        created.append({"id": payout["id"], "driver_id": drv["id"], "driver_name": drv.get("name"), "total": payout["total"]})
    return {"created": created, "skipped": skipped, "created_count": len(created), "skipped_count": len(skipped)}
