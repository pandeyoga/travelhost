"""services/trips.py — util perhitungan trip (E9 Phase B: Trip/KM & odometer).

- compute_distance: tentukan jarak tempuh trip dari odometer (akurat) atau
  estimasi rute OSRM (fallback). Mengembalikan (distance_km, basis|None).
  Prioritas: odometer (end-start) > est_distance_km (OSRM) > None.
- driver_stats / vehicle_stats: agregat total trip, total km, revenue + daftar trip terbaru
  (riwayat) untuk drawer detail driver & armada.
- finalize_trip_completion: SSOT penyelesaian trip (RC-03) — dipakai driver/checkout
  DAN trips/{id}/status=completed agar efek samping identik (anti split-brain).
"""
from pymongo.errors import DuplicateKeyError

from core_utils import money, new_id, now_iso, safe_doc


def compute_distance(odometer_start, odometer_end, est_distance_km=None):
    """(distance_km, basis) — basis: 'odometer' | 'osrm' | None."""
    if odometer_start is not None and odometer_end is not None:
        try:
            s, e = float(odometer_start), float(odometer_end)
            if e >= s:
                return round(e - s, 1), "odometer"
        except (TypeError, ValueError):
            pass
    if est_distance_km:
        try:
            v = float(est_distance_km)
            if v > 0:
                return round(v, 1), "osrm"
        except (TypeError, ValueError):
            pass
    return None, None


async def _name_maps(db):
    veh = {v["id"]: v.get("name") for v in await db.vehicles.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(2000)}
    drv = {d["id"]: d.get("name") for d in await db.drivers.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(2000)}
    return veh, drv


async def _recent(db, trips, limit=25):
    veh, drv = await _name_maps(db)
    out = []
    for t in trips[:limit]:
        bk = await db.bookings.find_one(
            {"id": t.get("booking_id")},
            {"_id": 0, "code": 1, "customer_name": 1, "origin": 1, "destination": 1}) or {}
        out.append({
            "id": t.get("id"), "booking_id": t.get("booking_id"), "code": bk.get("code"),
            "customer_name": bk.get("customer_name"),
            "origin": bk.get("origin"), "destination": bk.get("destination") or t.get("dest_name"),
            "status": t.get("status"), "start_at": t.get("start_at"), "end_at": t.get("end_at"),
            "distance_km": round(float(t.get("distance_km") or 0), 1), "distance_basis": t.get("distance_basis"),
            "revenue": round(float(t.get("revenue") or 0), 2),
            "vehicle_id": t.get("vehicle_id"), "vehicle_name": veh.get(t.get("vehicle_id")),
            "driver_id": t.get("driver_id"), "driver_name": drv.get(t.get("driver_id")),
        })
    return out


def _totals(trips):
    total = len(trips)
    completed = sum(1 for t in trips if t.get("status") == "completed")
    return {
        "total_trips": total, "completed": completed,
        "completion_rate": round(completed / total * 100, 1) if total else 0.0,
        "total_km": round(sum(float(t.get("distance_km") or 0) for t in trips), 1),
        "total_revenue": round(sum(float(t.get("revenue") or 0) for t in trips), 2),
    }


async def driver_stats(db, driver_id):
    trips = await db.trips.find({"driver_id": driver_id}, {"_id": 0}).sort("created_at", -1).to_list(3000)
    stats = _totals(trips)
    stats["last_trip_at"] = (trips[0].get("end_at") or trips[0].get("start_at")
                             or trips[0].get("created_at")) if trips else None
    return stats, await _recent(db, trips)


async def vehicle_stats(db, vehicle_id):
    trips = await db.trips.find({"vehicle_id": vehicle_id}, {"_id": 0}).sort("created_at", -1).to_list(3000)
    t = _totals(trips)
    totals = {"trips": t["total_trips"], "completed": t["completed"],
              "distance_km": t["total_km"], "revenue": t["total_revenue"]}
    return totals, await _recent(db, trips)


