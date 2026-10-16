"""services/availability.py — engine ANTI DOUBLE-BOOKING (INV-4).

Aturan: untuk vehicle_id sama, tidak boleh ada 2 booking berstatus aktif
(confirmed/ongoing) yang rentang [start,end] saling tumpang-tindih.

Fungsi murni `overlaps()` mudah diuji terpisah (POC). `find_conflicts()` memakai DB.

RC-16 (race/TOCTOU): karena cek `find_conflicts()` (baca) dan `insert`/`update` (tulis)
TIDAK atomik dan MongoDB di sini standalone (tanpa transaksi), pola baca-lalu-tulis
rawan balapan: N request paralel utk armada+waktu sama bisa sama-sama lolos cek lalu
sama-sama menulis → double-booking. `vehicle_lock()` menyediakan MUTEX per-armada
(koleksi `booking_locks`, `_id` unik) agar bagian kritis (cek-final + tulis) berjalan
serial per armada. Ada takeover lock basi + TTL index sebagai jaring pengaman crash.
"""
import asyncio
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from pymongo.errors import DuplicateKeyError

from services.geo import parse_iso

ACTIVE_BOOKING_STATUSES = {"hold", "confirmed", "ongoing"}  # E18: 'hold' mereservasi armada (DP-gate)

# --- MUTEX per-armada (anti-TOCTOU RC-16) ---
_LOCK_STALE_SECONDS = 20      # lock lebih tua dari ini dianggap basi (holder crash) → boleh diambil alih
_LOCK_ACQUIRE_TIMEOUT = 8.0   # batas tunggu total saat berebut lock
_LOCK_POLL = 0.03


async def _acquire_vehicle_lock(db, vehicle_id: str) -> str:
    key = f"vehicle:{vehicle_id}"
    deadline = time.monotonic() + _LOCK_ACQUIRE_TIMEOUT
    while True:
        now = datetime.now(timezone.utc)
        try:
            await db.booking_locks.insert_one({"_id": key, "acquired_at": now})
            return key
        except DuplicateKeyError:
            # Takeover lock basi (holder mungkin crash sebelum release / sebelum TTL jalan).
            await db.booking_locks.delete_one(
                {"_id": key, "acquired_at": {"$lt": now - timedelta(seconds=_LOCK_STALE_SECONDS)}})
            if time.monotonic() > deadline:
                # Fail-safe: jangan blok selamanya; sinyalkan sibuk agar klien retry.
                from fastapi import HTTPException
                raise HTTPException(status_code=409,
                                    detail="Armada sedang diproses permintaan lain, coba lagi sebentar")
            await asyncio.sleep(_LOCK_POLL)


async def _release_vehicle_lock(db, key: str) -> None:
    try:
        await db.booking_locks.delete_one({"_id": key})
    except Exception:  # noqa: BLE001 — release tidak boleh menutupi error bisnis
        pass


@asynccontextmanager
async def vehicle_lock(db, vehicle_id: str):
    """Mutex per-armada. Pakai utk membungkus cek-final ketersediaan + tulis booking."""
    key = await _acquire_vehicle_lock(db, vehicle_id)
    try:
        yield
    finally:
        await _release_vehicle_lock(db, key)


async def _acquire_driver_lock(db, driver_id: str) -> str:
    """RC-16 (dimensi DRIVER): mutex per-sopir — cegah 1 sopir di-assign paralel ke 2
    booking tumpang-tindih (TOCTOU) pada jalur non-atomik (mis. PATCH driver). Mekanisme
    identik `_acquire_vehicle_lock` (koleksi `booking_locks`, _id unik + takeover basi)."""
    key = f"driver:{driver_id}"
    deadline = time.monotonic() + _LOCK_ACQUIRE_TIMEOUT
    while True:
        now = datetime.now(timezone.utc)
        try:
            await db.booking_locks.insert_one({"_id": key, "acquired_at": now})
            return key
        except DuplicateKeyError:
            await db.booking_locks.delete_one(
                {"_id": key, "acquired_at": {"$lt": now - timedelta(seconds=_LOCK_STALE_SECONDS)}})
            if time.monotonic() > deadline:
                from fastapi import HTTPException
                raise HTTPException(status_code=409,
                                    detail="Driver sedang diproses permintaan lain, coba lagi sebentar")
            await asyncio.sleep(_LOCK_POLL)


