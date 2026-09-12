"""services/sequences.py — Nurturing Sequences / drip otomatis (E2).

Sequence = definisi langkah (delay + aksi WA/task/notif). Enrollment = peserta (lead/customer)
yang berjalan melewati langkah. Scheduler memproses enrollment jatuh tempo via E1 (send_wa).
Idempotent: 1 enrollment aktif per (sequence, target). Opt-out menghentikan langkah WA.
"""
import logging
from datetime import datetime, timedelta, timezone

from core_utils import new_id, now_iso

logger = logging.getLogger("travel_fleet.sequences")


async def enroll(db, sequence, target_id, name=None, phone=None):
    """Daftarkan 1 target ke sequence (skip bila sudah ada enrollment aktif). Return enrollment/None."""
    if not sequence.get("enabled", True) or not (sequence.get("steps") or []):
        return None
    exists = await db.sequence_enrollments.find_one(
        {"sequence_id": sequence["id"], "target_id": target_id, "status": "active"}, {"_id": 1})
    if exists:
        return None
    now = now_iso()
    doc = {
        "id": new_id("enr"), "sequence_id": sequence["id"], "sequence_name": sequence.get("name"),
        "audience": sequence.get("audience", "lead"), "target_id": target_id,
        "name": name or "Kontak", "phone": phone or "", "step_index": 0, "status": "active",
        "next_run_at": now, "enrolled_at": now, "last_step_at": None, "history": [],
    }
    await db.sequence_enrollments.insert_one(doc)
    await db.sequences.update_one({"id": sequence["id"]}, {"$inc": {"stats.enrolled": 1}})
    return doc


async def enroll_members(db, sequence, members):
    n = 0
    for m in members:
        if await enroll(db, sequence, m["target_id"], m.get("name"), m.get("phone")):
            n += 1
    return n


async def _resolve_phone(db, enr):
    if enr.get("phone"):
        return enr["phone"], enr.get("name")
    col = db.leads if enr.get("audience") == "lead" else db.customers
    nf = "customer_name" if enr.get("audience") == "lead" else "name"
    doc = await col.find_one({"id": enr["target_id"]}, {"_id": 0, "phone": 1, nf: 1})
    if not doc:
        return None, enr.get("name")
    return doc.get("phone"), doc.get(nf) or enr.get("name")


async def _execute_step(db, enr, step):
    """Jalankan 1 langkah sequence. Return ringkasan hasil."""
    action = (step.get("action") or "send_wa").lower()
    phone, name = await _resolve_phone(db, enr)
    variables = {"name": name, "customer_name": name}
    if action == "send_wa":
        if not phone:
            return {"action": action, "status": "skipped", "detail": "tanpa telepon"}
        from services.whatsapp import send_wa
        res = await send_wa(db, phone, text=step.get("text"), template_key=step.get("template_key"),
                            variables=variables,
                            lead_id=enr["target_id"] if enr.get("audience") == "lead" else None,
                            customer_id=enr["target_id"] if enr.get("audience") == "customer" else None,
                            contact_name=name, source=f"sequence:{enr['sequence_id']}")
        ok = res.get("status") in ("sent", "delivered", "read")
        return {"action": action, "status": "success" if ok else (res.get("status") or "failed"),
                "detail": f"Rp {int(res.get('cost') or 0)}"}
    # create_task / create_notification
    from services.automation import _upsert_notification  # reuse idempotent upsert
    title = (step.get("text") or step.get("title") or "Tindak lanjut nurturing")
    await _upsert_notification(db, dedupe_key=f"seq:{enr['id']}:{enr['step_index']}", base={
        "type": "task" if action == "create_task" else "automation",
        "title": f"{enr.get('sequence_name')}: {name}", "body": title,
        "ref_type": enr.get("audience"), "ref_id": enr["target_id"], "target_role": "manager"})
    return {"action": action, "status": "success", "detail": "notifikasi dibuat"}


async def process_due(db, limit=500):
    """Proses enrollment aktif yang jatuh tempo: jalankan langkah lalu majukan. Return jumlah langkah."""
    now = datetime.now(timezone.utc)
    now_s = now.isoformat()
    due = await db.sequence_enrollments.find(
        {"status": "active", "next_run_at": {"$lte": now_s}}, {"_id": 0}).to_list(limit)
    done = 0
    for enr in due:
        seq = await db.sequences.find_one({"id": enr["sequence_id"]}, {"_id": 0})
        steps = (seq or {}).get("steps") or []
        idx = enr.get("step_index", 0)
        if not seq or not seq.get("enabled", True) or idx >= len(steps):
            await db.sequence_enrollments.update_one({"id": enr["id"]}, {"$set": {"status": "completed"}})
            continue
        result = await _execute_step(db, enr, steps[idx])
        hist = {"step": idx, "at": now_s, **result}
        nxt = idx + 1
        upd = {"last_step_at": now_s}
        push = {"history": hist}
        if nxt >= len(steps):
            upd["status"] = "completed"
            upd["step_index"] = nxt
            await db.sequences.update_one({"id": seq["id"]}, {"$inc": {"stats.completed": 1}})
        else:
            delay = float(steps[nxt].get("delay_hours", 24) or 0)
            upd["step_index"] = nxt
            upd["next_run_at"] = (now + timedelta(hours=delay)).isoformat()
        await db.sequence_enrollments.update_one({"id": enr["id"]}, {"$set": upd, "$push": push})
        done += 1
    return done
