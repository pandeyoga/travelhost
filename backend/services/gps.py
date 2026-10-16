"""services/gps.py — GPS dual-source (E15): ingest device fisik via Traccar + failover.

Sumber lokasi:
- "phone"  : browser HP driver (POST /api/locations) — sudah ada sejak Phase 6.
- "device" : GPS tracker fisik (Teltonika FMC130) → Traccar → webhook POST /api/gps/webhook.

Kedua sumber mengisi koleksi `locations` (field `source`). Peta live memilih posisi per
armada dengan PRIORITAS device (bila fresh) lalu fallback phone — sesuai kebutuhan backup.

Konfigurasi device MENEMPEL di dokumen `vehicles` (TANPA koleksi baru):
  vehicles.gps      = {imei, provider:"traccar", enabled, note, installed_at}
  vehicles.gps_last = snapshot telemetri terakhir {at, power_v, battery, ignition, ...}

Alarm (powerCut/tamper/lowBattery/tow/sos) dipersist sbg notifikasi (`gps_alarm`) + event
`gps.alarm` (dedupe per armada+alarm+jam) karena Traccar mengirim alarm HANYA SEKALI saat kejadian.

Catatan protokol: speed dari Traccar berformat KNOT → dikonversi ×1.852 ke km/jam.
"""
from datetime import datetime, timezone

from core_utils import new_id, now_iso
from services.geo import parse_iso, valid_coord

KNOTS_TO_KMH = 1.852
STALE_SECONDS = 180          # sinkron dgn routers/locations (moving/idle vs offline)
MOVING_SPEED = 3.0           # km/j ambang bergerak
DEVICE_OFFLINE_SECONDS = 600  # device dianggap offline bila > 10 menit tanpa update

# Alarm yang dianggap penting → buat notifikasi. Nilai = label ID untuk UI.
ALARM_LABELS = {
    "powerCut": "Listrik/aki diputus",
    "power_cut": "Listrik/aki diputus",
    "tamper": "Perangkat GPS dirusak/dibuka",
    "lowBattery": "Baterai perangkat lemah",
    "low_battery": "Baterai perangkat lemah",
    "sos": "Tombol SOS ditekan",
    "tow": "Kendaraan diderek (tow)",
    "movement": "Bergerak tanpa izin",
    "vibration": "Getaran terdeteksi",
    "geofenceExit": "Keluar area geofence",
    "hardAcceleration": "Akselerasi mendadak",
    "hardBraking": "Pengereman mendadak",
    "overspeed": "Melebihi batas kecepatan",
    "jamming": "Sinyal GPS di-jamming",
}
CRITICAL_ALARMS = {"powerCut", "power_cut", "tamper", "sos", "tow", "jamming",
                   "lowBattery", "low_battery"}


def _b(v):
    """Normalisasi nilai boolean dari berbagai bentuk (bool/num/str)."""
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v != 0
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "yes", "on")
    return None


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def parse_traccar(payload):
    """Normalisasi payload Traccar position-forward → dict standar. Defensif thd variasi versi.

    Traccar (forward.type=json) mengirim: {position:{latitude,longitude,speed,course,fixTime,
    valid,attributes:{...}}, device:{uniqueId,name}}. Sebagian setup mengirim flat — di-handle.
    """
    payload = payload or {}
    pos = payload.get("position") or payload
    dev = payload.get("device") or {}
    attrs = pos.get("attributes") or {}
    imei = (dev.get("uniqueId") or payload.get("uniqueId")
            or pos.get("uniqueId") or attrs.get("uniqueId"))
    speed_knot = pos.get("speed")
    speed_kmh = round(_f(speed_knot) * KNOTS_TO_KMH, 1) if _f(speed_knot) is not None else 0.0
    return {
        "imei": str(imei) if imei is not None else None,
        "name": dev.get("name"),
        "lat": _f(pos.get("latitude", pos.get("lat"))),
        "lng": _f(pos.get("longitude", pos.get("lng"))),
        "speed_kmh": speed_kmh,
        "heading": _f(pos.get("course")) or 0.0,
        "valid": pos.get("valid", True),
        "fix_time": pos.get("fixTime") or pos.get("deviceTime"),
        "ignition": _b(attrs.get("ignition")),
        "motion": _b(attrs.get("motion")),
        "power_v": _f(attrs.get("power")),
        "battery": _f(attrs.get("battery")),
        "battery_level": attrs.get("batteryLevel"),
        "blocked": _b(attrs.get("blocked")),
        "out1": _b(attrs.get("out1")),
        "sat": attrs.get("sat"),
        "alarm": attrs.get("alarm"),
    }


