"""services/whatsapp.py — WhatsApp Adapter provider-agnostic (E1, MOCK-FIRST).

Antarmuka `WhatsAppProvider` (send_text/send_template/parse_webhook) dgn implementasi:
  - `mock`       : simulasi jujur (tanpa kredensial) — AKTIF sekarang.
  - `meta_cloud` : Meta WhatsApp Cloud API — STUB (diaktifkan di E6 saat kredensial siap).
  - `partner`    : alias stub (Wati/Qontak/Twilio) — menyusul.

In-app Inbox nyata-ready: pesan WA mengalir ke koleksi `conversations`+`messages`
(channel='whatsapp') dengan: session-window 24 jam, status, **cost tracking**, opt-in/out,
dan audit per pesan. Outbound via send_wa(); inbound via handle_inbound() (webhook/simulasi).

Konfigurasi & template disimpan di `settings` (key `wa_config`, `wa_templates`).
"""
import hashlib
import hmac
import logging
import secrets
from datetime import datetime, timedelta, timezone

import httpx

from core_utils import new_id, now_iso
from services.events import render_template
from services.geo import parse_iso

logger = logging.getLogger("travel_fleet.whatsapp")

DEFAULT_CONFIG = {
    "provider": "mock",            # mock | meta_cloud | partner
    "business_phone": "",
    "price_per_message": 350,       # estimasi biaya per pesan (IDR) utk cost tracking
    "session_hours": 24,
    "auto_reply_enabled": True,
    "auto_reply_text": "Halo! Terima kasih telah menghubungi {company}. Pesan Anda kami terima dan akan segera dibalas tim kami. 🙏",
    "away_reply_text": "Terima kasih telah menghubungi {company}. Saat ini di luar jam operasional ({open}–{close}). Tim kami akan membalas pada jam kerja.",
    "meta": {"phone_number_id": "", "access_token": "", "verify_token": "rahaza-wa-verify", "app_secret": "", "api_version": "v21.0"},
}

DEFAULT_TEMPLATES = {
    "lead_ack": {"name": "Sambutan Lead", "language": "id", "category": "marketing",
                 "body": "Halo {customer_name}! Terima kasih telah menghubungi {company}. Tim kami segera membantu rencana perjalanan Anda. 🚐"},
    "booking_confirm": {"name": "Konfirmasi Booking", "language": "id", "category": "utility",
                        "body": "Booking {code} dikonfirmasi. Total Rp {total_amount}. Mohon DP {dp_percent}% untuk mengamankan jadwal."},
    "departure_reminder": {"name": "Pengingat Keberangkatan", "language": "id", "category": "utility",
                           "body": "Pengingat keberangkatan {code} {when}. Driver {driver_name}, unit {vehicle_name}. Selamat jalan!"},
    "payment_thanks": {"name": "Terima Kasih Pembayaran", "language": "id", "category": "utility",
                       "body": "Pembayaran Rp {amount} untuk booking {code} sudah kami terima. Terima kasih!"},
}


# ---------------------------------------------------------------------------
# Provider implementations
# ---------------------------------------------------------------------------
class WhatsAppProvider:
    name = "base"

    async def send_text(self, to, text):
        raise NotImplementedError

    async def send_template(self, to, template_key, variables, body=None):
        raise NotImplementedError

    async def send_file(self, to, media, filename, caption):
        return {"status": "failed", "provider": self.name,
                "error": "Provider ini belum mendukung kirim media (gambar/PDF)"}

    def parse_webhook(self, payload):
        raise NotImplementedError


