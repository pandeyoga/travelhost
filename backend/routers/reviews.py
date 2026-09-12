"""routers/reviews.py — CMS-07: funnel ulasan pelanggan (sisi admin).

Publik mengisi ulasan lewat `/api/public/reviews/{token}` (lihat routers/public.py).
Di sisi admin, halaman **Konten Web → Ulasan** memakai endpoint di file ini untuk:

- melihat permintaan ulasan yang sudah dikirim & mana yang sudah diisi,
- mengirim / mengirim ulang tautan ulasan untuk pesanan yang sudah selesai,
- memoderasi ulasan masuk (setujui → tayang, tolak → tidak tayang),
- melihat rata-rata rating yang sedang tampil di situs.

RBAC section `cms` (owner + ops_admin) — sama dengan pengelola konten lain. Setiap
mutasi tercatat di Audit Log.

⚠️ WhatsApp masih **MOCK** di repo ini: tautan ulasan tercatat di Inbox, belum benar-benar
terkirim ke ponsel pelanggan (kredensial WhatsApp Cloud API belum ditempel).
"""
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response

from core_utils import safe_doc
from db import get_db
from dependencies import require_section
from services import reviews as review_svc
from services.audit import record

router = APIRouter(prefix="/api", tags=["reviews"])
CMS = require_section("cms")


@router.get("/reviews/summary")
async def reviews_summary(user=Depends(CMS)):
    """Ringkasan: jumlah ulasan tayang, rata-rata rating, dan yang menunggu moderasi."""
    db = get_db()
    summary = await review_svc.summary(db)
    requests_total = await db[review_svc.COLLECTION].count_documents({})
    submitted = await db[review_svc.COLLECTION].count_documents(
        {"status": review_svc.STATUS_SUBMITTED})
    waiting = await db[review_svc.COLLECTION].count_documents(
        {"status": review_svc.STATUS_SENT})
    rate = round((submitted / requests_total) * 100, 1) if requests_total else 0.0
    return {**summary, "requests": requests_total, "submitted": submitted,
            "waiting": waiting, "response_rate": rate, "channel": "whatsapp_mock"}


@router.get("/reviews/requests")
async def list_requests(response: Response,
                        status: Optional[str] = Query(default=None),
                        limit: int = Query(default=50, ge=1, le=200),
                        offset: int = Query(default=0, ge=0),
                        user=Depends(CMS)):
    """Daftar permintaan ulasan (terbaru dulu) + total via header `X-Total-Count`."""
    db = get_db()
    query = {}
    if status and status.strip() and status != "all":
        query["status"] = status.strip()
    total = await db[review_svc.COLLECTION].count_documents(query)
    rows = await (db[review_svc.COLLECTION].find(query, {"_id": 0})
                  .sort("created_at", -1).skip(offset).limit(limit).to_list(limit))
    response.headers["X-Total-Count"] = str(total)
    return safe_doc(rows)


@router.get("/reviews/eligible-bookings")
async def eligible_bookings(limit: int = Query(default=30, ge=1, le=100), user=Depends(CMS)):
    """Pesanan `completed` yang BELUM pernah dikirimi permintaan ulasan."""
    db = get_db()
    sent_ids = {r.get("booking_id") for r in await db[review_svc.COLLECTION].find(
        {}, {"_id": 0, "booking_id": 1}).to_list(1000)}
    rows = await db.bookings.find(
        {"status": "completed"},
        {"_id": 0, "id": 1, "code": 1, "customer_name": 1, "contact_phone": 1,
         "origin": 1, "destination": 1, "end_datetime": 1}
    ).sort("start_datetime", -1).to_list(300)
    out = [r for r in rows if r.get("id") not in sent_ids][:limit]
    return safe_doc(out)


@router.post("/reviews/requests")
async def create_request(body: dict = Body(...), user=Depends(CMS)):
    """Kirim (atau kirim ulang) tautan ulasan untuk satu pesanan yang sudah selesai."""
    booking_id = str(body.get("booking_id") or "").strip()
    if not booking_id:
        raise HTTPException(status_code=400, detail="ID pesanan wajib diisi")
    db = get_db()
    booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
    if not booking:
        raise HTTPException(status_code=404, detail="Pesanan tidak ditemukan")
    if booking.get("status") != "completed":
        raise HTTPException(status_code=400,
                            detail="Ulasan hanya diminta untuk pesanan yang sudah selesai")
    try:
        out = await review_svc.request_and_send(db, booking, actor=user, source="manual")
    except review_svc.ReviewError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    await record(db, actor=user, action="review_request", entity_type="booking",
                 entity_id=booking_id,
                 summary=f"Kirim permintaan ulasan (WA MOCK) untuk {booking.get('code') or booking_id}")
    return {"request": safe_doc(out["request"]), "send": out["send"],
            "note": "WhatsApp MOCK — pesan tercatat di Inbox, belum terkirim ke pelanggan"}


@router.get("/reviews/pending")
async def pending_reviews(limit: int = Query(default=50, ge=1, le=200), user=Depends(CMS)):
    """Ulasan masuk yang menunggu moderasi (belum tayang di situs)."""
    db = get_db()
    rows = await db.testimonials.find({"approved": False}, {"_id": 0}).sort(
        "submitted_at", -1).to_list(limit)
    return safe_doc(rows)


@router.post("/reviews/{testimonial_id}/moderate")
async def moderate_review(testimonial_id: str, body: dict = Body(...), user=Depends(CMS)):
    """Setujui (tayang) atau tolak ulasan. Penolakan tidak menghapus jejaknya."""
    action = str(body.get("action") or "").strip().lower()
    if action not in {"approve", "reject"}:
        raise HTTPException(status_code=400, detail="Aksi harus 'approve' atau 'reject'")
    db = get_db()
    doc = await db.testimonials.find_one({"id": testimonial_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Ulasan tidak ditemukan")
    approved = action == "approve"
    sets = {"approved": approved, "moderated_at": review_svc.now_iso(),
            "moderated_by": (user or {}).get("id") or "",
            "moderation": "approved" if approved else "rejected"}
    if str(body.get("note") or "").strip():
        sets["moderation_note"] = str(body["note"]).strip()[:400]
    await db.testimonials.update_one({"id": testimonial_id}, {"$set": sets})
    after = await db.testimonials.find_one({"id": testimonial_id}, {"_id": 0})
    await record(db, actor=user, action="moderate", entity_type="testimonials",
                 entity_id=testimonial_id, before=doc, after=after,
                 summary=f"{'Setujui' if approved else 'Tolak'} ulasan: {doc.get('name') or testimonial_id}")
    return safe_doc(after)
