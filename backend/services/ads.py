"""services/ads.py — E-ADS: ingest Lead Ads (Meta/Google/TikTok) → lead ber-atribusi (mock-first).

Webhook publik mem-parse payload (fleksibel ATAU envelope platform) menjadi lead di CRM dengan
`channel = {provider}_ads`, first/last touch, dan consent. Auto-assign agent + emit `lead.created`
(memicu otomasi E1/E2: WA ack, nurturing). Belum memanggil API platform mana pun (mock-first).
"""
import logging

from core_utils import new_id, now_iso
from services import attribution as attr
from services.crm import auto_assign_agent, log_activity
from services.events import emit
from services.refs import destination_normalize

logger = logging.getLogger("travel_fleet.ads")

PROVIDERS = {"meta", "google", "tiktok", "facebook"}
_PROVIDER_CHANNEL = {"meta": "meta_ads", "facebook": "meta_ads", "google": "google_ads", "tiktok": "tiktok_ads"}


def _first(d, *keys, default=""):
    for k in keys:
        v = (d or {}).get(k)
        if v not in (None, ""):
            return v
    return default


def parse_lead_payload(provider, payload):
    """Normalisasi payload Lead Ads jadi {name, phone, email, campaign, message, raw_fields}.

    Mendukung bentuk sederhana {name, phone, email, ...} ATAU envelope field_data Meta/Google
    (list {name, values}). Mock-first & toleran.
    """
    p = payload or {}
    fields = {}
    # envelope Meta: {field_data: [{name, values: [..]}]} (kadang dalam entry/changes)
    fd = p.get("field_data")
    if not fd:
        try:
            for entry in p.get("entry", []) or []:
                for ch in entry.get("changes", []) or []:
                    fd = (ch.get("value") or {}).get("field_data") or fd
        except Exception:  # noqa: BLE001
            fd = None
    if isinstance(fd, list):
        for f in fd:
            name = str(f.get("name") or "").lower()
            vals = f.get("values") or f.get("value") or []
            fields[name] = (vals[0] if isinstance(vals, list) and vals else vals)
    # gabung field_data dgn root agar key sederhana tetap terbaca
    src = {**fields, **{k: v for k, v in p.items() if not isinstance(v, (list, dict))}}
    return {
        "name": str(_first(src, "name", "full_name", "nama", default="Lead Iklan")).strip()[:120],
        "phone": str(_first(src, "phone", "phone_number", "whatsapp", "no_hp", default="")).strip()[:40],
        "email": str(_first(src, "email", "e-mail", default="")).strip()[:160],
        "campaign": str(_first(src, "campaign", "campaign_name", "utm_campaign",
                               default=p.get("campaign_name") or "")).strip()[:160],
        "message": str(_first(src, "message", "notes", "pesan", default="")).strip()[:300],
        "destination": str(_first(src, "destination", "destinasi", default="")).strip()[:120],
    }


async def create_ad_lead(db, provider, payload, *, ad_ids=None):
    """Buat lead dari Lead Ads / CTWA. Return {id, status, channel} atau {status:'ignored'}.

    `ad_ids` (F5) membawa atribusi LEVEL IKLAN dari platform: campaign_id/adset_id/ad_id/form_id
    (+ ctwa_clid untuk Klik-ke-WhatsApp). Tanpa ini, ROAS per iklan tidak mungkin dihitung —
    channel saja tidak cukup menjawab "iklan mana yang menghasilkan booking".
    """
    provider = (provider or "").lower()
    channel = _PROVIDER_CHANNEL.get(provider, f"{provider}_ads")
    parsed = parse_lead_payload(provider, payload)
    if not parsed["phone"] and not parsed["email"]:
        return {"status": "ignored", "reason": "tanpa phone/email"}
    ads = dict(ad_ids or {})

    # bangun atribusi: paksa channel = {provider}_ads
    touch_payload = {
        "utm_source": provider, "utm_medium": "paid",
        "utm_campaign": parsed["campaign"] or ads.get("campaign_id", ""),
        "utm_content": ads.get("ad_id", ""),
        "landing_page": ads.get("source_url") or f"lead-ads/{provider}",
    }
    built = attr.build_attribution({"first_touch": touch_payload, "last_touch": touch_payload},
                                   fallback_source=channel)
    built["channel"] = channel
    built["attribution"]["channel"] = channel
    built["attribution"]["first_touch"]["channel"] = channel
    built["attribution"]["last_touch"]["channel"] = channel

    try:
        from services.identity import normalize_phone
        norm = normalize_phone(parsed["phone"]) if parsed["phone"] else ""
    except Exception:  # noqa: BLE001
        norm = parsed["phone"]

    assigned = await auto_assign_agent(db)
    now = now_iso()
    doc = {
        "id": new_id("led"), "customer_name": parsed["name"], "phone": parsed["phone"],
        "phone_normalized": norm, "email": parsed["email"], "source": "ads", "stage": "new",
        "assigned_to": assigned, "trip_date": None, "pax": 0,
        "destination": await destination_normalize(db, parsed["destination"]),
        "message": parsed["message"], "value": 0.0, "quotation_amount": 0,
        "converted_customer_id": None, "linked_customer_id": None,
        "marketing_consent": True, "consent_at": now,  # lead ads = consent eksplisit di form platform
        "created_at": now, "last_activity_at": now,
        # --- atribusi LEVEL IKLAN (F5): dasar perhitungan ROAS per kampanye/adset/iklan ---
        "ad_platform": ads.get("platform") or provider,
        "ad_campaign_id": str(ads.get("campaign_id") or ""),
        "ad_adset_id": str(ads.get("adset_id") or ""),
        "ad_id": str(ads.get("ad_id") or ""),
        "ad_form_id": str(ads.get("form_id") or ""),
        "platform_lead_id": ads.get("platform_lead_id"),
        "ctwa_clid": str(ads.get("ctwa_clid") or ""),
        **built,
    }
    await db.leads.insert_one(doc)
    await log_activity(db, doc["id"], None, "created",
                       text=f"Lead masuk dari {attr.channel_label(channel)}"
                            + (f" · kampanye {parsed['campaign']}" if parsed["campaign"] else ""))
    await emit(db, "lead.created", {
        "lead_id": doc["id"], "customer_name": doc["customer_name"], "phone": doc["phone"],
        "destination": doc["destination"], "source": "ads", "channel": channel,
        "assigned_to": assigned,
    }, source="ads", ref_type="lead", ref_id=doc["id"], dedupe_key=f"lead.created:{doc['id']}")
    return {"id": doc["id"], "status": "received", "channel": channel}