async def find_vehicle_by_imei(db, imei):
    if not imei:
        return None
    return await db.vehicles.find_one({"gps.imei": imei}, {"_id": 0})


async def _active_trip(db, vehicle_id):
    return await db.trips.find_one(
        {"vehicle_id": vehicle_id, "status": {"$in": ["to_pickup", "on_trip"]}},
        {"_id": 0}, sort=[("created_at", -1)])


async def ingest_device(db, norm):
    """Simpan titik device ke `locations` (source=device) + update snapshot armada + alarm.

    Return dict status. TIDAK raise untuk payload tak dikenal supaya Traccar tak retry-storm.
    """
    imei = norm.get("imei")
    if not imei:
        return {"status": "ignored", "reason": "no_imei"}
    if not valid_coord(norm.get("lat"), norm.get("lng")):
        return {"status": "ignored", "reason": "invalid_coord", "imei": imei}
    veh = await find_vehicle_by_imei(db, imei)
    if not veh:
        return {"status": "ignored", "reason": "imei_unmapped", "imei": imei}
    vehicle_id = veh["id"]
    trip = await _active_trip(db, vehicle_id)
    trip_id = trip["id"] if trip else None
    driver_id = (trip or {}).get("driver_id")

    doc = {
        "id": new_id("loc"), "trip_id": trip_id, "driver_id": driver_id,
        "vehicle_id": vehicle_id, "source": "device",
        "lat": float(norm["lat"]), "lng": float(norm["lng"]),
        "speed": float(norm["speed_kmh"] or 0), "heading": float(norm["heading"] or 0),
        "ignition": norm.get("ignition"), "power_v": norm.get("power_v"),
        "battery": norm.get("battery"), "blocked": norm.get("blocked"),
        "alarm": norm.get("alarm"), "imei": imei, "timestamp": now_iso(),
    }
    await db.locations.insert_one(doc)

    snap = {
        "at": doc["timestamp"], "lat": doc["lat"], "lng": doc["lng"], "speed": doc["speed"],
        "ignition": norm.get("ignition"), "motion": norm.get("motion"),
        "power_v": norm.get("power_v"), "battery": norm.get("battery"),
        "battery_level": norm.get("battery_level"), "blocked": norm.get("blocked"),
        "sat": norm.get("sat"), "alarm": norm.get("alarm"),
    }
    await db.vehicles.update_one({"id": vehicle_id}, {"$set": {"gps_last": snap}})

    # Geofence auto-status utk device (bila ada trip aktif) — konsisten dgn ingest phone.
    geofence = None
    if trip:
        try:
            from services.geofence import evaluate as evaluate_geofence
            event, new_status = evaluate_geofence(trip, doc["lat"], doc["lng"])
            if new_status and new_status != trip.get("status"):
                updates = {"status": new_status}
                if new_status == "on_trip" and not trip.get("start_at"):
                    updates["start_at"] = now_iso()
                if new_status == "completed":
                    updates["end_at"] = now_iso()
                await db.trips.update_one({"id": trip_id}, {"$set": updates})
                geofence = {"event": event, "new_status": new_status}
        except Exception:  # noqa: BLE001 — geofence tak boleh gagalkan ingest
            geofence = None

    alarm_created = await _handle_alarm(db, veh, norm)
    out = {"status": "ok", "vehicle_id": vehicle_id, "source": "device",
           "trip_id": trip_id, "speed_kmh": doc["speed"], "alarm": alarm_created}
    if geofence:
        out["geofence"] = geofence
    return out