# === RC-03: SSOT penyelesaian trip (dipakai driver/checkout & trips/status=completed) ===
_ACTIVE_TRIP_STATUSES = ["standby", "to_pickup", "on_trip"]
STARTED_TRIP_STATUSES = ("to_pickup", "on_trip")
TERMINAL_TRIP_STATUSES = ("completed", "cancelled")
# Transisi MAJU yang sah lewat apply_trip_status (selesai lewat finalize_trip_completion).
# standby → on_trip diizinkan utk geofence jemput / sopir yang lupa menekan "berangkat".
_FORWARD = {"standby": ("to_pickup", "on_trip"), "to_pickup": ("on_trip",), "on_trip": ()}
TRIP_LABEL = {"standby": "Terjadwal", "to_pickup": "Menjemput", "on_trip": "Dalam Perjalanan",
              "completed": "Selesai", "cancelled": "Dibatalkan"}
CLOSED_BOOKING_STATUSES = ("completed", "cancelled")
# Status armada yang TIDAK boleh ditimpa otomatis oleh trip (dulu assign/selesai trip menimpa
# 'maintenance'/'inactive'/'sold' jadi on_trip/available → unit rusak/terjual tampak siap jalan).
_TERMINAL_LABEL = {"completed": "selesai", "cancelled": "dibatalkan"}


def _held_vehicle_statuses() -> list:
    from services.booking_search import BLOCKED_VEHICLE_STATUS
    return ["maintenance", *BLOCKED_VEHICLE_STATUS]


class TripStateError(ValueError):
    """Transisi trip/booking tidak sah (trip/booking sudah selesai/batal) → HTTP 400 (server.py)."""


async def assert_trip_open(db, trip: dict, action: str, *, allow_completed=False):
    """Tolak aksi pada trip/booking yang sudah ditutup (anti status "zombie").

    Dulu check-in/checkout/POD/tiba tetap jalan pada trip yang bookingnya dibatalkan →
    armada kembali 'on_trip', fee sopir terkredit, WA terkirim ke pesanan batal.
    """
    st = trip.get("status")
    if st == "cancelled" or (st == "completed" and not allow_completed):
        raise TripStateError(f"Trip sudah {_TERMINAL_LABEL[st]} — tidak bisa {action}")
    if trip.get("booking_id"):
        bk = await db.bookings.find_one({"id": trip["booking_id"]}, {"_id": 0, "status": 1}) or {}
        if bk.get("status") == "cancelled" or (bk.get("status") == "completed" and not allow_completed):
            raise TripStateError(f"Booking sudah {_TERMINAL_LABEL[bk['status']]} — tidak bisa {action}")


async def assert_trip_state(trip: dict, allowed, action: str):
    """Aksi hanya sah pada status tertentu (mis. POD/tiba setelah perjalanan dimulai)."""
    if trip.get("status") not in allowed:
        now = TRIP_LABEL.get(trip.get("status"), trip.get("status"))
        raise TripStateError(f"Trip masih '{now}' — belum bisa {action}")


async def notify_ops(db, trip: dict, kind: str, title: str, body: str) -> None:
    """Notifikasi in-app ke ops (owner/ops_admin) utk tiap update sopir. Idempotent per trip+jenis."""
    try:
        from services.notifications import create_task
        await create_task(db, f"trip-{kind}:{trip['id']}", {
            "type": f"trip_{kind}", "title": title, "body": body, "target_role": "manager",
            "ref_type": "trip", "ref_id": trip["id"], "booking_id": trip.get("booking_id"),
            "scheduled_at": now_iso()})
    except Exception:  # noqa: BLE001 — notifikasi tak boleh menggagalkan aksi sopir
        pass


async def _trip_ref(db, trip: dict) -> str:
    bk = await db.bookings.find_one({"id": trip.get("booking_id")}, {"_id": 0, "code": 1, "customer_name": 1}) or {}
    drv = await db.drivers.find_one({"id": trip.get("driver_id")}, {"_id": 0, "name": 1}) or {}
    return f"{bk.get('code') or '-'} · {drv.get('name') or 'sopir'}" + (
        f" · {bk['customer_name']}" if bk.get("customer_name") else "")


async def mark_vehicle_in_use(db, vehicle_id) -> None:
    """Armada → on_trip, KECUALI sedang perawatan/nonaktif/terjual (status itu dipertahankan)."""
    if vehicle_id:
        await db.vehicles.update_one({"id": vehicle_id, "status": {"$nin": _held_vehicle_statuses()}},
                                     {"$set": {"status": "on_trip"}})