@asynccontextmanager
async def driver_lock(db, driver_id: str):
    """Mutex per-sopir. Pakai utk membungkus cek-final konflik driver + tulis assignment."""
    key = await _acquire_driver_lock(db, driver_id)
    try:
        yield
    finally:
        await _release_vehicle_lock(db, key)  # release generik: hapus by _id


def overlaps(a_start, a_end, b_start, b_end) -> bool:
    """True bila rentang [a_start,a_end] dan [b_start,b_end] tumpang-tindih.

    Batas yang bersentuhan (a_end == b_start) TIDAK dianggap overlap.
    Menerima ISO string maupun datetime (dinormalkan ke UTC).
    """
    a_s, a_e = parse_iso(a_start), parse_iso(a_end)
    b_s, b_e = parse_iso(b_start), parse_iso(b_end)
    if not all([a_s, a_e, b_s, b_e]):
        return False
    return a_s < b_e and b_s < a_e


async def find_conflicts(db, vehicle_id: str, start, end, exclude_id: Optional[str] = None) -> List[dict]:
    """Kembalikan daftar booking aktif yang bentrok dengan rentang [start,end]."""
    if not vehicle_id:
        return []
    query = {"vehicle_id": vehicle_id, "status": {"$in": list(ACTIVE_BOOKING_STATUSES)}}
    if exclude_id:
        query["id"] = {"$ne": exclude_id}
    candidates = await db.bookings.find(query, {"_id": 0}).to_list(1000)
    conflicts = []
    for b in candidates:
        if b.get("start_datetime") and b.get("end_datetime") and overlaps(
            start, end, b["start_datetime"], b["end_datetime"]
        ):
            conflicts.append(b)
    return conflicts


async def is_available(db, vehicle_id: str, start, end, exclude_id: Optional[str] = None) -> bool:
    return len(await find_conflicts(db, vehicle_id, start, end, exclude_id)) == 0


async def find_driver_conflicts(db, driver_id: str, start, end,
                                exclude_booking_id: Optional[str] = None) -> List[dict]:
    """RC-07: daftar booking AKTIF (confirmed/ongoing) milik driver yang rentang
    waktunya tumpang-tindih dengan [start,end]. Analog `find_conflicts` tetapi dimensi
    DRIVER (bukan armada) — cegah 1 sopir di-assign ke 2 trip bentrok waktu.
    """
    if not driver_id:
        return []
    query = {"driver_id": driver_id, "status": {"$in": list(ACTIVE_BOOKING_STATUSES)}}
    if exclude_booking_id:
        query["id"] = {"$ne": exclude_booking_id}
    candidates = await db.bookings.find(query, {"_id": 0}).to_list(1000)
    conflicts = []
    for b in candidates:
        if b.get("start_datetime") and b.get("end_datetime") and overlaps(
            start, end, b["start_datetime"], b["end_datetime"]
        ):
            conflicts.append(b)
    return conflicts


# === Phase 6: maintenance window memblok availability (INV-21) ===
MAINT_BLOCKING_STATUSES = {"scheduled", "in_progress"}


async def find_maintenance_conflicts(db, vehicle_id: str, start, end) -> List[dict]:
    """Daftar window perawatan (status scheduled/in_progress) yang overlap [start,end]."""
    if not vehicle_id:
        return []
    recs = await db.maintenance_records.find(
        {"vehicle_id": vehicle_id, "status": {"$in": list(MAINT_BLOCKING_STATUSES)}},
        {"_id": 0},
    ).to_list(1000)
    out = []
    for m in recs:
        if m.get("start_date") and m.get("end_date") and overlaps(
            start, end, m["start_date"], m["end_date"]
        ):
            out.append(m)
    return out
