"""services/preventive.py — Servis preventif terjadwal (interval km + waktu).

Menghitung jatuh tempo servis berkala per armada berdasarkan DUA basis:
  - interval_km : vehicles.service_interval_km vs (odometer - last_service_odometer)
  - interval_hari: vehicles.service_interval_days vs (now - last_service_date)
Status akhir = paling mendesak antar-basis: overdue | due_soon | ok.
TIDAK membuat koleksi baru — konfigurasi menempel di dokumen `vehicles`.
"""
from datetime import datetime, timedelta, timezone

from services.geo import parse_iso

KM_SOON = 1000   # sisa <= 1000 km dianggap mendekati (due_soon)
DAYS_SOON = 14   # sisa <= 14 hari dianggap mendekati (due_soon)
ORDER = {"overdue": 0, "due_soon": 1, "ok": 2}


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _km_basis(v):
    interval = _num(v.get("service_interval_km"))
    last = _num(v.get("last_service_odometer"))
    odo = _num(v.get("odometer"))
    if not interval or last is None or odo is None:
        return None
    due_at_km = last + interval
    return {
        "interval_km": interval, "due_at_km": round(due_at_km),
        "odometer": round(odo), "remaining_km": round(due_at_km - odo),
    }


def _date_basis(v, now):
    interval = v.get("service_interval_days")
    last = parse_iso(v.get("last_service_date"))
    if not interval or not last:
        return None
    due_at = last + timedelta(days=int(interval))
    return {
        "interval_days": int(interval), "due_date": due_at.isoformat(),
        "remaining_days": (due_at - now).days,
    }


def _status(km, dt):
    st = "ok"
    if km:
        if km["remaining_km"] <= 0:
            st = "overdue"
        elif km["remaining_km"] <= KM_SOON:
            st = "due_soon"
    if dt:
        if dt["remaining_days"] < 0:
            st = "overdue"
        elif dt["remaining_days"] <= DAYS_SOON and st != "overdue":
            st = "due_soon"
    return st


def vehicle_preventive(v, now=None):
    """Hitung status preventif satu armada. None bila tak ada konfigurasi interval."""
    now = now or datetime.now(timezone.utc)
    km = _km_basis(v)
    dt = _date_basis(v, now)
    if not km and not dt:
        return None
    return {
        "vehicle_id": v.get("id"), "vehicle_name": v.get("name"), "code": v.get("code"),
        "odometer": v.get("odometer"), "last_service_date": v.get("last_service_date"),
        "last_service_odometer": v.get("last_service_odometer"),
        "km": km, "date": dt, "status": _status(km, dt),
    }


async def list_preventive(db):
    """Daftar armada ber-interval, terurut paling mendesak dulu."""
    veh = await db.vehicles.find({}, {"_id": 0}).to_list(2000)
    now = datetime.now(timezone.utc)
    out = [p for p in (vehicle_preventive(v, now) for v in veh) if p]
    out.sort(key=lambda r: (ORDER.get(r["status"], 9), r.get("vehicle_name") or ""))
    return out


async def summary(db):
    items = await list_preventive(db)
    return {
        "total": len(items),
        "overdue": sum(1 for i in items if i["status"] == "overdue"),
        "due_soon": sum(1 for i in items if i["status"] == "due_soon"),
        "ok": sum(1 for i in items if i["status"] == "ok"),
    }
