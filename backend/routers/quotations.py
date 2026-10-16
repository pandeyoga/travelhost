"""routers/quotations.py — Quotation Lifecycle (Phase 9 / B2).

Funnel: lead/website → penawaran (QUO-xxxx) → kirim → terima → konversi → booking.
Arsitektur 2a: penawaran terhubung CRM Leads → Bookings. Section RBAC 'crm'.
Harga ber-item dibangun Pricing Engine (B1). Nomor QUO via counters atomik.
INV-19: penawaran 'accepted' → 1 booking; tak boleh double-convert.

Urutan rute: literal & sub-path didefinisikan sebelum param generik /{quotation_id}.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from io import BytesIO

from core_utils import new_id, now_iso, safe_doc
from db import get_db
from dependencies import require_section
from schemas import QuotationConvert, QuotationDraftCreate, QuotationDraftUpdate
from services.availability import find_conflicts, find_maintenance_conflicts, find_driver_conflicts, vehicle_lock
from services.audit import record
from services.counters import next_booking_code
from services.crm import STAGE_LABEL, log_activity
from services.refs import destination_or_400
from services.events import emit
from services.exporter import quotation_pdf
from services.geo import parse_iso
from services.identity import ensure_customer
from services.pricing import compute_quote, get_pricing_rules
from services.quotations import (QUO_STATUS_LABEL, next_quotation_number,
                                 normalize_phone, valid_until_iso)

router = APIRouter(prefix="/api", tags=["quotations"])
# Section SSOT untuk penawaran adalah `quotations` (owner/ops_admin), BUKAN `crm`
# (yang juga memuat marketing_admin). FE sudah memakai <RoleGuard section="quotations">,
# jadi backend yang menyimpang = pintu terbuka tanpa menu.
QUOT = require_section("quotations")


async def _holidays(db):
    op = await db.settings.find_one({"key": "operational"}, {"_id": 0})
    if op and isinstance(op.get("value"), dict):
        return op["value"].get("holidays", []) or []
    return []


def _items_total(items):
    return sum(int(round(float(i.get("amount", 0) or 0))) for i in items)


@router.get("/quotations")
async def list_quotations(status: str = Query(default=None), lead_id: str = Query(default=None),
                          q: str = Query(default=None), limit: int = Query(default=300, le=1000),
                          skip: int = Query(default=0, ge=0), user=Depends(QUOT)):
    db = get_db()
    query = {}
    if status:
        query["status"] = status
    if lead_id:
        query["lead_id"] = lead_id
    if q:
        query["$or"] = [{"customer_name": {"$regex": q, "$options": "i"}},
                        {"number": {"$regex": q, "$options": "i"}},
                        {"destination": {"$regex": q, "$options": "i"}}]
    docs = await db.quotations.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).to_list(limit)
    return safe_doc(docs)


@router.post("/quotations")
async def create_quotation(body: QuotationDraftCreate, user=Depends(QUOT)):
    db = get_db()
    lead = customer = None
    if body.lead_id:
        lead = await db.leads.find_one({"id": body.lead_id}, {"_id": 0})
        if not lead:
            raise HTTPException(status_code=400, detail="Lead tidak ditemukan")
    if body.customer_id:
        customer = await db.customers.find_one({"id": body.customer_id}, {"_id": 0})
        if not customer:
            raise HTTPException(status_code=400, detail="Customer tidak ditemukan")

    name = (body.customer_name or (lead or {}).get("customer_name") or (customer or {}).get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Nama pelanggan wajib diisi")
    phone = body.phone or (lead or {}).get("phone") or (customer or {}).get("phone") or ""
    email = body.email or (lead or {}).get("email") or (customer or {}).get("email") or ""
    # INV-REF-02 batch 3: destinasi dari input divalidasi master; warisan dari lead dibiarkan.
    if body.destination:
        destination = await destination_or_400(db, body.destination, field_label="Destinasi penawaran")
    else:
        destination = (lead or {}).get("destination") or ""
    trip_date = body.trip_date or (lead or {}).get("trip_date")
    pax = int(body.pax or (lead or {}).get("pax") or 1)

    # Item: manual bila diisi; selain itu auto dari Pricing Engine (B1).
    if body.items:
        items = [{"label": i.label, "amount": int(round(float(i.amount or 0)))} for i in body.items]
    else:
        rules = await get_pricing_rules(db)
        q = compute_quote(rules, vehicle_type=body.vehicle_type, days=body.days,
                          distance_km=body.distance_km, when=trip_date,
                          holidays=await _holidays(db), include_travel=True)
        items = q["breakdown"]
    subtotal = _items_total(items)

    doc = {
        "id": new_id("quo"), "number": await next_quotation_number(db),
        "lead_id": body.lead_id, "customer_id": body.customer_id,
        "customer_name": name, "phone": phone, "phone_normalized": normalize_phone(phone),
        "email": email, "destination": destination, "trip_date": trip_date, "pax": pax,
        "items": items, "subtotal": subtotal, "total": subtotal,
        "status": "draft", "valid_until": valid_until_iso(body.valid_days),
        "notes": body.notes or "", "booking_id": None,
        "created_by": user.get("id"), "created_at": now_iso(), "updated_at": now_iso(),
    }
    await db.quotations.insert_one(doc)
    await record(db, actor=user, action="create", entity_type="quotation", entity_id=doc["id"],
                 after={"number": doc["number"], "total": doc["total"]},
                 summary=f"Buat penawaran {doc['number']} (Rp {doc['total']:,})".replace(",", "."))
    if body.lead_id:
        await log_activity(db, body.lead_id, user.get("id"), "note",
                           text=f"Penawaran {doc['number']} dibuat (Rp {doc['total']:,})".replace(",", "."))
        if (lead or {}).get("stage") in ("new", "contacted"):
            await db.leads.update_one({"id": body.lead_id}, {"$set": {"stage": "quoted", "last_activity_at": now_iso()}})
    return safe_doc(doc)


@router.get("/quotations/{quotation_id}/pdf")
async def quotation_pdf_export(quotation_id: str, user=Depends(QUOT)):
    quo = await get_db().quotations.find_one({"id": quotation_id}, {"_id": 0})
    if not quo:
        raise HTTPException(status_code=404, detail="Penawaran tidak ditemukan")
    data = quotation_pdf(quo)
    fname = f"{quo.get('number', 'penawaran')}.pdf"
    return StreamingResponse(BytesIO(data), media_type="application/pdf",
                             headers={"Content-Disposition": f'attachment; filename="{fname}"'})


@router.get("/quotations/{quotation_id}")
async def get_quotation(quotation_id: str, user=Depends(QUOT)):
    quo = await get_db().quotations.find_one({"id": quotation_id}, {"_id": 0})
    if not quo:
        raise HTTPException(status_code=404, detail="Penawaran tidak ditemukan")
    return safe_doc(quo)


@router.patch("/quotations/{quotation_id}")
async def update_quotation(quotation_id: str, body: QuotationDraftUpdate, user=Depends(QUOT)):
    db = get_db()
    quo = await db.quotations.find_one({"id": quotation_id}, {"_id": 0})
    if not quo:
        raise HTTPException(status_code=404, detail="Penawaran tidak ditemukan")
    if quo.get("status") not in ("draft", "sent"):
        raise HTTPException(status_code=400, detail="Hanya penawaran draft/terkirim yang bisa diubah")
    updates = {}
    for f in ("customer_name", "phone", "email", "destination", "trip_date", "pax", "notes", "valid_until"):
        v = getattr(body, f)
        if v is not None:
            updates[f] = v
    # INV-REF-02: destinasi hanya divalidasi bila DIUBAH (penawaran lama tetap bisa diedit).
    if "destination" in updates and updates["destination"] != quo.get("destination"):
        updates["destination"] = await destination_or_400(db, updates["destination"],
                                                          field_label="Destinasi penawaran")
    if "phone" in updates:
        updates["phone_normalized"] = normalize_phone(updates["phone"])
    if "pax" in updates:
        updates["pax"] = int(updates["pax"] or 0)
    if body.items is not None:
        items = [{"label": i.label, "amount": int(round(float(i.amount or 0)))} for i in body.items]
        updates["items"] = items
        updates["subtotal"] = _items_total(items)
        updates["total"] = updates["subtotal"]
    if updates:
        updates["updated_at"] = now_iso()
        await db.quotations.update_one({"id": quotation_id}, {"$set": updates})
        await record(db, actor=user, action="update", entity_type="quotation", entity_id=quotation_id,
                     after={k: updates[k] for k in ("total", "customer_name", "trip_date") if k in updates},
                     summary=f"Ubah penawaran {quo.get('number')}")
    doc = await db.quotations.find_one({"id": quotation_id}, {"_id": 0})
    return safe_doc(doc)


@router.delete("/quotations/{quotation_id}")
async def delete_quotation(quotation_id: str, user=Depends(QUOT)):
    """Hapus penawaran yang belum jadi booking (draft/terkirim/ditolak/kedaluwarsa)."""
    db = get_db()
    quo = await db.quotations.find_one({"id": quotation_id}, {"_id": 0})
    if not quo:
        raise HTTPException(status_code=404, detail="Penawaran tidak ditemukan")
    if quo.get("booking_id") or quo.get("status") in ("converted", "accepted"):
        raise HTTPException(status_code=400,
                            detail="Penawaran yang sudah diterima/jadi booking tidak bisa dihapus — gunakan Tolak")
    await db.quotations.delete_one({"id": quotation_id})
    await record(db, actor=user, action="delete", entity_type="quotation", entity_id=quotation_id,
                 before={"number": quo.get("number"), "total": quo.get("total"), "status": quo.get("status")},
                 summary=f"Hapus penawaran {quo.get('number')}")
    if quo.get("lead_id"):
        await log_activity(db, quo["lead_id"], user.get("id"), "note",
                           text=f"Penawaran {quo.get('number')} dihapus")
    return {"ok": True, "id": quotation_id}


async def _set_status(db, quotation_id, new_status, allowed_from, user, label):
    quo = await db.quotations.find_one({"id": quotation_id}, {"_id": 0})
    if not quo:
        raise HTTPException(status_code=404, detail="Penawaran tidak ditemukan")
    if quo.get("status") not in allowed_from:
        froms = ", ".join(QUO_STATUS_LABEL.get(s, s) for s in allowed_from)
        raise HTTPException(status_code=400, detail=f"Transisi tidak sah. Status harus salah satu: {froms}")
    ts_field = {"sent": "sent_at", "accepted": "accepted_at", "rejected": "rejected_at"}.get(new_status)
    upd = {"status": new_status, "updated_at": now_iso()}
    if ts_field:
        upd[ts_field] = now_iso()
    await db.quotations.update_one({"id": quotation_id}, {"$set": upd})
    await record(db, actor=user, action="update", entity_type="quotation", entity_id=quotation_id,
                 after={"status": new_status}, summary=f"Penawaran {quo.get('number')} → {label}")
    if quo.get("lead_id"):
        await log_activity(db, quo["lead_id"], user.get("id"), "note",
                           text=f"Penawaran {quo.get('number')} → {label}")
    doc = await db.quotations.find_one({"id": quotation_id}, {"_id": 0})
    return safe_doc(doc)


@router.post("/quotations/{quotation_id}/send")
async def send_quotation(quotation_id: str, user=Depends(QUOT)):
    db = get_db()
    res = await _set_status(db, quotation_id, "sent", {"draft", "sent"}, user, "Terkirim")
    await emit(db, "quotation.sent", {
        "quotation_id": res.get("id"), "number": res.get("number"),
        "customer_name": res.get("customer_name"), "phone": res.get("phone"),
        "total": float(res.get("total", 0) or 0), "valid_until": (res.get("valid_until") or "")[:10],
        "lead_id": res.get("lead_id"),
    }, source="quotations", ref_type="quotation", ref_id=res.get("id"),
        dedupe_key=f"quotation.sent:{quotation_id}")
    return res


@router.post("/quotations/{quotation_id}/accept")
async def accept_quotation(quotation_id: str, user=Depends(QUOT)):
    return await _set_status(get_db(), quotation_id, "accepted", {"sent", "draft"}, user, "Diterima")


@router.post("/quotations/{quotation_id}/reject")
async def reject_quotation(quotation_id: str, user=Depends(QUOT)):
    return await _set_status(get_db(), quotation_id, "rejected", {"draft", "sent", "accepted"}, user, "Ditolak")


@router.post("/quotations/{quotation_id}/convert")
async def convert_quotation(quotation_id: str, body: QuotationConvert, user=Depends(QUOT)):
    db = get_db()
    quo = await db.quotations.find_one({"id": quotation_id}, {"_id": 0})
    if not quo:
        raise HTTPException(status_code=404, detail="Penawaran tidak ditemukan")
    if quo.get("booking_id"):  # INV-19: cegah double-convert
        raise HTTPException(status_code=400, detail="Penawaran sudah dikonversi menjadi booking")
    if quo.get("status") != "accepted":
        raise HTTPException(status_code=400, detail="Hanya penawaran berstatus 'Diterima' yang bisa dikonversi")

    vehicle = await db.vehicles.find_one({"id": body.vehicle_id}, {"_id": 0})
    if not vehicle:
        raise HTTPException(status_code=400, detail="Armada tidak ditemukan")
    driver = None
    if body.driver_id:
        driver = await db.drivers.find_one({"id": body.driver_id}, {"_id": 0})
        if not driver:
            raise HTTPException(status_code=400, detail="Driver tidak ditemukan")
    start_dt = parse_iso(body.start_datetime)
    end_dt = parse_iso(body.end_datetime)
    if not start_dt or not end_dt:
        raise HTTPException(status_code=400, detail="Format tanggal tidak valid")
    if end_dt <= start_dt:
        raise HTTPException(status_code=400, detail="Tanggal selesai harus setelah tanggal mulai")
    start_iso, end_iso = start_dt.isoformat(), end_dt.isoformat()

    # Identitas: pakai customer terkait; selain itu dedupe (nomor/email) atau buat baru (B4).
    cust = None
    if quo.get("customer_id"):
        cust = await db.customers.find_one({"id": quo["customer_id"]}, {"_id": 0})
    if not cust:
        cust, _created = await ensure_customer(
            db, name=quo.get("customer_name") or "Customer", phone=quo.get("phone") or "",
            email=quo.get("email") or "", notes=f"Dari penawaran {quo.get('number')}")

    base = float(quo.get("total", 0) or 0)
    booking = {
        "id": new_id("bk"), "code": await next_booking_code(db),
        "customer_id": cust["id"], "vehicle_id": body.vehicle_id, "driver_id": body.driver_id,
        "origin": "", "destination": quo.get("destination") or "",
        "start_datetime": start_iso, "end_datetime": end_iso,
        "base_price": base, "add_ons": [], "total_amount": base, "paid_amount": 0.0,
        "payment_status": "belum_bayar", "status": "confirmed",
        "customer_name": cust.get("name"), "vehicle_name": vehicle.get("name"),
        "driver_name": driver.get("name") if driver else None,
        "notes": f"Dari penawaran {quo.get('number')}", "quotation_id": quo["id"], "created_at": now_iso(),
    }
    # RC-16 (anti-TOCTOU): cek-final bentrok armada/perawatan/driver + insert booking HARUS serial
    # per armada. (Celah lama: convert tak dibungkus vehicle_lock & TIDAK cek konflik driver →
    #  bisa double-book armada dan/atau sopir.)
    async with vehicle_lock(db, body.vehicle_id):
        conflicts = await find_conflicts(db, body.vehicle_id, start_iso, end_iso)
        if conflicts:
            codes = ", ".join(c.get("code", c.get("id")) for c in conflicts)
            raise HTTPException(status_code=400, detail=f"Armada bentrok dengan booking aktif: {codes}")
        maint = await find_maintenance_conflicts(db, body.vehicle_id, start_iso, end_iso)
        if maint:
            raise HTTPException(status_code=400, detail="Armada dalam masa perawatan")
        # RC-07: bila driver di-assign saat konversi, tolak bila bentrok jadwal driver.
        if body.driver_id:
            dconf = await find_driver_conflicts(db, body.driver_id, start_iso, end_iso)
            if dconf:
                raise HTTPException(status_code=400,
                                    detail=f"Driver bentrok dengan booking aktif: {dconf[0].get('code')}")
        await db.bookings.insert_one(booking)
    await db.quotations.update_one({"id": quotation_id}, {"$set": {
        "status": "converted", "booking_id": booking["id"], "customer_id": cust["id"],
        "updated_at": now_iso()}})
    await record(db, actor=user, action="update", entity_type="quotation", entity_id=quotation_id,
                 after={"status": "converted", "booking_id": booking["id"]},
                 summary=f"Konversi penawaran {quo.get('number')} → booking {booking['code']}")
    if quo.get("lead_id"):
        await db.leads.update_one({"id": quo["lead_id"]}, {"$set": {
            "stage": "won", "won_at": now_iso(), "converted_customer_id": cust["id"],
            "last_activity_at": now_iso()}})
        await log_activity(db, quo["lead_id"], user.get("id"), "converted",
                           text=f"Penawaran {quo.get('number')} → booking {booking['code']} ({STAGE_LABEL.get('won')})")
    await emit(db, "booking.confirmed", {
        "booking_id": booking["id"], "code": booking["code"],
        "customer_name": cust.get("name"), "phone": cust.get("phone"),
        "total_amount": float(booking.get("total_amount", 0) or 0), "dp_percent": 30,
        "vehicle_name": booking.get("vehicle_name"),
        "start_datetime": (booking.get("start_datetime") or "")[:16].replace("T", " "),
    }, source="quotations", ref_type="booking", ref_id=booking["id"],
        dedupe_key=f"booking.confirmed:{booking['id']}")
    return {"quotation": safe_doc(await db.quotations.find_one({"id": quotation_id}, {"_id": 0})),
            "booking": safe_doc(booking), "customer": safe_doc(cust)}