class MockProvider(WhatsAppProvider):
    """Simulasi jujur: hasilkan id pesan + status 'sent'. Tidak ada panggilan jaringan."""
    name = "mock"

    def __init__(self, cfg):
        self.cfg = cfg

    async def send_text(self, to, text):
        return {"status": "sent", "wa_message_id": f"wamid.mock_{secrets.token_hex(8)}",
                "cost": float(self.cfg.get("price_per_message", 0) or 0), "provider": self.name}

    async def send_template(self, to, template_key, variables, body=None):
        res = await self.send_text(to, template_key)
        res["template_key"] = template_key
        return res

    async def send_file(self, to, media, filename, caption):
        res = await self.send_text(to, caption or filename or "lampiran")
        res["attachment"] = filename
        return res

    def parse_webhook(self, payload):
        """Bentuk fleksibel: {from, text, name?} ATAU envelope Meta Cloud."""
        if not isinstance(payload, dict):
            return []
        if payload.get("from") and (payload.get("text") or payload.get("body")):
            return [{"from": str(payload["from"]), "text": payload.get("text") or payload.get("body"),
                     "name": payload.get("name"), "wa_message_id": payload.get("id"),
                     "referral": payload.get("referral") or {}}]
        return _parse_meta_envelope(payload)


class MetaCloudProvider(WhatsAppProvider):
    """Meta WhatsApp Cloud API (Graph). Pengiriman NYATA bila kredensial lengkap (E6).

    Tanpa kredensial → gagal dengan pesan jelas (tidak pernah raise). Default API version v21.0.
    """
    name = "meta_cloud"
    GRAPH_BASE = "https://graph.facebook.com"

    def __init__(self, cfg):
        self.cfg = cfg

    def _meta(self):
        return self.cfg.get("meta") or {}

    def _ready(self):
        m = self._meta()
        return bool(m.get("phone_number_id") and m.get("access_token"))

    @staticmethod
    def _digits(to):
        return "".join(ch for ch in str(to or "") if ch.isdigit())

    async def _post(self, payload):
        m = self._meta()
        if not self._ready():
            return {"status": "failed", "provider": self.name,
                    "error": "Kredensial Meta Cloud belum lengkap (Phone Number ID & Access Token wajib)."}
        version = (m.get("api_version") or "v21.0").strip()
        url = f"{self.GRAPH_BASE}/{version}/{m['phone_number_id']}/messages"
        headers = {"Authorization": f"Bearer {m['access_token']}", "Content-Type": "application/json"}
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.post(url, json=payload, headers=headers)
            try:
                data = r.json() if r.content else {}
            except Exception:  # noqa: BLE001
                data = {}
            if r.status_code >= 400:
                err = ((data.get("error") or {}).get("message")) or f"HTTP {r.status_code}"
                return {"status": "failed", "provider": self.name, "error": str(err)[:200]}
            wamid = None
            try:
                wamid = (data.get("messages") or [{}])[0].get("id")
            except Exception:  # noqa: BLE001
                pass
            return {"status": "sent", "wa_message_id": wamid,
                    "cost": float(self.cfg.get("price_per_message", 0) or 0), "provider": self.name}
        except Exception as exc:  # noqa: BLE001
            return {"status": "failed", "provider": self.name,
                    "error": f"Koneksi Graph API gagal: {str(exc)[:150]}"}

    async def send_text(self, to, text):
        return await self._post({
            "messaging_product": "whatsapp", "to": self._digits(to),
            "type": "text", "text": {"body": text or ""}})

    async def send_template(self, to, template_key, variables, body=None):
        # Mock-first: kirim isi template lokal yang sudah ter-render sebagai teks (butuh sesi 24 jam aktif).
        # Pengiriman template Meta resmi (by name+components) menyusul saat template di-approve di WABA.
        return await self.send_text(to, body if body is not None else template_key)

    def parse_webhook(self, payload):
        return _parse_meta_envelope(payload)


