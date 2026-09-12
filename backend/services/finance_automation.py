"""services/finance_automation.py — E5 Finance Automation.

Menutup gap finance:
  - G4: maintenance cost masuk P&L (total + alokasi per unit).
  - G5: rekonsiliasi invoice ↔ pembayaran + sinkronisasi status invoice.
  - AR collection otomatis: reminder WA (via event invoice.overdue → automation) + aging.
  - Cashflow bulanan (kas masuk vs keluar incl. maintenance) + proyeksi moving-average.

Read-only kecuali: sync_invoice_statuses (update invoices.status) & send reminder (emit event).
Reuse: services.finance (accounts_receivable, EXPENSE_CATEGORIES), services.analytics
(_month_keys/_next_months, ar_aging), services.events.emit.
"""
from datetime import datetime, timezone

from services.finance import EXPENSE_CATEGORIES, accounts_receivable
from services.analytics import _month_keys, _next_months
from services.events import emit


def _now():
    return datetime.now(timezone.utc)


def _month(dt_str):
    return (dt_str or "")[:7]


def _maint_date(m):
    """Tanggal realisasi biaya maintenance: completed_at bila ada, jika tidak created_at."""
    return m.get("completed_at") or m.get("created_at") or m.get("scheduled_date") or ""


async def _payments_by_booking(db):
    rows = await db.payments.aggregate([
        {"$group": {"_id": "$booking_id", "paid": {"$sum": {"$ifNull": ["$amount", 0]}}}},
    ]).to_list(5000)
    return {r["_id"]: float(r["paid"]) for r in rows}


# ----------------------------------------------------------------------------- P&L + maintenance
async def pl_full(db, period=None):
    """P&L komprehensif: revenue (cash-in) - opex - maintenance, total & per unit."""
    if not period:
        period = _now().strftime("%Y-%m")

    rev_rows = await db.payments.aggregate([
        {"$match": {"paid_at": {"$regex": f"^{period}"}}},
        {"$group": {"_id": None, "t": {"$sum": {"$ifNull": ["$amount", 0]}}}},
    ]).to_list(1)
    revenue = float(rev_rows[0]["t"]) if rev_rows else 0.0

    exp_rows = await db.expenses.aggregate([
        {"$match": {"created_at": {"$regex": f"^{period}"}}},
        {"$group": {"_id": "$category", "amount": {"$sum": {"$ifNull": ["$amount", 0]}}}},
    ]).to_list(100)
    opex_total = sum(float(r["amount"]) for r in exp_rows)
    by_cat = {c: 0.0 for c in EXPENSE_CATEGORIES}
    for r in exp_rows:
        cat = r["_id"] if r["_id"] in EXPENSE_CATEGORIES else "other"
        by_cat[cat] += float(r["amount"])
    expense_by_category = [{"category": c, "amount": round(v, 2)} for c, v in by_cat.items()]

    # Maintenance (fetch kecil → filter period di Python pakai tanggal efektif).
    maint = await db.maintenance_records.find(
        {}, {"_id": 0, "vehicle_id": 1, "vehicle_name": 1, "cost": 1,
             "completed_at": 1, "created_at": 1, "scheduled_date": 1}).to_list(5000)
    maint_total = 0.0
    maint_by_veh = {}
    for m in maint:
        if _month(_maint_date(m)) != period:
            continue
        c = float(m.get("cost", 0) or 0)
        maint_total += c
        maint_by_veh[m.get("vehicle_id")] = maint_by_veh.get(m.get("vehicle_id"), 0.0) + c

    total_cost = round(opex_total + maint_total, 2)
    profit = round(revenue - total_cost, 2)
    margin = round((profit / revenue * 100), 1) if revenue > 0 else 0.0

    # Per unit: revenue dari trips (period), opex via expenses(trip→vehicle), maintenance.
    trips = await db.trips.find(
        {"created_at": {"$regex": f"^{period}"}},
        {"_id": 0, "id": 1, "vehicle_id": 1, "revenue": 1}).to_list(5000)
    rev_by_veh, trip_to_veh, trip_ids = {}, {}, []
    for t in trips:
        v = t.get("vehicle_id")
        rev_by_veh[v] = rev_by_veh.get(v, 0.0) + float(t.get("revenue", 0) or 0)
        trip_to_veh[t["id"]] = v
        trip_ids.append(t["id"])
    opex_by_veh = {}
    if trip_ids:
        ex_rows = await db.expenses.aggregate([
            {"$match": {"trip_id": {"$in": trip_ids}, "created_at": {"$regex": f"^{period}"}}},
            {"$group": {"_id": "$trip_id", "amount": {"$sum": {"$ifNull": ["$amount", 0]}}}},
        ]).to_list(5000)
        for r in ex_rows:
            v = trip_to_veh.get(r["_id"])
            opex_by_veh[v] = opex_by_veh.get(v, 0.0) + float(r["amount"])

    vehicles = await db.vehicles.find({}, {"_id": 0, "id": 1, "name": 1, "code": 1}).to_list(1000)
    per_unit = []
    for v in vehicles:
        vid = v["id"]
        rev = round(rev_by_veh.get(vid, 0.0), 2)
        ope = round(opex_by_veh.get(vid, 0.0), 2)
        mnt = round(maint_by_veh.get(vid, 0.0), 2)
        per_unit.append({
            "vehicle_id": vid, "vehicle_name": v.get("name") or v.get("code"),
            "revenue": rev, "operational_expenses": ope, "maintenance": mnt,
            "profit": round(rev - ope - mnt, 2),
        })
    per_unit.sort(key=lambda x: -x["profit"])

    return {
        "period": period,
        "revenue": round(revenue, 2),
        "operational_expenses": round(opex_total, 2),
        "maintenance_cost": round(maint_total, 2),
        "total_cost": total_cost,
        "profit": profit,
        "margin": margin,
        "expense_by_category": expense_by_category,
        "per_unit": per_unit,
    }


