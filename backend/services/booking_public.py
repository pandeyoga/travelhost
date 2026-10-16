"""services/booking_public.py — PEMESANAN ONLINE dari situs publik (satu jalur untuk semua).

Sebelum modul ini, `POST /api/public/booking` menulis booking KOSONG:
`vehicle_id=None, base_price=0, total_amount=0, status='pending'`, tanpa memeriksa
ketersediaan sama sekali. Tamu "memesan" tanggal yang armadanya sudah penuh, lalu ops
menolak manual lewat WhatsApp — pengalaman yang tidak layak disebut pemesanan.

Sekarang SEMUA pembuatan booking dari publik lewat satu fungsi `create_booking()` supaya
tidak muncul lagi "dua dunia" (pelajaran dari penyatuan Media Library):

  service='daily_rental'      → unit dipilih tamu, harga dihitung server (hari × tarif),
                                ketersediaan divalidasi ULANG di dalam mutex armada.
  service='airport_transfer'  → tarif FLAT per rute per tipe unit (koleksi transfer_routes).
  service='request_only'      → jalur lama (paket/lepas kunci/kebutuhan khusus): tanpa unit,
                                harga ditetapkan ops saat menyetujui.

Prinsip yang dijaga:
* Harga SELALU dihitung ulang di server. Klien tidak pernah mengirim total — kalau dikirim,
  diabaikan (dijaga guardrail INV-BOOK-02).
* Ketersediaan diperiksa DUA KALI: saat pencarian (untuk UI) dan lagi di dalam
  `vehicle_lock` sesaat sebelum menulis (satu-satunya cek yang otoritatif).
* Idempoten: `idempotency_key` + unique index → klik ganda/retry jaringan tidak membuat
  dua booking untuk satu pesanan.
* Tanpa akun: pelanggan memakai kode booking + nomor WhatsApp (atau tautan ber-token).
"""
from datetime import datetime, timedelta, timezone

from core_utils import money, new_id, now_iso, safe_doc
from pymongo.errors import DuplicateKeyError

from services import booking_flow as bf
from services import booking_search as bs
from services import promos as promo_svc
from services.availability import (
    find_conflicts,
    find_maintenance_conflicts,
    vehicle_lock,
)
from services.counters import next_booking_code
from services.events import emit
from services.geo import parse_iso
from services.identity import ensure_customer, normalize_phone
from services.pricing import get_dp_percent, span_days
from services.refs import (
    destination_normalize,
    origin_normalize,
    vehicle_type_normalize,
)

MAX_ADD_ONS = 6
PROOF_MAX_BYTES = 5 * 1024 * 1024
PROOF_FOLDER_NAME = "Bukti Pembayaran"


class BookingPublicError(ValueError):
    """Permintaan pemesanan publik ditolak → 4xx berALASAN (bukan 5xx)."""


async def ensure_indexes(db):
    await db.bookings.create_index("public_token", unique=True, sparse=True)
    await db.bookings.create_index(
        "public_idempotency_key", unique=True,
        partialFilterExpression={"public_idempotency_key": {"$type": "string"}})
    await db.bookings.create_index([("source", 1), ("status", 1), ("created_at", -1)])
    await db.payment_proofs.create_index([("status", 1), ("created_at", -1)])
    await db.payment_proofs.create_index("booking_id")
    await db.transfer_routes.create_index("code", unique=True, sparse=True)
    await db.transfer_routes.create_index([("active", 1), ("position", 1)])


# ------------------------------------------------------------------ helper rute & add-on
async def route_or_error(db, route_id):
    doc = await db.transfer_routes.find_one({"id": str(route_id or "").strip()}, {"_id": 0})
    if not doc:
        raise BookingPublicError("Rute antar-jemput tidak ditemukan")
    if doc.get("active") is False:
        raise BookingPublicError("Rute antar-jemput sedang tidak dilayani")
    return doc


def clean_add_ons(items) -> list:
    out = []
    for raw in (items or [])[:MAX_ADD_ONS]:
        if not isinstance(raw, dict):
            continue
        amount = money(raw.get("amount"))
        label = str(raw.get("label") or "").strip()[:80]
        if amount < 0:
            raise BookingPublicError("Nominal layanan tambahan tidak boleh negatif")
        if label and amount >= 0:
            out.append({"label": label, "amount": amount})
    return out


