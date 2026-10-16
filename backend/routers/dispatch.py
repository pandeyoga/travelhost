"""routers/dispatch.py — E3 Dispatch & Komunikasi Operasi.

Ops Cockpit "Hari Ini" + Assign & Jadwalkan Trip (driver+unit+geocode tujuan -> perbaiki G1)
+ konfirmasi keberangkatan (WA) + status driver->customer (enroute/arrived, WA) + POD lokal.
Section RBAC 'dispatch' (owner/ops_admin). WA dipancarkan via Event Bus E1 (provider MOCK).

Kontrak rute (semua /api):
  GET  /dispatch/today?date=YYYY-MM-DD         -> {date, summary, departures[]}
  POST /dispatch/{booking_id}/assign           <- {driver_id, vehicle_id} -> trip standby + geocode + trip.assigned
  POST /dispatch/{booking_id}/confirm-departure -> booking.departure_confirmed (WA)
  POST /dispatch/trips/{trip_id}/enroute        -> trip to_pickup + trip.enroute (WA)
  POST /dispatch/trips/{trip_id}/arrived        -> trip arrived_at + trip.arrived (WA)
  POST /dispatch/trips/{trip_id}/pod            <- multipart(photo,recipient_name,note) -> trip.pod (lokal)
Urutan rute: literal/sub-path sebelum /{id} berparameter.
"""
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile

from core_utils import money, new_id, now_iso, safe_doc
from db import get_db
from dependencies import require_section
from schemas import AssignTripRequest
from services import availability
from services.audit import record
from services.events import emit
from services.geocode import geocode
from services.maps import route_eta

router = APIRouter(prefix="/api", tags=["dispatch"])
DISPATCH = require_section("dispatch")

UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", str(Path(__file__).resolve().parent.parent / "uploads")))
POD_DIR = UPLOAD_DIR / "pod"
POD_DIR.mkdir(parents=True, exist_ok=True)
ALLOWED_IMG = {"image/jpeg": ".jpg", "image/jpg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
MAX_POD_BYTES = 6 * 1024 * 1024  # 6 MB


def _day_range(date_str=None):
    if date_str:
        try:
            d = datetime.fromisoformat(date_str).date()
        except Exception:
            raise HTTPException(status_code=400, detail="Format tanggal tidak valid (YYYY-MM-DD)")
    else:
        d = datetime.now(timezone.utc).date()
    start = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
    return d.isoformat(), start.isoformat(), (start + timedelta(days=1)).isoformat()


async def _customer_phone(db, booking):
    # SSOT dipindah ke services.wa_payload (dipakai bersama dispatch & driver).
    from services.wa_payload import customer_phone
    return await customer_phone(db, booking)


async def _wa_payload(db, booking, trip=None):
    from services.wa_payload import build_wa_payload
    return await build_wa_payload(db, booking, trip)


async def _trip_for(db, booking_id):
    return await db.trips.find_one({"booking_id": booking_id}, {"_id": 0})


def _fee_days(bk):
    """Jumlah hari keberangkatan (pembulatan ke atas, min 1) utk fee driver per hari."""
    try:
        s = datetime.fromisoformat(str(bk.get("start_datetime")).replace("Z", "+00:00"))
        e = datetime.fromisoformat(str(bk.get("end_datetime")).replace("Z", "+00:00"))
        secs = (e - s).total_seconds()
        return max(1, int(-(-secs // 86400)))
    except Exception:  # noqa: BLE001
        return 1


async def _enrich(db, bk):
    trip = await _trip_for(db, bk["id"])
    drv = None
    if bk.get("driver_id"):
        drv = await db.drivers.find_one({"id": bk["driver_id"]}, {"_id": 0, "name": 1, "phone": 1})
    return {
        "id": bk["id"], "code": bk.get("code"), "customer_id": bk.get("customer_id"),
        "customer_name": bk.get("customer_name"), "origin": bk.get("origin"),
        "destination": bk.get("destination"), "start_datetime": bk.get("start_datetime"),
        "end_datetime": bk.get("end_datetime"), "status": bk.get("status"),
        "payment_status": bk.get("payment_status"),
        "vehicle_id": bk.get("vehicle_id"), "vehicle_name": bk.get("vehicle_name"),
        "driver_id": bk.get("driver_id"), "driver_name": bk.get("driver_name"),
        "driver_phone": (drv or {}).get("phone"),
        "assigned": bool(bk.get("driver_id") and bk.get("vehicle_id")),
        "departure_confirmed": bool(bk.get("departure_confirmed_at")),
        "trip_id": (trip or {}).get("id"), "trip_status": (trip or {}).get("status"),
        "dest_geocoded": (trip or {}).get("dest_lat") is not None,
        "pod": bool((trip or {}).get("pod")),
    }


@router.get("/dispatch/today")
async def dispatch_today(date: str = Query(default=None), user=Depends(DISPATCH)):
    db = get_db()
    d, start, end = _day_range(date)
    q = {"start_datetime": {"$gte": start, "$lt": end}, "status": {"$nin": ["cancelled"]}}
    docs = await db.bookings.find(q, {"_id": 0}).sort("start_datetime", 1).to_list(500)
    rows = [await _enrich(db, b) for b in docs]
    summary = {
        "date": d, "total": len(rows),
        "to_assign": sum(1 for r in rows if not r["assigned"]),
        "to_confirm": sum(1 for r in rows if r["assigned"] and not r["departure_confirmed"]),
        "ongoing": sum(1 for r in rows if r["status"] == "ongoing"),
        "completed": sum(1 for r in rows if r["status"] == "completed"),
    }
    return {"date": d, "summary": summary, "departures": safe_doc(rows)}


@router.get("/dispatch/{booking_id}/detail")
async def dispatch_detail(booking_id: str, user=Depends(DISPATCH)):
    """Detail satu keberangkatan utk papan operasi: booking + trip + kontak + timeline
    kronologis (sinkron dgn aksi driver — kedua sisi menulis dokumen trip yang SAMA)."""
    db = get_db()
    bk = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
    if not bk:
        raise HTTPException(status_code=404, detail="Booking tidak ditemukan")
    trip = await _trip_for(db, booking_id) or {}
    drv = None
    if bk.get("driver_id"):
        drv = await db.drivers.find_one({"id": bk["driver_id"]}, {"_id": 0, "name": 1, "phone": 1, "status": 1})
    cust = None
    if bk.get("customer_id"):
        cust = await db.customers.find_one({"id": bk["customer_id"]}, {"_id": 0, "name": 1, "phone": 1})
    pairs = [
        ("Booking dibuat", bk.get("created_at"), "system"),
        ("Driver & unit di-assign", trip.get("assigned_at"), "ops"),
        ("Keberangkatan dikonfirmasi (WA ke pelanggan)", bk.get("departure_confirmed_at"), "ops"),
        ("Driver mengonfirmasi tugas", trip.get("driver_ack_at"), "driver"),
        ("Berangkat menjemput", trip.get("enroute_at") or trip.get("start_at"), "driver"),
        ("Tiba di tujuan", trip.get("arrived_at"), "driver"),
        ("Trip selesai", trip.get("end_at"), "driver"),
        ("Bukti layanan (POD) diunggah", (trip.get("pod") or {}).get("at"), "driver"),
    ]
    timeline = [{"label": lbl, "at": at, "actor": act} for lbl, at, act in pairs if at]
    timeline.sort(key=lambda x: x["at"])
    return {"booking": safe_doc(bk), "trip": safe_doc(trip or None),
            "driver": safe_doc(drv), "customer": safe_doc(cust), "timeline": timeline}


@router.post("/dispatch/{booking_id}/assign")
async def assign_trip(booking_id: str, body: AssignTripRequest, user=Depends(DISPATCH)):
    db = get_db()
    bk = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
    if not bk:
        raise HTTPException(status_code=404, detail="Booking tidak ditemukan")
    if bk.get("status") in ("cancelled", "completed"):
        raise HTTPException(status_code=400, detail="Booking sudah selesai/dibatalkan, tidak bisa di-assign")
    drv = await db.drivers.find_one({"id": body.driver_id}, {"_id": 0})
    if not drv:
        raise HTTPException(status_code=404, detail="Driver tidak ditemukan")
    veh = await db.vehicles.find_one({"id": body.vehicle_id}, {"_id": 0})
    if not veh:
        raise HTTPException(status_code=404, detail="Armada tidak ditemukan")
    prev_vehicle_id = bk.get("vehicle_id")  # utk bebaskan unit lama bila re-assign ganti armada
    # Geocode tujuan (perbaiki G1) — best effort, di LUAR lock (I/O jaringan; jangan tahan mutex)
    geo = await geocode(db, bk.get("destination"))
    # E9: estimasi jarak rute (OSRM) origin->dest sebagai fallback distance_km — best effort
    est_km = None
    try:
        origin_geo = await geocode(db, bk.get("origin"))
        if origin_geo and geo:
            r = await route_eta(origin_geo["lat"], origin_geo["lng"], geo["lat"], geo["lng"])
            if r and r.get("distance_km"):
                est_km = round(float(r["distance_km"]), 1)
    except Exception:  # noqa: BLE001
        est_km = None
    # RC-16 (anti-TOCTOU): cek-final bentrok + tulis assignment HARUS serial per armada.
    # (Celah lama: assign tak dibungkus vehicle_lock → 2 assign paralel ke armada+waktu sama
    #  bisa sama-sama lolos find_conflicts lalu sama-sama menulis → double-book.)
    async with availability.vehicle_lock(db, body.vehicle_id):
        # INV-4: cek bentrok armada (kecuali booking ini sendiri)
        conflicts = await availability.find_conflicts(
            db, body.vehicle_id, bk.get("start_datetime"), bk.get("end_datetime"), exclude_id=booking_id)
        if conflicts:
            raise HTTPException(status_code=400, detail=f"Armada bentrok dengan booking {conflicts[0].get('code')}")
        # RC-07: cek bentrok DRIVER (1 sopir tak boleh di 2 trip tumpang-tindih waktu).
        dconf = await availability.find_driver_conflicts(
            db, body.driver_id, bk.get("start_datetime"), bk.get("end_datetime"), exclude_booking_id=booking_id)
        if dconf:
            raise HTTPException(status_code=400,
                                detail=f"Driver {drv.get('name')} bentrok dengan booking {dconf[0].get('code')}")
        # Update booking (driver+unit+nama snapshot)
        await db.bookings.update_one({"id": booking_id}, {"$set": {
            "driver_id": drv["id"], "driver_name": drv.get("name"),
            "vehicle_id": veh["id"], "vehicle_name": veh.get("name"),
        }})
        # Upsert trip terjadwal (standby) dgn koordinat tujuan
        trip = await _trip_for(db, booking_id)
        trip_set = {
            "vehicle_id": veh["id"], "driver_id": drv["id"],
            "dest_name": bk.get("destination"),
            "dest_lat": (geo or {}).get("lat"), "dest_lng": (geo or {}).get("lng"),
            "dest_display": (geo or {}).get("display_name"),
            "est_distance_km": est_km,
            "assigned_at": now_iso(),
        }
        # Fee driver PER KEBERANGKATAN: rate /hari bisa beda tiap assign; snapshot di trip
        # (dikreditkan ke saldo driver saat trip selesai — services.trips).
        # Semantik eksplisit: None = tidak diubah; 0 = HAPUS fee; >0 = set/ganti rate.
        if body.driver_fee_rate is not None:
            if float(body.driver_fee_rate) > 0:
                fee_days = _fee_days(bk)
                trip_set.update({
                    "driver_fee_rate": money(body.driver_fee_rate),
                    "driver_fee_days": fee_days,
                    "driver_fee_total": money(float(body.driver_fee_rate) * fee_days),
                })
            else:
                trip_set.update({"driver_fee_rate": None, "driver_fee_days": None,
                                 "driver_fee_total": None})
        if trip:
            await db.trips.update_one({"id": trip["id"]}, {"$set": trip_set})
            trip_id = trip["id"]
        else:
            trip_doc = {
                "id": new_id("trp"), "booking_id": booking_id, "status": "standby",
                "start_at": None, "end_at": None,
                "revenue": money(bk.get("total_amount", 0)), "profit": None,
                "distance_km": 0.0, "created_at": now_iso(), **trip_set,
            }
            await db.trips.insert_one(trip_doc)
            trip_id = trip_doc["id"]
        # Status armada/driver ringan
        await db.vehicles.update_one({"id": veh["id"]}, {"$set": {"status": "on_trip"}})
        # Re-assign ganti armada: bebaskan unit LAMA bila tak dipakai TRIP aktif lain
        # (celah lama: unit lama tetap 'on_trip' selamanya → tampak sibuk padahal bebas).
        # Selaras dgn _release_booking_resources: status 'on_trip' hanya ditimbulkan oleh dispatch/trip
        # aktif — booking 'confirmed' yg BELUM di-dispatch tidak membuat armada on_trip, jadi TIDAK
        # dijadikan alasan menahan (dulu cek other_bk terlalu ketat → unit lama tak pernah dibebaskan).
        if prev_vehicle_id and prev_vehicle_id != veh["id"]:
            other_trip = await db.trips.find_one(
                {"vehicle_id": prev_vehicle_id, "id": {"$ne": trip_id},
                 "status": {"$in": ["standby", "to_pickup", "on_trip"]}}, {"_id": 0, "id": 1})
            prev_veh = await db.vehicles.find_one({"id": prev_vehicle_id}, {"_id": 0, "status": 1})
            if not other_trip and prev_veh and prev_veh.get("status") == "on_trip":
                await db.vehicles.update_one({"id": prev_vehicle_id}, {"$set": {"status": "available"}})
    bk = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
    payload = await _wa_payload(db, bk)
    await emit(db, "trip.assigned", payload, source="dispatch", ref_type="booking",
              ref_id=booking_id, dedupe_key=f"trip.assigned:{booking_id}:{drv['id']}")
    await record(db, actor=user, action="assign", entity_type="booking", entity_id=booking_id,
                 summary=f"Assign driver {drv.get('name')} + unit {veh.get('name')} → trip terjadwal")
    out = await db.trips.find_one({"id": trip_id}, {"_id": 0})
    return {"trip": safe_doc(out), "geocode": geo, "booking": safe_doc(bk)}


@router.post("/dispatch/{booking_id}/confirm-departure")
async def confirm_departure(booking_id: str, user=Depends(DISPATCH)):
    db = get_db()
    bk = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
    if not bk:
        raise HTTPException(status_code=404, detail="Booking tidak ditemukan")
    if not (bk.get("driver_id") and bk.get("vehicle_id")):
        raise HTTPException(status_code=400, detail="Assign driver & unit dulu sebelum konfirmasi keberangkatan")
    await db.bookings.update_one({"id": booking_id}, {"$set": {"departure_confirmed_at": now_iso()}})
    bk = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
    payload = await _wa_payload(db, bk)
    await emit(db, "booking.departure_confirmed", payload, source="dispatch", ref_type="booking",
              ref_id=booking_id, dedupe_key=f"booking.departure_confirmed:{booking_id}")
    await record(db, actor=user, action="confirm_departure", entity_type="booking",
                 entity_id=booking_id, summary=f"Konfirmasi keberangkatan {bk.get('code')} (WA)")
    return {"ok": True, "booking": safe_doc(bk)}


async def _trip_or_404(db, trip_id):
    trip = await db.trips.find_one({"id": trip_id}, {"_id": 0})
    if not trip:
        raise HTTPException(status_code=404, detail="Trip tidak ditemukan")
    return trip


async def _emit_trip_event(db, trip, event_type, extra=None):
    bk = await db.bookings.find_one({"id": trip.get("booking_id")}, {"_id": 0}) or {}
    payload = await _wa_payload(db, bk) if bk else {}
    if extra:
        payload.update(extra)
    await emit(db, event_type, payload, source="dispatch", ref_type="booking",
              ref_id=trip.get("booking_id"), dedupe_key=f"{event_type}:{trip['id']}")


@router.post("/dispatch/trips/{trip_id}/enroute")
async def trip_enroute(trip_id: str, user=Depends(DISPATCH)):
    db = get_db()
    trip = await _trip_or_404(db, trip_id)
    await db.trips.update_one({"id": trip_id}, {"$set": {"status": "to_pickup", "enroute_at": now_iso()}})
    await _emit_trip_event(db, trip, "trip.enroute")
    await record(db, actor=user, action="trip_enroute", entity_type="trip", entity_id=trip_id,
                 summary="Driver dalam perjalanan menjemput (WA ke pelanggan)")
    return safe_doc(await db.trips.find_one({"id": trip_id}, {"_id": 0}))


@router.post("/dispatch/trips/{trip_id}/arrived")
async def trip_arrived(trip_id: str, user=Depends(DISPATCH)):
    db = get_db()
    trip = await _trip_or_404(db, trip_id)
    await db.trips.update_one({"id": trip_id}, {"$set": {"arrived_at": now_iso()}})
    await _emit_trip_event(db, trip, "trip.arrived")
    await record(db, actor=user, action="trip_arrived", entity_type="trip", entity_id=trip_id,
                 summary="Tiba di tujuan (WA ke pelanggan)")
    return safe_doc(await db.trips.find_one({"id": trip_id}, {"_id": 0}))


@router.post("/dispatch/trips/{trip_id}/pod")
async def upload_pod(trip_id: str, photo: UploadFile = File(default=None),
                     recipient_name: str = Form(default=""), note: str = Form(default=""),
                     user=Depends(DISPATCH)):
    db = get_db()
    trip = await _trip_or_404(db, trip_id)
    photo_url = None
    if photo is not None:
        ext = ALLOWED_IMG.get((photo.content_type or "").lower())
        if not ext:
            raise HTTPException(status_code=400, detail="Format foto harus JPG/PNG/WebP")
        data = await photo.read()
        if len(data) > MAX_POD_BYTES:
            raise HTTPException(status_code=400, detail="Ukuran foto maksimal 6 MB")
        fname = f"{trip_id}_{int(datetime.now(timezone.utc).timestamp())}{ext}"
        (POD_DIR / fname).write_bytes(data)
        photo_url = f"/api/uploads/pod/{fname}"
    if not photo_url and not recipient_name and not note:
        raise HTTPException(status_code=400, detail="Sertakan foto, nama penerima, atau catatan POD")
    pod = {"photo_url": photo_url, "recipient_name": recipient_name or None,
           "note": note or None, "at": now_iso(), "by": user.get("id")}
    await db.trips.update_one({"id": trip_id}, {"$set": {"pod": pod}})
    await record(db, actor=user, action="pod_upload", entity_type="trip", entity_id=trip_id,
                 summary=f"Bukti layanan (POD) diunggah—penerima {recipient_name or '-'}")
    # G2: POD via dispatch = TITIK PENYELESAIAN trip di alur ops (tak ada checkout terpisah di sini).
    # Delegasi ke SSOT finalize_trip_completion (RC-03) agar efek IDENTIK dengan driver/checkout:
    # bebaskan armada + hitung KM + selesaikan booking + emit `trip.completed` (idempotent) →
    # WA "terima kasih + ulasan" terkirim (menutup celah G2: sebelumnya POD dispatch senyap).
    from services.trips import finalize_trip_completion
    fresh = await db.trips.find_one({"id": trip_id}, {"_id": 0})
    if fresh:
        await finalize_trip_completion(db, fresh, user)
    return safe_doc(await db.trips.find_one({"id": trip_id}, {"_id": 0}))
