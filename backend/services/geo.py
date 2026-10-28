"""services/geo.py — helper waktu & geospasial bersama.

- parse_iso(): ISO-8601 (mendukung 'Z' & '+00:00') -> datetime aware UTC.
- haversine_km(): jarak great-circle (fallback bila OSRM tak tersedia).
- valid_coord(): validasi rentang lat/lng (INV-6).
- BUSINESS_TZ / business_date(): zona & tanggal operasional (WIB) — SSOT "hari apa ini" untuk
  surcharge akhir pekan/libur, syarat promo, batas periode jadwal. Data tetap disimpan UTC.
"""
from datetime import datetime, timedelta, timezone
from math import asin, cos, radians, sin, sqrt
from typing import Optional


BUSINESS_TZ = timezone(timedelta(hours=7))  # WIB — operasional Jawa–Bali


def business_date(value=None):
    """Tanggal kalender WIB untuk `value` (ISO/datetime; None → sekarang). None bila tak terbaca.

    Keberangkatan Sabtu 06:00 WIB = Jumat 23:00 UTC; memakai `.date()` UTC membuatnya
    dianggap hari kerja (surcharge & promo akhir pekan hilang).
    """
    dt = datetime.now(timezone.utc) if value is None else parse_iso(value)
    return dt.astimezone(BUSINESS_TZ).date() if dt else None


_MONTHS_ID = ("Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des")


def fmt_wib(value) -> str:
    """ISO/datetime → "28 Okt 2026 16.00 WIB" (teks notifikasi & WA; data tetap UTC)."""
    dt = parse_iso(value)
    if not dt:
        return "" if value is None else str(value)
    w = dt.astimezone(BUSINESS_TZ)
    return f"{w.day} {_MONTHS_ID[w.month - 1]} {w.year} {w:%H.%M} WIB"


def parse_iso(value) -> Optional[datetime]:
    """Konversi string ISO/atau datetime menjadi datetime aware UTC. None bila gagal."""
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        s = str(value).strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(s)
        except Exception:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def valid_coord(lat, lng) -> bool:
    try:
        return -90.0 <= float(lat) <= 90.0 and -180.0 <= float(lng) <= 180.0
    except (TypeError, ValueError):
        return False


def haversine_km(lat1, lng1, lat2, lng2) -> float:
    """Jarak great-circle (km). Dipakai sebagai fallback estimasi bila OSRM gagal."""
    r = 6371.0
    dlat = radians(float(lat2) - float(lat1))
    dlng = radians(float(lng2) - float(lng1))
    a = sin(dlat / 2) ** 2 + cos(radians(float(lat1))) * cos(radians(float(lat2))) * sin(dlng / 2) ** 2
    return round(2 * r * asin(sqrt(a)), 2)
