"""routers/booking_admin.py — sisi ERP untuk pemesanan online (verifikasi DP + ACC).

Dipisah dari `bookings.py` (781 baris, batas guardrail 800) dan hanya memuat permukaan
baru milik alur web:

  GET  /api/bookings/payment-proofs                    — antrean bukti transfer masuk
  POST /api/bookings/{id}/proofs/{proof_id}/verify     — sahkan → catat pembayaran
  POST /api/bookings/{id}/proofs/{proof_id}/reject     — tolak + alasan (tamu bisa unggah ulang)
  POST /api/bookings/{id}/approve-hold                 — mode ops_approval: pending → hold + DP

Keputusan penting: verifikasi bukti TIDAK menulis koleksi `payments` sendiri, melainkan
MEMANGGIL `routers.payments.create_payment` — satu-satunya jalur pembayaran yang sudah
dijaga invarian (INV-2 tak boleh overpay via `$expr` atomik, idempotency-key, derivasi
`payment_status`, audit, event `payment.recorded`, dan promosi otomatis `hold → confirmed`
pada DP-gate E18). Menyalin logikanya = mengundang drift dan kehilangan semua jaminan itu.
"""
from fastapi import APIRouter, Depends, HTTPException, Query

from core_utils import money, now_iso, safe_doc
from db import get_db
from dependencies import require_role, require_section
from schemas import PaymentCreate
from schemas_booking import ApproveHoldRequest, ProofRejectRequest, ProofVerifyRequest
from services import booking_flow as bf
from services import booking_search as bs
from services.audit import record
from services.availability import (find_conflicts, find_maintenance_conflicts, vehicle_lock)
from services.events import emit
from services.pricing import get_dp_percent

router = APIRouter(prefix="/api", tags=["booking-admin"])
FIN = require_section("finance")            # verifikasi uang = permukaan keuangan
MANAGER = require_role("owner", "ops_admin")  # persetujuan operasional


@router.get("/bookings/payment-proofs")
async def list_payment_proofs(status: str = Query(default="pending"),
                              limit: int = Query(default=100, le=300),
                              user=Depends(FIN)):
    """Antrean bukti transfer dari pelanggan web (default: yang belum diverifikasi)."""
    db = get_db()
    query = {}
    if status and status != "all":
        query["status"] = status
    rows = await db.payment_proofs.find(query, {"_id": 0}).sort("created_at", -1).to_list(limit)
    codes = {r.get("booking_id") for r in rows if r.get("booking_id")}
    bookings = await db.bookings.find(
        {"id": {"$in": list(codes)}},
        {"_id": 0, "id": 1, "code": 1, "status": 1, "total_amount": 1, "paid_amount": 1,
         "dp_amount": 1, "customer_name": 1, "vehicle_name": 1, "start_datetime": 1,
         "hold_expires_at": 1, "service_label": 1},
    ).to_list(300)
    by_id = {b["id"]: b for b in bookings}
    return {"proofs": safe_doc([{**r, "booking": safe_doc(by_id.get(r.get("booking_id")) or {})}
                                for r in rows]),
            "total": await db.payment_proofs.count_documents(query),
            "pending": await db.payment_proofs.count_documents({"status": "pending"})}


async def _proof_or_404(db, booking_id: str, proof_id: str):
    proof = await db.payment_proofs.find_one({"id": proof_id, "booking_id": booking_id},
                                            {"_id": 0})
    if not proof:
        raise HTTPException(status_code=404, detail="Bukti pembayaran tidak ditemukan")
    booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
    if not booking:
        raise HTTPException(status_code=404, detail="Booking tidak ditemukan")
    return proof, booking


