"""services/geofence.py — geofence auto-status untuk trip (Phase 6).

Saat lokasi GPS masuk, bila armada memasuki radius titik penjemputan/tujuan,
status trip diperbarui otomatis:
  - tiba di pickup (origin) saat status standby/to_pickup  -> on_trip (start_at diisi)
  - tiba di tujuan (dest) saat status on_trip              -> completed (end_at diisi)

Murni & mudah diuji. Memakai haversine (services.geo).
"""
from services.geo import haversine_km

DEFAULT_RADIUS_M = 300.0


def within_radius(lat1, lng1, lat2, lng2, radius_m=DEFAULT_RADIUS_M):
    """True bila titik (lat1,lng1) berada dalam radius_m meter dari (lat2,lng2)."""
    if None in (lat1, lng1, lat2, lng2):
        return False
    try:
        return haversine_km(lat1, lng1, lat2, lng2) * 1000.0 <= float(radius_m)
    except (TypeError, ValueError):
        return False


def evaluate(trip, lat, lng, radius_m=DEFAULT_RADIUS_M):
    """Kembalikan (event, new_status) bila geofence terpicu, else (None, None)."""
    if not trip:
        return None, None
    status = trip.get("status")
    if status == "on_trip" and trip.get("dest_lat") is not None and trip.get("dest_lng") is not None:
        if within_radius(lat, lng, trip.get("dest_lat"), trip.get("dest_lng"), radius_m):
            return "arrived_destination", "completed"
    if status in ("standby", "to_pickup") and trip.get("origin_lat") is not None and trip.get("origin_lng") is not None:
        if within_radius(lat, lng, trip.get("origin_lat"), trip.get("origin_lng"), radius_m):
            return "arrived_pickup", "on_trip"
    return None, None
