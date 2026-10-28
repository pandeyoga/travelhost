"""routers/booking_lifecycle.py — transisi status booking oleh ops + pratinjau harga.

  POST /api/bookings/{id}/approve          pending → confirmed (assign armada, harga final)
  POST /api/bookings/{id}/reject           pending|hold → cancelled (alasan tampil ke pelanggan)
  POST /api/bookings/{id}/complete         confirmed|ongoing → completed (jadwal sudah mulai)
  GET  /api/bookings/{id}/reprice-preview  harga baru utk jadwal/armada lain (tanpa menyimpan)

Dipisah dari routers/bookings.py (batas ukuran berkas). Aturan 2026-10-28 (audit flow):
- Selesai: hanya booking terkonfirmasi/berjalan yang jadwal mulainya sudah lewat. Dulu booking
  'hold' tanpa DP atau jadwal bulan depan bisa diselesaikan & permintaan ulasan langsung terkirim.
- Setujui: harga kosong = dihitung ulang dari tarif unit terpilih (add-on & promo dipertahankan,
  SSOT booking_search.repriced_fields). Dulu harga & rincian tetap milik unit lama.
- Tolak: alasan tersimpan, kuota promo kembali; ditolak bila ada pembayaran / bukti DP pending.
"""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from core_utils import money, now_iso, safe_doc
from db import get_db
from dependencies import require_role
from schemas import BookingApprove
from schemas_booking import RejectBooking
from services import booking_flow as bf
from services import booking_search as bs
from services.audit import record
from services.availability import (find_conflicts, find_driver_conflicts,
                                   find_maintenance_conflicts, vehicle_lock)
from services.events import emit
from services.finance import derive_payment_status, recompute_booking_payment
from services.geo import parse_iso

router = APIRouter(prefix="/api", tags=["booking-lifecycle"])
MANAGER = require_role("owner", "ops_admin")
COMPLETABLE = ("confirmed", "ongoing")


async def _booking_or_404(db, booking_id):
    booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
    if not booking:
        raise HTTPException(status_code=404, detail="Booking tidak ditemukan")
    return booking


def _addons_sum(booking) -> int:
    return sum(money(a.get("amount")) for a in booking.get("add_ons") or [])


