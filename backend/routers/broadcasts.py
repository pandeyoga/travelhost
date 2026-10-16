"""routers/broadcasts.py — Broadcast WhatsApp NYATA (via provider WA aktif).

Akses owner/ops_admin (section 'crm'). Segmentasi audiens berbasis koleksi `leads`
(stage/source). Pengiriman berjalan di background dengan JEDA ACAK antar pesan
(anti-banned utk provider nyata openwa/meta_cloud); progres (sent/failed/skipped)
di-update per penerima sehingga UI bisa mem-poll. Provider mock = tanpa jeda.
Pesan mendukung variabel {customer_name} & {company}.
"""
import asyncio
import logging
import random

from fastapi import APIRouter, Depends, HTTPException, Query

from core_utils import new_id, now_iso, safe_doc
from db import get_db
from dependencies import require_section
from schemas import BroadcastCreate, BroadcastUpdate
from services.audit import record

logger = logging.getLogger("travel_fleet.broadcasts")
router = APIRouter(prefix="/api", tags=["broadcasts"])
CRM = require_section("crm")

# Jeda acak antar pesan (detik) utk provider nyata — pola manusiawi, hindari deteksi spam.
THROTTLE_MIN, THROTTLE_MAX = 4.0, 9.0
MAX_RECIPIENTS = 2000


def _segment_query(stage, source):
    q = {}
    if stage:
        q["stage"] = stage
    if source:
        q["source"] = source
    return q


@router.get("/broadcasts")
async def list_broadcasts(limit: int = Query(default=200, le=500), skip: int = Query(default=0, ge=0),
                          user=Depends(CRM)):
    docs = await get_db().broadcasts.find({}, {"_id": 0}).sort("created_at", -1).skip(skip).to_list(limit)
    return safe_doc(docs)


@router.post("/broadcasts")
async def create_broadcast(body: BroadcastCreate, user=Depends(CRM)):
    db = get_db()
    recipients = await db.leads.count_documents(_segment_query(body.segment_stage, body.segment_source))
    doc = {
        "id": new_id("brd"), "title": body.title.strip(), "message": body.message.strip(),
        "segment": {"stage": body.segment_stage, "source": body.segment_source},
        "scheduled_at": body.scheduled_at, "status": "draft",
        "recipients_count": recipients, "created_by": user.get("id"), "created_at": now_iso(),
    }
    await db.broadcasts.insert_one(doc)
    await record(db, actor=user, action="create", entity_type="broadcast", entity_id=doc["id"],
                 summary=f"Buat broadcast '{doc.get('title')}' ({recipients} penerima)")
    return safe_doc(doc)


@router.patch("/broadcasts/{broadcast_id}")
async def update_broadcast(broadcast_id: str, body: BroadcastUpdate, user=Depends(CRM)):
    db = get_db()
    b = await db.broadcasts.find_one({"id": broadcast_id}, {"_id": 0})
    if not b:
        raise HTTPException(status_code=404, detail="Broadcast tidak ditemukan")
    if b.get("status") not in ("draft", "failed"):
        raise HTTPException(status_code=400, detail="Broadcast yang sudah/sedang dikirim tidak bisa diubah")
    updates = {}
    if body.title is not None:
        updates["title"] = body.title.strip()
    if body.message is not None:
        updates["message"] = body.message.strip()
    seg = dict(b.get("segment") or {})
    fields = body.model_fields_set
    if "segment_stage" in fields:
        seg["stage"] = body.segment_stage
    if "segment_source" in fields:
        seg["source"] = body.segment_source
    if "segment_stage" in fields or "segment_source" in fields:
        updates["segment"] = seg
        updates["recipients_count"] = await db.leads.count_documents(_segment_query(seg.get("stage"), seg.get("source")))
    if updates:
        updates["updated_at"] = now_iso()
        await db.broadcasts.update_one({"id": broadcast_id}, {"$set": updates})
    after = await db.broadcasts.find_one({"id": broadcast_id}, {"_id": 0})
    await record(db, actor=user, action="update", entity_type="broadcast", entity_id=broadcast_id,
                 before=b, after=after, summary=f"Ubah broadcast '{after.get('title')}'")
    return safe_doc(after)


@router.delete("/broadcasts/{broadcast_id}")
async def delete_broadcast(broadcast_id: str, user=Depends(CRM)):
    db = get_db()
    b = await db.broadcasts.find_one({"id": broadcast_id}, {"_id": 0})
    if not b:
        raise HTTPException(status_code=404, detail="Broadcast tidak ditemukan")
    if b.get("status") == "sending":
        raise HTTPException(status_code=400, detail="Broadcast sedang dikirim — tunggu selesai")
    await db.broadcasts.delete_one({"id": broadcast_id})
    await record(db, actor=user, action="delete", entity_type="broadcast", entity_id=broadcast_id, before=b,
                 summary=f"Hapus broadcast '{b.get('title')}'")
    return {"ok": True}