@router.post("/bookings/{booking_id}/proofs/{proof_id}/verify")
async def verify_proof(booking_id: str, proof_id: str, body: ProofVerifyRequest,
                       user=Depends(FIN)):
    """Sahkan bukti → catat pembayaran lewat jalur resmi (DP cukup → otomatis confirmed)."""
    db = get_db()
    proof, booking = await _proof_or_404(db, booking_id, proof_id)
    if proof.get("status") == "verified":
        return {"verified": True, "already": True, "proof": safe_doc(proof)}
    amount = money(body.amount if body.amount is not None else proof.get("amount_claimed"))
    if amount <= 0:
        raise HTTPException(status_code=400,
                            detail="Nominal pembayaran harus lebih dari 0 — isi nominal sesuai bukti")
    outstanding = max(money(booking.get("total_amount")) - money(booking.get("paid_amount")), 0)
    if amount > outstanding:
        raise HTTPException(
            status_code=400,
            detail=f"Nominal melebihi sisa tagihan (sisa Rp {outstanding:,})".replace(",", "."))
    from routers.payments import create_payment  # satu-satunya jalur pembayaran (lihat docstring)
    payment = await create_payment(
        PaymentCreate(booking_id=booking_id, amount=float(amount),
                      type="dp" if money(booking.get("paid_amount")) <= 0 else "settlement",
                      method=body.method or "transfer",
                      note=(body.note or f"Verifikasi bukti transfer {proof_id}")[:400],
                      idempotency_key=f"proof:{proof_id}"),
        user=user)
    await db.payment_proofs.update_one(
        {"id": proof_id},
        {"$set": {"status": "verified", "verified_by": user.get("email") or user.get("id"),
                  "verified_at": now_iso(), "amount_verified": amount,
                  "payment_id": (payment or {}).get("id") or "", "reject_reason": ""}})
    await db.bookings.update_one({"id": booking_id}, {"$set": {"proof_status": "verified"}})
    await record(db, actor=user, action="update", entity_type="booking", entity_id=booking_id,
                 summary=f"Verifikasi bukti transfer {booking.get('code')} — "
                         f"Rp {int(amount):,}".replace(",", "."))
    fresh = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
    return {"verified": True, "payment": safe_doc(payment),
            "booking": safe_doc(fresh), "already": False}


@router.post("/bookings/{booking_id}/proofs/{proof_id}/reject")
async def reject_proof(booking_id: str, proof_id: str, body: ProofRejectRequest,
                       user=Depends(FIN)):
    """Tolak bukti (mis. nominal tak cocok) — alasan tampil di halaman status pelanggan."""
    db = get_db()
    proof, booking = await _proof_or_404(db, booking_id, proof_id)
    if proof.get("status") == "verified":
        raise HTTPException(status_code=400,
                            detail="Bukti ini sudah diverifikasi — tidak bisa ditolak. "
                                   "Gunakan pembatalan/refund bila perlu koreksi.")
    await db.payment_proofs.update_one(
        {"id": proof_id},
        {"$set": {"status": "rejected", "reject_reason": body.reason[:240],
                  "verified_by": user.get("email") or user.get("id"), "verified_at": now_iso()}})
    await db.bookings.update_one({"id": booking_id}, {"$set": {"proof_status": "rejected"}})
    await record(db, actor=user, action="update", entity_type="booking", entity_id=booking_id,
                 summary=f"Tolak bukti transfer {booking.get('code')}: {body.reason[:80]}")
    await emit(db, "booking.payment_proof_rejected", {
        "booking_id": booking_id, "code": booking.get("code"),
        "customer_name": booking.get("customer_name"),
        "phone": booking.get("contact_phone"), "reason": body.reason[:240],
    }, source="bookings", ref_type="booking", ref_id=booking_id,
        dedupe_key=f"booking.proof_rejected:{proof_id}")
    return {"rejected": True, "proof_id": proof_id}


