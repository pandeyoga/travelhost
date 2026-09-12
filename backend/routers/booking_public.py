"""routers/booking_public.py — PEMESANAN ONLINE (publik, TANPA login).

Alur yang dilayani (analog Traveloka Rentcar / Antar-Jemput Bandara — bukan tiket per
kursi, karena yang dijual adalah SATU unit + driver):

  1. GET  /api/public/booking/config          — layanan aktif, tipe armada yang NYATA ada,
                                                rute bandara, DP%, batas waktu, kebijakan.
  2. POST /api/public/booking/search          — unit yang BENAR-BENAR bebas + harga masing2.
  3. POST /api/public/booking/quote           — rincian harga satu unit (langkah tinjau).
  4. POST /api/public/booking/submit          — buat pesanan (hold / menunggu ACC ops).
  5. POST /api/public/booking/lookup          — cek pesanan pakai kode + nomor WhatsApp.
  6. GET  /api/public/booking/{code}?token=   — halaman status (hitung mundur, instruksi DP).
  7. POST /api/public/booking/{code}/proof    — unggah bukti transfer (foto).
  8. POST /api/public/booking/{code}/cancel   — batalkan selama belum dikonfirmasi.

Seluruh logika ada di services/booking_public.py + services/booking_search.py (router thin).
Harga TIDAK PERNAH diterima dari klien — selalu dihitung ulang server (INV-BOOK-02).
Rute literal dideklarasikan SEBELUM `/{code}` agar tidak tertelan path-param.
"""
from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile

from core_utils import money, safe_doc
from db import get_db
from schemas_booking import (BookingCancelRequest, BookingLookupRequest, BookingPromoListRequest,
                            BookingQuoteRequest, BookingSearchRequest, PublicBookingSubmit)
from services import booking_flow as bf
from services import booking_public as bp
from services import booking_search as bs
from services import promos as promo_svc
from services.geo import parse_iso
from services.pricing import available_vehicle_types, get_dp_percent, get_pricing_rules
from services.ratelimit import allow, client_ip

router = APIRouter(prefix="/api/public/booking", tags=["booking-public"])


def _guard(request: Request, bucket: str, limit: int, window: int = 60):
    if not allow(f"{bucket}:{client_ip(request)}", limit, window):
        raise HTTPException(status_code=429,
                            detail="Terlalu banyak permintaan. Mohon coba lagi sebentar lagi.")


def _400(exc) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


async def _end_iso(db, body, flow):
    """Rentang waktu terpakai: sewa harian dari input tamu, bandara dari durasi rute."""
    start_dt = parse_iso(body.start_datetime)
    if not start_dt:
        raise _400("Format tanggal mulai tidak valid")
    route = None
    if body.service == "airport_transfer":
        try:
            route = await bp.route_or_error(db, getattr(body, "route_id", ""))
        except bp.BookingPublicError as exc:
            raise _400(exc) from None
        end_dt = bp.transfer_window(route, flow, start_dt)
    else:
        end_dt = parse_iso(getattr(body, "end_datetime", "") or "")
        days = getattr(body, "days", None)
        if not end_dt and days:
            from datetime import timedelta
            end_dt = start_dt + timedelta(days=int(days))
        if not end_dt:
            raise _400("Tanggal selesai (atau jumlah hari) wajib diisi")
    if end_dt <= start_dt:
        raise _400("Tanggal selesai harus setelah tanggal mulai")
    return start_dt.isoformat(), end_dt.isoformat(), route


@router.get("/config")
async def booking_config():
    """Semua yang dibutuhkan formulir publik — SELALU dari data, bukan daftar hardcode."""
    db = get_db()
    flow = await bf.get_flow(db)
    routes = await db.transfer_routes.find(
        {"active": {"$ne": False}}, {"_id": 0}).sort([("position", 1), ("name", 1)]).to_list(60)
    types = await available_vehicle_types(db)
    rules = await get_pricing_rules(db)
    payment = dict(flow.get("payment") or {})
    return {
        "services": [bf.SERVICES[s] for s in flow["enabled_services"] if s in bf.SERVICES],
        "mode": flow["mode"],
        "dp_percent": await get_dp_percent(db),
        "hold_hours": flow["hold_hours"],
        "approval_hold_hours": flow["approval_hold_hours"],
        "approval_sla_hours": flow["approval_sla_hours"],
        "min_lead_hours": flow["min_lead_hours"],
        "max_advance_days": flow["max_advance_days"],
        "min_days": flow["min_days"], "max_days": flow["max_days"],
        "vehicle_types": types,
        "routes": [{"id": r.get("id"), "code": r.get("code"), "name": r.get("name"),
                    "from_label": r.get("from_label"), "to_label": r.get("to_label"),
                    "airport_code": r.get("airport_code"),
                    "duration_minutes": r.get("duration_minutes"),
                    "from_price": min([money(v) for v in (r.get("rates") or {}).values()
                                       if money(v) > 0] or [0]),
                    "vehicle_types": [k for k, v in (r.get("rates") or {}).items()
                                      if money(v) > 0]} for r in routes],
        "payment": payment,
        "cancellation_policy": flow.get("cancellation_policy") or "",
        "terms": flow.get("terms") or "",
        "driver_fee_per_day": money(rules.get("driver_fee_per_day")),
        "toll_parking_per_day": money(rules.get("toll_parking_per_day")),
    }


