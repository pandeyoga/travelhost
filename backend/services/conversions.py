"""services/conversions.py — konversi server-side ke Meta CAPI & Google Data Manager.

Mengapa server-side (bukan hanya pixel): browser diblokir adblock/ITP, dan yang benar-benar
bernilai bagi bisnis ini adalah konversi yang HANYA diketahui backend — booking dikonfirmasi
dan DP masuk. Tiga konversi yang dilaporkan: lead terkirim, booking confirmed, pembayaran/DP
diterima (nilai IDR).

Keputusan penting sesuai dokumentasi resmi (riset 10 Agu 2026, playbook F3):
  - Meta: POST {graph}/{DATASET_ATAU_PIXEL_ID}/events pada **Graph v26.0**. `event_id` WAJIB sama
    dengan yang dikirim pixel browser agar Meta men-dedup (jendela 48 jam) -> event_id dibentuk
    dari ID BISNIS (`lead_<id>`, `booking_<id>`, `payment_<id>`), bukan UUID acak.
    `appsecret_proof` disertakan bila app secret tersedia.
  - Meta / Klik-ke-WhatsApp (CTWA): konversi dari percakapan WA memakai
    `action_source="business_messaging"` + `messaging_channel="whatsapp"` +
    `user_data.ctwa_clid` (TIDAK di-hash) + `whatsapp_business_account_id`.
  - Google: impor konversi offline & Enhanced Conversions for Leads memakai **Data Manager API**
    (`datamanager.googleapis.com/v1/events:ingest`). Bentuk payload yang BENAR:
    `destinations[].operatingAccount.accountType` (BUKAN `product`), root `encoding: "HEX"`,
    `consent` bernilai `GRANTED`/`DENIED` (BUKAN `CONSENT_GRANTED`), setiap event menunjuk
    `destinationReferences`. `validateOnly` = fast-fail (tidak ada partialFailure).
  - Semua PII (email/telepon) di-SHA-256 setelah dinormalkan (`services/pii.py`); nilai uang
    integer IDR; click id TIDAK PERNAH di-hash.

Outbox (koleksi `conversion_events`) memastikan TIDAK ADA konversi hilang diam-diam:
  unique index (provider, event_key) -> idempoten walau event bus mengirim dua kali/paralel;
  status: pending -> success | failed(+retry backoff) -> dead | skipped(kredensial kosong).
Dijaga guardrail INV-CONV-01.
"""
import logging
from datetime import datetime, timedelta, timezone

import httpx
from pymongo.errors import DuplicateKeyError

from core_utils import new_id, now_iso
from services import pii
from services.google_ads import DATA_MANAGER_URL, GoogleAdsClient
from services.meta_ads import DEFAULT_VERSION as META_VERSION
from services.meta_ads import GRAPH, appsecret_proof

logger = logging.getLogger("travel_fleet.conversions")

COLL = "conversion_events"
MAX_ATTEMPTS = 5
BACKOFF_SECONDS = [60, 300, 900, 3600, 10800]

# Peta event bisnis -> nama event platform (SSOT tunggal supaya browser & server tak melenceng).
EVENT_MAP = {
    "lead": {"meta": "Lead", "google_key": "lead_submitted", "ga4": "generate_lead"},
    "booking": {"meta": "Purchase", "google_key": "booking_confirmed", "ga4": "purchase"},
    "payment": {"meta": "Purchase", "google_key": "deposit_received", "ga4": "purchase"},
}
PROVIDERS = ("meta", "google", "ga4")
ACTION_SOURCE_WEB = "website"
ACTION_SOURCE_MESSAGING = "business_messaging"
DM_REFERENCE = "ads_conversion"


def sha256_email(value: str) -> str:
    return pii.hash_email(value)


def sha256_phone(value: str, default_cc: str = "62") -> str:
    return pii.hash_phone_meta(value, cc=default_cc)


def event_key(kind: str, ref_id: str) -> str:
    """ID bisnis untuk dedup lintas browser<->server (dipakai juga oleh pixel di frontend)."""
    return f"{kind}_{ref_id}"


async def ensure_indexes(db):
    await db[COLL].create_index([("provider", 1), ("event_key", 1)], unique=True, name="uniq_provider_event")
    await db[COLL].create_index([("status", 1), ("next_retry_at", 1)], name="queue_scan")
    await db[COLL].create_index([("created_at", -1)], name="recent")


