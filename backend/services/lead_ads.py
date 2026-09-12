"""services/lead_ads.py — akuisisi lead langsung dari platform (Meta Lead Ads) + CTWA.

Tiga jalur iklan yang dipakai bisnis ini (keputusan user) ditutup di sini:
  1. **Lead Ads** — form di dalam Facebook/Instagram. Tidak ada kunjungan web, jadi TIDAK ada
     `fbclid`. Atribusi datang dari webhook: `campaign_id`, `adgroup_id`(=adset), `ad_id`, `form_id`.
     Keamanan: `X-Hub-Signature-256` = HMAC-SHA256(app_secret, RAW body) — payload tanpa tanda
     tangan sah DITOLAK (tanpa itu siapa pun bisa menyuntik lead palsu ke CRM).
     Ketahanan: dedup `leadgen_id` (koleksi `platform_leads`, unique) + backfill per form.
  2. **Klik-ke-WhatsApp (CTWA)** — pesan WA masuk membawa objek `referral`
     (`source_id` = ad_id, `ctwa_clid`, `source_url`, `headline`). `ctwa_clid` disimpan MENTAH
     (bukan PII) dan dipakai saat mengirim konversi `action_source=business_messaging`.
  3. Traffic web/landing page sudah ditangani `services/attribution.py`.
"""
import hashlib
import hmac
import logging

from core_utils import new_id, now_iso
from services import ads_metrics

logger = logging.getLogger("travel_fleet.lead_ads")

COLL = "platform_leads"
FIELD_ALIASES = {
    "name": ("full_name", "name", "nama", "nama_lengkap", "first_name"),
    "phone": ("phone_number", "phone", "whatsapp", "no_hp", "nomor_whatsapp", "telepon"),
    "email": ("email", "e-mail", "work_email"),
    "destination": ("destination", "destinasi", "tujuan", "kota_tujuan"),
    "message": ("message", "pesan", "notes", "catatan"),
    "trip_date": ("trip_date", "tanggal", "tanggal_berangkat", "date"),
    "pax": ("pax", "jumlah_orang", "jumlah_peserta"),
}


async def ensure_indexes(db):
    await db[COLL].create_index("leadgen_id", unique=True, name="uniq_leadgen")
    await db[COLL].create_index([("created_at", -1)], name="platform_lead_recent")


def verify_signature(app_secret: str, raw_body: bytes, header: str) -> bool:
    """Verifikasi HMAC-SHA256 Meta atas RAW body. Tanpa app secret -> tolak (fail-closed)."""
    if not app_secret or not header:
        return False
    supplied = str(header).strip()
    if supplied.startswith("sha256="):
        supplied = supplied[7:]
    expected = hmac.new(app_secret.encode(), raw_body or b"", hashlib.sha256).hexdigest()
    try:
        return hmac.compare_digest(supplied, expected)
    except Exception:  # noqa: BLE001
        return False


def sign_payload(app_secret: str, raw_body: bytes) -> str:
    """Dipakai simulator internal (uji tanpa kredensial nyata) & pengujian otomatis."""
    return "sha256=" + hmac.new((app_secret or "").encode(), raw_body or b"",
                                hashlib.sha256).hexdigest()


def parse_leadgen(payload) -> list:
    """Ambil semua notifikasi `leadgen` dari envelope webhook Meta."""
    out = []
    for entry in (payload or {}).get("entry", []) or []:
        for change in entry.get("changes", []) or []:
            if change.get("field") != "leadgen":
                continue
            value = change.get("value") or {}
            leadgen_id = str(value.get("leadgen_id") or "").strip()
            if not leadgen_id:
                continue
            out.append({
                "leadgen_id": leadgen_id,
                "form_id": str(value.get("form_id") or ""),
                "page_id": str(value.get("page_id") or entry.get("id") or ""),
                "ad_id": str(value.get("ad_id") or ""),
                "adset_id": str(value.get("adgroup_id") or value.get("adset_id") or ""),
                "campaign_id": str(value.get("campaign_id") or ""),
                "created_time": value.get("created_time"),
            })
    return out


def parse_field_data(field_data) -> dict:
    """`field_data:[{name, values:[..]}]` -> dict lead yang bisa dipakai CRM."""
    raw = {}
    for item in field_data or []:
        key = str(item.get("name") or "").strip().lower()
        values = item.get("values") or item.get("value") or []
        value = values[0] if isinstance(values, list) and values else values
        if key:
            raw[key] = "" if value is None else str(value).strip()
    out = {}
    for target, aliases in FIELD_ALIASES.items():
        for alias in aliases:
            if raw.get(alias):
                out[target] = raw[alias]
                break
    out["raw_fields"] = raw
    return out