async def release_vehicle(db, vehicle_id, *, odometer=None, exclude_trip_id=None,
                          exclude_booking_id=None) -> None:
    """SSOT pembebasan armada: on_trip → available bila tak ada trip aktif lain.

    Hanya 'on_trip' yang dikembalikan; perawatan/nonaktif/terjual tidak disentuh. Odometer
    naik-saja (`$max`) — tak pernah turun karena angka checkout yang salah ketik.
    """
    if not vehicle_id:
        return
    if odometer is not None:
        await db.vehicles.update_one({"id": vehicle_id}, {"$max": {"odometer": float(odometer)}})
    q = {"vehicle_id": vehicle_id, "status": {"$in": _ACTIVE_TRIP_STATUSES}}
    if exclude_trip_id:
        q["id"] = {"$ne": exclude_trip_id}
    if exclude_booking_id:
        q["booking_id"] = {"$ne": exclude_booking_id}
    if not await db.trips.find_one(q, {"_id": 0, "id": 1}):
        await db.vehicles.update_one({"id": vehicle_id, "status": "on_trip"},
                                     {"$set": {"status": "available"}})


async def finalize_trip_completion(db, trip: dict, user=None, odometer_end=None, force=False) -> dict:
    """Selesaikan trip dengan efek samping LENGKAP & KONSISTEN (satu jalur, anti split-brain):
      1) trip → completed + end_at + distance_km/basis (odometer > OSRM est).
      2) armada dibebaskan → available (kecuali masih ada trip aktif lain pd armada itu);
         odometer armada dinaikkan bila odometer_end lebih besar.
      3) booking terkait → completed, lalu payment_status DITURUNKAN ULANG (RC-02) —
         jujur secara finansial (tetap 'dp'/'belum_bayar' bila belum lunas).
      4) driver → offline bila tak ada tugas aktif lain.
      5) emit `trip.completed` (idempotent) + audit.
    Idempotent: trip yang SUDAH selesai dikembalikan apa adanya (dulu checkout ulang menimpa
    odometer & km → uang jalan per km bisa dimanipulasi). Trip yang belum dimulai (standby)
    ditolak kecuali `force` (ops menutup booking yang jadwalnya sudah lewat).
    """
    from services.finance import recompute_booking_payment

    await assert_trip_open(db, trip, "diselesaikan", allow_completed=True)
    trip_id = trip["id"]
    if trip.get("status") == "completed":
        return safe_doc(await db.trips.find_one({"id": trip_id}, {"_id": 0}))
    if trip.get("status") == "standby" and not force:
        raise TripStateError("Trip belum dimulai — sopir harus check-in (berangkat menjemput) dulu")
    odo_end = odometer_end if odometer_end is not None else trip.get("odometer_end")
    if odo_end is not None:
        floor_val, floor_lbl = trip.get("odometer_start"), "odometer awal"
        if floor_val is None and trip.get("vehicle_id"):
            veh = await db.vehicles.find_one({"id": trip["vehicle_id"]}, {"_id": 0, "odometer": 1}) or {}
            floor_val, floor_lbl = veh.get("odometer"), "odometer armada"
        if floor_val is not None and float(odo_end) < float(floor_val):
            raise TripStateError(f"Odometer akhir ({float(odo_end):,.0f}) lebih kecil dari {floor_lbl} "
                                 f"({float(floor_val):,.0f}) — periksa angkanya".replace(",", "."))
    dist, basis = compute_distance(trip.get("odometer_start"), odo_end, trip.get("est_distance_km"))
    set_fields = {"status": "completed"}
    if not trip.get("end_at"):
        set_fields["end_at"] = now_iso()
    if odo_end is not None:
        set_fields["odometer_end"] = float(odo_end)
    if dist is not None:
        set_fields["distance_km"] = dist
        set_fields["distance_basis"] = basis
    # CAS: hanya dari status asal (batal / selesai paralel di antara baca & tulis → tak ditimpa).
    done = await db.trips.update_one({"id": trip_id, "status": trip.get("status")}, {"$set": set_fields})
    if not done.matched_count:
        latest = await db.trips.find_one({"id": trip_id}, {"_id": 0}) or {}
        if latest.get("status") == "completed":
            return safe_doc(latest)
        raise TripStateError("Status trip baru saja berubah — muat ulang")

    # (2) Bebaskan armada (on_trip → available; perawatan/nonaktif/terjual dipertahankan).
    await release_vehicle(db, trip.get("vehicle_id"), odometer=odo_end, exclude_trip_id=trip_id)

    # (3) Selesaikan booking + derivasi payment_status jujur (RC-02).
    bkid = trip.get("booking_id")
    if bkid:
        res = await db.bookings.update_one(
            {"id": bkid, "status": {"$in": ["ongoing", "confirmed"]}},
            {"$set": {"status": "completed"}})
        await recompute_booking_payment(db, bkid)
        if res.modified_count:
            try:
                from services.audit import record
                await record(db, actor=user or {}, action="trip_complete", entity_type="booking",
                             entity_id=bkid, summary="Trip selesai -> booking completed")
            except Exception:  # noqa: BLE001
                pass
            try:
                from services.events import emit
                from services.wa_payload import build_wa_payload
                bk = await db.bookings.find_one({"id": bkid}, {"_id": 0})
                if bk:
                    payload = await build_wa_payload(db, bk)
                    await emit(db, "trip.completed", payload, source="trips", ref_type="booking",
                               ref_id=bkid, dedupe_key=f"trip.completed:{bkid}")
            except Exception:  # noqa: BLE001
                pass
            # CMS-07 — funnel ulasan: trip selesai adalah SATU-SATUNYA momen tepat meminta
            # ulasan (pengalaman masih segar). Idempotent per pesanan; WhatsApp masih MOCK
            # (pesan tercatat di Inbox). Kegagalan di sini TIDAK boleh membatalkan trip.
            try:
                from services import reviews as _reviews
                bk_doc = await db.bookings.find_one({"id": bkid}, {"_id": 0})
                if bk_doc:
                    await _reviews.request_and_send(db, bk_doc, actor=user, source="trip_completed")
            except Exception:  # noqa: BLE001
                pass

    # (3b) Kredit FEE driver per keberangkatan (rate ditetapkan saat assign) — idempotent
    # per trip: trip yang sama tidak pernah menambah saldo dua kali.
    fresh = await db.trips.find_one({"id": trip_id}, {"_id": 0}) or trip
    if fresh.get("driver_id") and float(fresh.get("driver_fee_rate") or 0) > 0:
        dup = await db.driver_fee_entries.find_one({"trip_id": trip_id}, {"_id": 0, "id": 1})
        if not dup:
            bk_fee = await db.bookings.find_one({"id": fresh.get("booking_id")}, {"_id": 0, "code": 1}) or {}
            drv_fee = await db.drivers.find_one({"id": fresh["driver_id"]}, {"_id": 0, "name": 1}) or {}
            days = max(1, int(fresh.get("driver_fee_days") or 1))
            rate = money(fresh.get("driver_fee_rate"))
            amount = money(fresh.get("driver_fee_total") or rate * days)
            entry = {
                "id": new_id("dfe"), "driver_id": fresh["driver_id"],
                "driver_name": drv_fee.get("name"), "trip_id": trip_id,
                "booking_id": fresh.get("booking_id"), "booking_code": bk_fee.get("code"),
                "rate": rate, "days": days, "amount": amount,
                "status": "earned", "created_at": now_iso(),
            }
            try:  # unik per trip_id (index server.py) → finalize paralel tak mengkredit dua kali
                await db.driver_fee_entries.insert_one(dict(entry))
                # Biaya diakui SAAT DIPEROLEH (akrual, terkait trip & unit) — bukan saat dicairkan.
                from services.driver_fee_ledger import accrue_fee
                await accrue_fee(db, entry, fresh)
            except DuplicateKeyError:
                pass

    await notify_ops(db, trip, "completed", f"Trip selesai: {await _trip_ref(db, trip)}",
                     f"Jarak {dist or 0:g} km ({basis or 'tanpa odometer'})." if dist else "Trip ditutup.")

    # (4) Driver offline bila tak ada tugas aktif lain.
    did = trip.get("driver_id")
    if did:
        other_drv = await db.trips.find_one(
            {"driver_id": did, "id": {"$ne": trip_id}, "status": {"$in": _ACTIVE_TRIP_STATUSES}},
            {"_id": 0, "id": 1})
        if not other_drv:
            await db.drivers.update_one({"id": did}, {"$set": {"status": "offline"}})

    return safe_doc(await db.trips.find_one({"id": trip_id}, {"_id": 0}))


