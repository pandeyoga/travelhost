"""routers/departures.py — lapisan risiko "Perlu Perhatian" untuk Kalender Keberangkatan.

Terpisah dari `bookings.py` (sudah ~770 baris, batas guardrail 800) dan sengaja
read-only: seluruh logika ada di `services/attention.py`.

GET /api/departures/attention?month=YYYY-MM
GET /api/departures/attention?start=YYYY-MM-DD&end=YYYY-MM-DD
"""
from fastapi import APIRouter, Depends, Query

from db import get_db
from dependencies import require_section
from services.attention import departure_attention

router = APIRouter(prefix="/api", tags=["departures"])
# RBAC-CAL-01: kalender keberangkatan = permukaan manajemen (owner/ops_admin).
# Driver TIDAK boleh melihat ringkasan risiko seluruh armada (SSOT: permissions_config.SECTION_ACCESS).
CALENDAR = require_section("calendar")


@router.get("/departures/attention")
async def departures_attention(month: str = Query(default=None), start: str = Query(default=None),
                               end: str = Query(default=None), user=Depends(CALENDAR)):
    """Ringkasan + detail risiko keberangkatan pada rentang tampilan kalender.

    Kelas risiko: bentrok armada, bentrok sopir, tabrakan perawatan, hold DP kedaluwarsa,
    belum ada sopir, permintaan menunggu, belum dibayar (mendekati keberangkatan).
    """
    return await departure_attention(get_db(), month=month, start=start, end=end)
