"""services/segments.py — Segmentasi audiens dinamis (E2).

Segment = kriteria tersimpan atas `leads` (audience='lead') atau `customers` ('customer').
Dipakai Kampanye (broadcast nyata) & enroll Sequence. Mengembalikan anggota {target_id,name,phone}.
"""
import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger("travel_fleet.segments")


def build_query(criteria, audience):
    """Susun query Mongo dari kriteria. Field tergantung audience (lead|customer)."""
    c = criteria or {}
    q = {}
    if c.get("q"):
        rx = {"$regex": c["q"], "$options": "i"}
        name_field = "customer_name" if audience == "lead" else "name"
        q["$or"] = [{name_field: rx}, {"phone": rx}]
    if c.get("source"):
        q["source"] = c["source"]
    if c.get("channel"):
        q["channel"] = {"$in": c["channel"]} if isinstance(c["channel"], list) else c["channel"]
    if c.get("marketing_consent") is not None and audience == "lead":
        q["marketing_consent"] = bool(c["marketing_consent"])
    if c.get("stage"):
        q["stage"] = {"$in": c["stage"]} if isinstance(c["stage"], list) else c["stage"]
    if c.get("score_band"):
        q["score_band"] = c["score_band"]
    if c.get("rfm_segment"):
        q["rfm_segment"] = c["rfm_segment"]
    if c.get("lifecycle"):
        q["lifecycle"] = c["lifecycle"]
    if c.get("type"):
        q["type"] = c["type"]
    if c.get("city"):
        q["city"] = {"$regex": c["city"], "$options": "i"}
    if c.get("min_value") is not None:
        field = "value" if audience == "lead" else "lifetime_value"
        q[field] = {"$gte": float(c["min_value"])}
    if c.get("wa_opt_in") is not None:
        # hanya bermakna utk customer/lead dgn flag; lead tak punya → diabaikan jika audience lead
        if audience == "customer":
            q["wa_opt_in"] = {"$ne": False} if c["wa_opt_in"] else False
    if c.get("last_activity_days"):
        field = "last_activity_at" if audience == "lead" else "created_at"
        since = (datetime.now(timezone.utc) - timedelta(days=int(c["last_activity_days"]))).isoformat()
        q[field] = {"$gte": since}
    return q


async def resolve(db, audience, criteria, limit=5000):
    """Return (count, members[{target_id,name,phone}]). Hanya anggota ber-telepon utk WA."""
    col = db.leads if audience == "lead" else db.customers
    q = build_query(criteria, audience)
    name_field = "customer_name" if audience == "lead" else "name"
    proj = {"_id": 0, "id": 1, "phone": 1, name_field: 1}
    docs = await col.find(q, proj).to_list(limit)
    members = [{"target_id": d["id"], "name": d.get(name_field) or "Kontak", "phone": d.get("phone") or ""}
               for d in docs]
    return len(members), members


async def resolve_segment(db, segment, limit=5000):
    return await resolve(db, segment.get("audience", "customer"), segment.get("criteria") or {}, limit)
