"""routers/shares.py — Share-link publik bertoken (tanpa login, berbatas waktu, bisa di-revoke).

Dua jenis (siklus hidup bersama: services/share_links.py):
  * Tracking trip korporat (Phase 6) — `trip_shares`; konsumsi publik:
    GET /api/public/track/{token} (di bawah). Mutasi: owner/ops_admin (MANAGER).
  * Jadwal keberangkatan read-only — `schedule_shares`; konsumsi publik:
    GET /api/public/schedule/{token} (di bawah). Kelola: section "calendar" (owner/ops_admin).
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from core_utils import new_id, now_iso, safe_doc
from db import get_db
from dependencies import require_role, require_section
from schemas_ops import ScheduleShareCreate, ShareCreate
from services import share_links
from services.geo import parse_iso
from services.maps import fallback_eta, route_eta
from services.ratelimit import allow, client_ip
from services.schedule_share import (
    DEFAULT_STATUSES, build_public_schedule, count_departures, normalize_scope, scope_label,
)

router = APIRouter(prefix="/api", tags=["shares"])
MANAGER = require_role("owner", "ops_admin")
# Jadwal keberangkatan = permukaan Kalender (RBAC-CAL-01, SSOT permissions_config.SECTION_ACCESS).
CALENDAR = require_section("calendar")
STALE_SECONDS = 300  # posisi GPS lebih tua dari ini = "Offline" di halaman tracking publik


@router.get("/shares")
async def list_shares(active: bool = Query(default=None), trip_id: str = Query(default=None),
                      limit: int = Query(default=500, le=1000), skip: int = Query(default=0, ge=0),
                      user=Depends(MANAGER)):
    db = get_db()
    query = {}
    if trip_id:
        query["trip_id"] = trip_id
    docs = await db.trip_shares.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).to_list(limit)
    out = [share_links.share_state(s) for s in docs]
    if active is True:
        out = [s for s in out if s["is_active"]]
    return safe_doc(out)


@router.post("/shares")
async def create_share(body: ShareCreate, user=Depends(MANAGER)):
    db = get_db()
    trip = await db.trips.find_one({"id": body.trip_id}, {"_id": 0})
    if not trip:
        raise HTTPException(status_code=404, detail="Trip tidak ditemukan")
    veh = None
    if trip.get("vehicle_id"):
        veh = await db.vehicles.find_one({"id": trip["vehicle_id"]}, {"_id": 0})
    doc = {
        "id": new_id("shr"), "token": share_links.new_token(),
        "trip_id": body.trip_id, "vehicle_id": trip.get("vehicle_id"),
        "vehicle_name": veh.get("name") if veh else None,
        "label": (body.label or "").strip() or (veh.get("name") if veh else "Tracking Armada"),
        "expires_at": share_links.expiry_from_hours(body.hours, default=72, max_hours=24 * 30),
        "revoked": False, "revoked_at": None,
        "last_accessed_at": None, "access_count": 0,
        "created_by": user["id"], "created_at": now_iso(),
    }
    await db.trip_shares.insert_one(doc)
    return safe_doc(share_links.share_state(doc))


@router.post("/shares/{share_id}/revoke")
async def revoke_share(share_id: str, user=Depends(MANAGER)):
    return safe_doc(await share_links.revoke(get_db().trip_shares, share_id))


@router.delete("/shares/{share_id}")
async def delete_share(share_id: str, user=Depends(MANAGER)):
    return await share_links.delete(get_db().trip_shares, share_id)


@router.get("/public/track/{token}")
async def public_track(token: str):
    """Tracking publik korporat via share-link (TANPA auth). Validasi token + expiry + revoke.

    Mengembalikan posisi terkini, ETA, dan jejak (polyline) untuk peta read-only.
    """
    db = get_db()
    # Validasi token/revoke/expiry + catat akses: SATU sumber (services/share_links.py, INV-22).
    share = await share_links.resolve_public_share(db.trip_shares, token, "pelacakan")
    trip = await db.trips.find_one({"id": share.get("trip_id")}, {"_id": 0})
    if not trip:
        raise HTTPException(status_code=404, detail="Perjalanan tidak ditemukan")

    pts = await db.locations.find({"trip_id": trip["id"]}, {"_id": 0}).sort("timestamp", 1).to_list(2000)
    cur = pts[-1] if pts else None
    veh = None
    if trip.get("vehicle_id"):
        veh = await db.vehicles.find_one({"id": trip["vehicle_id"]}, {"_id": 0})

    eta = None
    if cur and trip.get("dest_lat") is not None and trip.get("dest_lng") is not None:
        res = await route_eta(cur["lat"], cur["lng"], trip["dest_lat"], trip["dest_lng"])
        if res is None:
            res = fallback_eta(cur["lat"], cur["lng"], trip["dest_lat"], trip["dest_lng"])
        eta = {"eta_minutes": res["eta_minutes"], "distance_km": res["distance_km"],
               "approx": res.get("approx", False)}

    stale = True
    if cur:
        ts = parse_iso(cur.get("timestamp"))
        stale = (datetime.now(timezone.utc) - ts).total_seconds() > STALE_SECONDS if ts else True

    return {
        "label": share.get("label"),
        "vehicle_name": (veh.get("name") if veh else share.get("vehicle_name")),
        "plate_number": veh.get("plate_number") if veh else None,
        "status": trip.get("status"),
        "dest_name": trip.get("dest_name"),
        "destination": ({"lat": trip.get("dest_lat"), "lng": trip.get("dest_lng")}
                        if trip.get("dest_lat") is not None else None),
        "current": ({"lat": cur["lat"], "lng": cur["lng"], "speed": cur.get("speed"),
                     "timestamp": cur.get("timestamp")} if cur else None),
        "stale": stale,
        "eta": eta,
        "track": [{"lat": p["lat"], "lng": p["lng"]} for p in pts],
        "expires_at": share.get("expires_at"),
    }


# ---------------------------------------------------------------- jadwal keberangkatan
async def _schedule_view(db, s: dict) -> dict:
    s = share_links.share_state(s)
    s["period_label"] = scope_label(s.get("scope") or {"type": "all"})
    s["departure_count"] = await count_departures(db, s)
    return s


@router.get("/schedule-shares")
async def list_schedule_shares(active: bool = Query(default=None),
                               limit: int = Query(default=200, ge=1, le=500),
                               skip: int = Query(default=0, ge=0), user=Depends(CALENDAR)):
    db = get_db()
    docs = await db.schedule_shares.find({}, {"_id": 0}).sort("created_at", -1).skip(skip).to_list(limit)
    out = [await _schedule_view(db, s) for s in docs]
    if active is True:
        out = [s for s in out if s["is_active"]]
    return safe_doc(out)


@router.post("/schedule-shares")
async def create_schedule_share(body: ScheduleShareCreate, user=Depends(CALENDAR)):
    db = get_db()
    scope = normalize_scope(body.scope, month=body.month, start=body.start, end=body.end, days=body.days)
    vehicle_ids = list(dict.fromkeys(v for v in body.vehicle_ids if v))
    if vehicle_ids:
        found = await db.vehicles.count_documents({"id": {"$in": vehicle_ids}})
        if found != len(vehicle_ids):
            raise HTTPException(status_code=400, detail="Ada armada yang tidak ditemukan")
    statuses = list(dict.fromkeys(body.statuses)) if body.statuses else list(DEFAULT_STATUSES)
    doc = {
        "id": new_id("ssh"), "token": share_links.new_token(),
        "label": (body.label or "").strip() or "Jadwal Keberangkatan",
        "scope": scope, "vehicle_ids": vehicle_ids, "statuses": statuses,
        "visibility": body.visibility.model_dump(),
        "expires_at": share_links.expiry_from_hours(body.hours, default=720, max_hours=24 * 365,
                                                    allow_never=True),
        "revoked": False, "revoked_at": None,
        "last_accessed_at": None, "access_count": 0,
        "created_by": user["id"], "created_at": now_iso(),
    }
    await db.schedule_shares.insert_one(doc)
    doc.pop("_id", None)
    return safe_doc(await _schedule_view(db, doc))


@router.post("/schedule-shares/{share_id}/revoke")
async def revoke_schedule_share(share_id: str, user=Depends(CALENDAR)):
    db = get_db()
    return safe_doc(await _schedule_view(db, await share_links.revoke(db.schedule_shares, share_id)))


@router.delete("/schedule-shares/{share_id}")
async def delete_schedule_share(share_id: str, user=Depends(CALENDAR)):
    return await share_links.delete(get_db().schedule_shares, share_id)


@router.get("/public/schedule/{token}")
async def public_schedule(token: str, request: Request):
    """Jadwal keberangkatan read-only via share-link (TANPA auth). Validasi token+expiry+revoke.

    Hanya field ALLOWLIST (services/schedule_share.public_departure) — tanpa nominal uang,
    tanpa kontak pelanggan, tanpa ID internal. Respons tidak di-cache & tidak diindeks.
    """
    if not allow(f"schedule_share:{client_ip(request)}", 120, 60):
        raise HTTPException(status_code=429, detail="Terlalu banyak permintaan. Mohon coba lagi sebentar lagi.")
    db = get_db()
    share = await share_links.resolve_public_share(db.schedule_shares, token, "jadwal")
    payload = await build_public_schedule(db, share)
    return JSONResponse(safe_doc(payload), headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex, nofollow"})
