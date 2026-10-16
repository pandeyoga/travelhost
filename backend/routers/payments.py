"""routers/payments.py — pencatatan pembayaran booking (DP/pelunasan).

INV-2: total pembayaran tidak melebihi total tagihan booking.
INV-3: payment_status booking diturunkan ulang setelah tiap pembayaran.
Akses section 'finance' (owner/ops_admin). Router thin; logika di services/finance.py.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from core_utils import money, new_id, now_iso, safe_doc
from db import get_db
from dependencies import require_section
from schemas import PaymentCreate
from services.audit import record
from services.refs import PAYMENT_METHODS, PAYMENT_TYPES, must_be_choice
from services.events import emit
from services.finance import derive_payment_status, sum_payments

router = APIRouter(prefix="/api", tags=["payments"])
FIN = require_section("finance")


@router.get("/payments")
async def list_payments(booking_id: str = Query(default=None), limit: int = Query(default=200, le=500),
                       skip: int = Query(default=0, ge=0), user=Depends(FIN)):
    query = {}
    if booking_id:
        query["booking_id"] = booking_id
    docs = await get_db().payments.find(query, {"_id": 0}).sort("paid_at", -1).skip(skip).to_list(limit)
    return safe_doc(docs)


@router.post("/payments")
async def create_payment(body: PaymentCreate, user=Depends(FIN)):
    db = get_db()
    booking = await db.bookings.find_one({"id": body.booking_id}, {"_id": 0})
    if not booking:
        raise HTTPException(status_code=400, detail="Booking tidak ditemukan")
    # RC-05: pembayaran DILARANG untuk booking yang dibatalkan.
    if booking.get("status") == "cancelled":
        raise HTTPException(status_code=400, detail="Booking dibatalkan — pembayaran ditolak")
    amount = money(body.amount)  # RC-11: rupiah integer (bebas drift float)
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Nominal pembayaran harus lebih dari 0")
    # IDEMPOTENCY (anti double-submit / retry jaringan / klik-ganda): bila client mengirim
    # idempotency_key & pembayaran dgn key itu SUDAH ada → replay (kembalikan yg lama, TANPA
    # menambah paid_amount / membuat catatan ganda). Tanpa ini, retry menggandakan pembayaran.
    idem = (body.idempotency_key or "").strip() or None
    if idem:
        prior = await db.payments.find_one({"idempotency_key": idem}, {"_id": 0})
        if prior:
            return safe_doc(prior)
    # RC-01: cek-sisa + tambah paid_amount jadi SATU operasi ATOMIK (anti-TOCTOU/race).
    # find_one_and_update dgn guard $expr: paid_amount + amount <= total_amount (+toleransi).
    # MongoDB menjamin atomicity level-dokumen → request paralel di-serialize, tak bisa overpay.
    # AFTER: kembalikan dokumen SETELAH $inc agar paid_amount hasil reservasi terbaca.
    guarded = await db.bookings.find_one_and_update(
        {
            "id": body.booking_id,
            "status": {"$ne": "cancelled"},
            "$expr": {"$lte": [
                {"$add": [{"$ifNull": ["$paid_amount", 0]}, amount]},
                {"$add": [{"$ifNull": ["$total_amount", 0]}, 0.01]},
            ]},
        },
        {"$inc": {"paid_amount": amount}},
        return_document=ReturnDocument.AFTER,
    )
    if not guarded:
        # Guard gagal → melebihi sisa (atau status berubah di tengah balapan).
        paid_now = await sum_payments(db, body.booking_id)
        remaining = max(money(booking.get("total_amount", 0)) - int(round(paid_now)), 0)
        raise HTTPException(
            status_code=400,
            detail=f"Pembayaran melebihi sisa tagihan (sisa Rp {remaining:,})".replace(",", "."),
        )
    doc = {
        "id": new_id("pay"), "booking_id": body.booking_id, "amount": amount,
        # INV-REF-01: jenis & metode pembayaran menggerakkan DP-gate, laporan kas, dan
        # rekonsiliasi. Nilai di luar daftar membuat DP tidak dikenali sebagai DP.
        "type": must_be_choice(body.type, PAYMENT_TYPES, field_label="Jenis pembayaran",
                               default="settlement"),
        "method": must_be_choice(body.method, PAYMENT_METHODS, field_label="Metode pembayaran",
                                 default="transfer"),
        "note": body.note or "", "recorded_by": user.get("id"), "paid_at": now_iso(),
        "idempotency_key": idem,
    }
    try:
        await db.payments.insert_one(doc)
    except DuplicateKeyError:
        # Replay KONKUREN: dua retry identik lolos pre-check bersamaan; salah satu kalah di
        # unique-index. Batalkan $inc yang barusan kita lakukan agar paid_amount tidak dobel,
        # lalu kembalikan pembayaran pemenang (idempotent).
        await db.bookings.update_one({"id": body.booking_id}, {"$inc": {"paid_amount": -amount}})
        cur = await db.bookings.find_one({"id": body.booking_id}, {"_id": 0, "paid_amount": 1, "total_amount": 1}) or {}
        await db.bookings.update_one(
            {"id": body.booking_id},
            {"$set": {"payment_status": derive_payment_status(
                money(cur.get("paid_amount", 0)), money(cur.get("total_amount", 0)))}})
        winner = await db.payments.find_one({"idempotency_key": idem}, {"_id": 0})
        return safe_doc(winner or doc)
    # RC-01 (perbaikan race): paid_amount adalah SSOT ATOMIK hasil $inc. JANGAN di-overwrite
    # dgn recompute Σpayments di jalur ini — di tengah balapan Σpayments bisa lagging (insert
    # belum semua landing) sehingga mereset reservasi & membuka celah overpay. Cukup turunkan
    # payment_status dari nilai `after`. (Jalur lain spt trip-complete tetap boleh recompute.)
    new_paid = money(guarded.get("paid_amount", 0))
    total = money(guarded.get("total_amount", 0))
    ps = derive_payment_status(new_paid, total)
    await db.bookings.update_one({"id": body.booking_id}, {"$set": {"payment_status": ps}})
    # Invoice DP/pelunasan booking ini ikut berubah status (partial/paid) — satu sumber angka.
    from services.documents import sync_invoice_status
    await sync_invoice_status(db, body.booking_id)
    await record(db, actor=user, action="create", entity_type="payment", entity_id=doc["id"],
                 after=doc,
                 summary=f"Catat pembayaran Rp {int(doc['amount']):,} untuk booking {booking.get('code') or body.booking_id}".replace(",", "."))
    cust = await db.customers.find_one({"id": booking.get("customer_id")}, {"_id": 0, "phone": 1}) or {}
    await emit(db, "payment.recorded", {
        "payment_id": doc["id"], "booking_id": body.booking_id, "code": booking.get("code"),
        "customer_name": booking.get("customer_name"), "phone": cust.get("phone"),
        "amount": float(doc["amount"]), "type": doc["type"],
    }, source="payments", ref_type="booking", ref_id=body.booking_id,
        dedupe_key=f"payment.recorded:{doc['id']}")
    # E18: DP-gate — bila booking 'hold' & DP tercukupi → promote ke 'confirmed' (idempotent via
    # filter status:'hold') + emit booking.confirmed (WA konfirmasi + instruksi pelunasan).
    if guarded.get("status") == "hold":
        dp_amount = money(guarded.get("dp_amount") or 0)
        if dp_amount <= 0:
            dp_amount = money(total * float(guarded.get("dp_percent", 30) or 30) / 100.0)
        if new_paid >= dp_amount:
            promoted = await db.bookings.find_one_and_update(
                {"id": body.booking_id, "status": "hold"},
                {"$set": {"status": "confirmed", "dp_met_at": now_iso()}},
                return_document=ReturnDocument.AFTER,
            )
            if promoted:
                await record(db, actor=user, action="update", entity_type="booking",
                             entity_id=body.booking_id,
                             summary=f"DP tercukupi → booking {promoted.get('code')} dikonfirmasi (hold→confirmed)")
                await emit(db, "booking.confirmed", {
                    "booking_id": promoted["id"], "code": promoted.get("code"),
                    "customer_name": promoted.get("customer_name"), "phone": cust.get("phone"),
                    "total_amount": float(money(promoted.get("total_amount", 0))),
                    "dp_percent": promoted.get("dp_percent", 30),
                    "vehicle_name": promoted.get("vehicle_name"),
                    "start_datetime": (promoted.get("start_datetime") or "")[:16].replace("T", " "),
                }, source="payments", ref_type="booking", ref_id=promoted["id"],
                    dedupe_key=f"booking.confirmed:{promoted['id']}")
    return safe_doc(doc)
