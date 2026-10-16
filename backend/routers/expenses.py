"""routers/expenses.py — pencatatan pengeluaran trip/booking (Phase 5).

Koleksi kanonik: `expenses`. FK: booking_id→bookings, trip_id→trips (keduanya opsional,
tapi bila diisi WAJIB valid — cegah referensi menggantung / 500).
Menjaga INV-5: bila expense terkait trip, trip.profit dihitung ulang.
Akses section 'finance' (owner/ops_admin). Router thin.
"""
from fastapi import APIRouter, Depends, HTTPException, Query

from core_utils import money, new_id, now_iso, safe_doc
from db import get_db
from dependencies import require_section
from schemas import ExpenseCreate, ExpenseUpdate
from services.audit import record
from services.finance import EXPENSE_CATEGORIES, recompute_trip_profit

router = APIRouter(prefix="/api", tags=["expenses"])
FIN = require_section("finance")


@router.get("/expenses")
async def list_expenses(booking_id: str = Query(default=None), trip_id: str = Query(default=None),
                        limit: int = Query(default=300, le=1000), skip: int = Query(default=0, ge=0),
                        user=Depends(FIN)):
    query = {}
    if booking_id:
        query["booking_id"] = booking_id
    if trip_id:
        query["trip_id"] = trip_id
    docs = await get_db().expenses.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).to_list(limit)
    return safe_doc(docs)


@router.post("/expenses")
async def create_expense(body: ExpenseCreate, user=Depends(FIN)):
    db = get_db()
    booking = None
    if body.booking_id:
        booking = await db.bookings.find_one({"id": body.booking_id}, {"_id": 0})
        if not booking:
            raise HTTPException(status_code=400, detail="Booking tidak ditemukan")
    if body.trip_id:
        trip = await db.trips.find_one({"id": body.trip_id}, {"_id": 0})
        if not trip:
            raise HTTPException(status_code=400, detail="Trip tidak ditemukan")
    category = body.category if body.category in EXPENSE_CATEGORIES else "other"
    doc = {
        "id": new_id("exp"),
        "booking_id": body.booking_id or None,
        "trip_id": body.trip_id or None,
        "category": category,
        "amount": money(body.amount),
        "note": body.note or "",
        "booking_code": (booking or {}).get("code"),
        "recorded_by": user.get("id"),
        "created_at": now_iso(),
    }
    await db.expenses.insert_one(doc)
    if body.trip_id:
        await recompute_trip_profit(db, body.trip_id)
    await record(db, actor=user, action="create", entity_type="expense", entity_id=doc["id"],
                 after=doc,
                 summary=f"Catat pengeluaran {category} Rp {int(doc['amount']):,}".replace(",", "."))
    return safe_doc(doc)


@router.patch("/expenses/{expense_id}")
async def update_expense(expense_id: str, body: ExpenseUpdate, user=Depends(FIN)):
    db = get_db()
    before = await db.expenses.find_one({"id": expense_id}, {"_id": 0})
    if not before:
        raise HTTPException(status_code=404, detail="Pengeluaran tidak ditemukan")
    updates = {}
    data = body.model_dump(exclude_unset=True)
    if "booking_id" in data:
        bid = data["booking_id"] or None
        booking = await db.bookings.find_one({"id": bid}, {"_id": 0, "code": 1}) if bid else None
        if bid and not booking:
            raise HTTPException(status_code=400, detail="Booking tidak ditemukan")
        updates["booking_id"] = bid
        updates["booking_code"] = (booking or {}).get("code")
    if data.get("category") is not None:
        updates["category"] = data["category"] if data["category"] in EXPENSE_CATEGORIES else "other"
    if data.get("amount") is not None:
        updates["amount"] = money(data["amount"])
    if data.get("note") is not None:
        updates["note"] = data["note"]
    if updates:
        updates["updated_at"] = now_iso()
        await db.expenses.update_one({"id": expense_id}, {"$set": updates})
    if before.get("trip_id"):
        await recompute_trip_profit(db, before["trip_id"])
    doc = await db.expenses.find_one({"id": expense_id}, {"_id": 0})
    await record(db, actor=user, action="update", entity_type="expense", entity_id=expense_id,
                 before=before, after=doc, summary=f"Ubah pengeluaran {doc.get('category')}")
    return safe_doc(doc)


@router.delete("/expenses/{expense_id}")
async def delete_expense(expense_id: str, user=Depends(FIN)):
    db = get_db()
    before = await db.expenses.find_one({"id": expense_id}, {"_id": 0})
    if not before:
        raise HTTPException(status_code=404, detail="Pengeluaran tidak ditemukan")
    await db.expenses.delete_one({"id": expense_id})
    if before.get("trip_id"):
        await recompute_trip_profit(db, before["trip_id"])
    await record(db, actor=user, action="delete", entity_type="expense", entity_id=expense_id,
                 before=before,
                 summary=f"Hapus pengeluaran {before.get('category')} Rp {int(before.get('amount') or 0):,}".replace(",", "."))
    return {"ok": True, "id": expense_id}