# ----------------------------------------------------------------------------- reconciliation (G5)
def _recon_status(invoice_amount, paid):
    if paid <= 0:
        return "belum"
    if paid + 0.01 < invoice_amount:
        return "sebagian"
    if paid > invoice_amount + 0.01:
        return "lebih"
    return "lunas"


def _status_from_paid(invoice_amount, paid, current):
    if invoice_amount > 0 and paid + 0.01 >= invoice_amount:
        return "paid"
    if paid > 0:
        return "partial"
    return current if current in ("draft", "sent") else "sent"


async def reconciliation(db):
    """Bandingkan tiap invoice vs Σ pembayaran booking-nya. Tandai selisih."""
    pay = await _payments_by_booking(db)
    invoices = await db.invoices.find({}, {"_id": 0}).to_list(2000)
    bookings = await db.bookings.find({}, {"_id": 0, "id": 1, "code": 1, "customer_name": 1}).to_list(5000)
    bk = {b["id"]: b for b in bookings}
    items = []
    summary = {"lunas": 0, "sebagian": 0, "belum": 0, "lebih": 0,
               "total_invoiced": 0.0, "total_paid": 0.0}
    for inv in invoices:
        amount = round(float(inv.get("amount", 0) or 0), 2)
        paid = round(float(pay.get(inv.get("booking_id"), 0.0)), 2)
        st = _recon_status(amount, paid)
        b = bk.get(inv.get("booking_id"), {})
        items.append({
            "invoice_id": inv.get("id"), "number": inv.get("number"),
            "booking_id": inv.get("booking_id"), "booking_code": b.get("code"),
            "customer_name": b.get("customer_name"),
            "invoice_amount": amount, "paid": paid, "diff": round(paid - amount, 2),
            "recon_status": st, "invoice_status": inv.get("status"), "due_at": inv.get("due_at"),
        })
        summary[st] += 1
        summary["total_invoiced"] = round(summary["total_invoiced"] + amount, 2)
        summary["total_paid"] = round(summary["total_paid"] + paid, 2)
    items.sort(key=lambda x: (x["recon_status"] == "lunas", x["number"] or ""))
    summary["mismatched"] = summary["sebagian"] + summary["belum"] + summary["lebih"]
    return {"items": items, "summary": summary}


async def sync_invoice_statuses(db):
    """Update invoices.status mengikuti pembayaran (paid/partial/sent)."""
    from core_utils import now_iso
    pay = await _payments_by_booking(db)
    invoices = await db.invoices.find({}, {"_id": 0, "id": 1, "amount": 1, "booking_id": 1, "status": 1, "number": 1}).to_list(2000)
    updated = []
    for inv in invoices:
        amount = float(inv.get("amount", 0) or 0)
        paid = float(pay.get(inv.get("booking_id"), 0.0))
        new_status = _status_from_paid(amount, paid, inv.get("status"))
        if new_status != inv.get("status"):
            await db.invoices.update_one({"id": inv["id"]},
                                         {"$set": {"status": new_status, "reconciled_at": now_iso()}})
            updated.append({"invoice_id": inv["id"], "number": inv.get("number"),
                            "from": inv.get("status"), "to": new_status})
    return {"updated_count": len(updated), "updated": updated}


