"""services/campaigns.py — Kampanye WhatsApp nyata (broadcast tersegmentasi) (E2).

Kampanye menarget Segment → buat campaign_recipients → kirim per-penerima via E1 (send_wa, mock).
Hormati opt-out (skipped_optout), lacak status & biaya per penerima + agregat. Scheduler kirim
kampanye terjadwal. Idempotent: hanya status draft/scheduled yang boleh dikirim.
"""
import logging
from datetime import datetime, timezone

from core_utils import new_id, now_iso
from services import segments as seg_svc

logger = logging.getLogger("travel_fleet.campaigns")


async def _members_for(db, campaign):
    if campaign.get("segment_id"):
        seg = await db.segments.find_one({"id": campaign["segment_id"]}, {"_id": 0})
        if seg:
            return await seg_svc.resolve_segment(db, seg)
    snap = campaign.get("segment_snapshot") or {}
    return await seg_svc.resolve(db, snap.get("audience", "customer"), snap.get("criteria") or {})


async def send_campaign(db, campaign):
    """Kirim kampanye sekarang. Return statistik. Idempotent (tolak bila sudah sent/sending)."""
    if campaign.get("status") in ("sending", "sent"):
        return {"error": "Kampanye sudah dikirim/sedang berjalan"}
    cid = campaign["id"]
    await db.campaigns.update_one({"id": cid}, {"$set": {"status": "sending"}})
    _, members = await _members_for(db, campaign)
    from services.whatsapp import send_wa
    stats = {"total": len(members), "sent": 0, "failed": 0, "skipped": 0, "cost": 0.0}
    for m in members:
        phone = m.get("phone")
        if not phone:
            stats["skipped"] += 1
            rec_status, cost, conv_id, msg_id, err = "skipped_optout", 0.0, None, None, "tanpa telepon"
        else:
            res = await send_wa(db, phone, text=campaign.get("message"),
                                template_key=campaign.get("template_key"),
                                variables={"name": m.get("name"), "customer_name": m.get("name")},
                                customer_id=m["target_id"] if campaign.get("audience") == "customer" else None,
                                lead_id=m["target_id"] if campaign.get("audience") == "lead" else None,
                                contact_name=m.get("name"), source=f"campaign:{cid}")
            st = res.get("status")
            cost, conv_id, msg_id, err = float(res.get("cost") or 0), res.get("conversation_id"), res.get("message_id"), res.get("error")
            if st in ("sent", "delivered", "read"):
                rec_status = "sent"; stats["sent"] += 1; stats["cost"] += cost
            elif st == "skipped":
                rec_status = "skipped_optout"; stats["skipped"] += 1
            else:
                rec_status = "failed"; stats["failed"] += 1
        await db.campaign_recipients.insert_one({
            "id": new_id("cre"), "campaign_id": cid, "target_id": m["target_id"], "name": m.get("name"),
            "phone": phone, "status": rec_status, "cost": cost, "conversation_id": conv_id,
            "message_id": msg_id, "error": err, "created_at": now_iso()})
    await db.campaigns.update_one({"id": cid}, {"$set": {
        "status": "sent", "sent_at": now_iso(), "stats": stats}})
    return stats


async def process_scheduled(db):
    """Kirim kampanye berstatus 'scheduled' yang waktunya tiba. Return jumlah kampanye terkirim."""
    now_s = datetime.now(timezone.utc).isoformat()
    due = await db.campaigns.find(
        {"status": "scheduled", "scheduled_at": {"$lte": now_s}}, {"_id": 0}).to_list(100)
    sent = 0
    for c in due:
        await send_campaign(db, c)
        sent += 1
    return sent