@router.post("/bookings/{booking_id}/approve")
async def approve_booking(booking_id: str, body: BookingApprove, user=Depends(MANAGER)):
    """E19: setujui permintaan `pending` → assign armada + harga final + `confirmed` (tanpa
    gerbang DP; utk minta DP dulu pakai /approve-hold). Re-cek INV-4/INV-21/RC-07."""
    db = get_db()
    booking = await _booking_or_404(db, booking_id)
    if booking.get("status") != "pending":
        raise HTTPException(status_code=400, detail="Hanya booking berstatus 'pending' yang bisa disetujui")
    vehicle = await db.vehicles.find_one({"id": body.vehicle_id}, {"_id": 0})
    if not vehicle:
        raise HTTPException(status_code=400, detail="Armada tidak ditemukan")
    driver = None
    if body.driver_id:
        driver = await db.drivers.find_one({"id": body.driver_id}, {"_id": 0})
        if not driver:
            raise HTTPException(status_code=400, detail="Driver tidak ditemukan")
    start_iso, end_iso = booking.get("start_datetime"), booking.get("end_datetime")
    # Harga: isi manual = harga nego (promo gugur); kosong = tarif unit terpilih (add-on & promo tetap).
    drop_promo = ""
    if body.base_price:
        base = money(body.base_price)
        price = {"base_price": base, "total_amount": base + _addons_sum(booking), "promo_discount": 0,
                 "price_breakdown": [{"label": "Harga ditetapkan tim", "amount": base},
                                     *[{"label": a.get("label") or "Layanan tambahan", "amount": money(a.get("amount"))}
                                       for a in booking.get("add_ons") or []]]}
        if booking.get("promo_id"):
            drop_promo = booking["promo_id"]
            price.update({"promo_id": "", "promo_code": ""})
    else:
        price, drop_promo = await bs.repriced_fields(db, booking, vehicle)
        if not price:
            raise HTTPException(status_code=400, detail="Harga otomatis tidak tersedia untuk unit/rute ini — isi harga manual")
    price["payment_status"] = derive_payment_status(money(booking.get("paid_amount")), price["total_amount"])
    # RC-16 (anti-TOCTOU): re-cek + set confirmed harus serial per armada.
    async with vehicle_lock(db, body.vehicle_id):
        conflicts = await find_conflicts(db, body.vehicle_id, start_iso, end_iso, exclude_id=booking_id)
        if conflicts:
            codes = ", ".join(c.get("code", c.get("id")) for c in conflicts)
            raise HTTPException(status_code=400, detail=f"Armada bentrok dengan booking aktif: {codes}")
        maint = await find_maintenance_conflicts(db, body.vehicle_id, start_iso, end_iso)
        if maint:
            titles = ", ".join((m.get("title") or m.get("type") or "perawatan") for m in maint)
            raise HTTPException(status_code=400, detail=f"Armada dalam masa perawatan: {titles}")
        if body.driver_id:
            dconf = await find_driver_conflicts(db, body.driver_id, start_iso, end_iso, exclude_booking_id=booking_id)
            if dconf:
                raise HTTPException(status_code=400,
                                    detail=f"Driver bentrok dengan booking aktif: {dconf[0].get('code')}")
        updates = {"vehicle_id": vehicle["id"], "vehicle_name": vehicle.get("name"),
                   "requested_vehicle_type": vehicle.get("type"), "status": "confirmed",
                   "approved_at": now_iso(), "approved_by": user.get("email") or user.get("id"), **price}
        if driver:
            updates.update({"driver_id": driver["id"], "driver_name": driver.get("name")})
        won = await db.bookings.update_one({"id": booking_id, "status": "pending"}, {"$set": updates})
        if not won.matched_count:
            raise HTTPException(status_code=409, detail="Status permintaan sudah berubah — muat ulang")
    if drop_promo:
        from services import promos as promo_svc
        await promo_svc.release(db, drop_promo)
    res = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
    await record(db, actor=user, action="approve", entity_type="booking", entity_id=booking_id,
                 summary=f"Setujui permintaan booking {res.get('code')} → confirmed "
                         f"(Rp {money(res.get('total_amount')):,})".replace(",", "."))
    await bf.emit_booking_confirmed(db, res)
    return safe_doc(res)


@router.post("/bookings/{booking_id}/reject")
async def reject_booking(booking_id: str, body: Optional[RejectBooking] = None, user=Depends(MANAGER)):
    """E19: tolak permintaan `pending`/`hold` → cancelled + WA `booking.cancelled`."""
    from services.trips import release_booking_resources
    db = get_db()
    booking = await _booking_or_404(db, booking_id)
    if booking.get("status") not in ("pending", "hold"):
        raise HTTPException(status_code=400, detail="Hanya booking 'pending'/'hold' yang bisa ditolak")
    if money(booking.get("paid_amount")) > 0:
        raise HTTPException(status_code=400, detail="Pesanan sudah menerima pembayaran — gunakan "
                            "Batalkan (dengan denda/refund) agar uangnya tercatat")
    if await bf.pending_proof(db, booking_id):
        raise HTTPException(status_code=400, detail="Ada bukti transfer DP yang menunggu verifikasi — "
                            "verifikasi atau tolak buktinya dulu")
    reason = ((body.reason if body else "") or "").strip()
    won = await db.bookings.find_one_and_update(
        {"id": booking_id, "status": {"$in": ["pending", "hold"]}},
        {"$set": {"status": "cancelled", "cancelled_at": now_iso(), "rejected_at": now_iso(),
                  "cancelled_by": user.get("id"), "cancellation_reason": reason or "Permintaan ditolak"}})
    if not won:
        raise HTTPException(status_code=409, detail="Status permintaan sudah berubah — muat ulang")
    if booking.get("promo_id"):  # kuota promo kembali (dulu bocor di jalur tolak admin)
        from services import promos as promo_svc
        await promo_svc.release(db, booking["promo_id"])
    await release_booking_resources(db, booking)
    res = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
    await record(db, actor=user, action="reject", entity_type="booking", entity_id=booking_id,
                 summary=f"Tolak permintaan booking {res.get('code')}" + (f": {reason[:120]}" if reason else ""))
    from services.wa_payload import build_wa_payload
    payload = await build_wa_payload(db, booking)
    payload["cancellation_reason"] = reason
    await emit(db, "booking.cancelled", payload, source="bookings", ref_type="booking",
               ref_id=booking_id, dedupe_key=f"booking.cancelled:{booking_id}")
    return safe_doc(res)


