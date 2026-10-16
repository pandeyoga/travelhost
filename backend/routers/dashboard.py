"""routers/dashboard.py — metrik ringkas role-aware (objek telanjang).
INV-9: active_bookings == jumlah booking status∈{confirmed,ongoing}; vehicles == total vehicles.
Tambahan Phase 2: pengingat dokumen armada due-soon, booking terbaru, pemasukan bulan ini.
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends

from core_utils import safe_doc
from db import get_db
from dependencies import get_current_user
from services.geo import parse_iso

router = APIRouter(prefix="/api", tags=["dashboard"])

_ACTIVE = ["confirmed", "ongoing"]
_DUE_WINDOW_DAYS = 30
_REMINDER_FIELDS = (("kir_expiry", "KIR"), ("tax_expiry", "Pajak"), ("next_service_date", "Servis"))


async def _build_reminders(db):
    now = datetime.now(timezone.utc)
    horizon = now + timedelta(days=_DUE_WINDOW_DAYS)
    veh = await db.vehicles.find(
        {}, {"_id": 0, "id": 1, "code": 1, "name": 1, "kir_expiry": 1, "tax_expiry": 1, "next_service_date": 1}
    ).to_list(1000)
    out = []
    for v in veh:
        for field, label in _REMINDER_FIELDS:
            d = parse_iso(v.get(field))
            if d and d <= horizon:
                out.append({
                    "vehicle_id": v.get("id"), "vehicle_name": v.get("name"), "code": v.get("code"),
                    "type": label, "due_date": v.get(field), "overdue": d < now,
                })
    out.sort(key=lambda r: r.get("due_date") or "")
    return out


@router.get("/dashboard")
async def dashboard(user=Depends(get_current_user)):
    db = get_db()
    role = user.get("role")

    vehicles = await db.vehicles.count_documents({})
    drivers = await db.drivers.count_documents({})
    customers = await db.customers.count_documents({})
    bookings_total = await db.bookings.count_documents({})
    active_bookings = await db.bookings.count_documents({"status": {"$in": _ACTIVE}})
    leads_total = await db.leads.count_documents({})
    leads_new = await db.leads.count_documents({"stage": "new"})

    async def _sum(coll, match):
        rows = await db[coll].aggregate([
            {"$match": match}, {"$group": {"_id": None, "t": {"$sum": {"$ifNull": ["$amount", 0]}}}}
        ]).to_list(1)
        return float(rows[0]["t"]) if rows else 0.0

    month_prefix = datetime.now(timezone.utc).strftime("%Y-%m")
    total_revenue = await _sum("payments", {})
    revenue_month = await _sum("payments", {"paid_at": {"$regex": f"^{month_prefix}"}})

    ar_rows = await db.bookings.aggregate([
        {"$match": {"status": {"$ne": "cancelled"}}},
        {"$group": {"_id": None, "t": {"$sum": {"$max": [
            {"$subtract": [{"$ifNull": ["$total_amount", 0]}, {"$ifNull": ["$paid_amount", 0]}]}, 0]}}}},
    ]).to_list(1)
    outstanding_ar = float(ar_rows[0]["t"]) if ar_rows else 0.0

    reminders = await _build_reminders(db)
    recent = await db.bookings.find(
        {}, {"_id": 0, "id": 1, "code": 1, "customer_name": 1, "vehicle_name": 1,
             "start_datetime": 1, "total_amount": 1, "payment_status": 1, "status": 1},
    ).sort("created_at", -1).to_list(6)

    base = {
        "role": role,
        "user_name": user.get("name"),
        "vehicles": vehicles,
        "drivers": drivers,
        "customers": customers,
        "bookings": bookings_total,
        "active_bookings": active_bookings,
        "leads": leads_total,
        "leads_new": leads_new,
        "due_soon_count": len(reminders),
        "reminders": reminders[:8],
        "recent_bookings": safe_doc(recent),
    }
    if role in ("owner", "ops_admin"):
        base["total_revenue"] = round(total_revenue, 2)
        base["revenue_month"] = round(revenue_month, 2)
        base["outstanding_ar"] = round(outstanding_ar, 2)
    if role == "driver":
        base["my_active_bookings"] = active_bookings
    return base
