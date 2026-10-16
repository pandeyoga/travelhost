"""routers/notifications.py — Notification Center + pemicu scan (Phase 7).

Notifikasi in-app untuk semua role login (difilter via services.notifications.visibility_query).
`/scan` memicu mesin reminder manual (owner/ops_admin) — di runtime juga dijalankan
scheduler loop di server.py. Urutan rute: literal sebelum berparameter.
"""
from fastapi import APIRouter, Depends, HTTPException, Query

from core_utils import now_iso, safe_doc
from db import get_db
from dependencies import get_current_user, require_role
from services.notifications import scan, visibility_query

router = APIRouter(prefix="/api", tags=["notifications"])
MANAGER = require_role("owner", "ops_admin")


@router.get("/notifications")
async def list_notifications(status: str = Query(default=None), limit: int = Query(default=50, le=200),
                             user=Depends(get_current_user)):
    q = visibility_query(user)
    if status:
        q = {"$and": [q, {"status": status}]}
    docs = await get_db().notification_tasks.find(q, {"_id": 0}).sort("created_at", -1).to_list(limit)
    return safe_doc(docs)


@router.get("/notifications/unread_count")
async def unread_count(user=Depends(get_current_user)):
    q = {"$and": [visibility_query(user), {"status": "pending"}]}
    return {"count": await get_db().notification_tasks.count_documents(q)}


@router.post("/notifications/scan")
async def trigger_scan(user=Depends(MANAGER)):
    created = await scan(get_db())
    return {"created": created}


@router.post("/notifications/read_all")
async def read_all(user=Depends(get_current_user)):
    q = {"$and": [visibility_query(user), {"status": "pending"}]}
    res = await get_db().notification_tasks.update_many(
        q, {"$set": {"status": "read", "read_at": now_iso()}})
    return {"updated": res.modified_count}


@router.post("/notifications/{notification_id}/read")
async def mark_read(notification_id: str, user=Depends(get_current_user)):
    db = get_db()
    # Hanya boleh menandai baca notifikasi yang memang terlihat oleh user (visibility).
    q = {"$and": [visibility_query(user), {"id": notification_id}]}
    n = await db.notification_tasks.find_one(q, {"_id": 0})
    if not n:
        raise HTTPException(status_code=404, detail="Notifikasi tidak ditemukan")
    await db.notification_tasks.update_one(
        {"id": notification_id}, {"$set": {"status": "read", "read_at": now_iso()}})
    return safe_doc(await db.notification_tasks.find_one({"id": notification_id}, {"_id": 0}))


@router.post("/notifications/{notification_id}/dismiss")
async def dismiss(notification_id: str, user=Depends(get_current_user)):
    db = get_db()
    # Hanya boleh menutup notifikasi yang terlihat oleh user (visibility).
    q = {"$and": [visibility_query(user), {"id": notification_id}]}
    if not await db.notification_tasks.find_one(q, {"_id": 1}):
        raise HTTPException(status_code=404, detail="Notifikasi tidak ditemukan")
    await db.notification_tasks.update_one(
        {"id": notification_id}, {"$set": {"status": "dismissed"}})
    return {"dismissed": True, "id": notification_id}