async def apply_trip_status(db, trip: dict, new_status: str, user=None, extra=None) -> dict:
    """SSOT transisi status trip — dipakai POST /trips/{id}/status dan geofence pickup
    (services/trips.apply_geofence). Dulu geofence menulis status sendiri: trip 'completed'
    tetapi booking tetap 'confirmed', tanpa event trip.completed (WA + permintaan ulasan).
    """
    if new_status == "completed":
        return await finalize_trip_completion(db, trip, user)
    cur = trip.get("status")
    if new_status == cur and not extra:
        return safe_doc(trip)
    # Trip selesai/batal tidak boleh mundur (dulu completed → on_trip menahan armada selamanya).
    await assert_trip_open(db, trip, f"diubah ke '{TRIP_LABEL.get(new_status, new_status)}'")
    if new_status != cur and new_status not in _FORWARD.get(cur, ()):
        raise TripStateError(f"Trip '{TRIP_LABEL.get(cur, cur)}' tidak bisa diubah ke "
                             f"'{TRIP_LABEL.get(new_status, new_status)}'")
    if new_status in STARTED_TRIP_STATUSES and trip.get("booking_id"):
        bk = await db.bookings.find_one({"id": trip["booking_id"]}, {"_id": 0, "status": 1}) or {}
        if bk.get("status") not in ("confirmed", "ongoing"):
            raise TripStateError("Booking belum terkonfirmasi (masih menunggu persetujuan/DP) — "
                                 "trip belum bisa dimulai")
    updates = {"status": new_status}
    now = now_iso()
    if new_status in STARTED_TRIP_STATUSES and not trip.get("enroute_at"):
        updates["enroute_at"] = now  # langkah "berangkat menjemput" (timeline ops)
    if new_status == "on_trip" and not trip.get("start_at"):
        updates["start_at"] = now  # penumpang naik / perjalanan dimulai
    if extra:
        updates.update(extra)
    res = await db.trips.update_one({"id": trip["id"], "status": cur}, {"$set": updates})
    if not res.matched_count:
        raise TripStateError("Status trip baru saja berubah — muat ulang")
    if new_status in STARTED_TRIP_STATUSES and new_status != cur:
        await _on_trip_started(db, trip, new_status, user)
    return safe_doc(await db.trips.find_one({"id": trip["id"]}, {"_id": 0}))


