"""routers/locations.py — ingest GPS (time-series) + posisi live + histori track.

Kontrak:
  POST /api/locations            ← {trip_id?,driver_id?,vehicle_id?,lat,lng,speed?,heading?}
                                   (+geofence auto-status trip bila tiba pickup/tujuan)
  GET  /api/locations/live        → [posisi TERBARU per vehicle] (+stale/offline + live_status)
  GET  /api/locations/history     → [titik lokasi] untuk vehicle_id / trip_id (playback)

INV-6: timestamp diisi server (now_iso) sehingga monotonik per trip; lat/lng divalidasi.
Phase 6: indikator stale/offline (last_seen umur) + geofence auto-update status trip.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query

from core_utils import new_id, now_iso, safe_doc
from db import get_db
from dependencies import get_current_user
from schemas import LocationCreate
from services.geo import parse_iso, valid_coord
from services.geofence import evaluate as evaluate_geofence

router = APIRouter(prefix="/api", tags=["locations"])

STALE_SECONDS = 180  # > 3 menit tanpa update dianggap stale/offline
MOVING_SPEED = 3.0   # km/j ambang "bergerak" vs "diam"


@router.post("/locations")
async def ingest_location(body: LocationCreate, user=Depends(get_current_user)):
    db = get_db()
    if not valid_coord(body.lat, body.lng):
        raise HTTPException(status_code=400, detail="Koordinat di luar rentang valid (-90..90 / -180..180)")
    trip_id = body.trip_id
    driver_id = body.driver_id
    vehicle_id = body.vehicle_id
    trip = None
    if trip_id:
        trip = await db.trips.find_one({"id": trip_id}, {"_id": 0})
        if not trip:
            raise HTTPException(status_code=404, detail="Trip tidak ditemukan")
        driver_id = driver_id or trip.get("driver_id")
        vehicle_id = vehicle_id or trip.get("vehicle_id")
    # RBAC kepemilikan: driver hanya boleh kirim lokasi untuk trip/dirinya sendiri
    # (cegah manipulasi status trip driver lain via geofence). Manajer bebas (monitoring).
    if user.get("role") == "driver":
        me = await db.drivers.find_one(
            {"$or": [{"user_id": user.get("id")}, {"phone": user.get("phone")},
                     {"name": user.get("name")}]}, {"_id": 0, "id": 1})
        my_id = (me or {}).get("id")
        if trip is not None and trip.get("driver_id") != my_id:
            raise HTTPException(status_code=403, detail="Hanya boleh kirim lokasi untuk trip milik Anda")
        if driver_id and driver_id != my_id:
            raise HTTPException(status_code=403, detail="driver_id tidak sesuai akun Anda")
    doc = {
        "id": new_id("loc"),
        "trip_id": trip_id,
        "driver_id": driver_id,
        "vehicle_id": vehicle_id,
        "lat": float(body.lat),
        "lng": float(body.lng),
        "speed": float(body.speed or 0),
        "heading": float(body.heading or 0),
        "timestamp": now_iso(),
    }
    await db.locations.insert_one(doc)

    # Geofence auto-status: tiba pickup → on_trip; tiba tujuan → completed.
    geofence = None
    if trip:
        event, new_status = evaluate_geofence(trip, float(body.lat), float(body.lng))
        if new_status and new_status != trip.get("status"):
            updates = {"status": new_status}
            if new_status == "on_trip" and not trip.get("start_at"):
                updates["start_at"] = now_iso()
            if new_status == "completed":
                updates["end_at"] = now_iso()
            await db.trips.update_one({"id": trip_id}, {"$set": updates})
            if new_status == "completed" and trip.get("vehicle_id"):
                veh = await db.vehicles.find_one({"id": trip["vehicle_id"]}, {"_id": 0})
                if veh and veh.get("status") == "on_trip":
                    await db.vehicles.update_one(
                        {"id": trip["vehicle_id"]}, {"$set": {"status": "available"}})
            geofence = {"event": event, "new_status": new_status}

    out = safe_doc(doc)
    if geofence:
        out["geofence"] = geofence
    return out


def _live_status(speed, stale):
    if stale:
        return "offline"
    return "moving" if float(speed or 0) > 3.0 else "idle"


@router.get("/locations/live")
async def live_locations(user=Depends(get_current_user)):
    """Posisi live per armada dgn FAILOVER device>phone (E15) + indikator stale/offline.

    Implementasi failover ada di services.gps.live_positions (memilih sumber device bila
    fresh, jika tidak fallback ke phone). Import lokal utk hindari import melingkar.
    """
    from services import gps as gps_svc
    return safe_doc(await gps_svc.live_positions(get_db()))


@router.get("/locations/history")
async def location_history(vehicle_id: str = Query(default=None), trip_id: str = Query(default=None),
                           limit: int = Query(default=1000, le=5000), user=Depends(get_current_user)):
    """Histori titik lokasi (playback) per vehicle atau per trip, urut waktu naik."""
    db = get_db()
    query = {}
    if vehicle_id:
        query["vehicle_id"] = vehicle_id
    if trip_id:
        query["trip_id"] = trip_id
    if not query:
        return []
    pts = await db.locations.find(query, {"_id": 0}).sort("timestamp", 1).to_list(limit)
    return safe_doc(pts)