async def enqueue(db, kind: str, ref_id: str, *, value=0, currency="IDR", identifiers=None,
                  source_url="", meta_extra=None, providers=PROVIDERS, channel="",
                  action_source="", consent_granted=None):
    """Catat niat mengirim konversi. Idempoten: pemanggilan ulang TIDAK membuat duplikat."""
    if kind not in EVENT_MAP:
        raise ValueError(f"Jenis konversi tak dikenal: {kind}")
    key = event_key(kind, ref_id)
    ident = dict(identifiers or {})
    resolved_source = action_source or (ACTION_SOURCE_MESSAGING if ident.get("ctwa_clid")
                                       else ACTION_SOURCE_WEB)
    created = []
    for provider in providers:
        doc = {
            "id": new_id("cvn"), "provider": provider, "event_key": key, "kind": kind,
            "ref_id": str(ref_id),
            "event_name": EVENT_MAP[kind]["meta"] if provider == "meta" else EVENT_MAP[kind]["google_key"],
            "value": int(float(value or 0)), "currency": currency or "IDR",
            "identifiers": ident, "source_url": source_url or "",
            "meta_extra": meta_extra or {}, "channel": channel or "",
            "action_source": resolved_source,
            "consent_granted": None if consent_granted is None else bool(consent_granted),
            "status": "pending", "attempts": 0, "http_status": None, "response": None,
            "last_error": None, "next_retry_at": None,
            "created_at": now_iso(), "updated_at": now_iso(),
        }
        try:
            await db[COLL].insert_one(doc)
            created.append(provider)
        except DuplicateKeyError:
            logger.info("Konversi %s/%s sudah ada — dilewati (idempoten)", provider, key)
    return {"event_key": key, "created": created}


def build_meta_payload(cfg: dict, secrets: dict, ev: dict, *, test: bool = False) -> dict:
    ident = ev.get("identifiers") or {}
    user_data = {}
    if ident.get("email"):
        user_data["em"] = [pii.hash_email(ident["email"])]
    if ident.get("phone"):
        user_data["ph"] = [pii.hash_phone_meta(ident["phone"])]
    for src, dst in (("fbp", "fbp"), ("fbc", "fbc"), ("ip", "client_ip_address"),
                     ("user_agent", "client_user_agent")):
        if ident.get(src):
            user_data[dst] = ident[src]
    if ident.get("external_id"):
        user_data["external_id"] = [pii.sha256_hex(str(ident["external_id"]))]
    action_source = ev.get("action_source") or (
        ACTION_SOURCE_MESSAGING if ident.get("ctwa_clid") else ACTION_SOURCE_WEB)
    if ident.get("ctwa_clid"):
        # click id percakapan: JANGAN di-hash (bukan PII, ini penanda klik iklan)
        user_data["ctwa_clid"] = ident["ctwa_clid"]
        waba = cfg.get("waba_id") or ident.get("waba_id") or ""
        if waba:
            user_data["whatsapp_business_account_id"] = str(waba)
    event = {
        "event_name": ev.get("event_name"),
        "event_time": int(datetime.now(timezone.utc).timestamp()),
        "event_id": ev.get("event_key"),
        "action_source": action_source,
        "user_data": user_data,
    }
    if action_source == ACTION_SOURCE_MESSAGING:
        event["messaging_channel"] = "whatsapp"
    elif ev.get("source_url"):
        event["event_source_url"] = ev["source_url"]
    if int(ev.get("value") or 0) > 0:
        event["custom_data"] = {"value": int(ev["value"]), "currency": ev.get("currency") or "IDR"}
    body = {"data": [event]}
    code = (secrets or {}).get("test_event_code") or ""
    if test and code:
        body["test_event_code"] = code
    if cfg.get("ldu_enabled"):
        body.update({"data_processing_options": ["LDU"],
                     "data_processing_options_country": 0, "data_processing_options_state": 0})
    return body


def _consent_block(granted: bool) -> dict:
    value = "GRANTED" if granted else "DENIED"
    return {"adUserData": value, "adPersonalization": value}