async def _on_trip_started(db, trip: dict, new_status: str, user=None) -> None:
    """Efek samping SATU jalur utk trip yang mulai jalan — check-in sopir, tombol ops,
    geofence jemput, /trips/{id}/status. Dulu hanya check-in yang membuat booking 'ongoing'
    & memberi tahu pelanggan; jalur lain membuat Booking/Kalender tetap 'Terkonfirmasi'."""
    from services.events import emit
    from services.wa_payload import build_wa_payload
    await mark_vehicle_in_use(db, trip.get("vehicle_id"))  # armada dipakai SAAT berangkat
    if trip.get("driver_id"):
        await db.drivers.update_one({"id": trip["driver_id"]}, {"$set": {"status": "online"}})
    bkid = trip.get("booking_id")
    if bkid:
        res = await db.bookings.update_one({"id": bkid, "status": "confirmed"}, {"$set": {"status": "ongoing"}})
        bk = await db.bookings.find_one({"id": bkid}, {"_id": 0})
        if res.modified_count:
            from services.audit import record
            await record(db, actor=user or {}, action="trip_start", entity_type="booking",
                         entity_id=bkid, summary="Trip dimulai -> booking ongoing")
            await emit(db, "trip.started", await build_wa_payload(db, bk), source="trips",
                       ref_type="booking", ref_id=bkid, dedupe_key=f"trip.started:{bkid}")
        if bk and new_status == "to_pickup":  # WA "sopir dalam perjalanan menjemput"
            await emit(db, "trip.enroute", await build_wa_payload(db, bk, trip), source="trips",
                       ref_type="booking", ref_id=bkid, dedupe_key=f"trip.enroute:{trip['id']}")
    label = "berangkat menjemput" if new_status == "to_pickup" else "memulai perjalanan"
    await notify_ops(db, trip, "started", f"Sopir {label}: {await _trip_ref(db, trip)}",
                     f"Status trip: {TRIP_LABEL[new_status]}.")


