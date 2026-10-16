"""services/growth.py — CRM Growth: Lead Scoring + SLA + RFM/LTV + Lifecycle (E2).

- Lead score 0–100 (sumber, nilai, kelengkapan, engagement, progres tahap) → band hot/warm/cold.
- SLA respons pertama: `first_response_due_at` dari created_at + jam SLA; status on_track/at_risk/breached.
- RFM/LTV pelanggan dari bookings+payments → segmen (Champions/Loyal/At Risk/…) + lifecycle.
- scan_sla / scan_rfm dipanggil scheduler → memancarkan event lead.sla_breached / customer.at_risk (E1).

Konfigurasi di `settings` key `crm_growth`.
"""
import logging
from datetime import datetime, timedelta, timezone

from core_utils import now_iso
from services.events import emit
from services.geo import parse_iso

logger = logging.getLogger("travel_fleet.growth")

DEFAULT_CONFIG = {
    "sla_first_response_hours": 4,
    "at_risk_days": 45,
    "churn_days": 90,
    "hot_threshold": 65,
    "warm_threshold": 35,
    "source_weights": {"referral": 25, "website": 20, "whatsapp": 18, "instagram": 15,
                        "ads": 15, "manual": 10},
}
RESPONSE_ACTIVITIES = {"call", "whatsapp", "email", "note", "contacted", "stage_change", "assignment"}


async def get_config(db):
    s = await db.settings.find_one({"key": "crm_growth"}, {"_id": 0})
    cfg = dict(DEFAULT_CONFIG)
    if s and isinstance(s.get("value"), dict):
        cfg.update(s["value"])
        merged = dict(DEFAULT_CONFIG["source_weights"])
        merged.update(s["value"].get("source_weights") or {})
        cfg["source_weights"] = merged
    return cfg


def compute_lead_score(lead, cfg, activity_count=0):
    """Return (score 0-100, band, factors)."""
    f = {}
    f["source"] = int((cfg.get("source_weights") or {}).get(lead.get("source") or "manual", 10))
    val = float(lead.get("value") or 0)
    f["value"] = 25 if val >= 5_000_000 else 15 if val >= 2_000_000 else 8 if val >= 1_000_000 else 0
    comp = 0
    comp += 5 if lead.get("phone") else 0
    comp += 5 if lead.get("email") else 0
    comp += 5 if lead.get("destination") else 0
    comp += 5 if lead.get("trip_date") else 0
    f["completeness"] = comp
    f["engagement"] = min(int(activity_count) * 4, 16)
    stage = lead.get("stage")
    f["stage"] = {"contacted": 5, "quoted": 10, "negotiation": 14, "won": 16}.get(stage, 0)
    score = min(sum(f.values()), 100)
    band = "hot" if score >= cfg.get("hot_threshold", 65) else "warm" if score >= cfg.get("warm_threshold", 35) else "cold"
    return score, band, f


def _sla_status(lead, cfg, now=None):
    now = now or datetime.now(timezone.utc)
    if lead.get("first_response_at"):
        return "on_track", lead.get("first_response_due_at")
    created = parse_iso(lead.get("created_at")) or now
    due = created + timedelta(hours=float(cfg.get("sla_first_response_hours", 4)))
    if now >= due:
        status = "breached"
    elif now >= due - timedelta(hours=1):
        status = "at_risk"
    else:
        status = "on_track"
    return status, due.isoformat()


async def apply_lead_growth(db, lead_id, *, mark_response=False):
    """Hitung ulang skor + SLA satu lead; opsi tandai first_response. Defensif (tak raise)."""
    try:
        lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
        if not lead:
            return None
        cfg = await get_config(db)
        updates = {}
        if mark_response and not lead.get("first_response_at"):
            updates["first_response_at"] = now_iso()
            lead["first_response_at"] = updates["first_response_at"]
        act = await db.lead_activities.count_documents({"lead_id": lead_id, "type": {"$ne": "created"}})
        score, band, factors = compute_lead_score(lead, cfg, act)
        status, due = _sla_status(lead, cfg)
        updates.update({"score": score, "score_band": band, "score_factors": factors,
                        "first_response_due_at": due, "sla_status": status})
        await db.leads.update_one({"id": lead_id}, {"$set": updates})
        return updates
    except Exception as exc:  # noqa: BLE001
        logger.warning("apply_lead_growth %s gagal: %s", lead_id, exc)
        return None


async def recompute_all(db):
    """Hitung ulang skor+SLA semua lead terbuka. Return jumlah."""
    from services.crm import OPEN_STAGES
    leads = await db.leads.find({"stage": {"$in": list(OPEN_STAGES)}}, {"_id": 0, "id": 1}).to_list(5000)
    for ld in leads:
        await apply_lead_growth(db, ld["id"])
    return len(leads)


