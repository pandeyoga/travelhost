"""routers/trips.py — trip: list/detail + track (polyline) + ETA (OSRM) + transisi status.

Kontrak:
  GET  /api/trips                     → [trip]
  GET  /api/trips/{id}                → trip
  GET  /api/trips/{id}/track          → [locations] (urut waktu, polyline)
  GET  /api/trips/{id}/eta?dest_lat&dest_lng → {eta_minutes,distance_km,available,...}
  POST /api/trips/{id}/status         ← {status} (standby|to_pickup|on_trip|completed)

Urutan rute: literal/spesifik sebelum /{id} agar tidak tertelan path param.
"""
from fastapi import APIRouter, Depends, HTTPException, Query

from core_utils import now_iso, safe_doc
from db import get_db
from dependencies import get_current_user
from schemas import TripStatusUpdate
from services.osrm import fallback_eta, route_eta

router = APIRouter(prefix="/api", tags=["trips"])

TRIP_STATUSES = {"standby", "to_pickup", "on_trip", "completed"}


async def _latest_location(db, trip_id):
    pts = await db.locations.find({"trip_id": trip_id}, {"_id": 0}).sort("timestamp", -1).limit(1).to_list(1)
    return pts[0] if pts else None


@router.get("/trips")
async def list_trips(status: str = Query(default=None), driver_id: str = Query(default=None),
                     limit: int = Query(default=500, le=1000), skip: int = Query(default=0, ge=0),
                     user=Depends(get_current_user)):
    query = {}
    if status:
        query["status"] = status
    if driver_id:
        query["driver_id"] = driver_id
    docs = await get_db().trips.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).to_list(limit)
    return safe_doc(docs)


@router.get("/trips/{trip_id}/track")
async def trip_track(trip_id: str, limit: int = Query(default=5000, le=5000),
                     user=Depends(get_current_user)):
    pts = await get_db().locations.find({"trip_id": trip_id}, {"_id": 0}).sort("timestamp", 1).to_list(limit)
    return safe_doc(pts)


@router.get("/trips/{trip_id}/eta")
async def trip_eta(trip_id: str, dest_lat: float = Query(default=None), dest_lng: float = Query(default=None),
                   user=Depends(get_current_user)):
    db = get_db()
    trip = await db.trips.find_one({"id": trip_id}, {"_id": 0})
    if not trip:
        raise HTTPException(status_code=404, detail="Trip tidak ditemukan")
    cur = await _latest_location(db, trip_id)
    if not cur:
        return {"available": False, "eta_minutes": None, "distance_km": None,
                "reason": "Belum ada lokasi terkirim untuk trip ini"}
    dlat = dest_lat if dest_lat is not None else trip.get("dest_lat")
    dlng = dest_lng if dest_lng is not None else trip.get("dest_lng")
    if dlat is None or dlng is None:
        return {"available": False, "eta_minutes": None, "distance_km": None,
                "reason": "Koordinat tujuan belum diset"}
    res = await route_eta(cur["lat"], cur["lng"], dlat, dlng)
    if res is None:
        res = fallback_eta(cur["lat"], cur["lng"], dlat, dlng)
    return {
        "available": True,
        "eta_minutes": res["eta_minutes"],
        "distance_km": res["distance_km"],
        "approx": res.get("approx", False),
        "dest_name": trip.get("dest_name"),
        "from": {"lat": cur["lat"], "lng": cur["lng"]},
        "to": {"lat": float(dlat), "lng": float(dlng)},
    }


@router.get("/trips/{trip_id}")
async def get_trip(trip_id: str, user=Depends(get_current_user)):
    doc = await get_db().trips.find_one({"id": trip_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Trip tidak ditemukan")
    return safe_doc(doc)


@router.post("/trips/{trip_id}/status")
async def update_trip_status(trip_id: str, body: TripStatusUpdate, user=Depends(get_current_user)):
    db = get_db()
    if body.status not in TRIP_STATUSES:
        raise HTTPException(status_code=400, detail="Status trip tidak valid")
    trip = await db.trips.find_one({"id": trip_id}, {"_id": 0})
    if not trip:
        raise HTTPException(status_code=404, detail="Trip tidak ditemukan")
    # RBAC: driver hanya boleh mengubah trip miliknya (manager/owner bebas).
    if user.get("role") == "driver":
        me = await db.drivers.find_one(
            {"$or": [{"user_id": user.get("id")}, {"phone": user.get("phone")},
                     {"name": user.get("name")}]}, {"_id": 0, "id": 1})
        if not me or trip.get("driver_id") != me.get("id"):
            raise HTTPException(status_code=403, detail="Hanya boleh mengubah trip milik Anda")
    # RC-03: 'completed' via jalur generik ini HARUS memicu efek samping identik dgn
    # driver/checkout (bebaskan armada, selesaikan booking, hitung KM) — anti split-brain.
    if body.status == "completed":
        from services.trips import finalize_trip_completion
        return await finalize_trip_completion(db, trip, user)
    updates = {"status": body.status}
    if body.status in ("to_pickup", "on_trip"):
        if body.status == "on_trip" and not trip.get("start_at"):
            updates["start_at"] = now_iso()
        # Sinkron sumber daya: armada dipakai, driver online.
        if trip.get("vehicle_id"):
            await db.vehicles.update_one({"id": trip["vehicle_id"]}, {"$set": {"status": "on_trip"}})
        if trip.get("driver_id"):
            await db.drivers.update_one({"id": trip["driver_id"]}, {"$set": {"status": "online"}})
    await db.trips.update_one({"id": trip_id}, {"$set": updates})
    doc = await db.trips.find_one({"id": trip_id}, {"_id": 0})
    return safe_doc(doc)
