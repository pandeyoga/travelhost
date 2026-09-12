"""services/subcharter.py — E16 Pinjam Armada / Sub-charter.

Logika inti sub-charter (menyewa unit dari travel mitra):
- AP (utang ke mitra): ap_total = Σ cost subcharter status∈{confirmed,settled};
  ap_paid = Σ partner_settlements.amount; ap_outstanding = ap_total − ap_paid. (INV-E16)
- COGS per booking: saat subcharter DIKONFIRMASI, biaya sewa mitra dicatat sebagai
  expenses(category='sewa_mitra', booking_id, trip_id) sehingga masuk P&L per booking/trip
  (jaga INV-5: trip.profit == revenue − Σ expenses).
- Payload WA ke MITRA: `phone` = telepon mitra (bukan pelanggan) agar event subcharter.*
  mengirim pesan ke mitra via Automation Engine (provider MOCK).
"""
from core_utils import new_id, now_iso
from services.finance import recompute_trip_profit

ACTIVE_STATUSES = ("requested", "confirmed")
LIABLE_STATUSES = ("confirmed", "settled")


async def _agg(db, coll, match, field):
    rows = await db[coll].aggregate([
        {"$match": match},
        {"$group": {"_id": None, "t": {"$sum": {"$ifNull": [f"${field}", 0]}}}},
    ]).to_list(1)
    return float(rows[0]["t"]) if rows else 0.0


async def partner_ap(db, partner_id):
    """Ringkasan utang (AP) ke satu mitra."""
    ap_total = await _agg(db, "subcharters",
                          {"partner_id": partner_id, "status": {"$in": list(LIABLE_STATUSES)}}, "cost")
    ap_paid = await _agg(db, "partner_settlements", {"partner_id": partner_id}, "amount")
    return {"ap_total": round(ap_total, 2), "ap_paid": round(ap_paid, 2),
            "ap_outstanding": round(ap_total - ap_paid, 2)}


async def enrich_partner(db, partner):
    """Tambahkan ringkasan AP + jumlah order ke dokumen mitra."""
    ap = await partner_ap(db, partner["id"])
    sc_count = await db.subcharters.count_documents(
        {"partner_id": partner["id"], "status": {"$ne": "cancelled"}})
    veh_count = await db.vehicles.count_documents({"partner_id": partner["id"]})
    out = dict(partner)
    out.update(ap)
    out["subcharter_count"] = sc_count
    out["vehicle_count"] = veh_count
    return out


async def find_subcharter_conflicts(db, vehicle_id, start, end, exclude_id=None):
    """Overlap unit mitra di antara sub-charter aktif (INV-4 utk unit partner).

    Overlap bila start < other.end AND end > other.start (interval terbuka).
    """
    if not (vehicle_id and start and end):
        return []
    q = {"vehicle_id": vehicle_id, "status": {"$in": list(ACTIVE_STATUSES)},
         "start_datetime": {"$lt": end}, "end_datetime": {"$gt": start}}
    if exclude_id:
        q["id"] = {"$ne": exclude_id}
    return await db.subcharters.find(
        q, {"_id": 0, "id": 1, "code": 1, "start_datetime": 1, "end_datetime": 1}).to_list(50)


async def build_partner_payload(db, subcharter, partner=None, booking=None):
    """Payload variabel WA/CRM utk event subcharter.* (dikirim ke MITRA)."""
    if partner is None:
        partner = await db.partners.find_one({"id": subcharter.get("partner_id")}, {"_id": 0}) or {}
    if booking is None and subcharter.get("booking_id"):
        booking = await db.bookings.find_one({"id": subcharter.get("booking_id")}, {"_id": 0}) or {}
    booking = booking or {}
    cfg = await db.settings.find_one({"key": "company_info"}, {"_id": 0, "value": 1}) or {}
    company = (cfg.get("value") or {}).get("name") or "RahazaTrans"
    return {
        "subcharter_id": subcharter.get("id"), "code": subcharter.get("code"),
        "partner_id": partner.get("id"), "partner_name": partner.get("name"),
        "pic": partner.get("pic"),
        "phone": partner.get("phone"),  # WA dikirim ke MITRA
        "vehicle_label": subcharter.get("vehicle_label") or subcharter.get("vehicle_name") or "unit",
        "start_datetime": (subcharter.get("start_datetime") or "")[:16].replace("T", " "),
        "end_datetime": (subcharter.get("end_datetime") or "")[:16].replace("T", " "),
        "cost": float(subcharter.get("cost", 0) or 0),
        "booking_code": booking.get("code"),
        "destination": booking.get("destination"),
        "origin": booking.get("origin"),
        "company": company,
    }


async def book_cogs_expense(db, subcharter, user):
    """Catat biaya sewa mitra sebagai COGS (expenses.category='sewa_mitra').

    Ditautkan ke booking + trip (bila ada) agar masuk P&L per booking/trip (INV-5).
    Return (expense_id, trip_id).
    """
    trip = await db.trips.find_one({"booking_id": subcharter.get("booking_id")}, {"_id": 0, "id": 1})
    trip_id = (trip or {}).get("id")
    exp = {
        "id": new_id("exp"), "booking_id": subcharter.get("booking_id"),
        "trip_id": trip_id, "category": "sewa_mitra",
        "amount": float(subcharter.get("cost", 0) or 0),
        "note": f"Sewa armada mitra {subcharter.get('partner_name') or ''} — {subcharter.get('code')}",
        "subcharter_id": subcharter.get("id"), "recorded_by": user.get("id"),
        "created_at": now_iso(),
    }
    await db.expenses.insert_one(exp)
    if trip_id:
        await recompute_trip_profit(db, trip_id)
    return exp["id"], trip_id


async def remove_cogs_expense(db, subcharter):
    """Hapus expense COGS saat subcharter dibatalkan + hitung ulang profit trip."""
    exp_id = subcharter.get("expense_id")
    if not exp_id:
        return
    exp = await db.expenses.find_one({"id": exp_id}, {"_id": 0, "trip_id": 1})
    await db.expenses.delete_one({"id": exp_id})
    if exp and exp.get("trip_id"):
        await recompute_trip_profit(db, exp["trip_id"])