class OpenWaProvider(WhatsAppProvider):
    """OpenWA (open-wa/wa-automate v5) — sidecar lokal via Easy API HTTP. Unofficial (scan QR).

    Gratis & tanpa approval template Meta; tanpa batasan session-window 24 jam.
    Sidecar dikelola services/openwa.py. Gagal rapi bila sidecar mati / belum scan QR.
    """
    name = "openwa"

    def __init__(self, cfg):
        self.cfg = cfg

    @staticmethod
    def _chat_id(to):
        digits = "".join(ch for ch in str(to or "") if ch.isdigit())
        if digits.startswith("0"):
            digits = "62" + digits[1:]
        return f"{digits}@c.us" if digits else ""

    async def _call(self, method, args, timeout=30):
        from services import openwa as ow
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                r = await client.post(f"{ow.base_url()}/api/messages/{method}",
                                      json={"args": args}, headers=ow.headers())
        except Exception as exc:  # noqa: BLE001
            return {"status": "failed", "provider": self.name,
                    "error": f"Sidecar OpenWA tidak terjangkau ({str(exc)[:100]}). "
                             "Pastikan service jalan & QR sudah discan (Integrasi API)."}
        try:
            data = r.json() if r.content else {}
        except Exception:  # noqa: BLE001
            data = {}
        if r.status_code >= 400 or (isinstance(data, dict) and data.get("error")):
            err = data.get("error") if isinstance(data, dict) else None
            if isinstance(err, dict):
                err = err.get("message") or err.get("details") or str(err)
            return {"status": "failed", "provider": self.name,
                    "error": str(err or f"HTTP {r.status_code}")[:200]}
        wamid = None
        if isinstance(data, dict):
            res = data.get("result") or data.get("response") or data.get("data")
            if isinstance(res, str):
                wamid = res
            elif isinstance(res, dict):
                wamid = res.get("id") or res.get("_serialized")
        return {"status": "sent", "wa_message_id": wamid, "cost": 0.0, "provider": self.name}

    async def send_text(self, to, text):
        chat_id = self._chat_id(to)
        if not chat_id:
            return {"status": "failed", "provider": self.name, "error": "Nomor tujuan tidak valid"}
        return await self._call("sendText", {"to": chat_id, "content": text or ""})

    async def send_file(self, to, media, filename, caption):
        chat_id = self._chat_id(to)
        if not chat_id:
            return {"status": "failed", "provider": self.name, "error": "Nomor tujuan tidak valid"}
        is_image = str(media or "").startswith("data:image/")
        if is_image:
            args = {"to": chat_id, "imgData": media, "filename": filename or "gambar.jpg",
                    "caption": caption or ""}
            return await self._call("sendImage", args, timeout=60)
        args = {"to": chat_id, "file": media, "filename": filename or "dokumen.pdf",
                "caption": caption or ""}
        return await self._call("sendFile", args, timeout=60)

    async def send_template(self, to, template_key, variables, body=None):
        # OpenWA tak butuh template approval Meta — kirim isi ter-render sebagai teks biasa.
        res = await self.send_text(to, body if body is not None else template_key)
        res["template_key"] = template_key
        return res

    def parse_webhook(self, payload):
        return _parse_openwa_event(payload)


def _parse_openwa_event(payload):
    """Ekstrak pesan inbound dari event webhook sidecar OpenWA (best-effort, toleran versi).

    Bentuk yang diterima: {event|type: 'onMessage', data|payload: {...}} atau objek pesan
    langsung. Pesan grup, status broadcast, dan pesan keluar (fromMe) diabaikan.
    """
    if not isinstance(payload, dict):
        return []
    ev = str(payload.get("event") or payload.get("type") or "")
    data = payload.get("data")
    if not isinstance(data, dict):
        data = payload.get("payload") if isinstance(payload.get("payload"), dict) else None
    if data is None and payload.get("from"):
        data = payload
    if not isinstance(data, dict):
        return []
    if ev and "message" not in ev.lower():
        return []
    if data.get("fromMe"):
        return []
    frm = str(data.get("from") or "")
    if not frm or "@g.us" in frm or "status@broadcast" in frm:
        return []
    phone = frm.split("@")[0]
    text = data.get("body") or data.get("content") or data.get("text") or data.get("caption") or ""
    if not (phone.strip() and str(text).strip()):
        return []
    sender = data.get("sender") or {}
    name = sender.get("pushname") or sender.get("name") or sender.get("formattedName") or data.get("notifyName")
    mid = data.get("id")
    if isinstance(mid, dict):
        mid = mid.get("_serialized") or mid.get("id")
    return [{"from": phone, "text": str(text), "name": name, "wa_message_id": mid, "referral": {}}]