async def scan_sla(db):
    """Tandai lead breach SLA respons pertama + pancarkan lead.sla_breached (1x/hari)."""
    from services.crm import OPEN_STAGES
    cfg = await get_config(db)
    day = datetime.now(timezone.utc).strftime("%Y%m%d")
    leads = await db.leads.find(
        {"stage": {"$in": list(OPEN_STAGES)}, "first_response_at": None}, {"_id": 0}).to_list(5000)
    created = 0
    umap = {u["id"]: u.get("name") for u in await db.users.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(500)}
    for ld in leads:
        status, due = _sla_status(ld, cfg)
        if ld.get("sla_status") != status:
            await db.leads.update_one({"id": ld["id"]}, {"$set": {"sla_status": status, "first_response_due_at": due}})
        if status == "breached":
            n = await emit(db, "lead.sla_breached", {
                "lead_id": ld["id"], "customer_name": ld.get("customer_name"), "phone": ld.get("phone"),
                "assigned_to": ld.get("assigned_to"), "agent_name": umap.get(ld.get("assigned_to")),
                "source": ld.get("source"), "due_at": due,
            }, source="growth", ref_type="lead", ref_id=ld["id"], dedupe_key=f"sla:{ld['id']}:{day}")
            created += 1 if n else 0
    return created


def _rfm_scores(recency_days, frequency, monetary):
    r = 5 if recency_days <= 30 else 4 if recency_days <= 60 else 3 if recency_days <= 120 else 2 if recency_days <= 240 else 1
    fr = 5 if frequency >= 6 else 4 if frequency >= 4 else 3 if frequency >= 2 else 2 if frequency >= 1 else 1
    m = 5 if monetary >= 20_000_000 else 4 if monetary >= 10_000_000 else 3 if monetary >= 4_000_000 else 2 if monetary > 0 else 1
    return r, fr, m


def _rfm_segment(r, f, m):
    if r >= 4 and f >= 4:
        return "Champions"
    if f >= 4:
        return "Loyal"
    if r >= 4 and f <= 2:
        return "Pelanggan Baru"
    if r >= 3 and m >= 3:
        return "Potensial"
    if r <= 2 and f >= 3:
        return "Berisiko (At Risk)"
    if r <= 2 and f <= 2:
        return "Hibernasi/Hilang"
    return "Perlu Perhatian"


async def rfm_for_customer(db, customer, cfg=None, now=None):
    cfg = cfg or await get_config(db)
    now = now or datetime.now(timezone.utc)
    bookings = await db.bookings.find(
        {"customer_id": customer["id"], "status": {"$in": ["confirmed", "ongoing", "completed"]}},
        {"_id": 0, "start_datetime": 1, "paid_amount": 1, "total_amount": 1}).to_list(500)
    freq = len(bookings)
    monetary = sum(float(b.get("paid_amount", 0) or 0) for b in bookings) or float(customer.get("lifetime_value") or 0)
    last_dt = None
    for b in bookings:
        dt = parse_iso(b.get("start_datetime"))
        if dt and (last_dt is None or dt > last_dt):
            last_dt = dt
    base = last_dt or parse_iso(customer.get("created_at")) or now
    recency_days = max((now - base).days, 0)
    r, f, m = _rfm_scores(recency_days, freq, monetary)
    seg = _rfm_segment(r, f, m)
    if freq == 0:
        lifecycle = "prospek"
    elif recency_days > cfg.get("churn_days", 90):
        lifecycle = "churned"
    elif recency_days > cfg.get("at_risk_days", 45):
        lifecycle = "at_risk"
    else:
        lifecycle = "aktif"
    return {"recency_days": recency_days, "frequency": freq, "monetary": round(monetary, 2),
            "r": r, "f": f, "m": m, "rfm_segment": seg, "lifecycle": lifecycle,
            "ltv": round(monetary, 2)}


async def scan_rfm(db):
    """Cache rfm_segment+lifecycle+ltv ke customer; pancarkan customer.at_risk (1x/hari). Return jumlah at-risk baru."""
    cfg = await get_config(db)
    day = datetime.now(timezone.utc).strftime("%Y%m%d")
    customers = await db.customers.find({}, {"_id": 0}).to_list(5000)
    flagged = 0
    for c in customers:
        rfm = await rfm_for_customer(db, c, cfg)
        await db.customers.update_one({"id": c["id"]}, {"$set": {
            "rfm_segment": rfm["rfm_segment"], "lifecycle": rfm["lifecycle"],
            "lifetime_value": rfm["ltv"], "recency_days": rfm["recency_days"],
            "frequency": rfm["frequency"]}})
        if rfm["lifecycle"] in ("at_risk", "churned") and rfm["frequency"] >= 1:
            n = await emit(db, "customer.at_risk", {
                "customer_id": c["id"], "customer_name": c.get("name"), "phone": c.get("phone"),
                "lifecycle": rfm["lifecycle"], "recency_days": rfm["recency_days"],
                "frequency": rfm["frequency"], "ltv": rfm["ltv"],
            }, source="growth", ref_type="customer", ref_id=c["id"], dedupe_key=f"churn:{c['id']}:{day}")
            flagged += 1 if n else 0
    return flagged