def build_google_payload(cfg: dict, ev: dict, *, test: bool = False) -> dict:
    """Bentuk payload Data Manager API v1 `events:ingest` (field sesuai dok resmi terbaru)."""
    ident = ev.get("identifiers") or {}
    action_ids = cfg.get("conversion_action_ids") or {}
    action_id = action_ids.get(ev.get("event_name")) or ""
    granted = ev.get("consent_granted")
    if granted is None:
        granted = cfg.get("consent_granted")
    granted = True if granted is None else bool(granted)
    consent = _consent_block(granted)

    destination = {
        "reference": DM_REFERENCE,
        "operatingAccount": {"accountType": "GOOGLE_ADS",
                             "accountId": pii.digits_only(cfg.get("customer_id"))},
        "productDestinationId": str(action_id),
    }
    login_id = pii.digits_only(cfg.get("login_customer_id"))
    if login_id:
        destination["loginAccount"] = {"accountType": "GOOGLE_ADS", "accountId": login_id}

    ad_ids = {}
    for key in ("gclid", "wbraid", "gbraid"):
        if ident.get(key):
            ad_ids[key] = ident[key]
            break
    identifiers = []
    if ident.get("email"):
        identifiers.append({"emailAddress": pii.hash_email(ident["email"])})
    if ident.get("phone"):
        identifiers.append({"phoneNumber": pii.hash_phone_google(ident["phone"])})

    event = {
        "destinationReferences": [DM_REFERENCE],
        "transactionId": ev.get("event_key"),
        "eventTimestamp": datetime.now(timezone.utc).isoformat(),
        "conversionValue": int(ev.get("value") or 0),
        "currency": ev.get("currency") or "IDR",
        "eventSource": (ev.get("meta_extra") or {}).get("event_source") or "WEB",
        "consent": consent,
    }
    if ad_ids:
        event["adIdentifiers"] = ad_ids
    if identifiers:
        event["userData"] = {"userIdentifiers": identifiers}
    body = {"destinations": [destination], "encoding": "HEX", "consent": consent,
            "events": [event]}
    if test:
        body["validateOnly"] = True
    return body


def _reason_not_ready(provider: str, cfg: dict, secrets: dict) -> str:
    if not cfg.get("enabled"):
        return "Integrasi belum diaktifkan di Pengaturan → Integrasi."
    if provider == "meta":
        if not (cfg.get("dataset_id") or cfg.get("pixel_id")):
            return "Pixel ID / Dataset ID Meta belum diisi."
        if not (secrets.get("access_token") or secrets.get("system_user_token")):
            return "Access token Meta belum diisi."
    if provider == "ga4":
        # GA4 memakai kredensial Google yang sama, tetapi syaratnya BEDA: hanya butuh
        # Measurement ID + API secret. Dipisahkan supaya GA4 tetap bisa jalan walau Google Ads
        # (customer_id/refresh token) belum diisi — dan sebaliknya.
        if not cfg.get("ga4_measurement_id"):
            return "GA4 Measurement ID (G-XXXX) belum diisi."
        if not secrets.get("ga4_api_secret"):
            return "GA4 API secret belum diisi (GA4 Admin → Data Streams → Measurement Protocol)."
        return ""
    if provider == "google":
        if not cfg.get("customer_id"):
            return "Customer ID Google Ads belum diisi."
        if not secrets.get("oauth_refresh_token"):
            return "Refresh token OAuth Google belum diisi."
        if not (cfg.get("conversion_action_ids") or {}):
            return "ID conversion action Google belum dipetakan."
    return ""


def meta_dataset_id(cfg: dict) -> str:
    return str((cfg or {}).get("dataset_id") or (cfg or {}).get("pixel_id") or "")


async def _send_meta(cfg, secrets, ev, test):
    version = cfg.get("api_version") or META_VERSION
    url = f"{GRAPH}/{version}/{meta_dataset_id(cfg)}/events"
    body = build_meta_payload(cfg, secrets, ev, test=test)
    token = secrets.get("access_token") or secrets.get("system_user_token") or ""
    params = {"access_token": token}
    if secrets.get("app_secret"):
        params["appsecret_proof"] = appsecret_proof(token, secrets["app_secret"])
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(url, params=params, json=body)
    return r.status_code, _safe_json(r)


async def _send_google(cfg, secrets, ev, test, access_token):
    body = build_google_payload(cfg, ev, test=test)
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(DATA_MANAGER_URL,
                              headers={"Authorization": f"Bearer {access_token}"}, json=body)
    return r.status_code, _safe_json(r)


def _safe_json(resp):
    try:
        data = resp.json()
    except Exception:  # noqa: BLE001
        return {"raw": (resp.text or "")[:400]}
    # buang jejak yang bisa memuat data pribadi; simpan diagnostik yang berguna saja
    if isinstance(data, dict):
        return {k: v for k, v in data.items() if k in
                ("events_received", "messages", "fbtrace_id", "error", "requestId", "validateOnly", "name")}
    return {"raw": str(data)[:400]}


async def google_access_token(cfg, secrets):
    """Tukar refresh token OAuth menjadi access token (Data Manager & Google Ads)."""
    client = GoogleAdsClient(cfg, secrets)
    return await client.access_token()



