"""routers/growth.py — CRM Growth API (E2): scoreboard, SLA aging, RFM/retensi, segments, config.

Section RBAC 'crm' (owner/ops_admin). Urutan rute: literal/sub-path sebelum /{id} berparameter.
"""
from fastapi import APIRouter, Depends, HTTPException, Query

from core_utils import new_id, now_iso, safe_doc
from db import get_db
from dependencies import require_role, require_section
from schemas import GrowthConfigUpdate, SegmentCreate, SegmentUpdate
from services import growth, segments as seg_svc
from services.audit import record
from services.crm import OPEN_STAGES

router = APIRouter(prefix="/api", tags=["growth"])
CRM = require_section("crm")
OWNER = require_role("owner")


async def _umap(db):
    return {u["id"]: u.get("name") for u in await db.users.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(500)}


@router.get("/crm/scoreboard")
async def scoreboard(band: str = Query(default=None), assigned: str = Query(default=None),
                     limit: int = Query(default=200, le=500), user=Depends(CRM)):
    db = get_db()
    q = {"stage": {"$in": list(OPEN_STAGES)}}
    if band:
        q["score_band"] = band
    if assigned == "mine":
        q["assigned_to"] = user.get("id")
    elif assigned == "unassigned":
        q["assigned_to"] = None
    docs = await db.leads.find(q, {"_id": 0}).sort("score", -1).to_list(limit)
    umap = await _umap(db)
    for d in docs:
        d["assignee_name"] = umap.get(d.get("assigned_to"))
    bands = {"hot": 0, "warm": 0, "cold": 0}
    for d in docs:
        bands[d.get("score_band", "cold")] = bands.get(d.get("score_band", "cold"), 0) + 1
    return {"leads": safe_doc(docs), "bands": bands, "total": len(docs)}


@router.get("/crm/aging")
async def aging(user=Depends(CRM)):
    db = get_db()
    q = {"stage": {"$in": list(OPEN_STAGES)}}
    docs = await db.leads.find(q, {"_id": 0}).to_list(2000)
    umap = await _umap(db)
    buckets = {"breached": [], "at_risk": [], "on_track": [], "responded": []}
    for d in docs:
        key = "responded" if d.get("first_response_at") else d.get("sla_status", "on_track")
        if key not in buckets:
            key = "on_track"
        d["assignee_name"] = umap.get(d.get("assigned_to"))
        buckets[key].append(safe_doc(d))
    return {"buckets": buckets,
            "counts": {k: len(v) for k, v in buckets.items()}}


@router.get("/crm/rfm")
async def rfm(segment: str = Query(default=None), lifecycle: str = Query(default=None),
              limit: int = Query(default=300, le=1000), user=Depends(CRM)):
    db = get_db()
    cfg = await growth.get_config(db)
    customers = await db.customers.find({}, {"_id": 0}).to_list(2000)
    rows, seg_counts, lc_counts = [], {}, {}
    for c in customers:
        r = await growth.rfm_for_customer(db, c, cfg)
        seg_counts[r["rfm_segment"]] = seg_counts.get(r["rfm_segment"], 0) + 1
        lc_counts[r["lifecycle"]] = lc_counts.get(r["lifecycle"], 0) + 1
        row = {"id": c["id"], "name": c.get("name"), "phone": c.get("phone"), **r}
        if segment and r["rfm_segment"] != segment:
            continue
        if lifecycle and r["lifecycle"] != lifecycle:
            continue
        rows.append(row)
    rows.sort(key=lambda x: x["monetary"], reverse=True)
    return {"customers": rows[:limit], "segments": seg_counts, "lifecycles": lc_counts,
            "total": len(customers)}


@router.post("/crm/recompute")
async def recompute(user=Depends(CRM)):
    db = get_db()
    n = await growth.recompute_all(db)
    m = await growth.scan_rfm(db)
    return {"leads_scored": n, "customers_rfm": await db.customers.count_documents({}), "at_risk_flagged": m}


@router.get("/crm/growth-config")
async def get_growth_config(user=Depends(CRM)):
    return await growth.get_config(get_db())


@router.patch("/crm/growth-config")
async def update_growth_config(body: GrowthConfigUpdate, user=Depends(OWNER)):
    db = get_db()
    cfg = await growth.get_config(db)
    upd = body.model_dump(exclude_unset=True)
    sw = upd.pop("source_weights", None)
    cfg.update({k: v for k, v in upd.items() if v is not None})
    if isinstance(sw, dict):
        merged = dict(cfg.get("source_weights") or {})
        merged.update(sw)
        cfg["source_weights"] = merged
    await db.settings.update_one({"key": "crm_growth"}, {"$set": {"key": "crm_growth", "value": cfg}}, upsert=True)
    await record(db, actor=user, action="update", entity_type="settings", entity_id="crm_growth",
                 summary="Ubah konfigurasi CRM Growth (skoring/SLA/RFM)")
    return cfg


# --- Segments ---
@router.get("/crm/segments")
async def list_segments(audience: str = Query(default=None), user=Depends(CRM)):
    q = {"audience": audience} if audience else {}
    docs = await get_db().segments.find(q, {"_id": 0}).sort("created_at", -1).to_list(300)
    return safe_doc(docs)


@router.post("/crm/segments")
async def create_segment(body: SegmentCreate, user=Depends(CRM)):
    db = get_db()
    now = now_iso()
    doc = {"id": new_id("seg"), "name": body.name.strip(),
           "audience": body.audience if body.audience in ("lead", "customer") else "customer",
           "criteria": body.criteria or {}, "description": body.description or "",
           "system": False, "created_at": now, "updated_at": now}
    await db.segments.insert_one(doc)
    await record(db, actor=user, action="create", entity_type="segment", entity_id=doc["id"],
                 summary=f"Buat segmen '{doc['name']}'")
    return safe_doc(doc)


@router.get("/crm/segments/{segment_id}/preview")
async def preview_segment(segment_id: str, user=Depends(CRM)):
    db = get_db()
    seg = await db.segments.find_one({"id": segment_id}, {"_id": 0})
    if not seg:
        raise HTTPException(status_code=404, detail="Segmen tidak ditemukan")
    # R6-4 fix: kriteria segmen bisa malformed (mis. operator/tipe tak valid) → resolve_segment
    # dulu melempar → HTTP 500. Bungkus jadi 400 yang jelas (client error, bukan server error).
    try:
        count, members = await seg_svc.resolve_segment(db, seg, limit=2000)
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Kriteria segmen tidak valid: {e}")
    return {"count": count, "sample": members[:25],
            "reachable": sum(1 for m in members if m.get("phone"))}


@router.patch("/crm/segments/{segment_id}")
async def update_segment(segment_id: str, body: SegmentUpdate, user=Depends(CRM)):
    db = get_db()
    seg = await db.segments.find_one({"id": segment_id}, {"_id": 0})
    if not seg:
        raise HTTPException(status_code=404, detail="Segmen tidak ditemukan")
    upd = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    if upd:
        upd["updated_at"] = now_iso()
        await db.segments.update_one({"id": segment_id}, {"$set": upd})
    return safe_doc(await db.segments.find_one({"id": segment_id}, {"_id": 0}))


@router.delete("/crm/segments/{segment_id}")
async def delete_segment(segment_id: str, user=Depends(CRM)):
    db = get_db()
    seg = await db.segments.find_one({"id": segment_id}, {"_id": 0})
    if not seg:
        raise HTTPException(status_code=404, detail="Segmen tidak ditemukan")
    await db.segments.delete_one({"id": segment_id})
    return {"deleted": True, "id": segment_id}