def transfer_window(route, flow, start_dt):
    """Rentang unit terpakai untuk antar-jemput bandara = durasi rute + jeda kembali."""
    minutes = int(money(route.get("duration_minutes")) or 180)
    buffer_min = int(money(flow.get("transfer_buffer_minutes")) or 0)
    return start_dt + timedelta(minutes=max(minutes, 30) + max(buffer_min, 0))


# ------------------------------------------------------------------ harga (server-side)
async def build_quote(db, *, service, vehicle, route, start_iso, end_iso, add_ons,
                     promo_code="", flow=None):
    """Hitung harga + validasi promo. Return (quote, promo_doc|None)."""
    add_ons = clean_add_ons(add_ons)
    base = await bs.quote_for_vehicle(db, vehicle, start_iso=start_iso, end_iso=end_iso,
                                     service=service, route=route, add_ons=add_ons)
    if not base:
        raise BookingPublicError("Unit ini tidak melayani rute yang dipilih")
    promo_doc, discount, label = None, 0, ""
    if str(promo_code or "").strip():
        result = await promo_svc.validate(
            db, promo_code, subtotal=base["subtotal"],
            days=base["days"] if service != "airport_transfer" else span_days(start_iso, end_iso),
            vehicle_type=vehicle.get("type"), service=service, start_dt=parse_iso(start_iso))
        promo_doc, discount, label = result["promo"], result["discount"], result["label"]
        base = await bs.quote_for_vehicle(
            db, vehicle, start_iso=start_iso, end_iso=end_iso, service=service, route=route,
            add_ons=add_ons, discount=discount, discount_label=label)
    return base, promo_doc


