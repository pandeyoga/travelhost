"""routers/partners.py — E16 Master Mitra Travel (Partner) + AP/Settlement.

Koleksi kanonik: `partners` (ptn_), `partner_settlements` (pst_).
Section RBAC 'partners' (owner/ops_admin). Driver tidak mengakses.
Urutan rute: literal sebelum /{partner_id} berparameter.
"""
from fastapi import APIRouter, Depends, HTTPException, Query

from core_utils import new_id, now_iso, safe_doc
from db import get_db
from dependencies import require_section
from schemas_partner import PartnerCreate, PartnerUpdate, SettlementCreate
from services.audit import record
from services.refs import city_or_400
from services.subcharter import enrich_partner, partner_ap

router = APIRouter(prefix="/api", tags=["partners"])
PARTNERS = require_section("partners")


@router.get("/partners")
async def list_partners(status: str = Query(default=None), limit: int = Query(default=200, le=500),
                        skip: int = Query(default=0, ge=0), user=Depends(PARTNERS)):
    db = get_db()
    q = {}
    if status:
        q["status"] = status
    docs = await db.partners.find(q, {"_id": 0}).sort("created_at", -1).skip(skip).to_list(limit)
    return safe_doc([await enrich_partner(db, p) for p in docs])


@router.post("/partners")
async def create_partner(body: PartnerCreate, user=Depends(PARTNERS)):
    db = get_db()
    doc = {
        "id": new_id("ptn"), "name": body.name.strip(),
        "pic": (body.pic or "").strip(), "phone": (body.phone or "").strip(),
        "email": (body.email or "").strip(),
        # INV-REF-02 batch 5: kota mitra = relasi master `cities` (nama kanonik).
        "city": await city_or_400(db, body.city, field_label="Kota mitra"),
        "address": (body.address or "").strip(), "rating": float(body.rating or 0),
        "notes": body.notes or "", "status": body.status or "active", "created_at": now_iso(),
    }
    await db.partners.insert_one(doc)
    await record(db, actor=user, action="create", entity_type="partner", entity_id=doc["id"],
                 after=doc, summary=f"Tambah mitra {doc.get('name')}")
    return safe_doc(await enrich_partner(db, doc))


@router.get("/partners/{partner_id}")
async def get_partner(partner_id: str, user=Depends(PARTNERS)):
    db = get_db()
    p = await db.partners.find_one({"id": partner_id}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Mitra tidak ditemukan")
    subs = await db.subcharters.find({"partner_id": partner_id}, {"_id": 0}).sort("created_at", -1).to_list(500)
    setts = await db.partner_settlements.find({"partner_id": partner_id}, {"_id": 0}).sort("created_at", -1).to_list(500)
    vehs = await db.vehicles.find({"partner_id": partner_id}, {"_id": 0, "id": 1, "name": 1, "plate_number": 1, "type": 1}).to_list(200)
    out = await enrich_partner(db, p)
    out["subcharters"] = safe_doc(subs)
    out["settlements"] = safe_doc(setts)
    out["vehicles"] = safe_doc(vehs)
    return safe_doc(out)


@router.patch("/partners/{partner_id}")
async def update_partner(partner_id: str, body: PartnerUpdate, user=Depends(PARTNERS)):
    db = get_db()
    before = await db.partners.find_one({"id": partner_id}, {"_id": 0})
    if not before:
        raise HTTPException(status_code=404, detail="Mitra tidak ditemukan")
    updates = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    if "rating" in updates:
        updates["rating"] = float(updates["rating"])
    if "city" in updates:
        updates["city"] = await city_or_400(db, updates["city"], field_label="Kota mitra")
    if updates:
        await db.partners.update_one({"id": partner_id}, {"$set": updates})
    doc = await db.partners.find_one({"id": partner_id}, {"_id": 0})
    await record(db, actor=user, action="update", entity_type="partner", entity_id=partner_id,
                 before=before, after=doc, summary=f"Ubah mitra {doc.get('name')}")
    return safe_doc(await enrich_partner(db, doc))


@router.delete("/partners/{partner_id}")
async def delete_partner(partner_id: str, user=Depends(PARTNERS)):
    db = get_db()
    before = await db.partners.find_one({"id": partner_id}, {"_id": 0})
    if not before:
        raise HTTPException(status_code=404, detail="Mitra tidak ditemukan")
    if await db.subcharters.count_documents({"partner_id": partner_id, "status": {"$ne": "cancelled"}}):
        raise HTTPException(status_code=400, detail="Mitra masih punya order sub-charter aktif — tidak bisa dihapus")
    if await db.vehicles.count_documents({"partner_id": partner_id}):
        raise HTTPException(status_code=400, detail="Masih ada armada mitra terdaftar — lepas dulu sebelum hapus")
    await db.partners.delete_one({"id": partner_id})
    await record(db, actor=user, action="delete", entity_type="partner", entity_id=partner_id,
                 before=before, summary=f"Hapus mitra {before.get('name')}")
    return {"deleted": True, "id": partner_id}


@router.get("/partners/{partner_id}/settlements")
async def list_settlements(partner_id: str, user=Depends(PARTNERS)):
    db = get_db()
    if not await db.partners.find_one({"id": partner_id}, {"_id": 1}):
        raise HTTPException(status_code=404, detail="Mitra tidak ditemukan")
    docs = await db.partner_settlements.find(
        {"partner_id": partner_id}, {"_id": 0}).sort("created_at", -1).to_list(500)
    return safe_doc(docs)


@router.post("/partners/{partner_id}/settlements")
async def create_settlement(partner_id: str, body: SettlementCreate, user=Depends(PARTNERS)):
    """Catat pembayaran (pelunasan) ke mitra — mengurangi AP outstanding."""
    db = get_db()
    partner = await db.partners.find_one({"id": partner_id}, {"_id": 0})
    if not partner:
        raise HTTPException(status_code=404, detail="Mitra tidak ditemukan")
    if float(body.amount) <= 0:
        raise HTTPException(status_code=400, detail="Nominal pelunasan harus lebih dari 0")
    sub_id = body.subcharter_id or None
    if sub_id and not await db.subcharters.find_one(
            {"id": sub_id, "partner_id": partner_id}, {"_id": 1}):
        raise HTTPException(status_code=400, detail="Sub-charter tidak ditemukan untuk mitra ini")
    doc = {
        "id": new_id("pst"), "partner_id": partner_id, "partner_name": partner.get("name"),
        "subcharter_id": sub_id, "amount": float(body.amount),
        "method": body.method or "transfer", "note": body.note or "",
        "paid_at": body.paid_at or now_iso(), "recorded_by": user.get("id"), "created_at": now_iso(),
    }
    await db.partner_settlements.insert_one(doc)
    await record(db, actor=user, action="create", entity_type="partner_settlement", entity_id=doc["id"],
                 after=doc, summary=f"Pelunasan ke mitra {partner.get('name')} Rp {int(doc['amount']):,}".replace(",", "."))
    ap = await partner_ap(db, partner_id)
    return {"settlement": safe_doc(doc), "ap": ap}