@router.post("/bookings/{booking_id}/approve-hold")
async def approve_hold(booking_id: str, body: ApproveHoldRequest, user=Depends(MANAGER)):
    """Mode `ops_approval`: setujui permintaan web → TAHAN unit + minta DP (pending → hold).

    Berbeda dari `/bookings/{id}/approve` (yang langsung `confirmed` tanpa syarat bayar),
    endpoint ini dipakai ketika pemilik memilih "ACC dulu, baru tamu bayar": unit baru
    dikunci setelah ops setuju, dan tamu punya batas waktu DP yang jelas.
    """
    db = get_db()
    booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
    if not booking:
        raise HTTPException(status_code=404, detail="Booking tidak ditemukan")
    if booking.get("status") != "pending":
        raise HTTPException(status_code=400,
                            detail="Hanya permintaan berstatus 'pending' yang bisa disetujui")
    flow = await bf.get_flow(db)
    vehicle_id = (body.vehicle_id or booking.get("vehicle_id") or "").strip()
    if not vehicle_id:
        raise HTTPException(status_code=400, detail="Tentukan armada untuk permintaan ini")
    vehicle = await db.vehicles.find_one({"id": vehicle_id}, {"_id": 0})
    if not vehicle:
        raise HTTPException(status_code=400, detail="Armada tidak ditemukan")
    start_iso, end_iso = booking.get("start_datetime"), booking.get("end_datetime")
    total = money(booking.get("total_amount"))
    if body.recompute_price is not False or total <= 0:
        route = None
        if booking.get("route_id"):
            route = await db.transfer_routes.find_one({"id": booking["route_id"]}, {"_id": 0})
        quote = await bs.quote_for_vehicle(
            db, vehicle, start_iso=start_iso, end_iso=end_iso,
            service=booking.get("service") or "daily_rental", route=route)
        if quote:
            total = money(quote["total"])
    dp_percent = int(money(booking.get("dp_percent")) or await get_dp_percent(db))
    hold = bf.hold_fields(total=total, dp_percent=dp_percent,
                         hold_hours=body.hold_hours or flow["approval_hold_hours"])
    async with vehicle_lock(db, vehicle_id):
        conflicts = await find_conflicts(db, vehicle_id, start_iso, end_iso, exclude_id=booking_id)
        if conflicts:
            codes = ", ".join(c.get("code", c.get("id")) for c in conflicts)
            raise HTTPException(status_code=400,
                                detail=f"Armada bentrok dengan booking aktif: {codes}")
        maint = await find_maintenance_conflicts(db, vehicle_id, start_iso, end_iso)
        if maint:
            titles = ", ".join((m.get("title") or m.get("type") or "perawatan") for m in maint)
            raise HTTPException(status_code=400, detail=f"Armada dalam masa perawatan: {titles}")
        updated = await db.bookings.find_one_and_update(
            {"id": booking_id, "status": "pending"},
            {"$set": {"status": "hold", "vehicle_id": vehicle_id,
                      "vehicle_name": vehicle.get("name"),
                      "requested_vehicle_type": vehicle.get("type"),
                      "base_price": total, "total_amount": total,
                      "approved_at": now_iso(), "approved_by": user.get("email") or user.get("id"),
                      **hold}})
    if not updated:
        raise HTTPException(status_code=400, detail="Status permintaan sudah berubah — muat ulang")
    fresh = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
    await record(db, actor=user, action="approve", entity_type="booking", entity_id=booking_id,
                 summary=f"Setujui permintaan web {booking.get('code')} → hold DP "
                         f"Rp {int(money(hold['dp_amount'])):,}".replace(",", "."))
    await emit(db, "booking.hold_created", {
        "booking_id": booking_id, "code": fresh.get("code"),
        "customer_name": fresh.get("customer_name"), "phone": fresh.get("contact_phone"),
        "vehicle_name": fresh.get("vehicle_name"), "total_amount": float(total),
        "dp_amount": float(money(hold["dp_amount"])), "hold_expires_at": hold["hold_expires_at"],
        "start_datetime": (start_iso or "")[:16].replace("T", " "),
    }, source="bookings", ref_type="booking", ref_id=booking_id,
        dedupe_key=f"booking.hold_created:{booking_id}")
    return safe_doc(fresh)
