"""services/geo.py — helper waktu & geospasial bersama.

- parse_iso(): ISO-8601 (mendukung 'Z' & '+00:00') -> datetime aware UTC.
- haversine_km(): jarak great-circle (fallback bila OSRM tak tersedia).
- valid_coord(): validasi rentang lat/lng (INV-6).
"""
from datetime import datetime, timezone
from math import asin, cos, radians, sin, sqrt
from typing import Optional


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
