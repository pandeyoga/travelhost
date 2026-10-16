"""routers/workshops.py — Master Vendor/Bengkel (E8 Fleet).

CRUD bengkel/vendor servis. Dipakai saat menjadwalkan perawatan
(`maintenance_records.workshop_id`). List/detail: semua role login (driver read-only).
Mutasi (create/update/delete): owner/ops_admin.

Kontrak rute (semua /api):
  GET    /workshops?active=&q=     -> [workshop]
  POST   /workshops                <- WorkshopCreate -> workshop
  PATCH  /workshops/{workshop_id}  <- WorkshopUpdate -> workshop
  DELETE /workshops/{workshop_id}  -> {deleted, id}
"""
from fastapi import APIRouter, Depends, HTTPException, Query

from core_utils import new_id, now_iso, safe_doc
from db import get_db
from dependencies import get_current_user, require_role
from schemas import WorkshopCreate, WorkshopUpdate
from services.audit import record
from services.refs import city_or_400

router = APIRouter(prefix="/api", tags=["workshops"])
MANAGER = require_role("owner", "ops_admin")


@router.get("/workshops")
async def list_workshops(active: bool = Query(default=None), q: str = Query(default=None),
                        user=Depends(get_current_user)):
    query = {}
    if active is not None:
        query["active"] = active
    docs = await get_db().workshops.find(query, {"_id": 0}).sort("name", 1).to_list(500)
    if q:
        ql = q.lower()
        docs = [d for d in docs
                if ql in ((d.get("name") or "") + " " + (d.get("city") or "")).lower()]
    return safe_doc(docs)


@router.post("/workshops")
async def create_workshop(body: WorkshopCreate, user=Depends(MANAGER)):
    db = get_db()
    doc = {
        "id": new_id("wsh"), "name": body.name.strip(),
        "phone": body.phone or "", "address": body.address or "",
        # INV-REF-02 batch 6: kota bengkel = relasi master `cities` (nama kanonik).
        "city": await city_or_400(db, body.city, field_label="Kota bengkel"),
        "specialties": body.specialties or [], "note": body.note or "",
        "active": True if body.active is None else bool(body.active),
        "created_at": now_iso(),
    }
    await db.workshops.insert_one(doc)
    await record(db, actor=user, action="create", entity_type="workshop", entity_id=doc["id"],
                 after=doc, summary=f"Tambah vendor/bengkel {doc['name']}")
    return safe_doc(doc)


@router.patch("/workshops/{workshop_id}")
async def update_workshop(workshop_id: str, body: WorkshopUpdate, user=Depends(MANAGER)):
    db = get_db()
    rec = await db.workshops.find_one({"id": workshop_id}, {"_id": 0})
    if not rec:
        raise HTTPException(status_code=404, detail="Vendor/bengkel tidak ditemukan")
    updates = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    if "city" in updates:
        updates["city"] = await city_or_400(db, updates["city"], field_label="Kota bengkel")
    if updates:
        await db.workshops.update_one({"id": workshop_id}, {"$set": updates})
    doc = await db.workshops.find_one({"id": workshop_id}, {"_id": 0})
    await record(db, actor=user, action="update", entity_type="workshop", entity_id=workshop_id,
                 before=rec, after=doc, summary=f"Ubah vendor/bengkel {doc.get('name')}")
    return safe_doc(doc)


@router.delete("/workshops/{workshop_id}")
async def delete_workshop(workshop_id: str, user=Depends(MANAGER)):
    db = get_db()
    rec = await db.workshops.find_one({"id": workshop_id}, {"_id": 0})
    if not rec:
        raise HTTPException(status_code=404, detail="Vendor/bengkel tidak ditemukan")
    await db.workshops.delete_one({"id": workshop_id})
    await record(db, actor=user, action="delete", entity_type="workshop", entity_id=workshop_id,
                 before=rec, summary=f"Hapus vendor/bengkel {rec.get('name')}")
    return {"deleted": True, "id": workshop_id}