# ------------------------------------------------------------------ pembuatan booking
async def create_booking(db, payload: dict, *, ip: str = "") -> dict:
    flow = await bf.get_flow(db)
    service = str(payload.get("service") or bf.SERVICE_REQUEST_ONLY).strip()
    if service != bf.SERVICE_REQUEST_ONLY and service not in flow["enabled_services"]:
        raise BookingPublicError("Layanan ini sedang tidak dibuka untuk pemesanan online")

    idem = str(payload.get("idempotency_key") or "").strip()[:64]
    if idem:
        prior = await db.bookings.find_one({"public_idempotency_key": idem}, {"_id": 0})
        if prior:
            return {**created_payload(prior, flow), "duplicate": True}

    name = str(payload.get("name") or "").strip()[:120]
    phone = str(payload.get("phone") or "").strip()[:24]
    if len(name) < 2:
        raise BookingPublicError("Nama pemesan wajib diisi (minimal 2 huruf)")
    if len(normalize_phone(phone)) < 9:
        raise BookingPublicError("Nomor WhatsApp tidak valid")

    start_dt = parse_iso(payload.get("start_datetime"))
    if not start_dt:
        raise BookingPublicError("Format tanggal mulai tidak valid")
    route = None
    if service == "airport_transfer":
        route = await route_or_error(db, payload.get("route_id"))
        end_dt = transfer_window(route, flow, start_dt)
    else:
        end_dt = parse_iso(payload.get("end_datetime"))
        if not end_dt:
            raise BookingPublicError("Format tanggal selesai tidak valid")
    if end_dt <= start_dt:
        raise BookingPublicError("Tanggal selesai harus setelah tanggal mulai")
    if service != bf.SERVICE_REQUEST_ONLY:
        # Jalur lama (request_only) sengaja tidak dikenai pagar jendela waktu agar formulir
        # "minta penawaran" yang sudah tayang tidak tiba-tiba menolak pengunjung.
        try:
            bf.validate_window(flow, start_dt=start_dt, end_dt=end_dt, service=service)
        except bf.FlowError as exc:
            raise BookingPublicError(str(exc)) from None
    start_iso, end_iso = start_dt.isoformat(), end_dt.isoformat()

    vehicle, quote, promo_doc = None, None, None
    if service != bf.SERVICE_REQUEST_ONLY:
        vid = str(payload.get("vehicle_id") or "").strip()
        if not vid:
            raise BookingPublicError("Pilih unit armada terlebih dahulu")
        rows = await bs.publishable_vehicles(db, vehicle_id=vid)
        vehicle = rows[0] if rows else None
        if not vehicle:
            raise BookingPublicError("Unit tidak tersedia untuk pemesanan online")
        pax = int(money(payload.get("pax")) or 1)
        if pax > int(vehicle.get("capacity") or 0) > 0:
            raise BookingPublicError(
                f"Kapasitas {vehicle.get('name')} hanya {vehicle.get('capacity')} orang")
        quote, promo_doc = await build_quote(
            db, service=service, vehicle=vehicle, route=route, start_iso=start_iso,
            end_iso=end_iso, add_ons=payload.get("add_ons"), promo_code=payload.get("promo_code"),
            flow=flow)

    customer, _created = await ensure_customer(
        db, name=name, phone=phone, email=str(payload.get("email") or "")[:160],
        notes="Dibuat dari pemesanan online (situs publik)")

    total = money((quote or {}).get("total"))
    dp_percent = int((quote or {}).get("dp_percent") or await get_dp_percent(db))
    status, hold_extra = "pending", {}
    if service != bf.SERVICE_REQUEST_ONLY and flow["mode"] == "hold_dp":
        status = "hold"
        hold_extra = bf.hold_fields(total=total, dp_percent=dp_percent,
                                   hold_hours=flow["hold_hours"])
    elif service != bf.SERVICE_REQUEST_ONLY:
        hold_extra = {"dp_percent": float(dp_percent),
                      "dp_amount": money(total * dp_percent / 100.0)}

    token = bf.new_public_token()
    doc = {
        "id": new_id("bk"), "code": await next_booking_code(db),
        "customer_id": customer["id"],
        "vehicle_id": (vehicle or {}).get("id"), "driver_id": None,
        "origin": await origin_normalize(db, str(payload.get("origin") or (route or {}).get("from_label") or "")[:160]),
        "destination": await destination_normalize(db, str(payload.get("destination") or (route or {}).get("to_label") or "")[:160]),
        "start_datetime": start_iso, "end_datetime": end_iso,
        "base_price": total, "add_ons": [], "total_amount": total, "paid_amount": 0,
        "payment_status": "belum_bayar", "status": status,
        "customer_name": customer.get("name"),
        "vehicle_name": (vehicle or {}).get("name"), "driver_name": None,
        "requested_vehicle_type": (vehicle or {}).get("type") or vehicle_type_normalize(
            str(payload.get("vehicle_type") or "")[:40]),
        "pax": int(money(payload.get("pax")) or 1),
        "service": service, "service_label": bf.service_meta(service)["label"],
        "route_id": (route or {}).get("id"), "route_name": (route or {}).get("name"),
        "price_breakdown": (quote or {}).get("breakdown") or [],
        "promo_code": (promo_doc or {}).get("code") or "",
        "promo_discount": money((quote or {}).get("discount")),
        "promo_id": (promo_doc or {}).get("id") or "",
        "pickup_address": str(payload.get("pickup_address") or "")[:240],
        "contact_phone": phone, "contact_email": str(payload.get("email") or "")[:160],
        "source": "web_booking" if service != bf.SERVICE_REQUEST_ONLY else "public",
        "public_token": token,
        "public_idempotency_key": idem or None,
        "notes": str(payload.get("message") or "")[:1000],
        "created_at": now_iso(), "created_ip": str(ip or "")[:64],
        **hold_extra,
    }
    if not idem:
        doc.pop("public_idempotency_key", None)
    # CMS-08: jejak konten terakhir (artikel/destinasi/paket) yang dibaca sebelum memesan —
    # dipakai laporan "konten → lead → pesanan → omzet" di Konten Web.
    try:
        from services.attribution import content_ref as _content_ref
        ref = _content_ref(payload.get("attribution"))
        if ref:
            doc["content_ref"] = ref
    except Exception:  # noqa: BLE001 — atribusi tak boleh menggagalkan pemesanan
        pass

    consumed = False
    try:
        if promo_doc:
            consumed = await promo_svc.consume(db, promo_doc)
            if not consumed:
                raise BookingPublicError("Kuota kode promo baru saja habis. Coba tanpa kode promo.")
        if doc["vehicle_id"] and status == "hold":
            # Satu-satunya cek ketersediaan yang OTORITATIF: di dalam mutex per armada,
            # tepat sebelum menulis (RC-16). Tanpa ini, dua pemesan paralel bisa sama-sama
            # lolos cek lalu sama-sama menahan unit yang sama.
            async with vehicle_lock(db, doc["vehicle_id"]):
                await assert_free(db, doc["vehicle_id"], start_iso, end_iso)
                await db.bookings.insert_one(dict(doc))
        else:
            if doc["vehicle_id"]:
                await assert_free(db, doc["vehicle_id"], start_iso, end_iso)
            await db.bookings.insert_one(dict(doc))
    except DuplicateKeyError:
        if consumed and promo_doc:
            await promo_svc.release(db, promo_doc.get("id"))
        prior = await db.bookings.find_one({"public_idempotency_key": idem}, {"_id": 0}) if idem else None
        if prior:
            return {**created_payload(prior, flow), "duplicate": True}
        raise BookingPublicError("Pesanan gagal disimpan, silakan coba lagi") from None
    except Exception:
        if consumed and promo_doc:
            await promo_svc.release(db, promo_doc.get("id"))
        raise

    await emit(db, "booking.requested", {
        "booking_id": doc["id"], "code": doc["code"], "customer_id": customer["id"],
        "customer_name": doc["customer_name"], "phone": phone,
        "destination": doc["destination"], "origin": doc["origin"],
        "start_datetime": start_iso[:16].replace("T", " "), "pax": doc["pax"],
        "service": service, "status": status, "total_amount": float(total),
        "dp_amount": float(money(doc.get("dp_amount"))),
        "hold_expires_at": doc.get("hold_expires_at"),
        "vehicle_name": doc.get("vehicle_name"),
        "channel": ((payload.get("attribution") or {}).get("channel") or "website"),
    }, source="public", ref_type="booking", ref_id=doc["id"],
        dedupe_key=f"booking.requested:{doc['id']}")
    return created_payload(doc, flow)


