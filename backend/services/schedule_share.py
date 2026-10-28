"""services/schedule_share.py — Share-link JADWAL KEBERANGKATAN (read-only, tanpa login).

Owner/ops membuat tautan dari Kalender Keberangkatan dengan memilih:
  * cakupan  : `upcoming` (mulai hari ini, N hari ke depan atau tanpa batas akhir),
               `month` (satu bulan), `range` (rentang tanggal), `all` (seluruh riwayat + mendatang)
  * saringan : status booking & (opsional) unit armada tertentu
  * visibilitas field: nama pelanggan, sopir (+ telepon), status pembayaran, catatan

Tautan menyimpan KRITERIA, bukan salinan data — penerima selalu melihat jadwal terbaru.
Payload publik dirakit lewat ALLOWLIST eksplisit (`public_departure`): nominal uang, telepon/
email pelanggan, ID internal & data risiko TIDAK PERNAH ikut, apa pun pilihan visibilitasnya.

Batas hari memakai zona waktu operasional WIB (UTC+7): "November 2026" = 1 Nov 00:00 WIB s/d
30 Nov 23:59 WIB, sehingga keberangkatan subuh tanggal 1 tidak terlempar ke bulan sebelumnya.
"""
from datetime import date, datetime, timedelta, timezone

from fastapi import HTTPException

from core_utils import now_iso
from services.calendar_export import period_label
from services.pricing import VEHICLE_TYPE_LABELS

BUSINESS_TZ = timezone(timedelta(hours=7))  # WIB — Bandung (operasional Jawa–Bali)
SCOPES = ("upcoming", "month", "range", "all")
SHAREABLE_STATUSES = ("pending", "hold", "confirmed", "ongoing", "completed", "cancelled")
DEFAULT_STATUSES = ["hold", "confirmed", "ongoing", "completed"]
VISIBILITY_KEYS = ("customer", "driver", "driver_phone", "payment", "notes")
DEFAULT_VISIBILITY = {"customer": True, "driver": True, "driver_phone": False, "payment": False, "notes": False}
MAX_RANGE_DAYS = 366
MAX_ITEMS = 1500

_MONTHS_SHORT = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]


def _parse_date(value: str, field: str) -> date:
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail=f"Tanggal {field} tidak valid (format YYYY-MM-DD)")


def _parse_month(value: str) -> date:
    try:
        y, m = str(value).split("-")
        return date(int(y), int(m), 1)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Bulan tidak valid (format YYYY-MM)")


def normalize_scope(scope_type: str, month=None, start=None, end=None, days=None) -> dict:
    """Validasi pilihan cakupan → dict tersimpan. Galat input → 400 (bukan 5xx)."""
    if scope_type not in SCOPES:
        raise HTTPException(status_code=400, detail="Cakupan jadwal tidak dikenal")
    if scope_type == "upcoming":
        n = int(days or 0)
        if n < 0 or n > MAX_RANGE_DAYS:
            raise HTTPException(status_code=400, detail=f"Jumlah hari 0–{MAX_RANGE_DAYS}")
        return {"type": "upcoming", "days": n or None}
    if scope_type == "month":
        if not month:
            raise HTTPException(status_code=400, detail="Pilih bulan yang dibagikan")
        return {"type": "month", "month": _parse_month(month).strftime("%Y-%m")}
    if scope_type == "range":
        if not (start and end):
            raise HTTPException(status_code=400, detail="Lengkapi tanggal mulai & selesai")
        s, e = _parse_date(start, "mulai"), _parse_date(end, "selesai")
        if e < s:
            raise HTTPException(status_code=400, detail="Tanggal selesai harus setelah tanggal mulai")
        if (e - s).days + 1 > MAX_RANGE_DAYS:
            raise HTTPException(status_code=400, detail=f"Rentang maksimal {MAX_RANGE_DAYS} hari")
        return {"type": "range", "start": s.isoformat(), "end": e.isoformat()}
    return {"type": "all"}


def _day_start_utc(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, tzinfo=BUSINESS_TZ).astimezone(timezone.utc)


def period_bounds(scope: dict, now: datetime = None):
    """(awal, akhir-eksklusif) dalam datetime UTC; None = tak dibatasi di sisi itu."""
    t = scope.get("type")
    if t == "upcoming":
        today = (now or datetime.now(timezone.utc)).astimezone(BUSINESS_TZ).date()
        lo = _day_start_utc(today)
        return lo, (lo + timedelta(days=scope["days"]) if scope.get("days") else None)
    if t == "month":
        first = _parse_month(scope["month"])
        nxt = date(first.year + (first.month == 12), first.month % 12 + 1, 1)
        return _day_start_utc(first), _day_start_utc(nxt)
    if t == "range":
        return (_day_start_utc(date.fromisoformat(scope["start"])),
                _day_start_utc(date.fromisoformat(scope["end"]) + timedelta(days=1)))
    return None, None


