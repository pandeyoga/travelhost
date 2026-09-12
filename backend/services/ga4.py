"""services/ga4.py — GA4 Measurement Protocol server-side (provider KETIGA outbox konversi).

Kenapa server-side, bukan hanya gtag di browser: pemblokir iklan, mode privat, dan pembatasan
cookie membuat sebagian konversi tidak pernah sampai dari browser. Konversi yang HANYA diketahui
server (booking dikonfirmasi, DP masuk) bahkan tidak mungkin dikirim dari browser. Tanpa jalur ini
laporan GA4 melaporkan lebih sedikit hasil daripada kenyataan → keputusan belanja iklan salah.

Kontrak yang WAJIB dipatuhi (playbook resmi 2026):
  * POST https://www.google-analytics.com/mp/collect?measurement_id=G-XXXX&api_secret=...
  * Body: `client_id` (wajib) + `events[]` (wajib, maks 25). `timestamp_micros` dalam MIKRO-detik.
  * Setiap event butuh `session_id` (bilangan positif) dan `engagement_time_msec` positif agar
    ikut dihitung dalam sesi & terlihat di DebugView/Realtime.
  * Nama event memakai nama rekomendasi (`generate_lead`, `purchase`) — BUKAN nama tercadang
    (`session_start`, `first_visit`, dst) dan bukan berawalan `ga_`/`google_`/`firebase_`/`_`.
  * **BAHAYA TERSEMBUNYI:** endpoint produksi membalas **204 walau payload salah**. Jadi 204 BUKAN
    bukti diterima. Verifikasi wajib memakai endpoint `/debug/mp/collect` yang mengembalikan
    `validationMessages` — itulah sebabnya `validate()` di bawah disediakan & dipakai POC.
  * `client_id` harus STABIL per pengunjung (jangan acak per event, jangan hash email).
"""
import json
import logging
import secrets as _secrets
import time

import httpx

from core_utils import now_iso

logger = logging.getLogger("travel_fleet.ga4")

COLLECT_URL = "https://www.google-analytics.com/mp/collect"
DEBUG_URL = "https://www.google-analytics.com/debug/mp/collect"
IDENT_COLL = "ga4_identities"
MAX_BODY_BYTES = 130_000
RESERVED_EVENTS = {"session_start", "first_visit", "first_open", "user_engagement", "error",
                   "ad_click", "ad_exposure", "app_install", "app_remove", "app_update",
                   "notification_open", "firebase_campaign"}
RESERVED_PREFIXES = ("_", "ga_", "google_", "firebase_", "gtag.")


async def ensure_indexes(db):
    try:
        await db[IDENT_COLL].create_index("identity_key", unique=True)
    except Exception as exc:  # noqa: BLE001
        logger.warning("index ga4_identities skip: %s", exc)


def new_client_id() -> str:
    """Bentuk mirip cookie `_ga` (dua komponen desimal) agar mudah dikenali di GA4."""
    return f"{_secrets.randbelow(10 ** 10)}.{_secrets.randbelow(10 ** 10)}"


async def client_id_for(db, identity_key: str) -> str:
    """Ambil/buat client_id yang STABIL untuk satu identitas. Wajib stabil: client_id acak per
    event membuat GA4 menghitung setiap konversi sebagai pengguna baru (sesi & atribusi rusak)."""
    key = str(identity_key or "")[:120] or "anon"
    try:
        row = await db[IDENT_COLL].find_one({"identity_key": key}, {"_id": 0, "client_id": 1})
        if row and row.get("client_id"):
            return row["client_id"]
        cid = new_client_id()
        await db[IDENT_COLL].update_one(
            {"identity_key": key},
            {"$setOnInsert": {"identity_key": key, "client_id": cid, "created_at": now_iso()}},
            upsert=True)
        row = await db[IDENT_COLL].find_one({"identity_key": key}, {"_id": 0, "client_id": 1})
        return (row or {}).get("client_id") or cid
    except Exception as exc:  # noqa: BLE001 — analitik tak boleh menggagalkan pengiriman
        logger.warning("gagal menyiapkan client_id GA4: %s", exc)
        return new_client_id()


def valid_event_name(name: str) -> bool:
    n = str(name or "")
    if not n or len(n) > 40 or n in RESERVED_EVENTS:
        return False
    return not any(n.startswith(p) for p in RESERVED_PREFIXES)


def build_payload(*, event_name: str, client_id: str, value=0, currency="IDR",
                  transaction_id="", params=None, consent=None, session_id=None,
                  timestamp_micros=None, debug=False) -> dict:
    """Bentuk body sesuai kontrak. Angka uang dikirim sebagai bilangan (IDR tanpa desimal)."""
    p = {k: v for k, v in (params or {}).items() if v not in (None, "")}
    if value:
        p["value"] = int(value)
        p["currency"] = currency or "IDR"
    if transaction_id:
        p["transaction_id"] = str(transaction_id)[:100]
    sid = session_id if (isinstance(session_id, int) and session_id > 0) else int(time.time())
    p["session_id"] = sid
    p.setdefault("engagement_time_msec", 1000)
    if debug:
        p["debug_mode"] = True
    body = {"client_id": client_id, "events": [{"name": event_name, "params": p}]}
    if timestamp_micros:
        body["timestamp_micros"] = int(timestamp_micros)
    if consent:
        body["consent"] = consent
    return body


def consent_block(granted: bool) -> dict:
    """Consent GA4 diturunkan dari `marketing_consent` yang tercatat — tidak pernah diasumsikan."""
    state = "GRANTED" if granted else "DENIED"
    return {"ad_user_data": state, "ad_personalization": state}


def _query(measurement_id: str, api_secret: str) -> dict:
    return {"measurement_id": measurement_id, "api_secret": api_secret}


async def send(measurement_id: str, api_secret: str, payload: dict, timeout=15.0):
    """-> (http_status, response_dict). TIDAK PERNAH melempar untuk kesalahan HTTP biasa.

    Catatan penting: 204 hanya berarti "permintaan diterima". Kebenaran payload TIDAK dijamin —
    karena itu status sukses di outbox ditandai `success` tetapi verifikasi kebenaran dilakukan
    lewat `validate()` (endpoint /debug) + GA4 DebugView, bukan dari kode 204.
    """
    raw = json.dumps(payload).encode("utf-8")
    if len(raw) >= MAX_BODY_BYTES:
        return 413, {"error": "payload GA4 melebihi 130 kB"}
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(COLLECT_URL, params=_query(measurement_id, api_secret),
                              content=raw, headers={"Content-Type": "application/json"})
    try:
        body = r.json() if r.content else {}
    except ValueError:
        body = {"raw": (r.text or "")[:200]}
    if 200 <= r.status_code < 300:
        body = {**body, "note": "GA4 membalas 2xx = permintaan diterima; kebenaran payload "
                                "harus diverifikasi lewat /debug atau DebugView."}
    return r.status_code, body


async def validate(measurement_id: str, api_secret: str, payload: dict, timeout=15.0):
    """Kirim ke endpoint /debug (TIDAK masuk laporan) -> daftar pesan validasi. Inilah satu-satunya
    cara mengetahui payload ditolak, karena endpoint produksi selalu 2xx."""
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(DEBUG_URL, params=_query(measurement_id, api_secret),
                              json={**payload, "validation_behavior": "ENFORCE_RECOMMENDATIONS"},
                              headers={"Content-Type": "application/json"})
    try:
        data = r.json()
    except ValueError:
        data = {"raw": (r.text or "")[:300]}
    return r.status_code, data
