"""services/notifications.py — mesin reminder + visibilitas notifikasi (Phase 7).

`scan(db)` memindai sumber reminder lalu meng-upsert `notification_tasks` (idempotent
via `dedupe_key` per skenario+hari) — dipanggil scheduler loop & endpoint /scan:
  - Dokumen armada (KIR/pajak/servis due ≤ 30 hari / overdue)  → target 'manager'
  - Masa berlaku SIM driver (≤ 30 hari / overdue)               → target 'manager'
  - Follow-up lead (open + trip_date H-7/3/1/overdue)          → target agen (assigned_to)
  - Pengingat keberangkatan booking (mulai ≤ 24 jam, aktif)     → target 'manager'

`visibility_query(user)` → filter Mongo notifikasi yang boleh dilihat user.
"""
from datetime import datetime, timezone, timedelta
import calendar

from core_utils import new_id, now_iso
from services.crm import OPEN_STAGES
from services.events import emit
from services.geo import parse_iso
from services.maintenance import build_doc_reminders


def _today_key():
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def visibility_query(user):
    """Notifikasi terlihat bila ditujukan ke user, role-nya, 'manager' (owner/ops), atau 'all'."""
    role = user.get("role")
    ors = [{"target_user_id": user.get("id")}, {"target_role": None},
           {"target_role": "all"}, {"target_role": role}]
    if role in ("owner", "ops_admin"):
        ors.append({"target_role": "manager"})
    return {"$or": ors}


async def _upsert(db, dedupe_key, base):
    """Buat notifikasi bila dedupe_key belum ada (idempotent). Return 1 bila dibuat."""
    if await db.notification_tasks.find_one({"dedupe_key": dedupe_key}, {"_id": 1}):
        return 0
    doc = {
        "id": new_id("ntf"), "dedupe_key": dedupe_key, "status": "pending",
        "channel": "in_app", "read_at": None, "created_at": now_iso(),
        "target_role": None, "target_user_id": None, "booking_id": None, "lead_id": None,
    }
    doc.update(base)
    await db.notification_tasks.insert_one(doc)
    return 1


async def create_task(db, dedupe_key, base):
    """Publik & idempotent: buat notifikasi in-app event-driven (mis. alarm GPS E15).

    `base` minimal berisi type/title/body/target_role/ref_type/ref_id. Return 1 bila dibuat,
    0 bila sudah ada (dedupe). Dipakai modul non-scheduler yang perlu push notifikasi.
    """
    return await _upsert(db, dedupe_key, base)


def _bucket(days):
    if days < 0:
        return "overdue", "lewat tempo"
    if days <= 1:
        return "h1", "besok"
    if days <= 3:
        return "h3", f"{days} hari lagi"
    if days <= 7:
        return "h7", f"{days} hari lagi"
    return None, None


