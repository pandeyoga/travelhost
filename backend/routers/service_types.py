"""routers/service_types.py — Master Jenis Service (E10 Phase A).

CRUD jenis service yang dapat dikonfigurasi (+ interval default km/hari). Dipakai sebagai
nilai `maintenance_records.type` (key) selain jenis bawaan (servis/kir/pajak/perbaikan/lainnya).
List/detail: semua role login. Mutasi: owner/ops_admin.
"""
import re

from fastapi import APIRouter, Depends, HTTPException, Query

from core_utils import new_id, now_iso, safe_doc
from db import get_db
from dependencies import get_current_user, require_role
from schemas import ServiceTypeCreate, ServiceTypeUpdate
from services.audit import record

router = APIRouter(prefix="/api", tags=["service-types"])
MANAGER = require_role("owner", "ops_admin")
BUILTIN = {"servis", "kir", "pajak", "perbaikan", "lainnya"}


def slugify(name):
    s = re.sub(r"[^a-z0-9]+", "_", (name or "").strip().lower()).strip("_")
    return s or "service"


@router.get("/service-types")
async def list_service_types(active: bool = Query(default=None), user=Depends(get_current_user)):
    q = {}
    if active is not None:
        q["active"] = active
    docs = await get_db().service_types.find(q, {"_id": 0}).sort("name", 1).to_list(500)
    return safe_doc(docs)


@router.post("/service-types")
async def create_service_type(body: ServiceTypeCreate, user=Depends(MANAGER)):
    db = get_db()
    key = slugify(body.name)
    if key in BUILTIN or await db.service_types.find_one({"key": key}):
        raise HTTPException(status_code=400, detail="Jenis service sudah ada (nama/kunci duplikat)")
    doc = {
        "id": new_id("svt"), "key": key, "name": body.name.strip(),
        "default_interval_km": body.default_interval_km,
        "default_interval_days": body.default_interval_days,
        "active": True if body.active is None else bool(body.active),
        "created_at": now_iso(),
    }
    await db.service_types.insert_one(doc)
    await record(db, actor=user, action="create", entity_type="service_type", entity_id=doc["id"],
                 after=doc, summary=f"Tambah jenis service {doc['name']}")
    return safe_doc(doc)


@router.patch("/service-types/{type_id}")
async def update_service_type(type_id: str, body: ServiceTypeUpdate, user=Depends(MANAGER)):
    db = get_db()
    rec = await db.service_types.find_one({"id": type_id}, {"_id": 0})
    if not rec:
        raise HTTPException(status_code=404, detail="Jenis service tidak ditemukan")
    updates = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    if updates:
        await db.service_types.update_one({"id": type_id}, {"$set": updates})
    doc = await db.service_types.find_one({"id": type_id}, {"_id": 0})
    await record(db, actor=user, action="update", entity_type="service_type", entity_id=type_id,
                 before=rec, after=doc, summary=f"Ubah jenis service {doc.get('name')}")
    return safe_doc(doc)


@router.delete("/service-types/{type_id}")
async def delete_service_type(type_id: str, user=Depends(MANAGER)):
    db = get_db()
    rec = await db.service_types.find_one({"id": type_id}, {"_id": 0})
    if not rec:
        raise HTTPException(status_code=404, detail="Jenis service tidak ditemukan")
    await db.service_types.delete_one({"id": type_id})
    await record(db, actor=user, action="delete", entity_type="service_type", entity_id=type_id,
                 before=rec, summary=f"Hapus jenis service {rec.get('name')}")
    return {"deleted": True, "id": type_id}
