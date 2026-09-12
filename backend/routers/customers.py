"""routers/customers.py — master customer + Customer 360 (Phase 2).

Akses owner/ops_admin (section 'customers'). Detail menyertakan riwayat booking
+ statistik terhitung (Customer 360). Mutasi & delete dengan guard FK.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pymongo.errors import DuplicateKeyError

from core_utils import new_id, now_iso, safe_doc
from db import get_db
from dependencies import require_section
from schemas import CustomerCreate, CustomerUpdate
from services.audit import record
from services.refs import CUSTOMER_TYPES, city_or_400, must_be_choice
from services.identity import find_customer_by_identity, normalize_phone

router = APIRouter(prefix="/api", tags=["customers"])
CUST = require_section("customers")


@router.get("/customers")
async def list_customers(type: str = Query(default=None), limit: int = Query(default=200, le=500),
                        skip: int = Query(default=0, ge=0), user=Depends(CUST)):
    query = {}
    if type:
        query["type"] = type
    docs = await get_db().customers.find(query, {"_id": 0}).sort("name", 1).skip(skip).to_list(limit)
    return safe_doc(docs)


@router.post("/customers")
async def create_customer(body: CustomerCreate, user=Depends(CUST)):
    db = get_db()
    # B4 Dedupe: tolak bila kontak (nomor/email) sudah terdaftar.
    dup = await find_customer_by_identity(db, phone=body.phone, email=body.email)
    if dup:
        raise HTTPException(status_code=409,
                            detail=f"Kontak sudah terdaftar sebagai '{dup.get('name')}' ({dup.get('phone') or dup.get('email')})")
    doc = {
        "id": new_id("cus"), "name": body.name.strip(), "phone": body.phone or "",
        "phone_normalized": normalize_phone(body.phone),
        "email": body.email or "",
        # INV-REF-01: jenis pelanggan menentukan perlakuan penawaran/faktur — nilai di luar
        # daftar membuat penyaring "Individu/Korporat" bocor tanpa ada yang menyadarinya.
        "type": must_be_choice(body.type, CUSTOMER_TYPES, field_label="Jenis pelanggan",
                               default="individual"),
        # INV-REF-02 batch 5: kota = relasi master `cities` (nama kanonik, bukan teks bebas).
        "city": await city_or_400(db, body.city, field_label="Kota pelanggan"),
        "address": body.address or "", "total_trips": 0, "lifetime_value": 0.0,
        "notes": body.notes or "", "created_at": now_iso(),
    }
    try:
        await db.customers.insert_one(doc)
    except DuplicateKeyError:
        # ID-RACE: pemeriksaan dedupe di atas bersifat TOCTOU; index unik-parsial adalah SSOT.
        # Bila request paralel menang lebih dulu → kembalikan 409 (konsisten dgn pesan dedupe).
        existing = await db.customers.find_one({"phone_normalized": doc["phone_normalized"]}, {"_id": 0})
        raise HTTPException(status_code=409,
                            detail=f"Kontak sudah terdaftar sebagai '{(existing or {}).get('name', '-')}' "
                                   f"({(existing or {}).get('phone') or (existing or {}).get('email') or '-'})")
    await record(db, actor=user, action="create", entity_type="customer", entity_id=doc["id"],
                 after=doc, summary=f"Tambah customer {doc.get('name')}")
    return safe_doc(doc)


@router.get("/customers/{customer_id}")
async def get_customer(customer_id: str, user=Depends(CUST)):
    db = get_db()
    doc = await db.customers.find_one({"id": customer_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Customer tidak ditemukan")
    norm = doc.get("phone_normalized") or normalize_phone(doc.get("phone"))

    bookings = safe_doc(await db.bookings.find({"customer_id": customer_id}, {"_id": 0})
                        .sort("start_datetime", -1).to_list(100))

    # B4 Contact 360: gabungkan lead, penawaran & percakapan via id ATAU nomor ter-normalisasi.
    lead_or = [{"converted_customer_id": customer_id}, {"linked_customer_id": customer_id}]
    quo_or = [{"customer_id": customer_id}]
    conv_or = [{"customer_id": customer_id}]
    if norm:
        lead_or.append({"phone_normalized": norm})
        quo_or.append({"phone_normalized": norm})
    if doc.get("phone"):
        conv_or.append({"contact_phone": doc.get("phone")})

    leads = safe_doc(await db.leads.find({"$or": lead_or}, {"_id": 0}).sort("created_at", -1).to_list(50))
    quotations = safe_doc(await db.quotations.find({"$or": quo_or}, {"_id": 0}).sort("created_at", -1).to_list(50))
    conversations = safe_doc(await db.conversations.find({"$or": conv_or}, {"_id": 0}).sort("created_at", -1).to_list(50))

    total_spent = sum(float(b.get("paid_amount", 0) or 0) for b in bookings)
    active = sum(1 for b in bookings if b.get("status") in ("confirmed", "ongoing"))

    # Timeline terpadu (desc by tanggal) — sumber: booking, penawaran, lead, percakapan.
    timeline = []
    for b in bookings:
        timeline.append({"type": "booking", "date": b.get("start_datetime") or b.get("created_at"),
                         "title": f"Booking {b.get('code')}", "subtitle": b.get("destination") or "",
                         "amount": b.get("total_amount"), "status": b.get("status"), "ref_id": b.get("id")})
    for q in quotations:
        timeline.append({"type": "quotation", "date": q.get("created_at"),
                         "title": f"Penawaran {q.get('number')}", "subtitle": q.get("destination") or "",
                         "amount": q.get("total"), "status": q.get("status"), "ref_id": q.get("id")})
    for l in leads:
        timeline.append({"type": "lead", "date": l.get("created_at"),
                         "title": f"Lead · {l.get('source') or 'manual'}", "subtitle": l.get("destination") or l.get("message") or "",
                         "status": l.get("stage"), "ref_id": l.get("id")})
    for c in conversations:
        timeline.append({"type": "conversation", "date": c.get("last_message_at") or c.get("created_at"),
                         "title": f"Percakapan · {c.get('channel') or 'internal'}", "subtitle": c.get("subject") or "",
                         "status": c.get("status"), "ref_id": c.get("id")})
    timeline.sort(key=lambda x: x.get("date") or "", reverse=True)

    out = safe_doc(doc)
    out["phone_normalized"] = norm
    out["bookings"] = bookings
    out["leads"] = leads
    out["quotations"] = quotations
    out["conversations"] = conversations
    out["timeline"] = timeline[:40]
    out["stats"] = {
        "bookings_count": len(bookings),
        "total_spent": round(total_spent, 2),
        "active_bookings": active,
        "leads_count": len(leads),
        "quotations_count": len(quotations),
        "conversations_count": len(conversations),
    }
    return out


@router.patch("/customers/{customer_id}")
async def update_customer(customer_id: str, body: CustomerUpdate, user=Depends(CUST)):
    db = get_db()
    before = await db.customers.find_one({"id": customer_id}, {"_id": 0})
    if not before:
        raise HTTPException(status_code=404, detail="Customer tidak ditemukan")
    updates = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    if "phone" in updates:
        updates["phone_normalized"] = normalize_phone(updates["phone"])
    if "type" in updates:
        updates["type"] = must_be_choice(updates["type"], CUSTOMER_TYPES,
                                         field_label="Jenis pelanggan",
                                         default=before.get("type"))
    if "city" in updates:
        updates["city"] = await city_or_400(db, updates["city"], field_label="Kota pelanggan")
    if updates:
        try:
            await db.customers.update_one({"id": customer_id}, {"$set": updates})
        except DuplicateKeyError:
            # ID-RACE: nomor ter-normalisasi bentrok dgn customer lain (index unik-parsial).
            raise HTTPException(status_code=409, detail="Nomor telepon sudah dipakai customer lain")
    doc = await db.customers.find_one({"id": customer_id}, {"_id": 0})
    await record(db, actor=user, action="update", entity_type="customer", entity_id=customer_id,
                 before=before, after=doc, summary=f"Ubah customer {doc.get('name')}")
    return safe_doc(doc)


@router.delete("/customers/{customer_id}")
async def delete_customer(customer_id: str, user=Depends(CUST)):
    db = get_db()
    before = await db.customers.find_one({"id": customer_id}, {"_id": 0})
    if not before:
        raise HTTPException(status_code=404, detail="Customer tidak ditemukan")
    if await db.bookings.count_documents({"customer_id": customer_id}):
        raise HTTPException(status_code=400, detail="Customer masih memiliki booking — tidak bisa dihapus")
    await db.customers.delete_one({"id": customer_id})
    await record(db, actor=user, action="delete", entity_type="customer", entity_id=customer_id,
                 before=before, summary=f"Hapus customer {before.get('name')}")
    return {"deleted": True, "id": customer_id}
