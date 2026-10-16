"""routers/addons.py — master Add-on booking (label + nominal default).

Add-on booking sebelumnya teks bebas per booking; kini bermaster agar konsisten
(label seragam, nominal default) dan bisa quick-add langsung dari form booking.
Baca: section 'bookings'. Mutasi: owner/ops_admin.
"""
import re

from fastapi import APIRouter, Depends, HTTPException, Query

from core_utils import money, new_id, now_iso, safe_doc
from db import get_db
from dependencies import require_role, require_section
from schemas_ops import AddonCreate, AddonUpdate
from services.audit import record

router = APIRouter(prefix="/api", tags=["addons"])
BOOK = require_section("bookings")
MANAGER = require_role("owner", "ops_admin")


@router.get("/addons")
async def list_addons(include_inactive: bool = Query(default=False), user=Depends(BOOK)):
    q = {} if include_inactive else {"active": {"$ne": False}}
    docs = await get_db().addons.find(q, {"_id": 0}).sort("label", 1).to_list(300)
    return safe_doc(docs)


@router.post("/addons")
async def create_addon(body: AddonCreate, user=Depends(MANAGER)):
    db = get_db()
    label = body.label.strip()
    dup = await db.addons.find_one({"label": {"$regex": f"^{re.escape(label)}$", "$options": "i"}}, {"_id": 0})
    if dup:
        raise HTTPException(status_code=409, detail=f"Add-on '{dup.get('label')}' sudah ada di master")
    doc = {"id": new_id("add"), "label": label, "default_amount": money(body.default_amount),
           "active": body.active is not False, "created_at": now_iso()}
    await db.addons.insert_one(doc)
    await record(db, actor=user, action="create", entity_type="addon", entity_id=doc["id"],
                 after=doc, summary=f"Tambah master add-on {label}")
    return safe_doc(doc)


@router.patch("/addons/{addon_id}")
async def update_addon(addon_id: str, body: AddonUpdate, user=Depends(MANAGER)):
    db = get_db()
    before = await db.addons.find_one({"id": addon_id}, {"_id": 0})
    if not before:
        raise HTTPException(status_code=404, detail="Add-on tidak ditemukan")
    updates = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    if "label" in updates:
        updates["label"] = updates["label"].strip()
    if "default_amount" in updates:
        updates["default_amount"] = money(updates["default_amount"])
    if updates:
        await db.addons.update_one({"id": addon_id}, {"$set": updates})
    doc = await db.addons.find_one({"id": addon_id}, {"_id": 0})
    await record(db, actor=user, action="update", entity_type="addon", entity_id=addon_id,
                 before=before, after=doc, summary=f"Ubah master add-on {doc.get('label')}")
    return safe_doc(doc)


@router.delete("/addons/{addon_id}")
async def delete_addon(addon_id: str, user=Depends(MANAGER)):
    db = get_db()
    before = await db.addons.find_one({"id": addon_id}, {"_id": 0})
    if not before:
        raise HTTPException(status_code=404, detail="Add-on tidak ditemukan")
    # Booking lama menyimpan SNAPSHOT label+amount sendiri, jadi hapus master aman.
    await db.addons.delete_one({"id": addon_id})
    await record(db, actor=user, action="delete", entity_type="addon", entity_id=addon_id,
                 before=before, summary=f"Hapus master add-on {before.get('label')}")
    return {"deleted": True, "id": addon_id}
