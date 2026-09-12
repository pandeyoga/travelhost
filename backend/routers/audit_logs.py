"""routers/audit_logs.py — Audit Log viewer (Phase 8 / A1).

GET /api/audit-logs — daftar jejak audit (terbaru dulu). Akses section 'audit'
(owner-only). Append-only: TIDAK ada endpoint tulis/ubah/hapus via API.
Filter: entity_type, action, q (cari di summary/aktor/entity), limit, skip.
"""
from fastapi import APIRouter, Depends, Query

from core_utils import safe_doc
from db import get_db
from dependencies import require_section

router = APIRouter(prefix="/api", tags=["audit_logs"])
AUDIT = require_section("audit")


@router.get("/audit-logs")
async def list_audit_logs(
    entity_type: str = Query(default=None),
    action: str = Query(default=None),
    q: str = Query(default=None),
    limit: int = Query(default=100, le=500),
    skip: int = Query(default=0, ge=0),
    user=Depends(AUDIT),
):
    query = {}
    if entity_type:
        query["entity_type"] = entity_type
    if action:
        query["action"] = action
    if q:
        rx = {"$regex": q, "$options": "i"}
        query["$or"] = [
            {"summary": rx}, {"actor_name": rx},
            {"entity_id": rx}, {"entity_type": rx},
        ]
    docs = await get_db().audit_logs.find(query, {"_id": 0}).sort("timestamp", -1).skip(skip).to_list(limit)
    return safe_doc(docs)
