"""services/geocode.py — Geocoding tujuan via OSM Nominatim (GRATIS, perbaiki gap G1).

Adapter pattern: default Nominatim (gratis, tanpa API key). Cache hasil di koleksi
`geocode_cache` (hemat rate-limit + idempotent). Mengembalikan {lat,lng,display_name} | None.
Bila ingin pindah ke Google Geocoding (E7), cukup tukar implementasi `_provider_geocode`.
"""
import logging
import os

import httpx

from core_utils import now_iso

logger = logging.getLogger("travel_fleet.geocode")

NOMINATIM_URL = os.environ.get("NOMINATIM_URL", "https://nominatim.openstreetmap.org/search")
GEOCODE_COUNTRY = os.environ.get("GEOCODE_COUNTRY", "id")  # batasi ke Indonesia (akurasi)
USER_AGENT = "travel-fleet-erp/1.0 (dispatch geocoder)"


def _norm(q):
    return " ".join((q or "").strip().lower().split())


async def _provider_geocode(query):
    """Panggil Nominatim. Return {lat,lng,display_name} | None (defensif)."""
    params = {"q": query, "format": "jsonv2", "limit": 1, "addressdetails": 0}
    if GEOCODE_COUNTRY:
        params["countrycodes"] = GEOCODE_COUNTRY
    try:
        async with httpx.AsyncClient(timeout=12.0, headers={"User-Agent": USER_AGENT}) as client:
            resp = await client.get(NOMINATIM_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("geocode gagal '%s': %s", query, exc)
        return None
    if not data:
        return None
    top = data[0]
    try:
        return {"lat": float(top["lat"]), "lng": float(top["lon"]),
                "display_name": top.get("display_name") or query}
    except (KeyError, TypeError, ValueError):
        return None


async def geocode(db, query):
    """Geocode teks tujuan -> {lat,lng,display_name} | None. Pakai cache bila ada."""
    q = _norm(query)
    if not q:
        return None
    if db is not None:
        try:
            cached = await db.geocode_cache.find_one({"q": q}, {"_id": 0})
        except Exception:  # noqa: BLE001
            cached = None
        if cached and cached.get("result"):
            return cached["result"]
    result = await _provider_geocode(query)
    if db is not None and result:
        try:
            await db.geocode_cache.update_one(
                {"q": q},
                {"$set": {"q": q, "query": query, "result": result,
                          "provider": "nominatim", "updated_at": now_iso()}},
                upsert=True,
            )
        except Exception:  # noqa: BLE001
            pass
    return result