def _parse_meta_envelope(payload):
    """Ekstrak pesan inbound dari envelope webhook Meta Cloud (best-effort)."""
    out = []
    try:
        for entry in payload.get("entry", []) or []:
            for ch in entry.get("changes", []) or []:
                val = ch.get("value", {}) or {}
                contacts = {c.get("wa_id"): (c.get("profile") or {}).get("name")
                            for c in val.get("contacts", []) or []}
                for m in val.get("messages", []) or []:
                    frm = m.get("from")
                    text = (m.get("text") or {}).get("body") if m.get("type") == "text" else m.get("type")
                    out.append({"from": frm, "text": text, "name": contacts.get(frm),
                                "wa_message_id": m.get("id"),
                                # CTWA: pesan dari iklan Klik-ke-WhatsApp membawa objek referral
                                # (source_id = ad_id, ctwa_clid). Sebelumnya dibuang -> atribusi hilang.
                                "referral": m.get("referral") or {}})
    except Exception as exc:  # noqa: BLE001
        logger.warning("parse meta envelope gagal: %s", exc)
    return out


# ---------------------------------------------------------------------------
# Config / templates
# ---------------------------------------------------------------------------
async def get_config(db):
    s = await db.settings.find_one({"key": "wa_config"}, {"_id": 0})
    cfg = dict(DEFAULT_CONFIG)
    if s and isinstance(s.get("value"), dict):
        cfg.update(s["value"])
        merged_meta = dict(DEFAULT_CONFIG["meta"])
        merged_meta.update(s["value"].get("meta") or {})
        cfg["meta"] = merged_meta
    return cfg


async def get_templates(db):
    s = await db.settings.find_one({"key": "wa_templates"}, {"_id": 0})
    if s and isinstance(s.get("value"), dict):
        return s["value"]
    return dict(DEFAULT_TEMPLATES)


def _provider_for(cfg):
    prov = (cfg or {}).get("provider", "mock")
    if prov == "meta_cloud":
        return MetaCloudProvider(cfg)
    if prov == "openwa":
        return OpenWaProvider(cfg)
    return MockProvider(cfg)  # mock | partner -> mock sim


async def _company_name(db):
    s = await db.settings.find_one({"key": "company_info"}, {"_id": 0})
    if s and isinstance(s.get("value"), dict):
        return s["value"].get("name") or "kami"
    return "kami"


def _within_session(conv):
    exp = parse_iso((conv or {}).get("session_expires_at"))
    return bool(exp and exp > datetime.now(timezone.utc))


async def ensure_conversation(db, phone, *, name=None, lead_id=None, customer_id=None):
    phone = (phone or "").strip()
    try:
        from services.identity import normalize_phone
        norm = normalize_phone(phone)
    except Exception:
        norm = phone
    conv = await db.conversations.find_one(
        {"channel": "whatsapp", "contact_phone": {"$in": list({phone, norm})}}, {"_id": 0})
    if conv:
        patch = {}
        if lead_id and not conv.get("lead_id"):
            patch["lead_id"] = lead_id
        if customer_id and not conv.get("customer_id"):
            patch["customer_id"] = customer_id
        if patch:
            await db.conversations.update_one({"id": conv["id"]}, {"$set": patch})
            conv.update(patch)
        return conv
    now = now_iso()
    doc = {
        "id": new_id("cnv"), "channel": "whatsapp", "contact_name": name or phone or "Kontak WA",
        "contact_phone": phone, "subject": "WhatsApp", "customer_id": customer_id, "lead_id": lead_id,
        "status": "open", "assigned_to": None, "labels": ["wa"], "unread": 0, "chat_token": None,
        "wa_opt_in": True, "session_expires_at": None, "total_cost": 0.0,
        "last_message_at": now, "last_message_preview": "", "snooze_until": None, "created_at": now,
    }
    await db.conversations.insert_one(doc)
    return doc