async def mark_trip_arrived(db, trip: dict, user=None, source: str = "driver") -> dict:
    """SSOT "tiba di tujuan": isi `arrived_at` (sekali) + emit `trip.arrived` (WA ke pelanggan).

    Dipakai tombol Dispatch, tombol Ruang Kerja Driver, dan geofence. Dulu dua tombol menulis
    sendiri dengan kunci dedupe BERBEDA (per trip vs per booking) → WA "tiba" bisa terkirim dua
    kali bila ops & sopir sama-sama menekan. Kini satu kunci per booking.
    """
    if trip.get("arrived_at"):  # idempotent: tombol kedua / ping geofence berikutnya
        return safe_doc(await db.trips.find_one({"id": trip["id"]}, {"_id": 0}))
    await assert_trip_open(db, trip, "ditandai tiba")
    # Tiba di TUJUAN hanya setelah penumpang naik (dulu bisa dari standby → WA "Anda telah tiba"
    # terkirim sebelum sopir berangkat).
    await assert_trip_state(trip, ("on_trip",), "ditandai tiba di tujuan")
    await db.trips.update_one({"id": trip["id"], "arrived_at": {"$in": [None, ""]}},
                              {"$set": {"arrived_at": now_iso()}})
    bkid = trip.get("booking_id")
    if bkid:
        from services.events import emit
        from services.wa_payload import build_wa_payload
        bk = await db.bookings.find_one({"id": bkid}, {"_id": 0})
        if bk:
            payload = await build_wa_payload(db, bk, trip)
            await emit(db, "trip.arrived", payload, source=source, ref_type="booking",
                       ref_id=bkid, dedupe_key=f"trip.arrived:{bkid}")
    await notify_ops(db, trip, "arrived", f"Tiba di tujuan: {await _trip_ref(db, trip)}",
                     f"Ditandai oleh {source}.")
    return safe_doc(await db.trips.find_one({"id": trip["id"]}, {"_id": 0}))


async def save_pod(db, trip: dict, pod: dict, user=None) -> dict:
    """SSOT bukti layanan (POD) — Dispatch & Ruang Kerja Driver. POD HANYA menyimpan bukti
    (dulu POD dari Dispatch diam-diam menyelesaikan trip dari standby + kredit fee + WA ulasan).
    Sah setelah perjalanan dimulai (on_trip) atau sesudah selesai."""
    await assert_trip_open(db, trip, "menerima POD", allow_completed=True)
    await assert_trip_state(trip, ("on_trip", "completed"), "menerima POD (penumpang belum naik)")
    await db.trips.update_one({"id": trip["id"]}, {"$set": {"pod": pod}})
    await notify_ops(db, trip, "pod", f"POD diunggah: {await _trip_ref(db, trip)}",
                     f"Penerima: {pod.get('recipient_name') or '-'}.")
    return safe_doc(await db.trips.find_one({"id": trip["id"]}, {"_id": 0}))


