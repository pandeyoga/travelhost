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

from core_utils import safe_doc
from db import get_db
from dependencies import get_current_user
from schemas import TripStatusUpdate
from services.osrm import fallback_eta, route_eta

router = APIRouter(prefix="/api", tags=["trips"])

TRIP_STATUSES = {"standby", "to_pickup", "on_trip", "completed"}


_DRIVER_HIDDEN = ("revenue", "profit")  # nilai bisnis tidak untuk sopir


async def _driver_scope(db, user):
    """Sopir hanya boleh melihat trip MILIKNYA (dulu GET /trips mengembalikan semua trip +
    pendapatannya). None = bukan sopir (tanpa batasan)."""
    if user.get("role") != "driver":
        return None
    from services.rbac_scope import resolve_driver
    me = await resolve_driver(db, user)
    return (me or {}).get("id") or "__tanpa_driver__"


async def _visible_trip_or_404(db, trip_id, user):
    trip = await db.trips.find_one({"id": trip_id}, {"_id": 0})
    scope = await _driver_scope(db, user)
    if not trip or (scope and trip.get("driver_id") != scope):
        raise HTTPException(status_code=404, detail="Trip tidak ditemukan")
    return trip, scope


def _for_viewer(doc, scope):
    return {k: v for k, v in doc.items() if k not in _DRIVER_HIDDEN} if scope else doc


async def _latest_location(db, trip_id):
    pts = await db.locations.find({"trip_id": trip_id}, {"_id": 0}).sort("timestamp", -1).limit(1).to_list(1)
    return pts[0] if pts else None


@router.get("/trips")
async def list_trips(status: str = Query(default=None), driver_id: str = Query(default=None),
                     active: bool = Query(default=False),
                     limit: int = Query(default=500, le=1000), skip: int = Query(default=0, ge=0),
                     user=Depends(get_current_user)):
    db = get_db()
    query = {}
    if status:
        query["status"] = status
    if active:  # GPS/live: hanya trip yang relevan dipantau (terjadwal/menjemput/dalam perjalanan)
        query["status"] = {"$in": ["standby", "to_pickup", "on_trip"]}
    if driver_id:
        query["driver_id"] = driver_id
    scope = await _driver_scope(db, user)
    if scope:
        query["driver_id"] = scope
    docs = await db.trips.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).to_list(limit)
    # Konteks booking (kode, rute, pelanggan) — dulu daftar GPS hanya "Jakarta — Standby" berulang.
    bks = {b["id"]: b for b in await db.bookings.find(
        {"id": {"$in": [d.get("booking_id") for d in docs if d.get("booking_id")]}},
        {"_id": 0, "id": 1, "code": 1, "origin": 1, "destination": 1, "customer_name": 1,
         "start_datetime": 1}).to_list(len(docs) or 1)}
    out = []
    for d in docs:
        b = bks.get(d.get("booking_id")) or {}
        out.append({**_for_viewer(d, scope), "booking_code": b.get("code"), "origin": b.get("origin"),
                    "destination": b.get("destination") or d.get("dest_name"),
                    "customer_name": b.get("customer_name"), "start_datetime": b.get("start_datetime")})
    return safe_doc(out)


@router.get("/trips/{trip_id}/track")
async def trip_track(trip_id: str, limit: int = Query(default=5000, le=5000),
                     user=Depends(get_current_user)):
    db = get_db()
    await _visible_trip_or_404(db, trip_id, user)
    pts = await db.locations.find({"trip_id": trip_id}, {"_id": 0}).sort("timestamp", 1).to_list(limit)
    return safe_doc(pts)


@router.get("/trips/{trip_id}/eta")
async def trip_eta(trip_id: str, dest_lat: float = Query(default=None), dest_lng: float = Query(default=None),
                   user=Depends(get_current_user)):
    db = get_db()
    trip, _ = await _visible_trip_or_404(db, trip_id, user)
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
    doc, scope = await _visible_trip_or_404(get_db(), trip_id, user)
    return safe_doc(_for_viewer(doc, scope))


@router.post("/trips/{trip_id}/status")
async def update_trip_status(trip_id: str, body: TripStatusUpdate, user=Depends(get_current_user)):
    db = get_db()
    if body.status not in TRIP_STATUSES:
        raise HTTPException(status_code=400, detail="Status trip tidak valid")
    trip = await db.trips.find_one({"id": trip_id}, {"_id": 0})
    if not trip:
        raise HTTPException(status_code=404, detail="Trip tidak ditemukan")
    # RBAC: driver hanya boleh mengubah trip miliknya (manager/owner bebas) — SSOT resolve_driver.
    scope = await _driver_scope(db, user)
    if scope and trip.get("driver_id") != scope:
        raise HTTPException(status_code=403, detail="Hanya boleh mengubah trip milik Anda")
    # RC-03: 'completed' via jalur generik ini HARUS memicu efek samping identik dgn
    # driver/checkout (bebaskan armada, selesaikan booking, hitung KM) — anti split-brain.
    from services.trips import apply_trip_status
    return await apply_trip_status(db, trip, body.status, user)