async def scan(db):
    """Hasilkan notifikasi terjadwal dari semua sumber. Return jumlah notifikasi baru."""
    created = 0
    now = datetime.now(timezone.utc)
    day = _today_key()

    # 1) Dokumen armada (KIR/pajak/servis)
    for r in await build_doc_reminders(db):
        urg = "lewat tempo" if r.get("overdue") else f"{r.get('days_left')} hari lagi"
        created += await _upsert(db, f"doc:{r['vehicle_id']}:{r['field']}:{str(r.get('due_date'))[:10]}", {
            "type": "document_reminder",
            "title": f"{r['type']} {r.get('code')} {urg}",
            "body": f"{r['type']} {r.get('vehicle_name')} jatuh tempo {str(r.get('due_date'))[:10]}.",
            "ref_type": "vehicle", "ref_id": r["vehicle_id"],
            "due_at": r.get("due_date"), "scheduled_at": now_iso(), "target_role": "manager",
        })

    # 2) Follow-up lead (open + trip_date dekat/lewat)
    leads = await db.leads.find(
        {"stage": {"$in": list(OPEN_STAGES)}, "trip_date": {"$ne": None}}, {"_id": 0}).to_list(2000)
    for ld in leads:
        dt = parse_iso(ld.get("trip_date"))
        if not dt:
            continue
        days = (dt.date() - now.date()).days
        bucket, label = _bucket(days)
        if not bucket:
            continue
        created += await _upsert(db, f"lead:{ld['id']}:{day}", {
            "type": "lead_followup",
            "title": f"Follow-up lead: {ld.get('customer_name')} ({label})",
            "body": f"Trip {ld.get('destination') or '-'} {label}. Tahap: {ld.get('stage')}.",
            "ref_type": "lead", "ref_id": ld["id"], "lead_id": ld["id"],
            "due_at": ld.get("trip_date"), "scheduled_at": now_iso(),
            "target_role": None if ld.get("assigned_to") else "manager",
            "target_user_id": ld.get("assigned_to"),
        })

    # 1b) Event doc.expiring (audit + otomasi)
    for r in await build_doc_reminders(db):
        await emit(db, "doc.expiring", {
            "vehicle_id": r["vehicle_id"], "vehicle_name": r.get("vehicle_name"),
            "type": r["type"], "code": r.get("code"), "due_date": str(r.get("due_date"))[:10],
            "days_left": r.get("days_left"), "overdue": bool(r.get("overdue")),
        }, source="scheduler", ref_type="vehicle", ref_id=r["vehicle_id"],
            dedupe_key=f"evt-doc:{r['vehicle_id']}:{r['field']}:{str(r.get('due_date'))[:10]}")

    # 1c) Masa berlaku SIM driver (≤ 30 hari / lewat tempo) → target 'manager'
    sim_horizon = now + timedelta(days=30)
    sim_drivers = await db.drivers.find(
        {"sim_expiry": {"$ne": None}},
        {"_id": 0, "id": 1, "name": 1, "sim_number": 1, "sim_expiry": 1}).to_list(3000)
    for d in sim_drivers:
        exp = parse_iso(d.get("sim_expiry"))
        if not exp or exp > sim_horizon:
            continue
        days_left = (exp - now).days
        overdue = exp < now
        urg = "lewat tempo" if overdue else f"{days_left} hari lagi"
        exp_key = str(d.get("sim_expiry"))[:10]
        created += await _upsert(db, f"sim:{d['id']}:{exp_key}", {
            "type": "sim_reminder",
            "title": f"SIM {d.get('name')} {urg}",
            "body": f"SIM {d.get('sim_number') or '-'} a.n. {d.get('name')} jatuh tempo {exp_key}.",
            "ref_type": "driver", "ref_id": d["id"],
            "due_at": d.get("sim_expiry"), "scheduled_at": now_iso(), "target_role": "manager",
        })
        await emit(db, "driver.sim_expiring", {
            "driver_id": d["id"], "driver_name": d.get("name"), "sim_number": d.get("sim_number"),
            "due_date": exp_key, "days_left": days_left, "overdue": overdue,
        }, source="scheduler", ref_type="driver", ref_id=d["id"],
            dedupe_key=f"evt-sim:{d['id']}:{exp_key}")

    # 3) Pengingat keberangkatan booking (mulai ≤ 24 jam, status aktif)
    bookings = await db.bookings.find(
        {"status": {"$in": ["confirmed", "ongoing"]}}, {"_id": 0}).to_list(3000)
    cust_phone = {c["id"]: c.get("phone") for c in await db.customers.find(
        {}, {"_id": 0, "id": 1, "phone": 1}).to_list(5000)}
    drv_name = {d["id"]: d.get("name") for d in await db.drivers.find(
        {}, {"_id": 0, "id": 1, "name": 1}).to_list(2000)}
    for bk in bookings:
        st = parse_iso(bk.get("start_datetime"))
        if not st:
            continue
        hours = (st - now).total_seconds() / 3600.0
        if 0 <= hours <= 24:
            created += await _upsert(db, f"booking:{bk['id']}:{day}", {
                "type": "booking_reminder",
                "title": f"Keberangkatan {bk.get('code')} dalam {round(hours)} jam",
                "body": f"{bk.get('customer_name')} → {bk.get('destination') or '-'} ({bk.get('vehicle_name') or '-'}).",
                "ref_type": "booking", "ref_id": bk["id"], "booking_id": bk["id"],
                "due_at": bk.get("start_datetime"), "scheduled_at": now_iso(), "target_role": "manager",
            })
            await emit(db, "booking.departure_due", {
                "booking_id": bk["id"], "code": bk.get("code"), "customer_name": bk.get("customer_name"),
                "phone": cust_phone.get(bk.get("customer_id")), "vehicle_name": bk.get("vehicle_name"),
                "driver_name": drv_name.get(bk.get("driver_id")), "when": f"dalam {round(hours)} jam",
            }, source="scheduler", ref_type="booking", ref_id=bk["id"],
                dedupe_key=f"evt-departure:{bk['id']}:{day}")

    # 4) Invoice lewat tempo (status terkirim & jatuh tempo terlewati)
    now_iso_s = now.isoformat()
    invoices = await db.invoices.find(
        {"status": {"$in": ["sent", "unpaid", "partial"]}}, {"_id": 0}).to_list(3000)
    for inv in invoices:
        due = parse_iso(inv.get("due_at"))
        if not due or due >= now:
            continue
        created += await _upsert(db, f"invoice:{inv['id']}:{day}", {
            "type": "invoice_overdue",
            "title": f"Invoice {inv.get('number')} lewat tempo",
            "body": f"{inv.get('customer_name')} — Rp {int(inv.get('amount', 0) or 0):,}.".replace(",", "."),
            "ref_type": "invoice", "ref_id": inv["id"], "booking_id": inv.get("booking_id"),
            "due_at": inv.get("due_at"), "scheduled_at": now_iso(), "target_role": "manager",
        })
        await emit(db, "invoice.overdue", {
            "invoice_id": inv["id"], "number": inv.get("number"), "customer_name": inv.get("customer_name"),
            "phone": cust_phone.get(inv.get("customer_id")), "amount": float(inv.get("amount", 0) or 0),
            "booking_id": inv.get("booking_id"),
        }, source="scheduler", ref_type="invoice", ref_id=inv["id"],
            dedupe_key=f"evt-invoice:{inv['id']}:{day}")

    # 5) Payroll: pengingat akhir periode (3 hari terakhir bulan) + payout menunggu diproses
    period_key = now.strftime("%Y-%m")
    days_in_month = calendar.monthrange(now.year, now.month)[1]
    if now.day >= days_in_month - 2:
        created += await _upsert(db, f"payroll-period:{period_key}", {
            "type": "payroll_reminder",
            "title": f"Periode payroll {period_key} akan berakhir",
            "body": "Generate payout driver untuk periode berjalan (Keuangan → Payroll).",
            "ref_type": "payroll", "ref_id": period_key,
            "due_at": now_iso(), "scheduled_at": now_iso(), "target_role": "manager",
        })
        await emit(db, "payroll.period_due", {"period": period_key, "day": now.day},
                   source="scheduler", ref_type="payroll", ref_id=period_key,
                   dedupe_key=f"evt-payroll-period:{period_key}")

    pending = await db.driver_payouts.find(
        {"status": {"$in": ["draft", "approved"]}}, {"_id": 0}).to_list(3000)
    for p in pending:
        need = "disetujui" if p.get("status") == "draft" else "dibayar"
        amt = f"{int(p.get('total', 0) or 0):,}".replace(",", ".")
        created += await _upsert(db, f"payroll-pending:{p['id']}:{day}", {
            "type": "payroll_reminder",
            "title": f"Payout {p.get('driver_name')} menunggu {need}",
            "body": f"Periode {p.get('period_start')}—{p.get('period_end')} · Rp {amt}. Status: {p.get('status')}.",
            "ref_type": "payroll", "ref_id": p["id"],
            "due_at": now_iso(), "scheduled_at": now_iso(), "target_role": "manager",
        })
        await emit(db, "payroll.payout_pending", {
            "payout_id": p["id"], "driver_name": p.get("driver_name"), "status": p.get("status"),
            "total": float(p.get("total", 0) or 0), "period_start": p.get("period_start"),
        }, source="scheduler", ref_type="payroll", ref_id=p["id"],
            dedupe_key=f"evt-payroll-pending:{p['id']}:{day}")

    # 6) E18 DP-gate — auto-expire 'hold' yang lewat batas & DP belum cukup → cancelled.
    holds = await db.bookings.find(
        {"status": "hold", "hold_expires_at": {"$ne": None, "$lt": now_iso_s}}, {"_id": 0}).to_list(2000)
    for bk in holds:
        dp_amount = float(bk.get("dp_amount") or 0)
        if dp_amount <= 0:
            dp_amount = float(bk.get("total_amount", 0) or 0) * float(bk.get("dp_percent", 30) or 30) / 100.0
        paid = float(bk.get("paid_amount", 0) or 0)
        if dp_amount > 0 and paid >= dp_amount:
            continue  # DP sudah cukup (akan/telah dipromosikan ke confirmed) — jangan batalkan
        cancelled = await db.bookings.find_one_and_update(
            {"id": bk["id"], "status": "hold"},
            {"$set": {"status": "cancelled", "hold_expired_at": now_iso()}})
        if not cancelled:
            continue
        await db.trips.update_many(
            {"booking_id": bk["id"], "status": {"$in": ["standby", "to_pickup"]}},
            {"$set": {"status": "cancelled"}})
        created += await _upsert(db, f"hold-expired:{bk['id']}", {
            "type": "booking_hold_expired",
            "title": f"Hold kedaluwarsa: {bk.get('code')}",
            "body": f"{bk.get('customer_name')} — DP tak masuk sebelum batas waktu; booking dibatalkan.",
            "ref_type": "booking", "ref_id": bk["id"], "booking_id": bk["id"],
            "scheduled_at": now_iso(), "target_role": "manager",
        })
        await emit(db, "booking.hold_expired", {
            "booking_id": bk["id"], "code": bk.get("code"), "customer_name": bk.get("customer_name"),
            "phone": cust_phone.get(bk.get("customer_id")), "vehicle_name": bk.get("vehicle_name"),
        }, source="scheduler", ref_type="booking", ref_id=bk["id"],
            dedupe_key=f"evt-hold-expired:{bk['id']}")
    return created