async def assert_free(db, vehicle_id, start_iso, end_iso):
    conflicts = await find_conflicts(db, vehicle_id, start_iso, end_iso)
    if conflicts:
        raise BookingPublicError(
            "Unit ini baru saja dipesan orang lain untuk tanggal tersebut. "
            "Silakan pilih unit atau tanggal lain.")
    maint = await find_maintenance_conflicts(db, vehicle_id, start_iso, end_iso)
    if maint:
        raise BookingPublicError("Unit ini masuk jadwal perawatan pada tanggal tersebut")


def created_payload(doc: dict, flow: dict) -> dict:
    return {
        "id": doc.get("id"), "code": doc.get("code"), "status": doc.get("status"),
        "token": doc.get("public_token") or "",
        "total_amount": money(doc.get("total_amount")),
        "dp_amount": money(doc.get("dp_amount")),
        "dp_percent": int(money(doc.get("dp_percent"))),
        "hold_expires_at": doc.get("hold_expires_at"),
        "mode": flow.get("mode"), "service": doc.get("service"),
        "duplicate": False,
        "message": status_message(doc, flow),
    }


def status_message(doc: dict, flow: dict) -> str:
    status = doc.get("status")
    if status == "hold":
        return ("Unit Anda sudah kami tahan. Selesaikan pembayaran DP sebelum batas waktu, "
                "lalu unggah bukti transfer pada halaman ini.")
    if status == "pending":
        sla = int(money(flow.get("approval_sla_hours")) or 6)
        return (f"Permintaan diterima. Tim kami memeriksa ketersediaan & mengonfirmasi "
                f"maksimal {sla} jam kerja — unit belum dikunci sampai disetujui.")
    if status == "confirmed":
        return "Pesanan Anda sudah dikonfirmasi. Terima kasih!"
    if status == "cancelled":
        return "Pesanan ini sudah dibatalkan."
    return ""


