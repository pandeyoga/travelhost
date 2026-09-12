"""services/quotations.py — Quotation Lifecycle helper (Phase 9 / B2).

Status: draft → sent → accepted → converted (atau rejected/expired).
Nomor QUO-<YYYY>-#### via counters atomik (INV-8/INV-17).
Item harga dibangun dari Pricing Engine (B1) atau manual.

normalize_phone: normalisasi ringan ke +62 (disempurnakan & dipakai dedupe
penuh pada B4 Identity/Dedupe).
"""
from datetime import datetime, timezone

from services.counters import next_seq
from services.identity import normalize_phone  # re-export (B4): satu sumber normalisasi

QUO_STATUS = {"draft", "sent", "accepted", "rejected", "expired", "converted"}
QUO_STATUS_LABEL = {
    "draft": "Draft", "sent": "Terkirim", "accepted": "Diterima",
    "rejected": "Ditolak", "expired": "Kedaluwarsa", "converted": "Jadi Booking",
}


async def next_quotation_number(db) -> str:
    """Nomor penawaran unik dgn reset tahunan: QUO-<YYYY>-0001 (atomik)."""
    year = datetime.now(timezone.utc).year
    seq = await next_seq(db, f"quotation:{year}")
    return f"QUO-{year}-{seq:04d}"


def valid_until_iso(days: int = 7) -> str:
    from datetime import timedelta
    return (datetime.now(timezone.utc) + timedelta(days=max(int(days or 7), 1))).isoformat()
