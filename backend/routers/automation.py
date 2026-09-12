"""routers/automation.py — Automation Engine API (E1).

Manajemen rules (event→kondisi→aksi) + monitoring eksekusi & event stream.
Section RBAC 'automation' (owner/ops_admin). Reset default = owner.
Urutan rute: literal/sub-path sebelum /{rule_id} berparameter.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query

from core_utils import new_id, now_iso, safe_doc
from db import get_db
from dependencies import require_role, require_section
from schemas import AutomationRuleCreate, AutomationRuleUpdate
from services.automation import ACTION_TYPES, default_rules
from services.audit import record
from services.events import EVENT_TYPES

router = APIRouter(prefix="/api", tags=["automation"])
AUTO = require_section("automation")
OWNER = require_role("owner")


@router.get("/automation/event-types")
async def list_event_types(user=Depends(AUTO)):
    return {
        "events": [{"key": k, "label": v} for k, v in EVENT_TYPES.items()],
        "actions": [{"key": k, "label": v} for k, v in ACTION_TYPES.items()],
    }


@router.get("/automation/stats")
async def automation_stats(user=Depends(AUTO)):
    db = get_db()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rules_total = await db.automation_rules.count_documents({})
    rules_active = await db.automation_rules.count_documents({"enabled": True})
    runs_total = await db.automation_runs.count_documents({})
    runs_today = await db.automation_runs.count_documents({"created_at": {"$regex": f"^{today}"}})
    runs_failed = await db.automation_runs.count_documents({"status": "failed"})
    events_total = await db.events.count_documents({})
    wa_sent = await db.messages.count_documents({"channel": "whatsapp", "direction": "out"})
    wa_in = await db.messages.count_documents({"channel": "whatsapp", "direction": "in"})
    agg = await db.messages.aggregate([
        {"$match": {"channel": "whatsapp", "direction": "out"}},
        {"$group": {"_id": None, "cost": {"$sum": "$cost"}}},
    ]).to_list(1)
    wa_cost = float(agg[0]["cost"]) if agg else 0.0
    return {
        "rules_total": rules_total, "rules_active": rules_active,
        "runs_total": runs_total, "runs_today": runs_today, "runs_failed": runs_failed,
        "events_total": events_total, "wa_sent": wa_sent, "wa_inbound": wa_in,
        "wa_cost": wa_cost,
    }


@router.get("/automation/runs")
async def list_runs(rule_id: str = Query(default=None), status: str = Query(default=None),
                    event_type: str = Query(default=None), limit: int = Query(default=100, le=300),
                    skip: int = Query(default=0, ge=0), user=Depends(AUTO)):
    q = {}
    if rule_id:
        q["rule_id"] = rule_id
    if status:
        q["status"] = status
    if event_type:
        q["event_type"] = event_type
    docs = await get_db().automation_runs.find(q, {"_id": 0}).sort("created_at", -1).skip(skip).to_list(limit)
    return safe_doc(docs)


@router.get("/automation/events")
async def list_events(event_type: str = Query(default=None), limit: int = Query(default=100, le=300),
                      skip: int = Query(default=0, ge=0), user=Depends(AUTO)):
    q = {}
    if event_type:
        q["type"] = event_type
    docs = await get_db().events.find(q, {"_id": 0}).sort("created_at", -1).skip(skip).to_list(limit)
    return safe_doc(docs)


@router.post("/automation/rules/reset-defaults")
async def reset_defaults(user=Depends(OWNER)):
    """Pasang ulang rule contoh sistem (aktif). Rule kustom non-sistem dibiarkan."""
    db = get_db()
    await db.automation_rules.delete_many({"system": True})
    rules = default_rules()
    await db.automation_rules.insert_many(rules)
    await record(db, actor=user, action="update", entity_type="automation_rule", entity_id="(defaults)",
                 summary=f"Reset {len(rules)} aturan otomasi default")
    return {"installed": len(rules)}


@router.get("/automation/rules")
async def list_rules(event_type: str = Query(default=None), enabled: str = Query(default=None),
                     limit: int = Query(default=200, le=500), user=Depends(AUTO)):
    q = {}
    if event_type:
        q["event_type"] = event_type
    if enabled in ("true", "false"):
        q["enabled"] = enabled == "true"
    docs = await get_db().automation_rules.find(q, {"_id": 0}).sort("created_at", 1).to_list(limit)
    return safe_doc(docs)


@router.post("/automation/rules")
async def create_rule(body: AutomationRuleCreate, user=Depends(AUTO)):
    db = get_db()
    if body.event_type not in EVENT_TYPES:
        raise HTTPException(status_code=400, detail="Jenis event tidak dikenal")
    now = now_iso()
    doc = {
        "id": new_id("aur"), "name": body.name.strip(), "description": body.description or "",
        "event_type": body.event_type, "enabled": bool(body.enabled), "system": False,
        "conditions": [c.model_dump() if hasattr(c, "model_dump") else dict(c) for c in (body.conditions or [])],
        "actions": [a.model_dump() if hasattr(a, "model_dump") else dict(a) for a in (body.actions or [])],
        "run_count": 0, "last_run_at": None, "created_at": now, "updated_at": now,
    }
    await db.automation_rules.insert_one(doc)
    await record(db, actor=user, action="create", entity_type="automation_rule", entity_id=doc["id"],
                 summary=f"Buat aturan otomasi '{doc['name']}' ({doc['event_type']})")
    return safe_doc(doc)


@router.get("/automation/rules/{rule_id}")
async def get_rule(rule_id: str, user=Depends(AUTO)):
    doc = await get_db().automation_rules.find_one({"id": rule_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Aturan tidak ditemukan")
    return safe_doc(doc)


@router.patch("/automation/rules/{rule_id}")
async def update_rule(rule_id: str, body: AutomationRuleUpdate, user=Depends(AUTO)):
    db = get_db()
    rule = await db.automation_rules.find_one({"id": rule_id}, {"_id": 0})
    if not rule:
        raise HTTPException(status_code=404, detail="Aturan tidak ditemukan")
    updates = {}
    if body.name is not None:
        updates["name"] = body.name.strip()
    if body.description is not None:
        updates["description"] = body.description
    if body.event_type is not None:
        if body.event_type not in EVENT_TYPES:
            raise HTTPException(status_code=400, detail="Jenis event tidak dikenal")
        updates["event_type"] = body.event_type
    if body.enabled is not None:
        updates["enabled"] = bool(body.enabled)
    if body.conditions is not None:
        updates["conditions"] = [c.model_dump() if hasattr(c, "model_dump") else dict(c) for c in body.conditions]
    if body.actions is not None:
        updates["actions"] = [a.model_dump() if hasattr(a, "model_dump") else dict(a) for a in body.actions]
    if updates:
        updates["updated_at"] = now_iso()
        await db.automation_rules.update_one({"id": rule_id}, {"$set": updates})
        await record(db, actor=user, action="update", entity_type="automation_rule", entity_id=rule_id,
                     summary=f"Ubah aturan otomasi '{rule.get('name')}': {', '.join(updates.keys())}")
    return safe_doc(await db.automation_rules.find_one({"id": rule_id}, {"_id": 0}))


@router.delete("/automation/rules/{rule_id}")
async def delete_rule(rule_id: str, user=Depends(AUTO)):
    db = get_db()
    rule = await db.automation_rules.find_one({"id": rule_id}, {"_id": 0})
    if not rule:
        raise HTTPException(status_code=404, detail="Aturan tidak ditemukan")
    await db.automation_rules.delete_one({"id": rule_id})
    await record(db, actor=user, action="delete", entity_type="automation_rule", entity_id=rule_id,
                 summary=f"Hapus aturan otomasi '{rule.get('name')}'")
    return {"deleted": True, "id": rule_id}