async def send_wa(db, to_phone, *, text=None, template_key=None, variables=None,
                  conversation_id=None, lead_id=None, customer_id=None, contact_name=None,
                  source="agent", author_id=None, media_data=None, media_filename=None):
    """Kirim WA (provider aktif) + catat ke Inbox dgn cost/status. Tak pernah raise.

    media_data (data URL base64) + media_filename → kirim gambar/dokumen (caption = text).
    """
    try:
        cfg = await get_config(db)
        provider = _provider_for(cfg)
        variables = dict(variables or {})
        variables.setdefault("company", await _company_name(db))
        used_template = None
        body = text
        if template_key:
            tpls = await get_templates(db)
            tpl = tpls.get(template_key)
            if tpl:
                body, used_template = tpl.get("body"), template_key
        body = render_template(body or "", variables)
        if not (to_phone or "").strip():
            return {"status": "failed", "error": "Nomor tujuan kosong"}
        conv = None
        if conversation_id:
            conv = await db.conversations.find_one({"id": conversation_id}, {"_id": 0})
        if not conv:
            conv = await ensure_conversation(db, to_phone, name=contact_name,
                                             lead_id=lead_id, customer_id=customer_id)
        if conv.get("wa_opt_in") is False:
            return {"status": "skipped", "reason": "opt_out", "conversation_id": conv["id"]}
        within = _within_session(conv)
        try:
            if media_data:
                res = await provider.send_file(to_phone, media_data, media_filename, body)
            elif used_template:
                res = await provider.send_template(to_phone, used_template, variables, body=body)
            else:
                res = await provider.send_text(to_phone, body)
        except Exception as exc:  # noqa: BLE001
            res = {"status": "failed", "error": str(exc)[:160], "provider": provider.name}
        ok = res.get("status") in ("sent", "delivered", "read")
        cost = float(res.get("cost") or 0) if ok else 0.0
        now = now_iso()
        msg = {
            "id": new_id("msg"), "conversation_id": conv["id"], "sender": "agent",
            "author_id": author_id, "body": body, "internal": False,
            "status": res.get("status", "sent"), "direction": "out", "channel": "whatsapp",
            "wa_message_id": res.get("wa_message_id"), "cost": cost, "template_key": used_template,
            "provider": provider.name, "source": source, "error": res.get("error"),
            "outside_session": (not within and not used_template), "created_at": now,
            "attachment": ({"filename": media_filename or "lampiran"} if media_data else None),
        }
        await db.messages.insert_one(msg)
        preview = (f"📎 {media_filename or 'lampiran'}" + (f" · {body}" if body else "")) if media_data else body
        await db.conversations.update_one({"id": conv["id"]}, {
            "$set": {"last_message_at": now, "last_message_preview": preview[:120]},
            "$inc": {"total_cost": cost}})
        return {"status": res.get("status"), "conversation_id": conv["id"], "message_id": msg["id"],
                "cost": cost, "within_session": within, "provider": provider.name,
                "wa_message_id": res.get("wa_message_id"), "error": res.get("error")}
    except Exception as exc:  # noqa: BLE001
        logger.warning("send_wa gagal: %s", exc)
        return {"status": "failed", "error": str(exc)[:160]}


async def _maybe_auto_reply(db, conv, cfg):
    if not cfg.get("auto_reply_enabled"):
        return
    text = cfg.get("auto_reply_text") or ""
    op = await db.settings.find_one({"key": "operational"}, {"_id": 0})
    wh = ((op or {}).get("value") or {}).get("work_hours") or {}
    open_h, close_h = wh.get("open", "08:00"), wh.get("close", "17:00")
    try:
        now_hm = datetime.now(timezone.utc).strftime("%H:%M")
        if not (open_h <= now_hm <= close_h):
            text = cfg.get("away_reply_text") or text
    except Exception as exc:  # noqa: BLE001
        logger.debug("cek jam kerja auto-reply gagal: %s", exc)
    await send_wa(db, conv.get("contact_phone"), text=text, conversation_id=conv["id"],
                  variables={"open": open_h, "close": close_h}, source="auto_reply")


