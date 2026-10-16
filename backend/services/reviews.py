"""services/reviews.py — CMS-07: ulasan pelanggan NYATA → testimoni tayang.

Masalah
-------
Testimoni di situs sebelumnya diketik manual oleh admin. Bukti sosial paling kuat
(ulasan pelanggan yang benar-benar jalan) tidak pernah difunnel: setelah trip selesai
tidak ada satu pun ajakan memberi ulasan.

Alur yang dibangun
------------------
1. Trip selesai → `create_request()` membuat token ulasan sekali-pakai untuk pesanan itu
   (idempotent per pesanan) dan mengirim tautannya lewat WhatsApp.
   **WhatsApp masih MOCK** di repo ini: pesan tercatat di Inbox, belum benar-benar terkirim.
2. Pelanggan membuka `/ulasan/<token>` → mengisi rating 1–5 + kutipan.
3. Jawaban masuk sebagai testimoni `approved=false` (moderasi) — TIDAK langsung tayang,
   supaya pemilik tetap memegang kendali atas halaman depan.
4. Admin menyetujui → testimoni tampil di situs & ikut rata-rata rating (AggregateRating).
"""
import os
import secrets
from datetime import datetime, timedelta, timezone

from core_utils import new_id, now_iso, safe_doc

COLLECTION = "review_requests"
TTL_DAYS = 45
MAX_QUOTE_CHARS = 1200
STATUS_SENT = "sent"
STATUS_SUBMITTED = "submitted"
STATUS_EXPIRED = "expired"


class ReviewError(ValueError):
    """Ulasan ditolak — dilaporkan 4xx dengan ALASAN berbahasa Indonesia."""


def _now_str() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def site_url() -> str:
    return (os.environ.get("PUBLIC_SITE_URL") or "").strip().rstrip("/")


def review_link(token: str) -> str:
    base = site_url()
    return f"{base}/ulasan/{token}" if base else f"/ulasan/{token}"


async def ensure_indexes(db):
    try:
        await db[COLLECTION].create_index("token", unique=True)
        await db[COLLECTION].create_index("booking_id")
        await db[COLLECTION].create_index([("status", 1), ("created_at", -1)])
        await db.testimonials.create_index([("approved", 1), ("created_at", -1)])
    except Exception:  # noqa: BLE001
        pass


async def create_request(db, booking: dict, *, actor: dict | None = None,
                         source: str = "auto") -> dict:
    """Buat (atau ambil kembali) permintaan ulasan untuk satu pesanan. Idempotent."""
    booking = booking or {}
    bid = booking.get("id")
    if not bid:
        raise ReviewError("Pesanan tidak dikenal")
    existing = await db[COLLECTION].find_one(
        {"booking_id": bid, "status": {"$ne": STATUS_EXPIRED}}, {"_id": 0})
    if existing:
        return existing
    token = secrets.token_urlsafe(18)
    expires = (datetime.now(timezone.utc) + timedelta(days=TTL_DAYS)).replace(
        microsecond=0).isoformat()
    row = {
        "id": new_id("rvq"), "token": token, "booking_id": bid,
        "booking_code": booking.get("code") or "",
        "customer_id": booking.get("customer_id") or "",
        "customer_name": booking.get("customer_name") or booking.get("contact_name") or "Pelanggan",
        "phone": booking.get("contact_phone") or booking.get("phone") or "",
        "route": " → ".join([x for x in [booking.get("origin"), booking.get("destination")] if x]),
        "status": STATUS_SENT, "source": source,
        "created_by": (actor or {}).get("id") or "",
        "created_at": now_iso(), "expires_at": expires,
        "sent_at": "", "submitted_at": "", "testimonial_id": "",
        "channel": "whatsapp_mock", "link": review_link(token),
    }
    await db[COLLECTION].insert_one(row)
    return row


async def send_request(db, req: dict) -> dict:
    """Kirim tautan ulasan lewat WhatsApp (MOCK → tercatat di Inbox)."""
    from services.whatsapp import send_wa
    text = (f"Terima kasih sudah menempuh perjalanan bersama kami, {req.get('customer_name')}! "
            f"Boleh bagikan pengalaman Anda untuk pesanan {req.get('booking_code') or ''}? "
            f"Isi ulasan singkat di sini: {req.get('link')} "
            "(1 menit saja, sangat membantu calon pelanggan lain).")
    result = {"status": "skipped", "reason": "nomor kosong"}
    if (req.get("phone") or "").strip():
        result = await send_wa(db, req["phone"], text=text,
                              customer_id=req.get("customer_id") or None,
                              contact_name=req.get("customer_name"), source="review_request")
    await db[COLLECTION].update_one(
        {"id": req["id"]},
        {"$set": {"sent_at": now_iso(), "send_status": result.get("status") or "unknown"}})
    return result


async def request_and_send(db, booking: dict, *, actor=None, source="auto") -> dict:
    """Jalur lengkap: buat permintaan + kirim tautan. Aman dipanggil berulang."""
    req = await create_request(db, booking, actor=actor, source=source)
    if req.get("status") == STATUS_SUBMITTED:
        return {"request": req, "send": {"status": "skipped", "reason": "sudah diisi"}}
    send = await send_request(db, req)
    fresh = await db[COLLECTION].find_one({"id": req["id"]}, {"_id": 0})
    return {"request": fresh or req, "send": send}