def parse_wa_referral(message) -> dict:
    """Ambil atribusi iklan dari pesan WhatsApp inbound (Klik-ke-WhatsApp)."""
    referral = (message or {}).get("referral") or {}
    if not referral:
        return {}
    if str(referral.get("source_type") or "").lower() not in ("ad", "post", ""):
        return {}
    ctwa = str(referral.get("ctwa_clid") or "").strip()
    ad_id = str(referral.get("source_id") or "").strip()
    if not ctwa and not ad_id:
        return {}
    return {"ctwa_clid": ctwa, "ad_id": ad_id, "ad_platform": "meta",
            "source_url": str(referral.get("source_url") or "")[:300],
            "headline": str(referral.get("headline") or "")[:200],
            "body": str(referral.get("body") or "")[:300],
            "source_type": str(referral.get("source_type") or "ad")}


async def already_ingested(db, leadgen_id: str) -> bool:
    return bool(await db[COLL].find_one({"leadgen_id": str(leadgen_id)}, {"_id": 1}))


async def ingest(db, notice: dict, *, fetch=None, provider: str = "meta") -> dict:
    """Proses satu notifikasi Lead Ads: dedup -> ambil isi -> buat lead CRM ber-atribusi.

    `fetch(leadgen_id)` opsional: coroutine yang mengembalikan `{status, data}` dari Graph API.
    Tanpa `fetch` (atau bila gagal), lead tetap dicatat sebagai `pending_fields` — JANGAN buang
    notifikasi, karena isinya masih bisa di-backfill nanti.
    """
    leadgen_id = str((notice or {}).get("leadgen_id") or "").strip()
    if not leadgen_id:
        return {"status": "ignored", "reason": "leadgen_id kosong"}
    if await already_ingested(db, leadgen_id):
        return {"status": "duplicate", "leadgen_id": leadgen_id}

    parsed, fetch_status, fetch_reason = {}, "skipped", ""
    if fetch is not None:
        res = await fetch(leadgen_id)
        fetch_status = res.get("status", "error")
        fetch_reason = res.get("reason", "")
        if fetch_status == "ok":
            data = res.get("data") or {}
            parsed = parse_field_data(data.get("field_data"))
            for key in ("ad_id", "adset_id", "campaign_id", "form_id"):
                if data.get(key):
                    notice[key] = str(data[key])

    doc = {"id": new_id("plead"), "provider": provider, "leadgen_id": leadgen_id,
           "form_id": notice.get("form_id", ""), "page_id": notice.get("page_id", ""),
           "ad_id": notice.get("ad_id", ""), "adset_id": notice.get("adset_id", ""),
           "campaign_id": notice.get("campaign_id", ""),
           "fields": parsed, "fetch_status": fetch_status, "fetch_reason": fetch_reason,
           "lead_id": None, "created_at": now_iso()}
    try:
        await db[COLL].insert_one(dict(doc))
    except Exception as exc:  # noqa: BLE001  (unique index = pengiriman ganda webhook)
        logger.info("platform lead %s sudah ada: %s", leadgen_id, exc)
        return {"status": "duplicate", "leadgen_id": leadgen_id}

    await ads_metrics.record_touch(db, {
        "click_id": f"leadgen:{leadgen_id}", "provider": provider, "kind": "lead_form",
        "ad_id": doc["ad_id"], "adset_id": doc["adset_id"], "campaign_id": doc["campaign_id"]})

    lead_id = None
    if parsed.get("phone") or parsed.get("email"):
        from services.ads import create_ad_lead
        created = await create_ad_lead(db, provider, {
            "name": parsed.get("name") or "Lead Iklan",
            "phone": parsed.get("phone", ""), "email": parsed.get("email", ""),
            "destination": parsed.get("destination", ""),
            "message": parsed.get("message", ""),
        }, ad_ids={"campaign_id": doc["campaign_id"], "adset_id": doc["adset_id"],
                   "ad_id": doc["ad_id"], "platform": provider,
                   "form_id": doc["form_id"], "platform_lead_id": doc["id"]})
        lead_id = created.get("id")
        if lead_id:
            await db[COLL].update_one({"leadgen_id": leadgen_id}, {"$set": {"lead_id": lead_id}})
    return {"status": "received", "leadgen_id": leadgen_id, "lead_id": lead_id,
            "platform_lead_id": doc["id"], "fetch_status": fetch_status,
            "has_fields": bool(parsed.get("phone") or parsed.get("email"))}


async def recent(db, *, limit=50):
    return await db[COLL].find({}, {"_id": 0}).sort("created_at", -1).to_list(limit)