@router.post("/bookings/{booking_id}/complete")
async def complete_booking(booking_id: str, user=Depends(MANAGER)):
    """Ops menutup booking (mis. sopir tidak memakai aplikasi). Hanya utk booking terkonfirmasi/
    berjalan yang jadwalnya sudah MULAI; trip yang belum sempat di-check-in ikut ditutup."""
    from services.trips import finalize_trip_completion, release_vehicle
    db = get_db()
    booking = await _booking_or_404(db, booking_id)
    if booking.get("status") not in COMPLETABLE:
        label = {"pending": "menunggu persetujuan", "hold": "menunggu DP", "cancelled": "dibatalkan",
                 "completed": "selesai"}.get(booking.get("status"), booking.get("status"))
        raise HTTPException(status_code=400, detail=f"Booking {label} — tidak bisa diselesaikan")
    start = parse_iso(booking.get("start_datetime"))
    if start and start > datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Jadwal keberangkatan belum dimulai — booking belum bisa diselesaikan")
    trip = await db.trips.find_one({"booking_id": booking_id, "status": {"$nin": ["cancelled", "completed"]}}, {"_id": 0})
    if trip:  # SSOT penyelesaian (armada, KM, fee, WA, ulasan); standby = override ops (force)
        await finalize_trip_completion(db, trip, user, force=True)
    else:
        await db.bookings.update_one({"id": booking_id, "status": {"$in": list(COMPLETABLE)}},
                                     {"$set": {"status": "completed"}})
        await recompute_booking_payment(db, booking_id)  # RC-02: derivasi jujur, bukan 'selesai'
        await release_vehicle(db, booking.get("vehicle_id"), exclude_booking_id=booking_id)
    res = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
    await record(db, actor=user, action="complete", entity_type="booking", entity_id=booking_id,
                 summary=f"Selesaikan booking {res.get('code')}")
    try:  # CMS-07: jalur tanpa trip juga meminta ulasan (idempotent per pesanan)
        from services import reviews as _reviews
        await _reviews.request_and_send(db, res, actor=user, source="booking_completed")
    except Exception:  # noqa: BLE001 — permintaan ulasan tak boleh menggagalkan penyelesaian
        pass
    return safe_doc(res)


@router.get("/bookings/{booking_id}/reprice-preview")
async def reprice_preview(booking_id: str, start: str = Query(...), end: str = Query(...),
                          vehicle_id: str = Query(default=None), user=Depends(MANAGER)):
    """Pratinjau harga jadwal ulang (sama persis dgn yg akan disimpan reschedule reprice=true)."""
    db = get_db()
    booking = await _booking_or_404(db, booking_id)
    s, e = parse_iso(start), parse_iso(end)
    if not s or not e or e <= s:
        raise HTTPException(status_code=400, detail="Rentang tanggal tidak valid")
    vehicle = await db.vehicles.find_one({"id": vehicle_id or booking.get("vehicle_id")}, {"_id": 0})
    if not vehicle:
        raise HTTPException(status_code=400, detail="Armada tidak ditemukan")
    price, drop = await bs.repriced_fields(db, booking, vehicle, start_iso=s.isoformat(), end_iso=e.isoformat())
    old_total = money(booking.get("total_amount"))
    if not price:
        return {"available": False, "old_total": old_total, "reason": "Harga otomatis tidak tersedia untuk unit/rute ini"}
    return {"available": True, "old_total": old_total, "new_total": price["total_amount"],
            "difference": price["total_amount"] - old_total, "breakdown": price["price_breakdown"],
            "promo_dropped": bool(drop), "paid_amount": money(booking.get("paid_amount"))}
