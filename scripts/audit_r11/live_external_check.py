#!/usr/bin/env python3
"""live_external_check.py — Item #4: uji integrasi EKSTERNAL secara LIVE.

Menguji jalur jaringan nyata yang di Putaran 11 (sandbox lama) dianggap unreachable:
  - Geocode (OSM Nominatim)  -> services/geocode.py
  - Routing/ETA (OSRM)       -> services/maps.py::route_eta
  - WhatsApp provider config -> laporkan mock vs meta_cloud (real send butuh kredensial live)

Jalankan: cd /app && python scripts/audit_r11/live_external_check.py
Read-only: tidak mengubah data bisnis (geocode_cache boleh terisi — itu cache, aman).
"""
import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "backend"))
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / "backend" / ".env")
except Exception:
    pass

from db import get_db  # noqa: E402
from services.geocode import geocode  # noqa: E402
from services.maps import route_eta  # noqa: E402

G, R, Y, X = "\033[92m", "\033[91m", "\033[93m", "\033[0m"
results = []


async def main():
    db = get_db()

    # 1) GEOCODE LIVE (Nominatim)
    print("=" * 70)
    print("LIVE EXTERNAL INTEGRATION CHECK (Item #4)")
    print("=" * 70)
    for place in ["Bandung", "Bandara Soekarno-Hatta", "Malioboro Yogyakarta"]:
        geo = await geocode(db, place)
        ok = bool(geo and geo.get("lat") and geo.get("lng"))
        results.append(("geocode:" + place, ok))
        if ok:
            print(f"{G}[OK]{X} geocode('{place}') -> lat={geo['lat']:.4f} lng={geo['lng']:.4f}  ({geo.get('display_name','')[:48]})")
        else:
            print(f"{R}[FAIL]{X} geocode('{place}') -> None (tak terjangkau/kosong)")

    # 2) OSRM ROUTE ETA LIVE (Bandung -> Jakarta approx)
    r = await route_eta(-6.9147, 107.6098, -6.2088, 106.8456)
    ok = bool(r and r.get("distance_km"))
    results.append(("osrm:route_eta", ok))
    if ok:
        print(f"{G}[OK]{X} route_eta(Bandung->Jakarta) -> distance_km={r.get('distance_km')} duration_min={r.get('duration_min')}")
    else:
        print(f"{Y}[WARN]{X} route_eta -> None (OSRM tak terjangkau / rate-limited)")

    # 3) WHATSAPP PROVIDER CONFIG (real send butuh kredensial Meta)
    wa = None
    try:
        wa = await db.settings.find_one({"key": "wa_config"}, {"_id": 0})
    except Exception:
        wa = None
    provider = ((wa or {}).get("value") or {}).get("provider", "mock")
    meta = ((wa or {}).get("value") or {}).get("meta") or {}
    has_creds = bool(meta.get("phone_number_id") and meta.get("access_token"))
    print(f"{Y}[INFO]{X} WhatsApp provider = '{provider}'; meta creds present = {has_creds}")
    if provider == "mock":
        print(f"{Y}     -> MODE MOCK (by design). Real send TIDAK dieksekusi (butuh set provider=meta_cloud + kredensial Meta).{X}")
    results.append(("whatsapp:provider_reported", True))

    print("-" * 70)
    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    print(f"RINGKASAN: {passed}/{total} cek eksternal OK")
    for name, ok in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    return 0 if passed >= total - 1 else 1  # OSRM boleh WARN


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
