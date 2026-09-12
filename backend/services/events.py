"""services/events.py — Event Bus (E1).

Jantung otomasi: aksi domain nyata memancarkan *event* (lead.created, booking.confirmed,
payment.recorded, dst). Setiap event dipersist ke koleksi `events` lalu diteruskan ke
Automation Engine (services.automation.process_event) untuk dievaluasi terhadap rules.

Desain:
- **Idempotent**: bila `dedupe_key` diberikan & sudah ada di `events`, event di-skip
  (mencegah duplikasi saat scheduler scan berulang).
- **Defensif**: emit TIDAK PERNAH menggagalkan alur bisnis (selalu di-try/except).
- **Lazy import** ke automation untuk menghindari import melingkar.

Koleksi kanonik baru: `events` (id berprefiks `evt_`).
"""
import logging
import re

from core_utils import new_id, now_iso

logger = logging.getLogger("travel_fleet.events")

# Katalog event domain (label utk UI rule-builder & monitoring).
EVENT_TYPES = {
    "lead.created": "Lead baru masuk",
    "quotation.sent": "Penawaran dikirim",
    "booking.confirmed": "Booking dikonfirmasi",
    "booking.cancelled": "Booking dibatalkan",
    "booking.rescheduled": "Booking dijadwalkan ulang",
    "booking.requested": "Permintaan booking (publik) masuk",
    "booking.hold_expired": "Booking hold kedaluwarsa (DP telat)",
    "payment.recorded": "Pembayaran tercatat",
    "booking.departure_due": "Keberangkatan ≤ 24 jam",
    "trip.assigned": "Trip ditugaskan (driver+unit)",
    "booking.departure_confirmed": "Keberangkatan dikonfirmasi",
    "trip.enroute": "Driver dalam perjalanan menjemput",
    "trip.started": "Trip dimulai",
    "trip.arrived": "Tiba di tujuan",
    "trip.completed": "Trip selesai",
    "invoice.overdue": "Invoice lewat tempo",
    "doc.expiring": "Dokumen armada jatuh tempo",
    "driver.sim_expiring": "SIM driver menjelang/lewat masa berlaku",
    "wa.inbound": "Pesan WhatsApp masuk",
    "lead.sla_breached": "SLA respons lead terlewati",
    "customer.at_risk": "Pelanggan berisiko churn",
    "payroll.period_due": "Periode payroll berakhir — generate payout",
    "payroll.payout_pending": "Payout driver menunggu diproses",
    "gps.alarm": "Alarm perangkat GPS (cabut/tamper/tow/SOS)",
    "subcharter.requested": "Permintaan pinjam armada ke mitra",
    "subcharter.confirmed": "Pinjam armada dikonfirmasi (ke mitra)",
    "subcharter.settled": "Pelunasan ke mitra (sub-charter)",
}


def _fmt(value):
    """Format nilai untuk render template: angka -> ribuan (1.500.000); lainnya -> str."""
    if isinstance(value, bool):
        return "ya" if value else "tidak"
    if isinstance(value, (int, float)):
        return f"{int(round(value)):,}".replace(",", ".")
    return "" if value is None else str(value)


def render_template(text, variables):
    """Substitusi sederhana `{field}` dari dict `variables`. Placeholder tak dikenal dibiarkan."""
    variables = variables or {}

    def repl(m):
        key = m.group(1).strip()
        return _fmt(variables[key]) if key in variables else m.group(0)

    return re.sub(r"\{([a-zA-Z0-9_]+)\}", repl, text or "")


async def emit(db, event_type, payload=None, *, source="system", ref_type=None,
               ref_id=None, dedupe_key=None):
    """Pancarkan event domain + jalankan Automation Engine. Return event doc / None.

    Tak pernah raise — kegagalan otomasi tidak boleh menggagalkan transaksi bisnis.
    """
    try:
        if dedupe_key and await db.events.find_one({"dedupe_key": dedupe_key}, {"_id": 1}):
            return None
        doc = {
            "id": new_id("evt"), "type": event_type, "payload": payload or {},
            "source": source, "ref_type": ref_type, "ref_id": ref_id,
            "dedupe_key": dedupe_key, "processed": False, "runs_created": 0,
            "created_at": now_iso(),
        }
        await db.events.insert_one(doc)
        runs = 0
        try:
            from services.automation import process_event
            runs = await process_event(db, doc)
        except Exception as exc:  # noqa: BLE001
            logger.warning("automation process_event gagal utk %s: %s", event_type, exc)
        # FASE F3 — INV-CONV-01: SATU titik pemanggilan menuju outbox konversi iklan.
        # Sengaja di sini (bukan di tiap router) supaya SEMUA sumber event (bookings, payments,
        # quotations, publik, Lead Ads, WhatsApp) otomatis terlapor ke Meta/Google tanpa ada
        # jalur yang terlewat. Tidak pernah menggagalkan transaksi bisnis.
        try:
            from services.conversion_hooks import handle_event as conversion_hook
            await conversion_hook(db, event_type, doc.get("payload") or {})
        except Exception as exc:  # noqa: BLE001
            logger.warning("conversion hook gagal utk %s: %s", event_type, exc)
        await db.events.update_one({"id": doc["id"]},
                                   {"$set": {"processed": True, "runs_created": runs}})
        doc["processed"], doc["runs_created"] = True, runs
        return doc
    except Exception as exc:  # noqa: BLE001
        logger.warning("emit event %s gagal: %s", event_type, exc)
        return None