# ----------------------------------------------------------------------------- cashflow + proyeksi
async def cashflow(db, months_back=6, horizon=3):
    months = _month_keys(months_back)
    pay_rows = await db.payments.aggregate([
        {"$group": {"_id": {"$substrBytes": [{"$ifNull": ["$paid_at", ""]}, 0, 7]},
                    "t": {"$sum": {"$ifNull": ["$amount", 0]}}}},
    ]).to_list(1000)
    cin = {r["_id"]: float(r["t"]) for r in pay_rows}
    exp_rows = await db.expenses.aggregate([
        {"$group": {"_id": {"$substrBytes": [{"$ifNull": ["$created_at", ""]}, 0, 7]},
                    "t": {"$sum": {"$ifNull": ["$amount", 0]}}}},
    ]).to_list(1000)
    cout = {r["_id"]: float(r["t"]) for r in exp_rows}
    # maintenance per bulan (tanggal efektif)
    maint = await db.maintenance_records.find({}, {"_id": 0, "cost": 1, "completed_at": 1, "created_at": 1, "scheduled_date": 1}).to_list(5000)
    mout = {}
    for m in maint:
        mk = _month(_maint_date(m))
        mout[mk] = mout.get(mk, 0.0) + float(m.get("cost", 0) or 0)

    rows = []
    balance = 0.0
    nets = []
    for k in months:
        inflow = round(cin.get(k, 0.0), 2)
        outflow = round(cout.get(k, 0.0) + mout.get(k, 0.0), 2)
        net = round(inflow - outflow, 2)
        balance = round(balance + net, 2)
        nets.append(net)
        rows.append({"month": k, "cash_in": inflow, "cash_out": outflow, "net": net, "balance": balance})

    window = min(3, len(nets) or 1)
    fc_keys = _next_months(months[-1], horizon)
    work = list(nets)
    projection = []
    bal = balance
    for k in fc_keys:
        tail = work[-window:] if window else work[-1:]
        pred = round(sum(tail) / len(tail), 2) if tail else 0.0
        bal = round(bal + pred, 2)
        projection.append({"month": k, "net": pred, "balance": bal})
        work.append(pred)

    return {"months": rows, "projection": projection, "window": window,
            "ending_balance": balance}


# ----------------------------------------------------------------------------- AR collection
def _age_days(start_dt):
    try:
        d = datetime.fromisoformat(str(start_dt).replace("Z", "+00:00"))
        return (_now() - d).days
    except Exception:
        return 0


async def ar_overdue(db):
    """Item AR yang sudah lewat tanggal mulai (overdue) — kandidat reminder."""
    ar = await accounts_receivable(db)
    items = [dict(i, age_days=_age_days(i.get("start_datetime"))) for i in ar["items"]]
    overdue = [i for i in items if i["age_days"] >= 0]
    overdue.sort(key=lambda x: -x["age_days"])
    return {"total_outstanding": ar["total_outstanding"], "count": len(overdue),
            "all_count": ar["count"], "items": overdue}


async def _reminder_payload(db, booking_id):
    b = await db.bookings.find_one({"id": booking_id}, {"_id": 0}) or {}
    phone = b.get("customer_phone") or ""
    if not phone and b.get("customer_id"):
        cust = await db.customers.find_one({"id": b["customer_id"]}, {"_id": 0, "phone": 1}) or {}
        phone = cust.get("phone", "")
    inv = await db.invoices.find_one({"booking_id": booking_id}, {"_id": 0, "number": 1}) or {}
    outstanding = round(float(b.get("total_amount", 0) or 0) - float(b.get("paid_amount", 0) or 0), 2)
    return {
        "booking_id": booking_id, "code": b.get("code"),
        "customer_id": b.get("customer_id"), "customer_name": b.get("customer_name"),
        "phone": phone, "number": inv.get("number") or b.get("code"),
        "amount": outstanding,
    }


async def send_ar_reminder(db, booking_id):
    """Kirim reminder tagih (emit invoice.overdue → automation → WA mock).

    dedupe_key unik+non-null (hindari tabrakan index unik `dedupe_key`; null hanya
    boleh 1 baris) — reminder boleh dikirim berulang (timestamp + uuid).
    """
    import uuid
    from core_utils import now_iso
    payload = await _reminder_payload(db, booking_id)
    dkey = f"ar_reminder:{booking_id}:{now_iso()}:{uuid.uuid4().hex[:8]}"
    ev = await emit(db, "invoice.overdue", payload, source="finance:ar_collection",
                    ref_type="booking", ref_id=booking_id, dedupe_key=dkey)
    return {"sent": bool(ev), "runs": (ev or {}).get("runs_created", 0),
            "customer_name": payload["customer_name"], "phone": payload["phone"],
            "amount": payload["amount"]}


async def send_bulk_ar_reminders(db):
    overdue = await ar_overdue(db)
    results = []
    for item in overdue["items"]:
        r = await send_ar_reminder(db, item["booking_id"])
        results.append({"booking_id": item["booking_id"], **r})
    sent = sum(1 for r in results if r["sent"])
    return {"attempted": len(results), "sent": sent, "results": results}


# ----------------------------------------------------------------------------- assemble report
async def assemble_finance_report(db, period=None):
    from services.analytics import ar_aging
    pl = await pl_full(db, period)
    return {
        "period": pl["period"],
        "pl": pl,
        "ar_aging": await ar_aging(db),
        "cashflow": await cashflow(db, months_back=6, horizon=3),
        "reconciliation": (await reconciliation(db))["summary"],
    }
