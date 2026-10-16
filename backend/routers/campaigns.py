"""routers/campaigns.py — Nurturing Sequences + Campaign broadcast API (E2).

Section RBAC 'crm'. Sequences: definisi langkah + enroll (target/segmen) + monitoring enrollment.
Campaigns: broadcast WA tersegmentasi (kirim sekarang/terjadwal) + per-penerima + statistik.
"""
from fastapi import APIRouter, Depends, HTTPException, Query

from core_utils import new_id, now_iso, safe_doc
from db import get_db
from services.refs import must_exist
from dependencies import require_section
from schemas import (CampaignCreate, CampaignUpdate, SequenceCreate,
                     SequenceEnrollRequest, SequenceUpdate)
from services import campaigns as cmp_svc, segments as seg_svc, sequences as seq_svc
from services.audit import record

router = APIRouter(prefix="/api", tags=["campaigns"])
CRM = require_section("crm")


def _steps(steps):
    return [s.model_dump() if hasattr(s, "model_dump") else dict(s) for s in (steps or [])]


# ---------------- Sequences ----------------
@router.get("/crm/sequences")
async def list_sequences(user=Depends(CRM)):
    docs = await get_db().sequences.find({}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return safe_doc(docs)


@router.post("/crm/sequences")
async def create_sequence(body: SequenceCreate, user=Depends(CRM)):
    db = get_db()
    now = now_iso()
    doc = {"id": new_id("seq"), "name": body.name.strip(), "description": body.description or "",
           "audience": body.audience if body.audience in ("lead", "customer") else "lead",
           "enabled": bool(body.enabled), "steps": _steps(body.steps),
           "stats": {"enrolled": 0, "completed": 0}, "created_at": now, "updated_at": now}
    await db.sequences.insert_one(doc)
    await record(db, actor=user, action="create", entity_type="sequence", entity_id=doc["id"],
                 summary=f"Buat sequence '{doc['name']}'")
    return safe_doc(doc)


@router.get("/crm/sequences/{sequence_id}/enrollments")
async def list_enrollments(sequence_id: str, status: str = Query(default=None),
                           limit: int = Query(default=200, le=500), user=Depends(CRM)):
    q = {"sequence_id": sequence_id}
    if status:
        q["status"] = status
    docs = await get_db().sequence_enrollments.find(q, {"_id": 0}).sort("enrolled_at", -1).to_list(limit)
    return safe_doc(docs)


@router.post("/crm/sequences/{sequence_id}/enroll")
async def enroll_sequence(sequence_id: str, body: SequenceEnrollRequest, user=Depends(CRM)):
    db = get_db()
    seq = await db.sequences.find_one({"id": sequence_id}, {"_id": 0})
    if not seq:
        raise HTTPException(status_code=404, detail="Sequence tidak ditemukan")
    if body.segment_id:
        segment = await db.segments.find_one({"id": body.segment_id}, {"_id": 0})
        if not segment:
            raise HTTPException(status_code=404, detail="Segmen tidak ditemukan")
        _, members = await seg_svc.resolve_segment(db, segment)
        n = await seq_svc.enroll_members(db, seq, members)
        return {"enrolled": n, "from_segment": body.segment_id}
    if not body.target_id:
        raise HTTPException(status_code=400, detail="target_id atau segment_id wajib diisi")
    col = db.leads if seq.get("audience") == "lead" else db.customers
    nf = "customer_name" if seq.get("audience") == "lead" else "name"
    t = await col.find_one({"id": body.target_id}, {"_id": 0, "phone": 1, nf: 1})
    if not t:
        raise HTTPException(status_code=404, detail="Target tidak ditemukan")
    enr = await seq_svc.enroll(db, seq, body.target_id, name=t.get(nf), phone=t.get("phone"))
    return {"enrolled": 1 if enr else 0, "enrollment": safe_doc(enr) if enr else None}


@router.patch("/crm/sequences/{sequence_id}")
async def update_sequence(sequence_id: str, body: SequenceUpdate, user=Depends(CRM)):
    db = get_db()
    seq = await db.sequences.find_one({"id": sequence_id}, {"_id": 0})
    if not seq:
        raise HTTPException(status_code=404, detail="Sequence tidak ditemukan")
    upd = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    if "steps" in upd:
        upd["steps"] = _steps(body.steps)
    if upd:
        upd["updated_at"] = now_iso()
        await db.sequences.update_one({"id": sequence_id}, {"$set": upd})
    return safe_doc(await db.sequences.find_one({"id": sequence_id}, {"_id": 0}))


@router.delete("/crm/sequences/{sequence_id}")
async def delete_sequence(sequence_id: str, user=Depends(CRM)):
    db = get_db()
    if not await db.sequences.find_one({"id": sequence_id}, {"_id": 1}):
        raise HTTPException(status_code=404, detail="Sequence tidak ditemukan")
    await db.sequences.delete_one({"id": sequence_id})
    await db.sequence_enrollments.update_many({"sequence_id": sequence_id, "status": "active"},
                                              {"$set": {"status": "stopped"}})
    return {"deleted": True, "id": sequence_id}


@router.post("/crm/enrollments/{enrollment_id}/stop")
async def stop_enrollment(enrollment_id: str, user=Depends(CRM)):
    db = get_db()
    if not await db.sequence_enrollments.find_one({"id": enrollment_id}, {"_id": 1}):
        raise HTTPException(status_code=404, detail="Enrollment tidak ditemukan")
    await db.sequence_enrollments.update_one({"id": enrollment_id}, {"$set": {"status": "stopped"}})
    return {"stopped": True, "id": enrollment_id}


# ---------------- Campaigns ----------------
@router.get("/crm/campaigns")
async def list_campaigns(user=Depends(CRM)):
    docs = await get_db().campaigns.find({}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return safe_doc(docs)


@router.post("/crm/campaigns")
async def create_campaign(body: CampaignCreate, user=Depends(CRM)):
    db = get_db()
    if not body.segment_id and not body.criteria:
        raise HTTPException(status_code=400, detail="segment_id atau criteria wajib diisi")
    if not body.message and not body.template_key:
        raise HTTPException(status_code=400, detail="message atau template_key wajib diisi")
    aud = body.audience if body.audience in ("lead", "customer") else "customer"
    # INV-REF-01: segmen yang dituju WAJIB ada. Kampanye dengan `segment_id` hantu terkirim
    # ke NOL penerima dan tampak "sukses" di dasbor — anggaran & waktu ops habis tanpa jejak.
    await must_exist(db, "segments", body.segment_id)
    doc = {"id": new_id("cmp"), "name": body.name.strip(), "channel": "whatsapp", "audience": aud,
           "segment_id": body.segment_id, "segment_snapshot": {"audience": aud, "criteria": body.criteria or {}},
           "template_key": body.template_key, "message": body.message or "",
           "scheduled_at": body.scheduled_at,
           "status": "scheduled" if body.scheduled_at else "draft",
           "stats": {}, "created_by": user.get("id"), "created_at": now_iso(), "sent_at": None}
    await db.campaigns.insert_one(doc)
    await record(db, actor=user, action="create", entity_type="campaign", entity_id=doc["id"],
                 summary=f"Buat kampanye '{doc['name']}'")
    return safe_doc(doc)


@router.get("/crm/campaigns/{campaign_id}")
async def get_campaign(campaign_id: str, user=Depends(CRM)):
    db = get_db()
    c = await db.campaigns.find_one({"id": campaign_id}, {"_id": 0})
    if not c:
        raise HTTPException(status_code=404, detail="Kampanye tidak ditemukan")
    recs = await db.campaign_recipients.find({"campaign_id": campaign_id}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    out = safe_doc(c)
    out["recipients"] = safe_doc(recs)
    return out


@router.patch("/crm/campaigns/{campaign_id}")
async def update_campaign(campaign_id: str, body: CampaignUpdate, user=Depends(CRM)):
    db = get_db()
    c = await db.campaigns.find_one({"id": campaign_id}, {"_id": 0})
    if not c:
        raise HTTPException(status_code=404, detail="Kampanye tidak ditemukan")
    if c.get("status") in ("sending", "sent"):
        raise HTTPException(status_code=400, detail="Kampanye sudah dikirim, tidak bisa diubah")
    upd = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    if "criteria" in upd:
        upd["segment_snapshot"] = {"audience": c.get("audience", "customer"), "criteria": upd["criteria"]}
    if "scheduled_at" in upd:
        upd["status"] = "scheduled" if upd["scheduled_at"] else "draft"
    if upd:
        await db.campaigns.update_one({"id": campaign_id}, {"$set": upd})
    return safe_doc(await db.campaigns.find_one({"id": campaign_id}, {"_id": 0}))


@router.delete("/crm/campaigns/{campaign_id}")
async def delete_campaign(campaign_id: str, user=Depends(CRM)):
    db = get_db()
    if not await db.campaigns.find_one({"id": campaign_id}, {"_id": 1}):
        raise HTTPException(status_code=404, detail="Kampanye tidak ditemukan")
    await db.campaigns.delete_one({"id": campaign_id})
    await db.campaign_recipients.delete_many({"campaign_id": campaign_id})
    return {"deleted": True, "id": campaign_id}


@router.post("/crm/campaigns/{campaign_id}/send")
async def send_campaign(campaign_id: str, user=Depends(CRM)):
    db = get_db()
    c = await db.campaigns.find_one({"id": campaign_id}, {"_id": 0})
    if not c:
        raise HTTPException(status_code=404, detail="Kampanye tidak ditemukan")
    stats = await cmp_svc.send_campaign(db, c)
    if stats.get("error"):
        raise HTTPException(status_code=400, detail=stats["error"])
    await record(db, actor=user, action="send", entity_type="campaign", entity_id=campaign_id,
                 summary=f"Kirim kampanye '{c.get('name')}' ke {stats.get('total')} kontak")
    return stats
