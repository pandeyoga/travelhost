"""routers/shares.py — Share-link korporat untuk tracking trip (Phase 6).

Membuat tautan publik (token rahasia) berbatas waktu (expiry) yang bisa dibagikan ke
customer korporat untuk memantau posisi armada TANPA login. Bisa di-revoke.
Konsumsi publik: GET /api/public/track/{token} (lihat routers/public.py).
Semua mutasi: owner/ops_admin (MANAGER).
"""
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query

from core_utils import new_id, now_iso, safe_doc
from db import get_db
from dependencies import require_role
from schemas import ShareCreate
from services.geo import parse_iso

router = APIRouter(prefix="/api", tags=["shares"])
MANAGER = require_role("owner", "ops_admin")


def _enrich(s):
    now = datetime.now(timezone.utc)
    exp = parse_iso(s.get("expires_at"))
    s["expired"] = bool(exp and exp <= now)
    s["is_active"] = (not s.get("revoked")) and not s["expired"]
    return s


@router.get("/shares")
async def list_shares(active: bool = Query(default=None), trip_id: str = Query(default=None),
                      limit: int = Query(default=500, le=1000), skip: int = Query(default=0, ge=0),
                      user=Depends(MANAGER)):
    db = get_db()
    query = {}
    if trip_id:
        query["trip_id"] = trip_id
    docs = await db.trip_shares.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).to_list(limit)
    out = [_enrich(s) for s in docs]
    if active is True:
        out = [s for s in out if s["is_active"]]
    return safe_doc(out)


@router.post("/shares")
async def create_share(body: ShareCreate, user=Depends(MANAGER)):
    db = get_db()
    trip = await db.trips.find_one({"id": body.trip_id}, {"_id": 0})
    if not trip:
        raise HTTPException(status_code=404, detail="Trip tidak ditemukan")
    hours = min(max(int(body.hours or 72), 1), 24 * 30)
    veh = None
    if trip.get("vehicle_id"):
        veh = await db.vehicles.find_one({"id": trip["vehicle_id"]}, {"_id": 0})
    doc = {
        "id": new_id("shr"), "token": secrets.token_urlsafe(24),
        "trip_id": body.trip_id, "vehicle_id": trip.get("vehicle_id"),
        "vehicle_name": veh.get("name") if veh else None,
        "label": (body.label or "").strip() or (veh.get("name") if veh else "Tracking Armada"),
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat(),
        "revoked": False, "revoked_at": None,
        "last_accessed_at": None, "access_count": 0,
        "created_by": user["id"], "created_at": now_iso(),
    }
    await db.trip_shares.insert_one(doc)
    return safe_doc(_enrich(doc))


@router.post("/shares/{share_id}/revoke")
async def revoke_share(share_id: str, user=Depends(MANAGER)):
    db = get_db()
    s = await db.trip_shares.find_one({"id": share_id}, {"_id": 0})
    if not s:
        raise HTTPException(status_code=404, detail="Tautan tidak ditemukan")
    await db.trip_shares.update_one(
        {"id": share_id}, {"$set": {"revoked": True, "revoked_at": now_iso()}})
    doc = await db.trip_shares.find_one({"id": share_id}, {"_id": 0})
    return safe_doc(_enrich(doc))


@router.delete("/shares/{share_id}")
async def delete_share(share_id: str, user=Depends(MANAGER)):
    db = get_db()
    if not await db.trip_shares.find_one({"id": share_id}, {"_id": 0}):
        raise HTTPException(status_code=404, detail="Tautan tidak ditemukan")
    await db.trip_shares.delete_one({"id": share_id})
    return {"deleted": True, "id": share_id}
