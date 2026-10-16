"""services/osrm.py — client routing/ETA via OSRM (OSM gratis).

Adapter pattern (AD-4): bila ingin ganti ke Google Directions, cukup tukar implementasi
fungsi `route_eta()` tanpa mengubah router. Base URL dari env `OSRM_BASE_URL`.

Kontrak keluaran route_eta():
  {"distance_km": float, "eta_minutes": float, "geometry": [[lat,lng], ...] | []}
  -> None bila tidak ada rute / provider gagal (router boleh fallback haversine).
"""
import os

import httpx

from services.geo import haversine_km

OSRM_BASE_URL = os.environ.get("OSRM_BASE_URL", "https://router.project-osrm.org")
_AVG_SPEED_KMH = 40.0  # estimasi kasar untuk fallback ETA


async def route_eta(start_lat, start_lng, dest_lat, dest_lng, with_geometry: bool = False):
    """Hitung jarak + ETA berkendara antara dua titik via OSRM.

    with_geometry=True -> sertakan polyline [[lat,lng], ...] untuk peta.
    Mengembalikan None bila provider tidak mengembalikan rute valid.
    """
    coords = f"{float(start_lng)},{float(start_lat)};{float(dest_lng)},{float(dest_lat)}"
    url = f"{OSRM_BASE_URL}/route/v1/driving/{coords}"
    params = {"overview": "full" if with_geometry else "false"}
    if with_geometry:
        params["geometries"] = "geojson"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        return None
    if data.get("code") != "Ok" or not data.get("routes"):
        return None
    route = data["routes"][0]
    out = {
        "distance_km": round(float(route.get("distance", 0)) / 1000.0, 2),
        "eta_minutes": round(float(route.get("duration", 0)) / 60.0, 1),
        "geometry": [],
    }
    if with_geometry:
        # GeoJSON memakai [lng,lat]; Leaflet butuh [lat,lng].
        out["geometry"] = [[c[1], c[0]] for c in route.get("geometry", {}).get("coordinates", [])]
    return out


def fallback_eta(start_lat, start_lng, dest_lat, dest_lng):
    """Estimasi sederhana bila OSRM tak tersedia: haversine / kecepatan rata-rata."""
    dist = haversine_km(start_lat, start_lng, dest_lat, dest_lng)
    return {
        "distance_km": dist,
        "eta_minutes": round((dist / _AVG_SPEED_KMH) * 60.0, 1),
        "geometry": [[float(start_lat), float(start_lng)], [float(dest_lat), float(dest_lng)]],
        "approx": True,
    }
