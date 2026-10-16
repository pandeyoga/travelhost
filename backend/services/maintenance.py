"""services/maintenance.py — engine Maintenance (Phase 6).

- derive_status()     : status terkomputasi (scheduled|in_progress|done|cancelled).
- build_doc_reminders : reminder dokumen armada (KIR/pajak/servis) dgn bucket urgensi
                        H-30/14/7/overdue, dari `vehicles.kir_expiry/tax_expiry/next_service_date`.
- in_service_vehicle_ids: armada yang sedang in_service (window in_progress) — info dashboard.

Window perawatan (status scheduled/in_progress dgn start_date+end_date) MEMBLOK
availability armada (INV-21) — lihat services/availability.find_maintenance_conflicts.
"""
from datetime import datetime, timedelta, timezone

from services.geo import parse_iso

REMINDER_FIELDS = (("kir_expiry", "KIR"), ("tax_expiry", "Pajak"), ("next_service_date", "Servis"))
WINDOW_DAYS = 30
MAINT_TYPES = {"servis", "kir", "pajak", "perbaikan", "lainnya"}
MAINT_STATUSES = {"scheduled", "in_progress", "done", "cancelled"}
BLOCKING_STATUSES = {"scheduled", "in_progress"}


def bucket(days_left):
    """Klasifikasi urgensi berdasarkan sisa hari."""
    if days_left is None:
        return "none"
    if days_left < 0:
        return "overdue"
    if days_left <= 7:
        return "h7"
    if days_left <= 14:
        return "h14"
    return "h30"


def derive_status(record, now=None):
    """Status terkomputasi bila tidak diset eksplisit ke done/cancelled."""
    st = record.get("status")
    if st in ("done", "cancelled"):
        return st
    now = now or datetime.now(timezone.utc)
    start = parse_iso(record.get("start_date"))
    end = parse_iso(record.get("end_date"))
    if start and end and start <= now <= end:
        return "in_progress"
    return st or "scheduled"


async def build_doc_reminders(db, horizon_days=WINDOW_DAYS):
    """Reminder dokumen armada due-soon (≤ horizon) + overdue, dgn bucket urgensi."""
    now = datetime.now(timezone.utc)
    horizon = now + timedelta(days=horizon_days)
    veh = await db.vehicles.find(
        {}, {"_id": 0, "id": 1, "code": 1, "name": 1, "kir_expiry": 1,
             "tax_expiry": 1, "next_service_date": 1, "status": 1},
    ).to_list(2000)
    out = []
    for v in veh:
        for field, label in REMINDER_FIELDS:
            d = parse_iso(v.get(field))
            if d and d <= horizon:
                days_left = (d - now).days
                out.append({
                    "vehicle_id": v.get("id"), "vehicle_name": v.get("name"), "code": v.get("code"),
                    "type": label, "field": field, "due_date": v.get(field),
                    "days_left": days_left, "overdue": d < now, "bucket": bucket(days_left),
                })
    out.sort(key=lambda r: r.get("due_date") or "")
    return out


async def in_service_vehicle_ids(db):
    """Set vehicle_id yang sedang dalam window perawatan in_progress sekarang."""
    now = datetime.now(timezone.utc)
    recs = await db.maintenance_records.find(
        {"status": {"$in": list(BLOCKING_STATUSES)}}, {"_id": 0}
    ).to_list(2000)
    ids = set()
    for m in recs:
        start = parse_iso(m.get("start_date"))
        end = parse_iso(m.get("end_date"))
        if start and end and start <= now <= end and m.get("vehicle_id"):
            ids.add(m["vehicle_id"])
    return ids


async def summary(db):
    """Ringkasan KPI untuk halaman & dashboard."""
    recs = await db.maintenance_records.find({}, {"_id": 0}).to_list(5000)
    counts = {"scheduled": 0, "in_progress": 0, "done": 0, "cancelled": 0}
    total_cost = 0.0
    for m in recs:
        st = m.get("status", "scheduled")
        counts[st] = counts.get(st, 0) + 1
        if st == "done":
            total_cost += float(m.get("cost", 0) or 0)
    reminders = await build_doc_reminders(db)
    return {
        "total": len(recs),
        "scheduled": counts.get("scheduled", 0),
        "in_progress": counts.get("in_progress", 0),
        "done": counts.get("done", 0),
        "cancelled": counts.get("cancelled", 0),
        "due_soon": len(reminders),
        "overdue": sum(1 for r in reminders if r.get("overdue")),
        "total_service_cost": round(total_cost, 2),
    }