async def reassign_trip_driver(db, booking: dict, driver: dict, user=None) -> int:
    """Ganti sopir dari Booking/Kalender ikut memindahkan trip yang belum selesai (SSOT dgn
    Dispatch assign). Dulu hanya booking yang berubah: sopir lama tetap melihat & menjalankan
    tugas (fee masuk ke dia), sopir baru tak melihat apa-apa. Trip yang sedang berjalan
    (penumpang sudah naik) tidak boleh dipindah."""
    trips = await db.trips.find({"booking_id": booking["id"], "status": {"$in": _ACTIVE_TRIP_STATUSES}},
                                {"_id": 0}).to_list(10)
    if any(t.get("status") == "on_trip" for t in trips):
        raise TripStateError("Perjalanan sudah berjalan — sopir tidak bisa diganti di tengah trip")
    moved = 0
    for t in trips:
        if t.get("driver_id") == driver["id"]:
            continue
        await db.trips.update_one({"id": t["id"]}, {"$set": {
            "driver_id": driver["id"], "driver_ack_at": None, "assigned_at": now_iso()}})
        moved += 1
        old = t.get("driver_id")
        if old and not await db.trips.find_one({"driver_id": old, "id": {"$ne": t["id"]},
                                                "status": {"$in": STARTED_TRIP_STATUSES}}, {"_id": 1}):
            await db.drivers.update_one({"id": old}, {"$set": {"status": "offline"}})
    if moved:
        from services.events import emit
        from services.wa_payload import build_wa_payload
        fresh = await db.bookings.find_one({"id": booking["id"]}, {"_id": 0}) or booking
        await emit(db, "trip.assigned", await build_wa_payload(db, fresh), source="bookings",
                   ref_type="booking", ref_id=booking["id"],
                   dedupe_key=f"trip.assigned:{booking['id']}:{driver['id']}")
    return moved


async def apply_geofence(db, trip: dict, lat: float, lng: float, user=None):
    """Evaluasi geofence untuk satu ping lokasi (HP driver & device GPS) → dict hasil / None."""
    from services.geofence import evaluate
    event, new_status = evaluate(trip, lat, lng)
    if event == "arrived_destination":
        await mark_trip_arrived(db, trip, user, source="geofence")
        return {"event": event, "new_status": trip.get("status"), "arrived": True}
    if new_status and new_status != trip.get("status"):
        try:
            await apply_trip_status(db, trip, new_status, user)
        except TripStateError:  # ping lokasi untuk trip yang sudah ditutup → abaikan
            return None
        return {"event": event, "new_status": new_status}
    return None


async def recompute_trip_fee(db, booking_id, start_iso, end_iso):
    """Fee /hari disnapshot saat assign — hitung ULANG days/total saat tanggal berubah
    (reschedule). Hanya trip AKTIF; trip completed sudah dikreditkan & tak boleh berubah."""
    try:
        from datetime import datetime
        s = datetime.fromisoformat(str(start_iso).replace("Z", "+00:00"))
        e = datetime.fromisoformat(str(end_iso).replace("Z", "+00:00"))
        days = max(1, int(-(-(e - s).total_seconds() // 86400)))
    except Exception:  # noqa: BLE001
        return
    trips = await db.trips.find({"booking_id": booking_id, "status": {"$in": _ACTIVE_TRIP_STATUSES}},
                                {"_id": 0, "id": 1, "driver_fee_rate": 1}).to_list(20)
    for t in trips:
        rate = float(t.get("driver_fee_rate") or 0)
        if rate > 0:
            await db.trips.update_one({"id": t["id"]}, {"$set": {
                "driver_fee_days": days, "driver_fee_total": money(rate * days)}})


async def release_booking_resources(db, booking):
    """RC-04: saat booking di-cancel/reject — batalkan trip terkait yang belum jalan &
    bebaskan armada/driver bila tak ada tugas aktif lain. Idempotent & defensif.
    (Dipindah dari routers/bookings.py — SSOT pelepasan sumber daya kini satu file dgn
    finalize_trip_completion.)"""
    bkid = booking["id"]
    active = ["standby", "to_pickup", "on_trip"]
    await db.trips.update_many(
        {"booking_id": bkid, "status": {"$nin": ["completed", "cancelled"]}},
        {"$set": {"status": "cancelled"}})
    await release_vehicle(db, booking.get("vehicle_id"), exclude_booking_id=bkid)
    did = booking.get("driver_id")
    if did:
        other_drv = await db.trips.find_one(
            {"driver_id": did, "booking_id": {"$ne": bkid}, "status": {"$in": active}},
            {"_id": 0, "id": 1})
        if not other_drv:
            await db.drivers.update_one({"id": did}, {"$set": {"status": "offline"}})