async def _send_ga4(db, cfg, secrets, ev, test=False):
    """Kirim satu konversi ke GA4 Measurement Protocol.

    `client_id` diambil dari identitas yang STABIL (id pengunjung halaman iklan bila ada, kalau
    tidak dari id lead/booking) dan disimpan di `ga4_identities` — client_id acak per event akan
    membuat GA4 mengira setiap konversi berasal dari pengguna baru.
    """
    from services import ga4
    name = (EVENT_MAP.get(ev.get("kind")) or {}).get("ga4") or "generate_lead"
    if not ga4.valid_event_name(name):
        return 400, {"error": f"nama event GA4 tidak sah: {name}"}
    extra = ev.get("meta_extra") or {}
    identity = extra.get("ga4_client_id") or extra.get("visitor_id") or f"{ev.get('kind')}:{ev.get('ref_id')}"
    client_id = await ga4.client_id_for(db, identity)
    payload = ga4.build_payload(
        event_name=name, client_id=client_id,
        value=ev.get("value") or 0, currency=ev.get("currency") or "IDR",
        transaction_id=(ev.get("ref_id") if name == "purchase" else ""),
        params={"lead_source": ev.get("channel") or "", "event_key": ev.get("event_key") or "",
                "landing_slug": extra.get("landing_slug") or ""},
        consent=ga4.consent_block(bool(ev.get("consent_granted", True))),
        debug=bool(test) or bool(cfg.get("test_mode")))
    return await ga4.send(cfg.get("ga4_measurement_id") or "", secrets.get("ga4_api_secret") or "",
                          payload)


async def dispatch_one(db, ev, cfgs, *, test=False, sender=None):
    """Kirim satu event. TIDAK PERNAH melempar — semua hasil ditulis ke outbox."""
    provider = ev.get("provider")
    cfg = (cfgs or {}).get(provider) or {}
    secrets = cfg.get("_secrets") or {}
    reason = _reason_not_ready(provider, cfg, secrets)
    if reason:
        await db[COLL].update_one({"id": ev["id"]}, {"$set": {
            "status": "skipped", "last_error": reason, "updated_at": now_iso()}})
        return "skipped", reason
    attempts = int(ev.get("attempts") or 0) + 1
    try:
        if sender is not None:
            status, payload = await sender(provider, cfg, secrets, ev, test)
        elif provider == "meta":
            status, payload = await _send_meta(cfg, secrets, ev, test)
        elif provider == "ga4":
            status, payload = await _send_ga4(db, cfg, secrets, ev, test)
        else:
            token = await google_access_token(cfg, secrets)
            if not token:
                raise RuntimeError("Gagal menukar refresh token Google menjadi access token.")
            status, payload = await _send_google(cfg, secrets, ev, test, token)
    except Exception as exc:  # noqa: BLE001
        return await _mark_failure(db, ev, attempts, None, f"{type(exc).__name__}: {exc}"[:300])
    if 200 <= status < 300:
        await db[COLL].update_one({"id": ev["id"]}, {"$set": {
            "status": "success", "attempts": attempts, "http_status": status,
            "response": payload, "last_error": None, "next_retry_at": None,
            "sent_at": now_iso(), "updated_at": now_iso()}})
        return "success", payload
    return await _mark_failure(db, ev, attempts, status, str(payload)[:300])


async def _mark_failure(db, ev, attempts, http_status, error):
    dead = attempts >= MAX_ATTEMPTS
    delay = BACKOFF_SECONDS[min(attempts - 1, len(BACKOFF_SECONDS) - 1)]
    nxt = None if dead else (datetime.now(timezone.utc) + timedelta(seconds=delay)).isoformat()
    await db[COLL].update_one({"id": ev["id"]}, {"$set": {
        "status": "dead" if dead else "failed", "attempts": attempts, "http_status": http_status,
        "last_error": error, "next_retry_at": nxt, "updated_at": now_iso()}})
    logger.warning("Konversi %s/%s gagal (attempt %s): %s", ev.get("provider"), ev.get("event_key"), attempts, error)
    return ("dead" if dead else "failed"), error


async def dispatch_pending(db, cfgs, *, limit=50, sender=None):
    now = datetime.now(timezone.utc).isoformat()
    query = {"$or": [{"status": "pending"},
                     {"status": "failed", "next_retry_at": {"$lte": now}}]}
    docs = await db[COLL].find(query, {"_id": 0}).sort("created_at", 1).to_list(limit)
    out = {"success": 0, "failed": 0, "skipped": 0, "dead": 0}
    for ev in docs:
        status, _ = await dispatch_one(db, ev, cfgs, sender=sender)
        out[status] = out.get(status, 0) + 1
    return out


async def health_summary(db):
    pipeline = [{"$group": {"_id": {"provider": "$provider", "status": "$status"}, "n": {"$sum": 1}}}]
    rows = await db[COLL].aggregate(pipeline).to_list(200)
    summary = {p: {"success": 0, "failed": 0, "pending": 0, "skipped": 0, "dead": 0} for p in PROVIDERS}
    for r in rows:
        p = (r["_id"] or {}).get("provider")
        s = (r["_id"] or {}).get("status")
        if p in summary and s in summary[p]:
            summary[p][s] = r["n"]
    return summary
