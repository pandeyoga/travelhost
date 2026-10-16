"""routers/subcharters.py — E16 Order Sub-charter (pinjam unit dari mitra).

Koleksi kanonik: `subcharters` (sbc_). Section RBAC 'partners' (owner/ops_admin).
Siklus: requested → confirmed → settled (atau cancelled).
  - confirm  : bukukan COGS (expenses 'sewa_mitra' → P&L/INV-5) + WA ke MITRA + notifikasi.
  - settle   : catat pelunasan (partner_settlements) → kurangi AP.
  - cancel   : hapus COGS bila sudah dibukukan.
Anti double-booking unit mitra via services.subcharter.find_subcharter_conflicts.
Urutan rute: literal/sub-path sebelum /{subcharter_id} berparameter.
"""
from fastapi import APIRouter, Depends, HTTPException, Query

from core_utils import new_id, now_iso, safe_doc
from db import get_db
from dependencies import require_section
from schemas_partner import SubcharterCreate, SubcharterUpdate
from services.audit import record
from services.counters import next_seq
from services.events import emit
from services import subcharter as sc_svc
from services.availability import vehicle_lock

router = APIRouter(prefix="/api", tags=["subcharters"])
PARTNERS = require_section("partners")


async def _next_code(db):
    seq = await next_seq(db, "subcharter")
    return f"SC-{seq:04d}"


def _slim(c):
    return {"id": c.get("id"), "code": c.get("code"),
            "start_datetime": c.get("start_datetime"), "end_datetime": c.get("end_datetime")}


@router.get("/subcharters")
async def list_subcharters(booking_id: str = Query(default=None), partner_id: str = Query(default=None),
                           status: str = Query(default=None), limit: int = Query(default=300, le=1000),
                           skip: int = Query(default=0, ge=0), user=Depends(PARTNERS)):
    q = {}
    if booking_id:
        q["booking_id"] = booking_id
    if partner_id:
        q["partner_id"] = partner_id
    if status:
        q["status"] = status
    docs = await get_db().subcharters.find(q, {"_id": 0}).sort("created_at", -1).skip(skip).to_list(limit)
    return safe_doc(docs)


@router.get("/subcharters/available-partners")
async def available_partner_vehicles(start: str = Query(...), end: str = Query(...),
                                     user=Depends(PARTNERS)):
    """Saran unit MITRA yang bebas pada jendela waktu (backlog E16 #4).

    Mengembalikan armada ownership=partner yang tak bentrok dengan sub-charter aktif.
    """
    db = get_db()
    vehs = await db.vehicles.find(
        {"ownership": "partner"}, {"_id": 0, "id": 1, "name": 1, "plate_number": 1,
                                    "type": 1, "partner_id": 1, "capacity": 1}).to_list(300)
    out = []
    for v in vehs:
        conflicts = await sc_svc.find_subcharter_conflicts(db, v["id"], start, end)
        if not conflicts:
            partner = await db.partners.find_one({"id": v.get("partner_id")}, {"_id": 0, "name": 1, "phone": 1})
            v["partner_name"] = (partner or {}).get("name")
            v["partner_phone"] = (partner or {}).get("phone")
            out.append(v)
    return safe_doc(out)


@router.post("/subcharters")
async def create_subcharter(body: SubcharterCreate, user=Depends(PARTNERS)):
    db = get_db()
    booking = await db.bookings.find_one({"id": body.booking_id}, {"_id": 0})
    if not booking:
        raise HTTPException(status_code=400, detail="Booking tidak ditemukan")
    partner = await db.partners.find_one({"id": body.partner_id}, {"_id": 0})
    if not partner:
        raise HTTPException(status_code=400, detail="Mitra tidak ditemukan")
    if float(body.cost or 0) <= 0:
        raise HTTPException(status_code=400, detail="Biaya sewa ke mitra harus lebih dari 0")
    vehicle_id = body.vehicle_id or None
    vehicle_label = (body.vehicle_label or "").strip()
    if vehicle_id:
        veh = await db.vehicles.find_one({"id": vehicle_id}, {"_id": 0})
        if not veh:
            raise HTTPException(status_code=400, detail="Armada tidak ditemukan")
        vehicle_label = vehicle_label or veh.get("name")
    start = body.start_datetime or booking.get("start_datetime")
    end = body.end_datetime or booking.get("end_datetime")
    if not start or not end:
        raise HTTPException(status_code=400, detail="Tanggal mulai & selesai wajib diisi")
    if end <= start:
        raise HTTPException(status_code=400, detail="Tanggal selesai harus setelah tanggal mulai")
    doc = {
        "id": new_id("sbc"), "code": await _next_code(db),
        "booking_id": body.booking_id, "booking_code": booking.get("code"),
        "partner_id": body.partner_id, "partner_name": partner.get("name"),
        "vehicle_id": vehicle_id, "vehicle_label": vehicle_label or "Unit mitra",
        "start_datetime": start, "end_datetime": end,
        "cost": float(body.cost), "status": "requested", "note": body.note or "",
        "expense_id": None, "confirmed_at": None, "settled_at": None, "created_at": now_iso(),
    }
    # RC-16 (anti-TOCTOU): cek-final bentrok unit mitra + insert HARUS serial per unit.
    if vehicle_id:
        async with vehicle_lock(db, vehicle_id):
            conflicts = await sc_svc.find_subcharter_conflicts(db, vehicle_id, start, end)
            if conflicts:
                codes = ", ".join(c.get("code", c.get("id")) for c in conflicts)
                raise HTTPException(status_code=400, detail=f"Unit mitra bentrok dengan sub-charter aktif: {codes}")
            await db.subcharters.insert_one(doc)
    else:
        await db.subcharters.insert_one(doc)
    payload = await sc_svc.build_partner_payload(db, doc, partner=partner, booking=booking)
    await emit(db, "subcharter.requested", payload, source="subcharter", ref_type="subcharter",
              ref_id=doc["id"], dedupe_key=f"subcharter.requested:{doc['id']}")
    await record(db, actor=user, action="create", entity_type="subcharter", entity_id=doc["id"],
                 after=doc, summary=f"Buat order sub-charter {doc['code']} ke {partner.get('name')}")
    return safe_doc(doc)