def _short(d: date) -> str:
    return f"{d.day} {_MONTHS_SHORT[d.month - 1]} {d.year}"


def scope_label(scope: dict, now: datetime = None) -> str:
    t = scope.get("type")
    if t == "month":
        return period_label(month=scope["month"])
    if t == "range":
        return period_label(start=scope["start"], end=scope["end"])
    if t == "upcoming":
        lo, hi = period_bounds(scope, now)
        start = lo.astimezone(BUSINESS_TZ).date()
        if not hi:
            return f"Semua jadwal mendatang (mulai {_short(start)})"
        last = (hi - timedelta(seconds=1)).astimezone(BUSINESS_TZ).date()
        return f"{scope['days']} hari ke depan ({_short(start)} – {_short(last)})"
    return "Semua keberangkatan"


def build_query(share: dict, now: datetime = None) -> dict:
    """Query `bookings` dari kriteria tautan (dipakai endpoint publik & hitungan di ERP)."""
    q = {"status": {"$in": list(share.get("statuses") or DEFAULT_STATUSES)}}
    if share.get("vehicle_ids"):
        q["vehicle_id"] = {"$in": list(share["vehicle_ids"])}
    lo, hi = period_bounds(share.get("scope") or {"type": "all"}, now)
    rng = {}
    if lo:
        rng["$gte"] = lo.isoformat()
    if hi:
        rng["$lt"] = hi.isoformat()
    if rng:
        q["start_datetime"] = rng
    return q


def public_departure(b: dict, vis: dict, vehicles: dict, drivers: dict) -> dict:
    """ALLOWLIST field yang boleh dilihat penerima tautan (read-only)."""
    veh = vehicles.get(b.get("vehicle_id")) or {}
    vtype = veh.get("type") or b.get("requested_vehicle_type")
    item = {
        "ref": b.get("code"),
        "start_datetime": b.get("start_datetime"), "end_datetime": b.get("end_datetime"),
        "origin": b.get("origin") or "", "destination": b.get("destination") or "",
        "status": b.get("status"), "pax": b.get("pax"),
        "vehicle_name": veh.get("name") or b.get("vehicle_name"),
        "plate_number": veh.get("plate_number"), "capacity": veh.get("capacity"),
        "vehicle_type_label": VEHICLE_TYPE_LABELS.get(vtype, (vtype or "").replace("_", " ")) or None,
    }
    if vis.get("customer"):
        item["customer_name"] = b.get("customer_name")
    if vis.get("driver"):
        item["driver_name"] = b.get("driver_name")
        if vis.get("driver_phone"):
            item["driver_phone"] = (drivers.get(b.get("driver_id")) or {}).get("phone")
    if vis.get("payment"):
        item["payment_status"] = b.get("payment_status")
    if vis.get("notes"):
        item["notes"] = b.get("notes") or ""
    return item


async def count_departures(db, share: dict) -> int:
    return await db.bookings.count_documents(build_query(share))


async def build_public_schedule(db, share: dict) -> dict:
    vis = {**DEFAULT_VISIBILITY, **(share.get("visibility") or {})}
    rows = await db.bookings.find(build_query(share), {"_id": 0}).sort("start_datetime", 1).to_list(MAX_ITEMS + 1)
    truncated = len(rows) > MAX_ITEMS
    rows = rows[:MAX_ITEMS]
    veh_ids = list({r["vehicle_id"] for r in rows if r.get("vehicle_id")})
    vehicles = {v["id"]: v for v in await db.vehicles.find(
        {"id": {"$in": veh_ids}}, {"_id": 0, "id": 1, "name": 1, "plate_number": 1, "capacity": 1, "type": 1}
    ).to_list(len(veh_ids) or 1)}
    drivers = {}
    if vis.get("driver") and vis.get("driver_phone"):
        drv_ids = list({r["driver_id"] for r in rows if r.get("driver_id")})
        drivers = {d["id"]: d for d in await db.drivers.find(
            {"id": {"$in": drv_ids}}, {"_id": 0, "id": 1, "phone": 1}).to_list(len(drv_ids) or 1)}
    lo, hi = period_bounds(share.get("scope") or {"type": "all"})
    return {
        "label": share.get("label") or "Jadwal Keberangkatan",
        "scope": share.get("scope"),
        "period_label": scope_label(share.get("scope") or {"type": "all"}),
        "period": {"start": lo.isoformat() if lo else None,
                   "end": (hi - timedelta(seconds=1)).isoformat() if hi else None},
        "statuses": share.get("statuses") or DEFAULT_STATUSES,
        "visibility": vis,
        "expires_at": share.get("expires_at"),
        "generated_at": now_iso(),
        "total": len(rows), "truncated": truncated,
        "items": [public_departure(r, vis, vehicles, drivers) for r in rows],
    }
