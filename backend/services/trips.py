"""services/trips.py — util perhitungan trip (E9 Phase B: Trip/KM & odometer).

- compute_distance: tentukan jarak tempuh trip dari odometer (akurat) atau
  estimasi rute OSRM (fallback). Mengembalikan (distance_km, basis|None).
  Prioritas: odometer (end-start) > est_distance_km (OSRM) > None.
- driver_stats / vehicle_stats: agregat total trip, total km, revenue + daftar trip terbaru
  (riwayat) untuk drawer detail driver & armada.
- finalize_trip_completion: SSOT penyelesaian trip (RC-03) — dipakai driver/checkout
  DAN trips/{id}/status=completed agar efek samping identik (anti split-brain).
"""
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


async def finalize_trip_completion(db, trip: dict, user=None, odometer_end=None) -> dict:
    """Selesaikan trip dengan efek samping LENGKAP & KONSISTEN (satu jalur, anti split-brain):
      1) trip → completed + end_at + distance_km/basis (odometer > OSRM est).
      2) armada dibebaskan → available (kecuali masih ada trip aktif lain pd armada itu);
         odometer armada dinaikkan bila odometer_end lebih besar.
      3) booking terkait → completed, lalu payment_status DITURUNKAN ULANG (RC-02) —
         jujur secara finansial (tetap 'dp'/'belum_bayar' bila belum lunas).
      4) driver → offline bila tak ada tugas aktif lain.
      5) emit `trip.completed` (idempotent) + audit.
    Idempotent & defensif: aman dipanggil pada trip yang telah completed.
    """
    from services.finance import recompute_booking_payment

    trip_id = trip["id"]
    odo_end = odometer_end if odometer_end is not None else trip.get("odometer_end")
    dist, basis = compute_distance(trip.get("odometer_start"), odo_end, trip.get("est_distance_km"))
    set_fields = {"status": "completed"}
    if not trip.get("end_at"):
        set_fields["end_at"] = now_iso()
    if odo_end is not None:
        set_fields["odometer_end"] = float(odo_end)
    if dist is not None:
        set_fields["distance_km"] = dist
        set_fields["distance_basis"] = basis
    await db.trips.update_one({"id": trip_id}, {"$set": set_fields})

    # (2) Bebaskan armada — kecuali masih ada trip aktif lain pd armada yg sama.
    vid = trip.get("vehicle_id")
    if vid:
        other_active = await db.trips.find_one(
            {"vehicle_id": vid, "id": {"$ne": trip_id}, "status": {"$in": _ACTIVE_TRIP_STATUSES}},
            {"_id": 0, "id": 1})
        if not other_active:
            veh_set = {"status": "available"}
            if odo_end is not None:
                veh = await db.vehicles.find_one({"id": vid}, {"_id": 0, "odometer": 1})
                if float((veh or {}).get("odometer") or 0) < float(odo_end):
                    veh_set["odometer"] = float(odo_end)
            await db.vehicles.update_one({"id": vid}, {"$set": veh_set})

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
            await db.driver_fee_entries.insert_one({
                "id": new_id("dfe"), "driver_id": fresh["driver_id"],
                "driver_name": drv_fee.get("name"), "trip_id": trip_id,
                "booking_id": fresh.get("booking_id"), "booking_code": bk_fee.get("code"),
                "rate": rate, "days": days, "amount": amount,
                "status": "earned", "created_at": now_iso(),
            })

    # (4) Driver offline bila tak ada tugas aktif lain.
    did = trip.get("driver_id")
    if did:
        other_drv = await db.trips.find_one(
            {"driver_id": did, "id": {"$ne": trip_id}, "status": {"$in": _ACTIVE_TRIP_STATUSES}},
            {"_id": 0, "id": 1})
        if not other_drv:
            await db.drivers.update_one({"id": did}, {"$set": {"status": "offline"}})

    return safe_doc(await db.trips.find_one({"id": trip_id}, {"_id": 0}))


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
    vid = booking.get("vehicle_id")
    if vid:
        other_active = await db.trips.find_one(
            {"vehicle_id": vid, "booking_id": {"$ne": bkid}, "status": {"$in": active}},
            {"_id": 0, "id": 1})
        veh = await db.vehicles.find_one({"id": vid}, {"_id": 0, "status": 1})
        if not other_active and veh and veh.get("status") == "on_trip":
            await db.vehicles.update_one({"id": vid}, {"$set": {"status": "available"}})
    did = booking.get("driver_id")
    if did:
        other_drv = await db.trips.find_one(
            {"driver_id": did, "booking_id": {"$ne": bkid}, "status": {"$in": active}},
            {"_id": 0, "id": 1})
        if not other_drv:
            await db.drivers.update_one({"id": did}, {"$set": {"status": "offline"}})