# ------------------------------------------------------------------ status & bukti bayar
async def status_payload(db, booking: dict, flow: dict = None) -> dict:
    flow = flow or await bf.get_flow(db)
    proofs = await db.payment_proofs.find(
        {"booking_id": booking["id"]}, {"_id": 0}).sort("created_at", -1).to_list(20)
    payments = await db.payments.find(
        {"booking_id": booking["id"]}, {"_id": 0, "amount": 1, "type": 1, "paid_at": 1},
    ).sort("paid_at", 1).to_list(50)
    total = money(booking.get("total_amount"))
    paid = money(booking.get("paid_amount"))
    dp_amount = money(booking.get("dp_amount")) or money(
        total * money(booking.get("dp_percent")) / 100.0)
    return {
        "code": booking.get("code"), "status": booking.get("status"),
        "payment_status": booking.get("payment_status"),
        "service": booking.get("service") or bf.SERVICE_REQUEST_ONLY,
        "service_label": booking.get("service_label") or bf.service_meta(
            booking.get("service"))["label"],
        "customer_name": booking.get("customer_name"),
        "vehicle_name": booking.get("vehicle_name"),
        "route_name": booking.get("route_name"),
        "origin": booking.get("origin"), "destination": booking.get("destination"),
        "pickup_address": booking.get("pickup_address"),
        "start_datetime": booking.get("start_datetime"),
        "end_datetime": booking.get("end_datetime"),
        "pax": booking.get("pax"), "days": span_days(booking.get("start_datetime"),
                                                     booking.get("end_datetime")),
        "price_breakdown": booking.get("price_breakdown") or [],
        "promo_code": booking.get("promo_code") or "",
        "total_amount": total, "paid_amount": paid,
        "outstanding": max(total - paid, 0),
        "dp_amount": dp_amount, "dp_percent": int(money(booking.get("dp_percent"))),
        "dp_met": bool(dp_amount and paid >= dp_amount),
        "hold_expires_at": booking.get("hold_expires_at"),
        "message": status_message(booking, flow),
        "payment": flow.get("payment"),
        "cancellation_policy": flow.get("cancellation_policy"),
        "mode": flow.get("mode"),
        "can_upload_proof": booking.get("status") in ("hold", "pending", "confirmed")
        and paid < total,
        "can_cancel": booking.get("status") in ("hold", "pending"),
        "payments": safe_doc(payments),
        "proofs": [{"id": p.get("id"), "status": p.get("status"),
                    "amount_claimed": money(p.get("amount_claimed")),
                    "media_url": p.get("media_url"), "created_at": p.get("created_at"),
                    "reject_reason": p.get("reject_reason") or ""} for p in proofs],
    }


async def _proof_folder_id(db) -> str:
    from services import media_lib as ml
    doc = await db[ml.FOLDERS].find_one({"name": PROOF_FOLDER_NAME, "parent_id": ml.ROOT},
                                        {"_id": 0, "id": 1})
    if doc:
        return doc["id"]
    created = await ml.create_folder(db, PROOF_FOLDER_NAME, ml.ROOT,
                                    {"email": "sistem"})
    return created["id"]


async def attach_proof(db, booking: dict, *, data: bytes, content_type: str, filename: str,
                      amount_claimed=0, sender_name="", bank="", note="") -> dict:
    """Simpan bukti transfer sebagai aset Media Library + catat di `payment_proofs`.

    Bukti bayar sengaja masuk Media Library yang SAMA dengan aset lain (bukan folder liar):
    ops sudah punya alat untuk melihat/mengunduh/menghapusnya, dan tidak ada lagi berkas
    tanpa catatan Mongo — kesalahan yang sudah kita berantas di Fase 2 penyatuan media.
    """
    from services import media_lib as ml
    from services import media_store as ms
    if not data:
        raise BookingPublicError("Berkas bukti pembayaran kosong")
    if len(data) > PROOF_MAX_BYTES:
        raise BookingPublicError(
            f"Ukuran bukti maksimal {PROOF_MAX_BYTES // (1024 * 1024)} MB")
    kind, _ext, _limit = ms.classify(content_type)
    if kind != "image":
        raise BookingPublicError("Bukti pembayaran harus berupa foto/tangkapan layar "
                                "(jpg/png/webp). Berkas PDF belum didukung.")
    if money(amount_claimed) < 0:
        raise BookingPublicError("Nominal transfer tidak boleh negatif")
    try:
        meta = ms.upload_bytes(data, content_type, filename=filename or "bukti-bayar",
                              folder="bukti-bayar")
    except ms.MediaError as exc:
        raise BookingPublicError(str(exc)) from None
    asset = await ml.register_asset(
        db, meta, {"email": f"publik:{booking.get('code')}"},
        folder_id=await _proof_folder_id(db), alt=f"Bukti pembayaran {booking.get('code')}",
        source="payment_proof", extra={"booking_id": booking["id"]})
    doc = {
        "id": new_id("ppf"), "booking_id": booking["id"], "booking_code": booking.get("code"),
        "customer_name": booking.get("customer_name"),
        "media_id": asset["id"], "media_url": ml.media_url(asset["id"], asset.get("version", 1)),
        "amount_claimed": money(amount_claimed) or money(booking.get("dp_amount")),
        "sender_name": str(sender_name or "")[:120], "bank": str(bank or "")[:60],
        "note": str(note or "")[:400], "status": "pending",
        "verified_by": "", "verified_at": None, "reject_reason": "",
        "created_at": now_iso(),
    }
    await db.payment_proofs.insert_one(dict(doc))
    await db.bookings.update_one({"id": booking["id"]},
                                {"$set": {"proof_status": "pending",
                                          "proof_uploaded_at": now_iso()}})
    await emit(db, "booking.payment_proof_uploaded", {
        "booking_id": booking["id"], "code": booking.get("code"),
        "customer_name": booking.get("customer_name"),
        "amount": float(doc["amount_claimed"]), "proof_id": doc["id"],
    }, source="public", ref_type="booking", ref_id=booking["id"],
        dedupe_key=f"booking.proof:{doc['id']}")
    return safe_doc(doc)


