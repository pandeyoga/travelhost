"""routers/driver.py — surface DRIVER: lihat tugas, check-in/out trip.

Kontrak:
  GET  /api/driver/my-trips   -> [trip] milik driver yang login
  POST /api/driver/checkin    <- {trip_id?|booking_id?} -> status to_pickup (+buat trip dari booking bila perlu)
  POST /api/driver/checkout   <- {trip_id} -> status completed

Pemetaan user->driver via field drivers.user_id (fallback phone/nama).

E0/G2: status booking 'ongoing' kini NYATA:
  - checkin (trip mulai)  -> booking confirmed => ongoing
  - checkout (trip selesai) -> booking ongoing/confirmed => completed. payment_status
    diturunkan ulang jujur (RC-02) — bukan dipaksa 'selesai'; delegasi ke SSOT
    services.trips.finalize_trip_completion.
Sinkron: Dashboard `_ACTIVE` & guard hapus driver memakai {confirmed, ongoing}.
"""
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile

import os
from datetime import datetime, timezone
from pathlib import Path

from core_utils import new_id, now_iso, safe_doc
from db import get_db
from dependencies import require_section
from schemas import CheckinRequest
from services.audit import record
from services.events import emit
from services.trips import compute_distance

router = APIRouter(prefix="/api", tags=["driver"])
# RBAC-SECT-01: seluruh permukaan Ruang Kerja Driver lewat pintu section `driver-workspace`
# ({owner, ops_admin, driver}). Sebelumnya cukup "sudah login", sehingga `marketing_admin`
# mendapat HTTP 200 pada daftar trip & tugas sopir — data operasional yang menunya memang tidak
# pernah ada untuk peran itu. Kepemilikan per-sopir tetap dijaga `_resolve_driver`/`_owned_trip`.
WORKSPACE = require_section("driver-workspace")

UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", str(Path(__file__).resolve().parent.parent / "uploads")))
POD_DIR = UPLOAD_DIR / "pod"
POD_DIR.mkdir(parents=True, exist_ok=True)
ALLOWED_IMG = {"image/jpeg": ".jpg", "image/jpg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
MAX_POD_BYTES = 6 * 1024 * 1024  # 6 MB


async def _emit_trip(db, booking_id, event_type):
    """Pancarkan event trip (started/completed/arrived) dgn payload WA lengkap (SSOT).

    Memakai services.wa_payload.build_wa_payload agar variabel WA (company/destination/
    driver_phone/pickup dll.) konsisten dengan dispatch — cegah drift template kosong.
    """
    bk = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
    if not bk:
        return
    from services.wa_payload import build_wa_payload
    payload = await build_wa_payload(db, bk)
    await emit(db, event_type, payload, source="driver", ref_type="booking",
              ref_id=booking_id, dedupe_key=f"{event_type}:{booking_id}")


async def _resolve_driver(db, user):
    """Delegasi ke SSOT `services.rbac_scope.resolve_driver` (INV-RBAC-05).

    Sebelumnya logika pemetaan user->driver diduplikasi di sini; duplikasi itu berisiko
    melenceng dari penyaring row-level di routers/bookings.py & drivers.py.
    """
    from services.rbac_scope import resolve_driver
    return await resolve_driver(db, user)


async def _target_driver(db, user, driver_id=None):
    """Driver efektif utk permukaan baca: owner/ops_admin boleh MELIHAT-SEBAGAI driver lain
    (override admin) via query driver_id; peran lain selalu dipetakan ke dirinya sendiri."""
    if driver_id and user.get("role") in ("owner", "ops_admin"):
        return await db.drivers.find_one({"id": driver_id}, {"_id": 0})
    return await _resolve_driver(db, user)


@router.get("/driver/my-trips")
async def my_trips(limit: int = Query(default=200, le=500), skip: int = Query(default=0, ge=0),
                   driver_id: str = Query(default=None), user=Depends(WORKSPACE)):
    db = get_db()
    drv = await _target_driver(db, user, driver_id)
    if not drv:
        return []
    docs = await db.trips.find({"driver_id": drv["id"]}, {"_id": 0}).sort("created_at", -1).skip(skip).to_list(limit)
    return safe_doc(docs)


@router.post("/driver/checkin")
async def checkin(body: CheckinRequest, user=Depends(WORKSPACE)):
    db = get_db()
    # RBAC kepemilikan: driver hanya boleh check-in trip/booking miliknya.
    # Manajer (owner/ops_admin) boleh atas nama driver (fallback operasional).
    is_manager = user.get("role") in ("owner", "ops_admin")
    drv = await _resolve_driver(db, user)
    if not is_manager and not drv:
        raise HTTPException(status_code=403, detail="Akun Anda belum tertaut ke data driver")
    my_id = (drv or {}).get("id")
    trip = None
    if body.trip_id:
        trip = await db.trips.find_one({"id": body.trip_id}, {"_id": 0})
        if not trip:
            raise HTTPException(status_code=404, detail="Trip tidak ditemukan")
        if not is_manager and trip.get("driver_id") != my_id:
            raise HTTPException(status_code=403, detail="Trip ini bukan tugas Anda")
    elif body.booking_id:
        trip = await db.trips.find_one({"booking_id": body.booking_id}, {"_id": 0})
        if not trip:
            booking = await db.bookings.find_one({"id": body.booking_id}, {"_id": 0})
            if not booking:
                raise HTTPException(status_code=404, detail="Booking tidak ditemukan")
            if not is_manager and booking.get("driver_id") != my_id:
                raise HTTPException(status_code=403, detail="Booking ini bukan tugas Anda")
            trip = {
                "id": new_id("trp"), "booking_id": booking["id"],
                "vehicle_id": booking.get("vehicle_id"), "driver_id": booking.get("driver_id"),
                "status": "to_pickup", "start_at": now_iso(), "end_at": None,
                "revenue": float(booking.get("total_amount", 0) or 0), "profit": None,
                "distance_km": 0.0, "dest_name": booking.get("destination"),
                "dest_lat": None, "dest_lng": None, "created_at": now_iso(),
            }
            await db.trips.insert_one(trip)
        elif not is_manager and trip.get("driver_id") != my_id:
            raise HTTPException(status_code=403, detail="Trip ini bukan tugas Anda")
    else:
        raise HTTPException(status_code=400, detail="Sertakan trip_id atau booking_id")
    await db.trips.update_one({"id": trip["id"]}, {"$set": {"status": "to_pickup"}})
    if body.odometer_start is not None:
        await db.trips.update_one({"id": trip["id"]}, {"$set": {"odometer_start": float(body.odometer_start)}})
    if trip.get("vehicle_id"):
        await db.vehicles.update_one({"id": trip["vehicle_id"]}, {"$set": {"status": "on_trip"}})
    if trip.get("driver_id"):
        await db.drivers.update_one({"id": trip["driver_id"]}, {"$set": {"status": "online"}})
    # G2: booking yang trip-nya dimulai => 'ongoing' (hanya bila masih 'confirmed').
    if trip.get("booking_id"):
        res = await db.bookings.update_one(
            {"id": trip["booking_id"], "status": "confirmed"},
            {"$set": {"status": "ongoing"}},
        )
        if res.modified_count:
            await record(db, actor=user, action="trip_start", entity_type="booking",
                         entity_id=trip["booking_id"], summary="Trip dimulai -> booking ongoing")
            await _emit_trip(db, trip["booking_id"], "trip.started")
    doc = await db.trips.find_one({"id": trip["id"]}, {"_id": 0})
    return safe_doc(doc)


@router.post("/driver/checkout")
async def checkout(body: CheckinRequest, user=Depends(WORKSPACE)):
    db = get_db()
    if not body.trip_id:
        raise HTTPException(status_code=400, detail="trip_id wajib")
    # RBAC kepemilikan: driver hanya boleh checkout trip miliknya (manajer boleh atas nama).
    is_manager = user.get("role") in ("owner", "ops_admin")
    drv = await _resolve_driver(db, user)
    if not is_manager and not drv:
        raise HTTPException(status_code=403, detail="Akun Anda belum tertaut ke data driver")
    trip = await db.trips.find_one({"id": body.trip_id}, {"_id": 0})
    if not trip:
        raise HTTPException(status_code=404, detail="Trip tidak ditemukan")
    if not is_manager and trip.get("driver_id") != (drv or {}).get("id"):
        raise HTTPException(status_code=403, detail="Trip ini bukan tugas Anda")
    # RC-03: penyelesaian trip lewat SSOT tunggal (efek identik dgn /trips/{id}/status=completed).
    from services.trips import finalize_trip_completion
    return await finalize_trip_completion(db, trip, user, odometer_end=body.odometer_end)


# === E8: Driver Workspace (jadwal tugas, konfirmasi, navigasi, POD) ===
async def _owned_trip(db, trip_id, drv, manager=False):
    """Ambil trip milik driver yang login. 404 bila tak ada, 403 bila bukan miliknya.
    manager=True (owner/ops_admin) boleh bertindak atas nama driver (override admin)."""
    trip = await db.trips.find_one({"id": trip_id}, {"_id": 0})
    if not trip:
        raise HTTPException(status_code=404, detail="Trip tidak ditemukan")
    if not manager and trip.get("driver_id") != (drv or {}).get("id"):
        raise HTTPException(status_code=403, detail="Trip ini bukan tugas Anda")
    return trip


async def _task_from_trip(db, trip):
    bk = await db.bookings.find_one({"id": trip.get("booking_id")}, {"_id": 0}) or {}
    cust = {}
    if bk.get("customer_id"):
        cust = await db.customers.find_one({"id": bk["customer_id"]}, {"_id": 0, "phone": 1}) or {}
    veh = {}
    if trip.get("vehicle_id"):
        veh = await db.vehicles.find_one({"id": trip["vehicle_id"]}, {"_id": 0, "name": 1, "plate_number": 1, "odometer": 1}) or {}
    pod = trip.get("pod") or None
    return {
        "trip_id": trip.get("id"), "booking_id": trip.get("booking_id"), "code": bk.get("code"),
        "customer_name": bk.get("customer_name"), "customer_phone": cust.get("phone"),
        "origin": bk.get("origin"), "destination": bk.get("destination") or trip.get("dest_name"),
        "start_datetime": bk.get("start_datetime"), "end_datetime": bk.get("end_datetime"),
        "trip_status": trip.get("status"), "booking_status": bk.get("status"),
        "dest_lat": trip.get("dest_lat"), "dest_lng": trip.get("dest_lng"),
        "dest_display": trip.get("dest_display"),
        "vehicle_id": trip.get("vehicle_id"), "vehicle_name": veh.get("name"),
        "vehicle_plate": veh.get("plate_number"), "vehicle_odometer": veh.get("odometer"),
        "odometer_start": trip.get("odometer_start"), "odometer_end": trip.get("odometer_end"),
        "distance_km": trip.get("distance_km"), "distance_basis": trip.get("distance_basis"),
        "est_distance_km": trip.get("est_distance_km"),
        "acknowledged": bool(trip.get("driver_ack_at")), "ack_at": trip.get("driver_ack_at"),
        "arrived": bool(trip.get("arrived_at")), "arrived_at": trip.get("arrived_at"),
        "has_pod": bool(pod), "pod": pod,
    }


@router.get("/driver/tasks")
async def my_tasks(limit: int = Query(default=200, le=500), driver_id: str = Query(default=None),
                   user=Depends(WORKSPACE)):
    db = get_db()
    drv = await _target_driver(db, user, driver_id)
    if not drv:
        return []
    trips = await db.trips.find({"driver_id": drv["id"]}, {"_id": 0}).sort("created_at", -1).to_list(limit)
    return safe_doc([await _task_from_trip(db, t) for t in trips])


@router.get("/driver/summary")
async def my_summary(driver_id: str = Query(default=None), user=Depends(WORKSPACE)):
    db = get_db()
    drv = await _target_driver(db, user, driver_id)
    if not drv:
        return {"is_driver": False, "today": 0, "active": 0, "completed": 0, "need_pod": 0, "total": 0}
    trips = await db.trips.find({"driver_id": drv["id"]}, {"_id": 0}).to_list(500)
    today = datetime.now(timezone.utc).date().isoformat()
    active_st = {"standby", "assigned", "to_pickup", "arrived", "on_trip"}
    completed = sum(1 for t in trips if t.get("status") == "completed")
    return {
        "is_driver": True, "driver_name": drv.get("name"), "total": len(trips),
        "today": sum(1 for t in trips if str(t.get("start_at") or "")[:10] == today
                     or str(t.get("assigned_at") or "")[:10] == today),
        "active": sum(1 for t in trips if t.get("status") in active_st),
        "completed": completed,
        "need_pod": sum(1 for t in trips if t.get("status") == "completed" and not t.get("pod")),
    }


@router.post("/driver/tasks/{trip_id}/ack")
async def ack_task(trip_id: str, user=Depends(WORKSPACE)):
    db = get_db()
    is_manager = user.get("role") in ("owner", "ops_admin")
    drv = await _resolve_driver(db, user)
    if not is_manager and not drv:
        raise HTTPException(status_code=403, detail="Akun Anda belum tertaut ke data driver")
    trip = await _owned_trip(db, trip_id, drv, manager=is_manager)
    await db.trips.update_one({"id": trip_id}, {"$set": {"driver_ack_at": now_iso()}})
    await record(db, actor=user, action="trip_ack", entity_type="trip", entity_id=trip_id,
                 summary="Driver mengonfirmasi tugas")
    return safe_doc(await db.trips.find_one({"id": trip_id}, {"_id": 0}))


@router.post("/driver/tasks/{trip_id}/arrived")
async def arrived_task(trip_id: str, user=Depends(WORKSPACE)):
    db = get_db()
    is_manager = user.get("role") in ("owner", "ops_admin")
    drv = await _resolve_driver(db, user)
    if not is_manager and not drv:
        raise HTTPException(status_code=403, detail="Akun Anda belum tertaut ke data driver")
    trip = await _owned_trip(db, trip_id, drv, manager=is_manager)
    await db.trips.update_one({"id": trip_id}, {"$set": {"arrived_at": now_iso()}})
    if trip.get("booking_id"):
        await _emit_trip(db, trip["booking_id"], "trip.arrived")
    await record(db, actor=user, action="trip_arrived", entity_type="trip", entity_id=trip_id,
                 summary="Driver tiba di tujuan (WA ke pelanggan)")
    return safe_doc(await db.trips.find_one({"id": trip_id}, {"_id": 0}))


@router.post("/driver/tasks/{trip_id}/pod")
async def upload_pod(trip_id: str, photo: UploadFile = File(default=None),
                     recipient_name: str = Form(default=""), note: str = Form(default=""),
                     user=Depends(WORKSPACE)):
    db = get_db()
    is_manager = user.get("role") in ("owner", "ops_admin")
    drv = await _resolve_driver(db, user)
    if not is_manager and not drv:
        raise HTTPException(status_code=403, detail="Akun Anda belum tertaut ke data driver")
    await _owned_trip(db, trip_id, drv, manager=is_manager)
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
                 summary=f"Driver unggah bukti layanan (POD)—penerima {recipient_name or '-'}")
    return safe_doc(await db.trips.find_one({"id": trip_id}, {"_id": 0}))
