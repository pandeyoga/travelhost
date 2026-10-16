"""services/reports.py — agregasi laporan (Phase 5).

Mengkombinasikan payments (revenue cash-in), expenses, bookings, customers, vehicles
menjadi ringkasan laporan: total, tren bulanan, breakdown status/kategori, top customer,
utilisasi armada. Read-only (tidak menulis DB).
"""
from datetime import datetime, timezone

from services.finance import _agg_sum, accounts_receivable, EXPENSE_CATEGORIES

BOOKING_STATUSES = ("draft", "confirmed", "ongoing", "completed", "cancelled")


def _last_months(n: int):
    now = datetime.now(timezone.utc)
    y, m = now.year, now.month
    keys = []
    for _ in range(n):
        keys.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    return list(reversed(keys))


async def summary(db, period=None) -> dict:
    # Totalan via aggregation server-side (tanpa memuat semua dokumen ke memori).
    revenue_total = await _agg_sum(db, "payments")
    expense_total = await _agg_sum(db, "expenses")
    profit_total = round(revenue_total - expense_total, 2)

    ar = await accounts_receivable(db)

    # Tren 6 bulan terakhir — group by bulan (substring YYYY-MM) di DB.
    months = _last_months(6)
    rev_rows = await db.payments.aggregate([
        {"$group": {"_id": {"$substrBytes": [{"$ifNull": ["$paid_at", ""]}, 0, 7]},
                    "t": {"$sum": {"$ifNull": ["$amount", 0]}}}},
    ]).to_list(1000)
    exp_rows_m = await db.expenses.aggregate([
        {"$group": {"_id": {"$substrBytes": [{"$ifNull": ["$created_at", ""]}, 0, 7]},
                    "t": {"$sum": {"$ifNull": ["$amount", 0]}}}},
    ]).to_list(1000)
    rev_by_m = {r["_id"]: float(r["t"]) for r in rev_rows}
    exp_by_m = {r["_id"]: float(r["t"]) for r in exp_rows_m}
    revenue_by_month = [
        {"month": k, "revenue": round(rev_by_m.get(k, 0.0), 2), "expenses": round(exp_by_m.get(k, 0.0), 2),
         "profit": round(rev_by_m.get(k, 0.0) - exp_by_m.get(k, 0.0), 2)}
        for k in months
    ]

    # Breakdown status booking + utilisasi armada — via aggregation.
    status_rows = await db.bookings.aggregate([
        {"$group": {"_id": "$status", "c": {"$sum": 1}}},
    ]).to_list(100)
    status_count = {s: 0 for s in BOOKING_STATUSES}
    for r in status_rows:
        if r["_id"] in status_count:
            status_count[r["_id"]] = r["c"]
    bookings_by_status = [{"status": s, "count": c} for s, c in status_count.items()]

    util_rows = await db.bookings.aggregate([
        {"$match": {"status": {"$ne": "cancelled"}, "vehicle_id": {"$ne": None}}},
        {"$group": {"_id": "$vehicle_id", "vehicle_name": {"$first": "$vehicle_name"}, "bookings": {"$sum": 1}}},
        {"$sort": {"bookings": -1}},
    ]).to_list(1000)
    fleet_utilization = [
        {"vehicle_name": r.get("vehicle_name") or r["_id"], "bookings": r["bookings"]} for r in util_rows
    ]

    # Breakdown kategori pengeluaran — group by category.
    cat_rows = await db.expenses.aggregate([
        {"$group": {"_id": "$category", "amount": {"$sum": {"$ifNull": ["$amount", 0]}}}},
    ]).to_list(100)
    cat = {c: 0.0 for c in EXPENSE_CATEGORIES}
    for r in cat_rows:
        c = r["_id"] if r["_id"] in cat else "other"
        cat[c] += float(r["amount"])
    expense_by_category = [{"category": c, "amount": round(v, 2)} for c, v in cat.items()]

    # Top customer — sort + limit di DB (bukan muat 5000 lalu sort di Python).
    customers = await db.customers.find(
        {}, {"_id": 0, "name": 1, "lifetime_value": 1, "total_trips": 1}
    ).sort("lifetime_value", -1).to_list(5)
    top_customers = [
        {"name": c.get("name"), "lifetime_value": round(float(c.get("lifetime_value", 0) or 0), 2),
         "total_trips": int(c.get("total_trips", 0) or 0)}
        for c in customers
    ]

    # Ringkasan invoice — group by status.
    inv_rows = await db.invoices.aggregate([
        {"$group": {"_id": "$status", "c": {"$sum": 1}}},
    ]).to_list(100)
    inv_by = {r["_id"]: r["c"] for r in inv_rows}
    invoice_summary = {
        "count": sum(inv_by.values()),
        "draft": inv_by.get("draft", 0),
        "sent": inv_by.get("sent", 0),
        "paid": inv_by.get("paid", 0),
    }

    return {
        "period": period or datetime.now(timezone.utc).strftime("%Y-%m"),
        "revenue_total": round(revenue_total, 2),
        "expense_total": round(expense_total, 2),
        "profit_total": profit_total,
        "outstanding_ar": ar["total_outstanding"],
        "ar_count": ar["count"],
        "revenue_by_month": revenue_by_month,
        "bookings_by_status": bookings_by_status,
        "expense_by_category": expense_by_category,
        "top_customers": top_customers,
        "fleet_utilization": fleet_utilization,
        "invoices": invoice_summary,
    }
