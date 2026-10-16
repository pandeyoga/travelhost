"""services/conversion_hooks.py — JEMBATAN event bus -> outbox konversi (INV-CONV-01).

Akar masalah yang ditutup modul ini: sampai fase F2, `services/conversions.py` sudah lengkap tapi
TIDAK PERNAH dipanggil siapa pun. Artinya dua konversi paling bernilai — **booking dikonfirmasi**
dan **DP/pembayaran masuk** — tidak pernah dilaporkan ke Meta/Google, sehingga algoritma iklan
hanya belajar dari "form terkirim" dan salah mengoptimalkan.

Satu-satunya titik pemanggilan adalah `services/events.emit()` (setelah automation), sehingga
SEMUA sumber event (router bookings, payments, quotations, publik, Lead Ads, WhatsApp) otomatis
ikut terlapor tanpa perlu menyentuh tiap router — dan bisa dijaga guardrail statik.

Identitas yang dikumpulkan (untuk match rate maksimal, semua PII di-hash saat dikirim):
  email, telepon, gclid/fbclid(->fbc)/ttclid, ctwa_clid (Klik-ke-WhatsApp), external_id,
  serta atribusi level iklan (campaign/adset/ad) untuk pelaporan ROAS.
"""
import logging
from datetime import datetime, timezone

from core_utils import money
from services import conversions as cv

logger = logging.getLogger("travel_fleet.conversion_hooks")

# Event bisnis bernilai -> jenis konversi. DAFTAR INI DIJAGA GUARDRAIL INV-CONV-01.
BUSINESS_EVENTS = {
    "lead.created": "lead",
    "booking.confirmed": "booking",
    "payment.recorded": "payment",
}
BOOKING_REVENUE_STATUS = ("confirmed", "ongoing", "completed")


def _fbc_from_fbclid(fbclid: str, when: str = "") -> str:
    """Meta menganjurkan mengirim cookie `_fbc`. Bila hanya fbclid yang tersimpan, bentuk ulang:
    fb.1.<epoch_ms>.<fbclid> (subdomain index 1 = domain utama)."""
    if not fbclid:
        return ""
    stamp = None
    try:
        stamp = int(datetime.fromisoformat(str(when).replace("Z", "+00:00")).timestamp() * 1000)
    except Exception:  # noqa: BLE001
        stamp = int(datetime.now(timezone.utc).timestamp() * 1000)
    return f"fb.1.{stamp}.{fbclid}"


def identifiers_from_lead(lead=None, customer=None) -> dict:
    lead = lead or {}
    customer = customer or {}
    attribution = lead.get("attribution") or {}
    last = attribution.get("last_touch") or {}
    first = attribution.get("first_touch") or {}

    def touch(key):
        return last.get(key) or first.get(key) or lead.get(key) or ""

    out = {
        "email": lead.get("email") or customer.get("email") or "",
        "phone": lead.get("phone") or customer.get("phone") or "",
        "external_id": customer.get("id") or lead.get("id") or "",
    }
    for key in ("gclid", "fbclid", "ttclid", "wbraid", "gbraid"):
        if touch(key):
            out[key] = touch(key)
    for key in ("fbp", "fbc", "ctwa_clid", "waba_id"):
        if lead.get(key):
            out[key] = lead[key]
    if out.get("fbclid") and not out.get("fbc"):
        out["fbc"] = _fbc_from_fbclid(out["fbclid"], lead.get("created_at") or "")
    return {k: v for k, v in out.items() if v}


async def _lead_of_customer(db, customer_id, phone=""):
    if customer_id:
        lead = await db.leads.find_one(
            {"$or": [{"converted_customer_id": customer_id}, {"linked_customer_id": customer_id}]},
            {"_id": 0}, sort=[("created_at", -1)])
        if lead:
            return lead
    if phone:
        try:
            from services.identity import normalize_phone
            norm = normalize_phone(phone)
        except Exception:  # noqa: BLE001
            norm = phone
        return await db.leads.find_one(
            {"$or": [{"phone": phone}, {"phone_normalized": norm}]}, {"_id": 0},
            sort=[("created_at", -1)])
    return None


async def _context_for_booking(db, booking_id):
    booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0}) or {}
    customer = {}
    if booking.get("customer_id"):
        customer = await db.customers.find_one({"id": booking["customer_id"]}, {"_id": 0}) or {}
    lead = await _lead_of_customer(db, booking.get("customer_id"),
                                   customer.get("phone") or booking.get("phone") or "")
    return booking, customer, lead


async def build_conversion(db, event_type: str, payload: dict):
    """Tentukan (kind, ref_id, kwargs) untuk satu event bisnis. None bila tak relevan."""
    kind = BUSINESS_EVENTS.get(event_type)
    if not kind:
        return None
    payload = payload or {}
    if kind == "lead":
        lead_id = payload.get("lead_id")
        if not lead_id:
            return None
        lead = await db.leads.find_one({"id": lead_id}, {"_id": 0}) or {}
        return kind, lead_id, {
            "value": money(lead.get("value") or payload.get("value") or 0),
            "identifiers": identifiers_from_lead(lead),
            "channel": lead.get("channel") or payload.get("channel") or "",
            "source_url": (lead.get("attribution") or {}).get("last_touch", {}).get("landing_page") or "",
            "consent_granted": bool(lead.get("marketing_consent")),
            "meta_extra": {"lead_stage": lead.get("stage"), "ad_id": lead.get("ad_id") or ""},
        }
    if kind == "booking":
        booking_id = payload.get("booking_id")
        if not booking_id:
            return None
        booking, customer, lead = await _context_for_booking(db, booking_id)
        value = money(booking.get("total_amount") or payload.get("total_amount") or 0)
        return kind, booking_id, {
            "value": value,
            "identifiers": identifiers_from_lead(lead, customer),
            "channel": (lead or {}).get("channel") or "",
            "consent_granted": bool((lead or {}).get("marketing_consent", True)),
            "meta_extra": {"booking_code": booking.get("code") or payload.get("code") or "",
                           "lead_id": (lead or {}).get("id") or ""},
        }
    payment_id = payload.get("payment_id")
    if not payment_id:
        return None
    payment = await db.payments.find_one({"id": payment_id}, {"_id": 0}) or {}
    booking_id = payment.get("booking_id") or payload.get("booking_id") or ""
    booking, customer, lead = await _context_for_booking(db, booking_id)
    return kind, payment_id, {
        "value": money(payment.get("amount") or payload.get("amount") or 0),
        "identifiers": identifiers_from_lead(lead, customer),
        "channel": (lead or {}).get("channel") or "",
        "consent_granted": bool((lead or {}).get("marketing_consent", True)),
        "meta_extra": {"booking_code": booking.get("code") or "",
                       "payment_type": payment.get("type") or payload.get("type") or "",
                       "lead_id": (lead or {}).get("id") or ""},
    }


async def handle_event(db, event_type: str, payload: dict):
    """Dipanggil `services.events.emit`. TIDAK PERNAH melempar (jangan gagalkan transaksi bisnis)."""
    try:
        built = await build_conversion(db, event_type, payload)
        if not built:
            return None
        kind, ref_id, kwargs = built
        return await cv.enqueue(db, kind, ref_id, **kwargs)
    except Exception as exc:  # noqa: BLE001
        logger.warning("gagal menjadwalkan konversi utk %s: %s", event_type, exc)
        return None