async def _handle_alarm(db, veh, norm):
    alarm = norm.get("alarm")
    if not alarm or alarm not in ALARM_LABELS:
        return None
    label = ALARM_LABELS.get(alarm, alarm)
    hour_key = datetime.now(timezone.utc).strftime("%Y%m%d%H")
    dedupe = f"gps_alarm:{veh['id']}:{alarm}:{hour_key}"
    from services.notifications import create_task
    created = await create_task(db, dedupe, {
        "type": "gps_alarm",
        "title": f"Alarm GPS: {label}",
        "body": f"{veh.get('name')} ({veh.get('plate_number') or veh.get('code')}): {label}.",
        "target_role": "manager",
        "ref_type": "vehicle", "ref_id": veh["id"],
        "severity": "critical" if alarm in CRITICAL_ALARMS else "warning",
    })
    if created:
        from services.events import emit
        await emit(db, "gps.alarm", {
            "vehicle_id": veh["id"], "vehicle_name": veh.get("name"),
            "plate_number": veh.get("plate_number"), "alarm": alarm, "label": label,
        }, source="gps", ref_type="vehicle", ref_id=veh["id"], dedupe_key=dedupe)
    return {"alarm": alarm, "label": label, "created": bool(created)}


def _live_status(speed, stale):
    if stale:
        return "offline"
    return "moving" if float(speed or 0) > MOVING_SPEED else "idle"


def _fresh(doc, now):
    ts = parse_iso(doc.get("timestamp"))
    return ts is not None and (now - ts).total_seconds() <= STALE_SECONDS


async def live_positions(db):
    """Posisi live per armada dgn FAILOVER: device (fresh) diprioritaskan atas phone.

    Bila device fresh → pakai device. Bila tidak, pakai phone (fresh). Bila keduanya stale
    → ambil yang paling baru (ditandai stale/offline). Menyertakan `source` + telemetri device.
    """
    pipeline = [
        {"$match": {"vehicle_id": {"$ne": None}}},
        {"$sort": {"timestamp": -1}},
        {"$group": {"_id": {"v": "$vehicle_id", "s": {"$ifNull": ["$source", "phone"]}},
                    "doc": {"$first": "$$ROOT"}}},
    ]
    grouped = await db.locations.aggregate(pipeline).to_list(4000)
    per_vehicle = {}
    for g in grouped:
        per_vehicle.setdefault(g["_id"]["v"], {})[g["_id"]["s"]] = g["doc"]

    now = datetime.now(timezone.utc)
    veh_ids = list(per_vehicle.keys())
    vehicles = await db.vehicles.find({"id": {"$in": veh_ids}}, {"_id": 0}).to_list(1000)
    vmap = {v["id"]: v for v in vehicles}

    out, driver_ids = [], []
    for vid, sources in per_vehicle.items():
        dev, phone = sources.get("device"), sources.get("phone")
        chosen, chosen_src = None, None
        if dev and _fresh(dev, now):
            chosen, chosen_src = dev, "device"
        elif phone and _fresh(phone, now):
            chosen, chosen_src = phone, "phone"
        else:
            cands = [(s, d) for s, d in (("device", dev), ("phone", phone)) if d]
            cands.sort(key=lambda x: x[1].get("timestamp") or "", reverse=True)
            if cands:
                chosen_src, chosen = cands[0]
        if not chosen:
            continue
        veh = vmap.get(vid, {})
        ts = parse_iso(chosen.get("timestamp"))
        age = (now - ts).total_seconds() if ts else None
        stale = age is None or age > STALE_SECONDS
        if chosen.get("driver_id"):
            driver_ids.append(chosen["driver_id"])
        out.append({
            "vehicle_id": vid, "vehicle_name": veh.get("name"), "plate_number": veh.get("plate_number"),
            "driver_id": chosen.get("driver_id"), "driver_name": None,
            "trip_id": chosen.get("trip_id"),
            "lat": chosen.get("lat"), "lng": chosen.get("lng"),
            "speed": chosen.get("speed"), "heading": chosen.get("heading"),
            "timestamp": chosen.get("timestamp"), "last_seen": chosen.get("timestamp"),
            "age_seconds": round(age) if age is not None else None, "stale": stale,
            "live_status": _live_status(chosen.get("speed"), stale),
            "source": chosen_src, "has_device": bool(dev), "has_phone": bool(phone),
            "ignition": chosen.get("ignition"), "power_v": chosen.get("power_v"),
            "battery": chosen.get("battery"), "blocked": chosen.get("blocked"),
            "alarm": chosen.get("alarm"),
        })
    if driver_ids:
        drivers = await db.drivers.find({"id": {"$in": driver_ids}},
                                        {"_id": 0, "id": 1, "name": 1}).to_list(1000)
        dmap = {d["id"]: d.get("name") for d in drivers}
        for o in out:
            if o.get("driver_id"):
                o["driver_name"] = dmap.get(o["driver_id"])
    out.sort(key=lambda r: (r.get("vehicle_name") or ""))
    return out