async def _run_broadcast(broadcast_id):
    """Worker background: kirim per-penerima via send_wa + jeda anti-banned + progres."""
    db = get_db()
    try:
        b = await db.broadcasts.find_one({"id": broadcast_id}, {"_id": 0})
        if not b:
            return
        seg = b.get("segment") or {}
        q = _segment_query(seg.get("stage"), seg.get("source"))
        q["phone"] = {"$nin": [None, ""]}
        leads = await db.leads.find(q, {"_id": 0, "id": 1, "phone": 1, "customer_name": 1}) \
                              .to_list(MAX_RECIPIENTS)
        from services.whatsapp import get_config, send_wa
        cfg = await get_config(db)
        real = cfg.get("provider") in ("openwa", "meta_cloud")
        sent = failed = skipped = 0
        for i, ld in enumerate(leads):
            try:
                res = await send_wa(db, ld.get("phone"), text=b.get("message"),
                                    variables={"customer_name": ld.get("customer_name") or ""},
                                    lead_id=ld.get("id"), contact_name=ld.get("customer_name"),
                                    source="broadcast")
                st = res.get("status")
                if st in ("sent", "delivered", "read"):
                    sent += 1
                elif st == "skipped":
                    skipped += 1
                else:
                    failed += 1
            except Exception as exc:  # noqa: BLE001
                logger.warning("broadcast %s kirim gagal: %s", broadcast_id, exc)
                failed += 1
            await db.broadcasts.update_one({"id": broadcast_id}, {"$set": {
                "sent_count": sent, "failed_count": failed, "skipped_count": skipped}})
            if real and i < len(leads) - 1:
                await asyncio.sleep(random.uniform(THROTTLE_MIN, THROTTLE_MAX))
        await db.broadcasts.update_one({"id": broadcast_id}, {"$set": {
            "status": "sent", "sent_at": now_iso(), "recipients_count": len(leads),
            "sent_count": sent, "failed_count": failed, "skipped_count": skipped}})
        logger.info("broadcast %s selesai: sent=%d failed=%d skipped=%d",
                    broadcast_id, sent, failed, skipped)
    except Exception as exc:  # noqa: BLE001
        logger.warning("broadcast %s worker error: %s", broadcast_id, exc)
        await db.broadcasts.update_one({"id": broadcast_id}, {"$set": {
            "status": "failed", "error": str(exc)[:200]}})


async def reap_stale_sending():
    """Startup: broadcast 'sending' yatim (worker mati saat restart/reload) → failed,
    supaya tombol Kirim Ulang muncul dan UI tidak polling selamanya."""
    db = get_db()
    r = await db.broadcasts.update_many(
        {"status": "sending"},
        {"$set": {"status": "failed",
                  "error": "Terputus saat backend restart — silakan Kirim Ulang"}})
    if r.modified_count:
        logger.warning("reap %d broadcast 'sending' yatim → failed", r.modified_count)


@router.post("/broadcasts/{broadcast_id}/send")
async def send_broadcast(broadcast_id: str, user=Depends(CRM)):
    db = get_db()
    # Klaim atomik draft/failed → sending: klik ganda / dua admin tidak menggandakan kiriman.
    b = await db.broadcasts.find_one_and_update(
        {"id": broadcast_id, "status": {"$in": ["draft", "failed"]}},
        {"$set": {"status": "sending", "send_started_at": now_iso(),
                  "sent_count": 0, "failed_count": 0, "skipped_count": 0, "error": None}})
    if not b:
        if not await db.broadcasts.find_one({"id": broadcast_id}, {"_id": 1}):
            raise HTTPException(status_code=404, detail="Broadcast tidak ditemukan")
        raise HTTPException(status_code=400, detail="Broadcast sudah/sedang dikirim")
    seg = b.get("segment") or {}
    q = _segment_query(seg.get("stage"), seg.get("source"))
    q["phone"] = {"$nin": [None, ""]}
    recipients = await db.leads.count_documents(q)
    await db.broadcasts.update_one({"id": broadcast_id}, {"$set": {"recipients_count": recipients}})
    asyncio.create_task(_run_broadcast(broadcast_id))
    await record(db, actor=user, action="send", entity_type="broadcast", entity_id=broadcast_id,
                 summary=f"Mulai kirim broadcast '{b.get('title')}' ke {recipients} penerima")
    return safe_doc(await db.broadcasts.find_one({"id": broadcast_id}, {"_id": 0}))
