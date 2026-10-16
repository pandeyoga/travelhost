"""services/maps.py — Map/Routing Provider Adapter (AD-4).

Default provider = OSRM + OpenStreetMap (gratis, server-side). Struktur ini SIAP
di-swap ke Google Maps Directions tanpa mengubah pemanggil: cukup isi
`GOOGLE_MAPS_API_KEY` (env) lalu implementasikan `_google_route_eta`.

Pemanggil (router) cukup memakai `route_eta(...)` dari modul ini — bukan provider
spesifik — sehingga ganti provider = satu titik perubahan.
"""
import os

from services.osrm import fallback_eta as _fallback_eta
from services.osrm import route_eta as _osrm_route_eta

MAP_PROVIDER = os.environ.get("MAP_PROVIDER", "leaflet_osm")
GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY", "")


def provider_info():
    """Info provider aktif (untuk Settings/diagnostics)."""
    return {
        "provider": MAP_PROVIDER,
        "routing": "osrm",
        "google_ready": bool(GOOGLE_MAPS_API_KEY),
    }


async def route_eta(start_lat, start_lng, dest_lat, dest_lng, with_geometry=False):
    """Hitung jarak + ETA. Saat ini via OSRM; Google diaktifkan bila key tersedia.

    Mengembalikan dict {distance_km, eta_minutes, geometry[, approx]} atau None.
    """
    if GOOGLE_MAPS_API_KEY:
        google = await _google_route_eta(start_lat, start_lng, dest_lat, dest_lng, with_geometry)
        if google is not None:
            return google
    return await _osrm_route_eta(start_lat, start_lng, dest_lat, dest_lng, with_geometry)


def fallback_eta(start_lat, start_lng, dest_lat, dest_lng):
    """Estimasi haversine bila provider rute tak tersedia."""
    return _fallback_eta(start_lat, start_lng, dest_lat, dest_lng)


async def _google_route_eta(start_lat, start_lng, dest_lat, dest_lng, with_geometry=False):
    """Stub Google Directions — diaktifkan saat GOOGLE_MAPS_API_KEY diisi.

    Sengaja mengembalikan None agar fallback ke OSRM hingga implementasi nyata
    ditambahkan (key + endpoint Directions). Tidak memengaruhi alur saat ini.
    """
    return None