@router.post("/search")
async def booking_search(body: BookingSearchRequest, request: Request):
    """Ketersediaan NYATA + harga per unit. Tidak menulis apa pun ke database."""
    _guard(request, "booking-search", 60)
    db = get_db()
    flow = await bf.get_flow(db)
    if body.service not in flow["enabled_services"]:
        raise _400("Layanan ini sedang tidak dibuka untuk pemesanan online")
    start_iso, end_iso, route = await _end_iso(db, body, flow)
    try:
        bf.validate_window(flow, start_dt=parse_iso(start_iso), end_dt=parse_iso(end_iso),
                          service=body.service)
    except bf.FlowError as exc:
        raise _400(exc) from None
    discount, label, promo_error = 0, "", ""
    result = await bs.search(db, service=body.service, start_iso=start_iso, end_iso=end_iso,
                            pax=body.pax or 0, vehicle_type=(body.vehicle_type or "").strip() or None,
                            route=route)
    if (body.promo_code or "").strip() and result["options"]:
        first = result["options"][0]
        try:
            checked = await promo_svc.validate(
                db, body.promo_code, subtotal=first["quote"]["subtotal"],
                days=first["quote"]["days"], vehicle_type=first["vehicle"]["type"],
                service=body.service, start_dt=parse_iso(start_iso))
            discount, label = checked["discount"], checked["label"]
            result = await bs.search(db, service=body.service, start_iso=start_iso,
                                    end_iso=end_iso, pax=body.pax or 0,
                                    vehicle_type=(body.vehicle_type or "").strip() or None,
                                    route=route, discount=discount, discount_label=label)
        except promo_svc.PromoError as exc:
            promo_error = str(exc)
    return {
        **result,
        "search": {"service": body.service, "start_datetime": start_iso,
                   "end_datetime": end_iso, "pax": body.pax or 1,
                   "route": {"id": (route or {}).get("id"), "name": (route or {}).get("name")}
                   if route else None},
        "promo": {"code": (body.promo_code or "").strip().upper(), "discount": discount,
                  "label": label, "error": promo_error},
    }


@router.post("/quote")
async def booking_quote(body: BookingQuoteRequest, request: Request):
    """Rincian harga final satu unit (dipakai langkah tinjau sebelum memesan)."""
    _guard(request, "booking-quote", 60)
    db = get_db()
    flow = await bf.get_flow(db)
    start_iso, end_iso, route = await _end_iso(db, body, flow)
    rows = await bs.publishable_vehicles(db, vehicle_id=body.vehicle_id)
    if not rows:
        raise HTTPException(status_code=404, detail="Unit tidak tersedia untuk pemesanan online")
    vehicle = rows[0]
    busy = await bs.busy_map(db, start_iso, end_iso)
    try:
        quote, promo = await bp.build_quote(
            db, service=body.service, vehicle=vehicle, route=route, start_iso=start_iso,
            end_iso=end_iso, add_ons=[a.model_dump() for a in (body.add_ons or [])],
            promo_code=body.promo_code, flow=flow)
    except (bp.BookingPublicError, promo_svc.PromoError) as exc:
        raise _400(exc) from None
    return {
        "vehicle": bs.public_vehicle(vehicle, rate=quote.get("day_rate"),
                                    basis=quote.get("rate_basis", "")),
        "quote": quote, "available": vehicle["id"] not in busy,
        "unavailable_reason": busy.get(vehicle["id"], ""),
        "promo": {"code": (promo or {}).get("code", ""), "discount": quote.get("discount", 0)},
        "start_datetime": start_iso, "end_datetime": end_iso,
        "mode": flow["mode"], "hold_hours": flow["hold_hours"],
    }


@router.post("/promos")
async def booking_promos(body: BookingPromoListRequest, request: Request):
    """Daftar promo aktif + kelayakannya untuk pesanan yang sedang disusun.

    Subtotal dihitung ULANG di sini (mesin harga yang sama dengan `/quote`), lalu setiap promo
    dinilai `services/promos.evaluate`. Jadi angka "Hemat Rp X" yang tampil di wizard adalah
    angka yang benar-benar akan dipakai saat memesan — bukan taksiran frontend.
    """
    _guard(request, "booking-promos", 60)
    db = get_db()
    flow = await bf.get_flow(db)
    start_iso, end_iso, route = await _end_iso(db, body, flow)
    rows = await bs.publishable_vehicles(db, vehicle_id=body.vehicle_id)
    if not rows:
        raise HTTPException(status_code=404, detail="Unit tidak tersedia untuk pemesanan online")
    vehicle = rows[0]
    base = await bs.quote_for_vehicle(db, vehicle, start_iso=start_iso, end_iso=end_iso,
                                      service=body.service, route=route, add_ons=[])
    if not base:
        raise _400("Unit ini tidak melayani rute yang dipilih")
    days = base["days"] if body.service != "airport_transfer" else bp.span_days(start_iso, end_iso)
    promos = await promo_svc.list_for_context(
        db, subtotal=base["subtotal"], days=days, vehicle_type=vehicle.get("type"),
        service=body.service, start_dt=parse_iso(start_iso))
    return {"promos": promos, "total": len(promos),
            "eligible_count": sum(1 for p in promos if p.get("eligible"))}