async def cancel_public(db, booking: dict, reason: str = "") -> dict:
    """Pembatalan oleh pelanggan — hanya selama belum dikonfirmasi (hold/pending)."""
    if booking.get("status") not in ("hold", "pending"):
        raise BookingPublicError("Pesanan ini tidak bisa dibatalkan sendiri. "
                                "Hubungi kami via WhatsApp untuk bantuan.")
    res = await db.bookings.find_one_and_update(
        {"id": booking["id"], "status": {"$in": ["hold", "pending"]}},
        {"$set": {"status": "cancelled", "cancelled_at": now_iso(),
                  "cancel_reason": str(reason or "Dibatalkan pelanggan")[:240],
                  "cancelled_by": "pelanggan"}})
    if not res:
        raise BookingPublicError("Pesanan sudah berubah status. Muat ulang halaman ini.")
    if booking.get("promo_id"):
        await promo_svc.release(db, booking.get("promo_id"))
    await emit(db, "booking.cancelled", {
        "booking_id": booking["id"], "code": booking.get("code"),
        "customer_name": booking.get("customer_name"), "by": "pelanggan",
    }, source="public", ref_type="booking", ref_id=booking["id"],
        dedupe_key=f"booking.cancelled:{booking['id']}")
    return {"cancelled": True, "code": booking.get("code")}


async def find_by_code_phone(db, code: str, phone: str):
    """Cari pesanan tanpa akun: kode booking + nomor WhatsApp harus cocok."""
    clean_code = str(code or "").strip().upper()[:20]
    if not clean_code:
        return None
    booking = await db.bookings.find_one({"code": clean_code}, {"_id": 0})
    if not booking:
        return None
    norm = normalize_phone(phone)
    if not norm:
        return None
    candidates = {normalize_phone(booking.get("contact_phone"))}
    customer = await db.customers.find_one({"id": booking.get("customer_id")},
                                          {"_id": 0, "phone": 1, "phone_normalized": 1})
    if customer:
        candidates.add(normalize_phone(customer.get("phone")))
        candidates.add(str(customer.get("phone_normalized") or ""))
    return booking if norm in {c for c in candidates if c} else None


async def ensure_token(db, booking: dict) -> str:
    """Booking lama (dibuat sebelum fitur ini) belum punya token — buatkan sekali."""
    token = booking.get("public_token")
    if token:
        return token
    token = bf.new_public_token()
    await db.bookings.update_one({"id": booking["id"]}, {"$set": {"public_token": token}})
    return token


async def hold_countdown_seconds(booking: dict) -> int:
    exp = parse_iso(booking.get("hold_expires_at"))
    if not exp:
        return 0
    return max(int((exp - datetime.now(timezone.utc)).total_seconds()), 0)