async def list_devices(db):
    """Daftar SEMUA armada + status device GPS (utk halaman manajemen Perangkat GPS)."""
    veh = await db.vehicles.find({}, {"_id": 0}).sort("code", 1).to_list(1000)
    now = datetime.now(timezone.utc)
    out = []
    for v in veh:
        gps = v.get("gps") or {}
        last = v.get("gps_last") or {}
        ts = parse_iso(last.get("at"))
        age = (now - ts).total_seconds() if ts else None
        online = age is not None and age <= DEVICE_OFFLINE_SECONDS
        out.append({
            "vehicle_id": v["id"], "code": v.get("code"), "name": v.get("name"),
            "plate_number": v.get("plate_number"),
            "imei": gps.get("imei"), "enabled": gps.get("enabled", bool(gps.get("imei"))),
            "provider": gps.get("provider", "traccar"), "note": gps.get("note"),
            "installed_at": gps.get("installed_at"), "has_device": bool(gps.get("imei")),
            "online": bool(online), "last_seen": last.get("at"),
            "age_seconds": round(age) if age is not None else None,
            "power_v": last.get("power_v"), "battery": last.get("battery"),
            "ignition": last.get("ignition"), "blocked": last.get("blocked"),
            "last_alarm": last.get("alarm"), "speed": last.get("speed"),
        })
    return out


async def summary(db):
    devices = await list_devices(db)
    with_dev = [d for d in devices if d["has_device"]]
    return {
        "total_vehicles": len(devices),
        "with_device": len(with_dev),
        "online": sum(1 for d in with_dev if d["online"]),
        "offline": sum(1 for d in with_dev if not d["online"]),
        "alarms": sum(1 for d in with_dev if d.get("last_alarm")),
    }


async def assign_device(db, vehicle_id, imei, enabled=True, note=""):
    veh = await db.vehicles.find_one({"id": vehicle_id}, {"_id": 0})
    if not veh:
        return None, "Kendaraan tidak ditemukan"
    imei = (imei or "").strip()
    if not imei:
        return None, "IMEI wajib diisi"
    clash = await db.vehicles.find_one({"gps.imei": imei, "id": {"$ne": vehicle_id}},
                                       {"_id": 0, "id": 1, "name": 1})
    if clash:
        return None, f"IMEI sudah dipakai armada lain ({clash.get('name')})"
    gps = {
        "imei": imei, "provider": "traccar", "enabled": bool(enabled), "note": note or "",
        "installed_at": (veh.get("gps") or {}).get("installed_at") or now_iso(),
    }
    await db.vehicles.update_one({"id": vehicle_id}, {"$set": {"gps": gps}})
    return await db.vehicles.find_one({"id": vehicle_id}, {"_id": 0}), None


async def unassign_device(db, vehicle_id):
    veh = await db.vehicles.find_one({"id": vehicle_id}, {"_id": 0})
    if not veh:
        return False
    await db.vehicles.update_one({"id": vehicle_id}, {"$unset": {"gps": "", "gps_last": ""}})
    return True