@router.post("/submit")
async def booking_submit(body: PublicBookingSubmit, request: Request):
    """Buat pesanan sungguhan: unit nyata + harga server + reservasi/persetujuan.

    Batas laju 60/menit per IP DENGAN SENGAJA longgar: pengunjung seluler Indonesia berbagi
    satu IP publik lewat CGNAT operator, jadi ambang ketat akan menolak pemesan SAH yang
    berbeda orang — kehilangan penjualan nyata (pelajaran sama seperti form lead halaman
    iklan). Pengaman utama di sini bukan IP, melainkan honeypot + idempotency-key + mutex
    armada (satu unit tidak mungkin ganda) + verifikasi DP sebelum pesanan berlaku.
    """
    _guard(request, "booking-submit", 60)
    if (body.hp or "").strip():  # bot → balas sukses palsu tanpa menulis DB
        return {"status": "received", "code": "", "token": "", "duplicate": False,
                "message": "Permintaan diterima."}
    db = get_db()
    payload = body.model_dump()
    payload["add_ons"] = [a.model_dump() if hasattr(a, "model_dump") else a
                          for a in (body.add_ons or [])]
    try:
        result = await bp.create_booking(db, payload, ip=client_ip(request))
    except (bp.BookingPublicError, promo_svc.PromoError, bf.FlowError) as exc:
        raise _400(exc) from None
    return {"status": "received", **result}


@router.post("/lookup")
async def booking_lookup(body: BookingLookupRequest, request: Request):
    """Tanpa akun: kode booking + nomor WhatsApp → tautan status ber-token."""
    _guard(request, "booking-lookup", 12)
    db = get_db()
    booking = await bp.find_by_code_phone(db, body.code, body.phone)
    if not booking:
        raise HTTPException(status_code=404,
                            detail="Pesanan tidak ditemukan. Periksa kode booking & nomor WhatsApp.")
    token = await bp.ensure_token(db, booking)
    return {"code": booking.get("code"), "token": token,
            "status": await bp.status_payload(db, booking)}


@router.get("/{code}")
async def booking_status(code: str, token: str = Query(default="")):
    """Halaman status pesanan (tautan ber-token — tanpa login)."""
    db = get_db()
    booking = await db.bookings.find_one({"code": str(code or "").strip().upper()}, {"_id": 0})
    if not booking or not str(token or "").strip() or \
            str(token).strip() != str(booking.get("public_token") or ""):
        raise HTTPException(status_code=404, detail="Tautan status pesanan tidak valid")
    payload = await bp.status_payload(db, booking)
    payload["countdown_seconds"] = await bp.hold_countdown_seconds(booking)
    return payload


@router.post("/{code}/proof")
async def booking_proof(code: str, request: Request, token: str = Form(default=""),
                        amount: float = Form(default=0), sender_name: str = Form(default=""),
                        bank: str = Form(default=""), note: str = Form(default=""),
                        image: UploadFile = File(...)):
    """Unggah bukti transfer DP (foto). Masuk Media Library + antrean verifikasi ops."""
    _guard(request, "booking-proof", 10)
    db = get_db()
    booking = await db.bookings.find_one({"code": str(code or "").strip().upper()}, {"_id": 0})
    if not booking or str(token or "").strip() != str(booking.get("public_token") or ""):
        raise HTTPException(status_code=404, detail="Tautan status pesanan tidak valid")
    if booking.get("status") == "cancelled":
        raise _400("Pesanan sudah dibatalkan — bukti pembayaran tidak bisa diunggah")
    data = await image.read()
    try:
        proof = await bp.attach_proof(
            db, booking, data=data, content_type=image.content_type or "",
            filename=image.filename or "bukti-bayar", amount_claimed=amount,
            sender_name=sender_name, bank=bank, note=note)
    except bp.BookingPublicError as exc:
        raise _400(exc) from None
    fresh = await db.bookings.find_one({"id": booking["id"]}, {"_id": 0})
    return {"uploaded": True, "proof": proof, "status": await bp.status_payload(db, fresh)}


@router.post("/{code}/cancel")
async def booking_cancel(code: str, body: BookingCancelRequest, request: Request):
    _guard(request, "booking-cancel", 10)
    db = get_db()
    booking = await db.bookings.find_one({"code": str(code or "").strip().upper()}, {"_id": 0})
    if not booking or str(body.token or "").strip() != str(booking.get("public_token") or ""):
        raise HTTPException(status_code=404, detail="Tautan status pesanan tidak valid")
    try:
        res = await bp.cancel_public(db, booking, body.reason)
    except bp.BookingPublicError as exc:
        raise _400(exc) from None
    fresh = await db.bookings.find_one({"id": booking["id"]}, {"_id": 0})
    return {**res, "status": await bp.status_payload(db, safe_doc(fresh))}
