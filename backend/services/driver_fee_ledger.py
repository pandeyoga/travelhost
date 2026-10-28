"""services/driver_fee_ledger.py — pembukuan FEE SOPIR per keberangkatan (keputusan 2026-10-28).

Dulu fee baru menjadi biaya saat DICAIRKAN (expense gaji_driver dibuat ketika pencairan dibayar,
tanpa trip_id): laba bulan trip terlalu tinggi, fee tak pernah mengurangi laba per trip/unit,
dan expense itu bisa dihapus sehingga P&L kehilangan biaya. Kini:

  1) Trip selesai → `accrue_fee`: expense gaji_driver (source="driver_fee") AKRUAL, terkait
     trip/booking/unit, `paid=False`. Masuk P&L bulan trip, laba trip & laba per unit.
  2) Pencairan dibayar → TIDAK membuat expense baru (anti dobel). `settle` menandai expense
     fee lunas FIFO sejauh total pencairan dibayar menutupinya. Arus kas membaca pencairan
     langsung (services.finance_automation.cashflow) — kas keluar tetap di tanggal transfer.
  3) `backfill` (idempotent, saat startup): fee lama tanpa expense. Bagian yang SUDAH dibiayakan
     oleh expense pencairan model lama (FIFO) ditandai `expensed_by="legacy_withdrawal"`;
     sisanya dibuatkan akrual. Total biaya tidak pernah dobel.
"""
from core_utils import money, new_id, now_iso

SOURCE = "driver_fee"


async def accrue_fee(db, entry: dict, trip: dict = None, *, created_at: str = None) -> str:
    """Expense akrual utk satu fee entry (idempotent per entry). Return expense_id."""
    existing = await db.expenses.find_one({"driver_fee_entry_id": entry["id"]}, {"_id": 0, "id": 1})
    if existing:
        return existing["id"]
    trip = trip or await db.trips.find_one({"id": entry.get("trip_id")}, {"_id": 0}) or {}
    exp = {
        "id": new_id("exp"), "category": "gaji_driver", "amount": money(entry.get("amount")),
        "trip_id": entry.get("trip_id"), "booking_id": entry.get("booking_id"),
        "booking_code": entry.get("booking_code"), "vehicle_id": trip.get("vehicle_id"),
        "driver_id": entry.get("driver_id"), "driver_fee_entry_id": entry["id"], "source": SOURCE,
        "note": f"Fee keberangkatan {entry.get('driver_name') or ''} · {entry.get('booking_code') or '-'}".strip(),
        "paid": False, "paid_at": None, "created_at": created_at or entry.get("created_at") or now_iso(),
    }
    await db.expenses.insert_one(dict(exp))
    await db.driver_fee_entries.update_one({"id": entry["id"]},
                                           {"$set": {"expense_id": exp["id"], "expensed_by": "accrual"}})
    if exp["trip_id"]:
        from services.finance import recompute_trip_profit
        await recompute_trip_profit(db, exp["trip_id"])  # INV-5: laba trip ikut fee sopir
    return exp["id"]


async def _legacy_cash(db, driver_id: str) -> int:
    """Σ expense pencairan MODEL LAMA (dibuat saat bayar pencairan, ber-withdrawal_id)."""
    rows = await db.expenses.aggregate([
        {"$match": {"driver_id": driver_id, "withdrawal_id": {"$nin": [None, ""]}}},
        {"$group": {"_id": None, "t": {"$sum": {"$ifNull": ["$amount", 0]}}}}]).to_list(1)
    return money(rows[0]["t"]) if rows else 0


async def settle(db, driver_id: str, withdrawal_id: str = None) -> int:
    """Tandai expense fee lunas FIFO sejauh Σ pencairan dibayar menutupinya. Return jumlah ditandai."""
    rows = await db.driver_withdrawals.aggregate([
        {"$match": {"driver_id": driver_id, "status": "paid"}},
        {"$group": {"_id": None, "t": {"$sum": {"$ifNull": ["$amount", 0]}}}}]).to_list(1)
    budget = money(rows[0]["t"]) if rows else 0
    marked = 0
    entries = await db.driver_fee_entries.find({"driver_id": driver_id}, {"_id": 0}).sort("created_at", 1).to_list(10000)
    for e in entries:
        amount = money(e.get("amount"))
        if budget < amount:
            break
        budget -= amount
        if e.get("expense_id"):
            res = await db.expenses.update_one(
                {"id": e["expense_id"], "paid": False},
                {"$set": {"paid": True, "paid_at": now_iso(), "settled_by_withdrawal": withdrawal_id}})
            marked += res.modified_count
    return marked


async def backfill(db) -> int:
    """Migrasi idempotent fee lama → akrual (lihat docstring modul). Return expense dibuat."""
    created = 0
    for driver_id in await db.driver_fee_entries.distinct("driver_id", {"expensed_by": {"$exists": False}}):
        covered = await _legacy_cash(db, driver_id)
        done = await db.driver_fee_entries.find(
            {"driver_id": driver_id, "expensed_by": "legacy_withdrawal"}, {"_id": 0, "amount": 1}).to_list(10000)
        covered -= sum(money(d.get("amount")) for d in done)
        todo = await db.driver_fee_entries.find(
            {"driver_id": driver_id, "expensed_by": {"$exists": False}}, {"_id": 0}).sort("created_at", 1).to_list(10000)
        for e in todo:
            amount = money(e.get("amount"))
            if covered >= amount:  # sudah dibiayakan oleh expense pencairan lama
                covered -= amount
                await db.driver_fee_entries.update_one({"id": e["id"]}, {"$set": {"expensed_by": "legacy_withdrawal"}})
                continue
            covered = 0
            await accrue_fee(db, e)
            created += 1
        await settle(db, driver_id)
    return created


async def unpaid_accrued(db, driver_id: str = None) -> int:
    """Fee sopir yang sudah dibiayakan tapi belum dicairkan (utang ke sopir)."""
    q = {"source": SOURCE, "paid": False}
    if driver_id:
        q["driver_id"] = driver_id
    rows = await db.expenses.aggregate([{"$match": q}, {"$group": {"_id": None, "t": {"$sum": "$amount"}}}]).to_list(1)
    return money(rows[0]["t"]) if rows else 0


PROTECTED_KEYS = ("payout_id", "withdrawal_id", "driver_fee_entry_id", "subcharter_id")


def is_system_expense(doc: dict) -> bool:
    """Expense otomatis (payroll, pencairan lama, fee sopir, sewa mitra) — diubah lewat modulnya.
    Dulu bisa dihapus bebas: pencairan tetap 'dibayar' & saldo sopir berkurang, P&L kehilangan biaya."""
    return any(doc.get(k) for k in PROTECTED_KEYS) or doc.get("source") == SOURCE