async def handle_inbound(db, from_phone, text, *, name=None, provider_msg_id=None, referral=None):
    """Proses pesan WA masuk (webhook/simulasi): identitas → conversation → auto-reply → event.

    FASE F5 — `referral` (Klik-ke-WhatsApp): bila pesan berasal dari iklan CTWA, Meta menyertakan
    `ctwa_clid` + `source_id`(=ad_id). Data itu SATU-SATUNYA jembatan antara chat WhatsApp dan
    iklan yang membayarnya, jadi disimpan ke lead + `ad_touches` dan dipakai saat mengirim
    konversi (`action_source=business_messaging`).
    """
    cfg = await get_config(db)
    from_phone = (from_phone or "").strip()
    if not from_phone or not (text or "").strip():
        return {"status": "ignored", "reason": "from/text kosong"}
    ad_ref = {}
    try:
        from services.lead_ads import parse_wa_referral
        ad_ref = parse_wa_referral({"referral": referral or {}})
    except Exception as exc:  # noqa: BLE001
        logger.warning("baca referral CTWA gagal: %s", exc)
    try:
        from services.identity import normalize_phone
        norm = normalize_phone(from_phone)
    except Exception:
        norm = from_phone
    customer = await db.customers.find_one(
        {"$or": [{"phone": from_phone}, {"phone_normalized": norm}]}, {"_id": 0})
    lead = await db.leads.find_one(
        {"$or": [{"phone": from_phone}, {"phone_normalized": norm}]}, {"_id": 0})
    conv = await ensure_conversation(db, from_phone, name=name,
                                     lead_id=lead["id"] if lead else None,
                                     customer_id=customer["id"] if customer else None)
    lead_created = False
    if not conv.get("lead_id") and not conv.get("customer_id"):
        from services.crm import auto_assign_agent, log_activity
        assigned = await auto_assign_agent(db)
        lead_doc = {
            "id": new_id("led"), "customer_name": name or from_phone, "phone": from_phone,
            "phone_normalized": norm, "email": "", "source": "whatsapp", "stage": "new",
            "assigned_to": assigned, "destination": "", "trip_date": None, "pax": 0,
            "message": text[:300], "value": 0.0, "quotation_amount": 0,
            "converted_customer_id": None, "linked_customer_id": None,
            "created_at": now_iso(), "last_activity_at": now_iso(),
        }
        if ad_ref:
            # lead dari iklan CTWA: channel & atribusi level iklan langsung terpasang
            lead_doc.update({
                "source": "ads", "channel": "meta_ads", "ad_platform": "meta",
                "ad_id": ad_ref.get("ad_id", ""), "ctwa_clid": ad_ref.get("ctwa_clid", ""),
                "marketing_consent": True, "consent_at": now_iso(),
                "attribution": {"channel": "meta_ads",
                                "first_touch": {"utm_source": "meta", "utm_medium": "paid",
                                                "utm_content": ad_ref.get("ad_id", ""),
                                                "landing_page": ad_ref.get("source_url", ""),
                                                "channel": "meta_ads"},
                                "last_touch": {"utm_source": "meta", "utm_medium": "paid",
                                               "utm_content": ad_ref.get("ad_id", ""),
                                               "landing_page": ad_ref.get("source_url", ""),
                                               "channel": "meta_ads"}},
            })
        await db.leads.insert_one(lead_doc)
        note = "Lead masuk dari WhatsApp"
        if ad_ref:
            note = ("Lead masuk dari iklan Klik-ke-WhatsApp"
                    + (f" · {ad_ref.get('headline')}" if ad_ref.get("headline") else "")
                    + (f" · iklan {ad_ref.get('ad_id')}" if ad_ref.get("ad_id") else ""))
        await log_activity(db, lead_doc["id"], None, "created", text=note)
        await db.conversations.update_one({"id": conv["id"]}, {"$set": {"lead_id": lead_doc["id"]}})
        conv["lead_id"] = lead_doc["id"]
        lead_created = True
    elif ad_ref and conv.get("lead_id"):
        # lead sudah ada: lengkapi atribusi iklan bila belum pernah terisi (jangan menimpa)
        await db.leads.update_one(
            {"id": conv["lead_id"], "$or": [{"ctwa_clid": {"$in": [None, ""]}},
                                            {"ctwa_clid": {"$exists": False}}]},
            {"$set": {"ad_platform": "meta", "ad_id": ad_ref.get("ad_id", ""),
                      "ctwa_clid": ad_ref.get("ctwa_clid", ""), "channel": "meta_ads"}})
    if ad_ref:
        try:
            from services.ads_metrics import record_touch
            await record_touch(db, {"click_id": ad_ref.get("ctwa_clid") or f"ctwa:{from_phone}",
                                    "provider": "meta", "kind": "ctwa",
                                    "ad_id": ad_ref.get("ad_id", ""),
                                    "lead_id": conv.get("lead_id"),
                                    "source_url": ad_ref.get("source_url", ""),
                                    "headline": ad_ref.get("headline", "")})
        except Exception as exc:  # noqa: BLE001
            logger.warning("catat ad_touch CTWA gagal: %s", exc)
    now = now_iso()
    msg = {
        "id": new_id("msg"), "conversation_id": conv["id"], "sender": "customer", "author_id": None,
        "body": text, "internal": False, "status": "delivered", "direction": "in",
        "channel": "whatsapp", "wa_message_id": provider_msg_id, "cost": 0.0,
        "provider": cfg.get("provider"), "created_at": now,
    }
    await db.messages.insert_one(msg)
    sess_exp = (datetime.now(timezone.utc) + timedelta(hours=int(cfg.get("session_hours", 24)))).isoformat()
    await db.conversations.update_one({"id": conv["id"]}, {
        "$set": {"last_message_at": now, "last_message_preview": text[:120],
                 "session_expires_at": sess_exp, "wa_opt_in": True, "status": "open"},
        "$inc": {"unread": 1}})
    await _maybe_auto_reply(db, conv, cfg)
    try:
        from services.events import emit
        await emit(db, "wa.inbound", {
            "conversation_id": conv["id"], "contact_name": conv.get("contact_name"),
            "phone": from_phone, "text": text, "lead_id": conv.get("lead_id"),
            "customer_id": conv.get("customer_id"),
        }, source="whatsapp", ref_type="conversation", ref_id=conv["id"])
    except Exception as exc:  # noqa: BLE001
        logger.warning("emit wa.inbound gagal: %s", exc)
    if ad_ref and lead_created and conv.get("lead_id"):
        # CTWA: lead dari iklan -> pancarkan lead.created supaya konversi terkirim ke Meta
        # (jalur baru F5; lead WA biasa tetap seperti sebelumnya agar tak ada regresi otomasi).
        try:
            from services.events import emit as emit_lead
            await emit_lead(db, "lead.created", {
                "lead_id": conv["lead_id"], "customer_name": name or from_phone,
                "phone": from_phone, "source": "ads", "channel": "meta_ads",
                "ad_id": ad_ref.get("ad_id", ""),
            }, source="whatsapp", ref_type="lead", ref_id=conv["lead_id"],
                dedupe_key=f"lead.created:{conv['lead_id']}")
        except Exception as exc:  # noqa: BLE001
            logger.warning("emit lead.created (CTWA) gagal: %s", exc)
    return {"status": "received", "conversation_id": conv["id"], "lead_created": lead_created,
            "from_ad": bool(ad_ref), "ad_id": ad_ref.get("ad_id", "") if ad_ref else ""}


def verify_signature(app_secret, body_bytes, signature_header):
    """Verifikasi X-Hub-Signature-256 (Meta). True bila cocok / tak ada secret (mock)."""
    if not app_secret:
        return True
    if not signature_header:
        return False
    expected = "sha256=" + hmac.new(app_secret.encode(), body_bytes, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header)