@router.get("/subcharters/{subcharter_id}")
async def get_subcharter(subcharter_id: str, user=Depends(PARTNERS)):
    doc = await get_db().subcharters.find_one({"id": subcharter_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Sub-charter tidak ditemukan")
    return safe_doc(doc)


@router.patch("/subcharters/{subcharter_id}")
async def update_subcharter(subcharter_id: str, body: SubcharterUpdate, user=Depends(PARTNERS)):
    db = get_db()
    sc = await db.subcharters.find_one({"id": subcharter_id}, {"_id": 0})
    if not sc:
        raise HTTPException(status_code=404, detail="Sub-charter tidak ditemukan")
    if sc.get("status") != "requested":
        raise HTTPException(status_code=400, detail="Hanya order berstatus 'requested' yang bisa diubah")
    updates = {}
    if body.cost is not None:
        if float(body.cost) <= 0:
            raise HTTPException(status_code=400, detail="Biaya sewa harus lebih dari 0")
        updates["cost"] = float(body.cost)
    for f in ("start_datetime", "end_datetime", "note", "vehicle_label"):
        v = getattr(body, f)
        if v is not None:
            updates[f] = v
    if body.vehicle_id is not None:
        if body.vehicle_id:
            if not await db.vehicles.find_one({"id": body.vehicle_id}, {"_id": 1}):
                raise HTTPException(status_code=400, detail="Armada tidak ditemukan")
        updates["vehicle_id"] = body.vehicle_id or None
    # R6-1: PATCH dulu MELEWATI cek bentrok saat ubah tanggal/unit → bisa double-book unit mitra
    # (persis pola B1 di /bookings). Re-validasi jendela + bentrok unit mitra dgn NILAI EFEKTIF baru.
    eff_start = updates.get("start_datetime", sc.get("start_datetime"))
    eff_end = updates.get("end_datetime", sc.get("end_datetime"))
    eff_vehicle = updates["vehicle_id"] if "vehicle_id" in updates else sc.get("vehicle_id")
    time_or_vehicle_changed = any(k in updates for k in ("start_datetime", "end_datetime", "vehicle_id"))
    if time_or_vehicle_changed and eff_start and eff_end and eff_end <= eff_start:
        raise HTTPException(status_code=400, detail="Tanggal selesai harus setelah tanggal mulai")
    if time_or_vehicle_changed and eff_vehicle and eff_start and eff_end:
        async with vehicle_lock(db, eff_vehicle):
            conflicts = await sc_svc.find_subcharter_conflicts(
                db, eff_vehicle, eff_start, eff_end, exclude_id=subcharter_id)
            if conflicts:
                codes = ", ".join(c.get("code", c.get("id")) for c in conflicts)
                raise HTTPException(status_code=400, detail=f"Unit mitra bentrok dengan sub-charter aktif: {codes}")
            if updates:
                await db.subcharters.update_one({"id": subcharter_id}, {"$set": updates})
        return safe_doc(await db.subcharters.find_one({"id": subcharter_id}, {"_id": 0}))
    if updates:
        await db.subcharters.update_one({"id": subcharter_id}, {"$set": updates})
    return safe_doc(await db.subcharters.find_one({"id": subcharter_id}, {"_id": 0}))


@router.post("/subcharters/{subcharter_id}/confirm")
async def confirm_subcharter(subcharter_id: str, user=Depends(PARTNERS)):
    """Konfirmasi order → bukukan COGS (sewa_mitra) + WA ke MITRA + notifikasi."""
    db = get_db()
    sc = await db.subcharters.find_one({"id": subcharter_id}, {"_id": 0})
    if not sc:
        raise HTTPException(status_code=404, detail="Sub-charter tidak ditemukan")
    if sc.get("status") != "requested":
        raise HTTPException(status_code=400, detail="Order sudah dikonfirmasi/selesai/dibatalkan")
    expense_id, _trip_id = await sc_svc.book_cogs_expense(db, sc, user)
    await db.subcharters.update_one({"id": subcharter_id}, {"$set": {
        "status": "confirmed", "expense_id": expense_id, "confirmed_at": now_iso()}})
    sc = await db.subcharters.find_one({"id": subcharter_id}, {"_id": 0})
    payload = await sc_svc.build_partner_payload(db, sc)
    await emit(db, "subcharter.confirmed", payload, source="subcharter", ref_type="subcharter",
              ref_id=subcharter_id, dedupe_key=f"subcharter.confirmed:{subcharter_id}")
    await record(db, actor=user, action="confirm", entity_type="subcharter", entity_id=subcharter_id,
                 summary=f"Konfirmasi sub-charter {sc.get('code')} (COGS Rp {int(sc.get('cost') or 0):,})".replace(",", "."))
    return safe_doc(sc)


@router.post("/subcharters/{subcharter_id}/settle")
async def settle_subcharter(subcharter_id: str, user=Depends(PARTNERS)):
    """Tandai lunas → catat pembayaran ke mitra (partner_settlements) sebesar cost."""
    db = get_db()
    sc = await db.subcharters.find_one({"id": subcharter_id}, {"_id": 0})
    if not sc:
        raise HTTPException(status_code=404, detail="Sub-charter tidak ditemukan")
    if sc.get("status") != "confirmed":
        raise HTTPException(status_code=400, detail="Hanya order 'confirmed' yang bisa dilunasi")
    settlement = {
        "id": new_id("pst"), "partner_id": sc.get("partner_id"), "partner_name": sc.get("partner_name"),
        "subcharter_id": subcharter_id, "amount": float(sc.get("cost", 0) or 0),
        "method": "transfer", "note": f"Pelunasan {sc.get('code')}", "paid_at": now_iso(),
        "recorded_by": user.get("id"), "created_at": now_iso(),
    }
    await db.partner_settlements.insert_one(settlement)
    await db.subcharters.update_one({"id": subcharter_id}, {"$set": {
        "status": "settled", "settled_at": now_iso()}})
    sc = await db.subcharters.find_one({"id": subcharter_id}, {"_id": 0})
    payload = await sc_svc.build_partner_payload(db, sc)
    await emit(db, "subcharter.settled", payload, source="subcharter", ref_type="subcharter",
              ref_id=subcharter_id, dedupe_key=f"subcharter.settled:{subcharter_id}")
    await record(db, actor=user, action="settle", entity_type="subcharter", entity_id=subcharter_id,
                 summary=f"Lunasi sub-charter {sc.get('code')} ke {sc.get('partner_name')}")
    return safe_doc(sc)


@router.delete("/subcharters/{subcharter_id}")
async def delete_subcharter(subcharter_id: str, user=Depends(PARTNERS)):
    db = get_db()
    sc = await db.subcharters.find_one({"id": subcharter_id}, {"_id": 0})
    if not sc:
        raise HTTPException(status_code=404, detail="Sub-charter tidak ditemukan")
    if sc.get("status") not in ("requested", "cancelled"):
        raise HTTPException(status_code=400, detail="Hanya order 'requested' atau 'cancelled' yang bisa dihapus — batalkan dulu")
    await db.subcharters.delete_one({"id": subcharter_id})
    await record(db, actor=user, action="delete", entity_type="subcharter", entity_id=subcharter_id, before=sc,
                 summary=f"Hapus sub-charter {sc.get('code')}")
    return {"ok": True}


@router.post("/subcharters/{subcharter_id}/cancel")
async def cancel_subcharter(subcharter_id: str, user=Depends(PARTNERS)):
    db = get_db()
    sc = await db.subcharters.find_one({"id": subcharter_id}, {"_id": 0})
    if not sc:
        raise HTTPException(status_code=404, detail="Sub-charter tidak ditemukan")
    if sc.get("status") == "settled":
        raise HTTPException(status_code=400, detail="Order sudah dilunasi — tidak bisa dibatalkan")
    if sc.get("status") == "cancelled":
        return safe_doc(sc)
    await sc_svc.remove_cogs_expense(db, sc)
    await db.subcharters.update_one({"id": subcharter_id}, {"$set": {
        "status": "cancelled", "expense_id": None}})
    sc = await db.subcharters.find_one({"id": subcharter_id}, {"_id": 0})
    await record(db, actor=user, action="cancel", entity_type="subcharter", entity_id=subcharter_id,
                 summary=f"Batalkan sub-charter {sc.get('code')}")
    return safe_doc(sc)