async def get_context(db, token: str) -> dict:
    """Konteks halaman ulasan publik (nama, kode pesanan, rute). Raise ReviewError bila tak sah."""
    row = await db[COLLECTION].find_one({"token": str(token or "").strip()}, {"_id": 0})
    if not row:
        raise ReviewError("Tautan ulasan tidak dikenal atau sudah dicabut")
    if row.get("status") == STATUS_SUBMITTED:
        raise ReviewError("Ulasan untuk pesanan ini sudah kami terima. Terima kasih!")
    if str(row.get("expires_at") or "") <= _now_str():
        await db[COLLECTION].update_one({"id": row["id"]}, {"$set": {"status": STATUS_EXPIRED}})
        raise ReviewError("Tautan ulasan sudah kedaluwarsa")
    return {
        "customer_name": row.get("customer_name") or "Pelanggan",
        "booking_code": row.get("booking_code") or "",
        "route": row.get("route") or "",
        "expires_at": row.get("expires_at") or "",
    }


async def submit(db, token: str, *, rating, quote: str, name: str = "", role: str = "",
                 consent: bool = True) -> dict:
    """Simpan ulasan sebagai testimoni MENUNGGU MODERASI (approved=false)."""
    row = await db[COLLECTION].find_one({"token": str(token or "").strip()}, {"_id": 0})
    if not row:
        raise ReviewError("Tautan ulasan tidak dikenal atau sudah dicabut")
    if row.get("status") == STATUS_SUBMITTED:
        raise ReviewError("Ulasan untuk pesanan ini sudah kami terima. Terima kasih!")
    if str(row.get("expires_at") or "") <= _now_str():
        await db[COLLECTION].update_one({"id": row["id"]}, {"$set": {"status": STATUS_EXPIRED}})
        raise ReviewError("Tautan ulasan sudah kedaluwarsa")
    try:
        stars = int(rating)
    except (TypeError, ValueError):
        raise ReviewError("Rating harus angka 1–5") from None
    if stars < 1 or stars > 5:
        raise ReviewError("Rating harus di antara 1 sampai 5")
    text = str(quote or "").strip()[:MAX_QUOTE_CHARS]
    if len(text) < 10:
        raise ReviewError("Mohon tulis ulasan minimal 10 karakter")
    if not consent:
        raise ReviewError("Persetujuan penayangan diperlukan agar ulasan bisa ditampilkan")

    doc = {
        "id": new_id("tst"),
        "name": (str(name or "").strip() or row.get("customer_name") or "Pelanggan")[:120],
        "role": str(role or "").strip()[:120],
        "quote": text, "rating": stars, "avatar": "",
        "approved": False, "position": 0,
        "source": "review", "review_request_id": row["id"],
        "booking_code": row.get("booking_code") or "",
        "booking_id": row.get("booking_id") or "",
        "submitted_at": now_iso(), "created_at": now_iso(),
    }
    await db.testimonials.insert_one(doc)
    await db[COLLECTION].update_one({"id": row["id"]}, {"$set": {
        "status": STATUS_SUBMITTED, "submitted_at": now_iso(),
        "testimonial_id": doc["id"], "rating": stars}})
    return safe_doc(doc)


async def summary(db) -> dict:
    """Rata-rata rating dari testimoni TAYANG (untuk AggregateRating & panel admin)."""
    visible = {"$or": [{"approved": True}, {"approved": {"$exists": False}}]}
    docs = await db.testimonials.find(visible, {"_id": 0, "rating": 1}).to_list(500)
    ratings = [int(d.get("rating") or 0) for d in docs if int(d.get("rating") or 0) > 0]
    count = len(ratings)
    avg = round(sum(ratings) / count, 2) if count else 0
    pending = await db.testimonials.count_documents({"approved": False})
    return {"count": count, "average": avg, "total_published": len(docs), "pending": pending}


async def scan_due(db, limit: int = 25) -> int:
    """Scheduler: pesanan `completed` yang belum pernah diminta ulasan → kirim.

    Jaring pengaman bila hook penyelesaian trip terlewat (mis. penyelesaian manual lewat
    jalur lain). Idempotent karena `create_request` dedupe per pesanan.
    """
    sent = 0
    rows = await db.bookings.find({"status": "completed"},
                                  {"_id": 0, "id": 1, "code": 1, "customer_id": 1,
                                   "customer_name": 1, "contact_name": 1, "contact_phone": 1,
                                   "origin": 1, "destination": 1}).sort("id", 1).to_list(200)
    for bk in rows:
        if sent >= limit:
            break
        exists = await db[COLLECTION].find_one({"booking_id": bk["id"]}, {"_id": 0, "id": 1})
        if exists:
            continue
        try:
            await request_and_send(db, bk, source="scheduler")
            sent += 1
        except Exception:  # noqa: BLE001
            continue
    return sent
