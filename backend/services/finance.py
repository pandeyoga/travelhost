"""services/finance.py — logika pembayaran booking (INV-2 & INV-3).

INV-2: booking.paid_amount == Σ payments[booking].amount, dan paid <= total.
INV-3: derivasi payment_status = sinyal FINANSIAL murni (RC-02) — status operasional
  ('completed') TIDAK memaksa 'selesai'. Nilai:
  - 'belum_bayar'  bila paid <= 0
  - 'lunas'        bila paid >= total (total > 0)
  - 'dp'           bila 0 < paid < total
Dipusatkan di sini agar router tetap thin & tidak ada drift derivasi.
"""
from core_utils import money


def derive_payment_status(paid: float, total: float, status: str = None) -> str:
    """Derivasi status FINANSIAL murni dari (paid, total).

    RC-02: status OPERASIONAL ('completed') TIDAK lagi memaksa payment_status='selesai'.
    Sinyal finansial harus jujur — booking selesai tapi belum lunas tetap 'dp'/'belum_bayar'
    sehingga tetap muncul di Piutang (AR) & konsisten dgn INV-3. Parameter `status`
    dipertahankan utk kompatibilitas pemanggil, namun tidak lagi mengubah derivasi.
    """
    if paid <= 0:
        return "belum_bayar"
    if total > 0 and paid >= total:
        return "lunas"
    return "dp"


async def _agg_sum(db, coll: str, match=None, field: str = "amount") -> float:
    """Σ `field` via aggregation server-side (hindari memuat semua dokumen ke memori)."""
    pipeline = [{"$match": match or {}},
                {"$group": {"_id": None, "t": {"$sum": {"$ifNull": [f"${field}", 0]}}}}]
    rows = await db[coll].aggregate(pipeline).to_list(1)
    return float(rows[0]["t"]) if rows else 0.0


async def sum_payments(db, booking_id: str) -> float:
    return await _agg_sum(db, "payments", {"booking_id": booking_id})


async def recompute_booking_payment(db, booking_id: str):
    """Hitung ulang paid_amount + payment_status booking dari koleksi payments.
    Kembalikan (paid, payment_status) atau None bila booking tak ada."""
    booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
    if not booking:
        return None
    paid = await sum_payments(db, booking_id)
    total = float(booking.get("total_amount", 0) or 0)
    ps = derive_payment_status(paid, total, booking.get("status"))
    await db.bookings.update_one(
        {"id": booking_id}, {"$set": {"paid_amount": money(paid), "payment_status": ps}}
    )
    return paid, ps



# === Phase 5: agregasi keuangan (profit-loss, AR, invoice numbering) ===
from datetime import datetime as _dt, timezone as _tz

EXPENSE_CATEGORIES = ("bbm", "tol", "uang_jalan", "gaji_driver", "sewa_mitra", "other")


async def next_invoice_number(db) -> str:
    """Nomor invoice unik dgn reset tahunan: INV-<YYYY>-0001 (INV-8).

    A2: ATOMIK via counters ($inc) — gantikan pola `max(...)+1` yang rawan
    duplikasi saat dua request menerbitkan invoice bersamaan.
    """
    from services.counters import next_seq

    year = _dt.now(_tz.utc).year
    seq = await next_seq(db, f"invoice:{year}")
    return f"INV-{year}-{seq:04d}"


async def sum_expenses(db, query=None) -> float:
    return await _agg_sum(db, "expenses", query or {})


async def recompute_trip_profit(db, trip_id: str):
    """Jaga INV-5: trip.profit == revenue - Σ expenses(trip)."""
    trip = await db.trips.find_one({"id": trip_id}, {"_id": 0})
    if not trip:
        return None
    rev = float(trip.get("revenue", 0) or 0)
    exp = await sum_expenses(db, {"trip_id": trip_id})
    profit = money(rev - exp)
    await db.trips.update_one({"id": trip_id}, {"$set": {"profit": profit}})
    return profit


async def profit_loss(db, period=None) -> dict:
    """Laba-rugi periodik. period = 'YYYY-MM' (default: bulan berjalan).
    revenue = Σ payments (cash-in) pada periode; expenses = Σ expenses pada periode.
    """
    if not period:
        period = _dt.now(_tz.utc).strftime("%Y-%m")

    revenue = await _agg_sum(db, "payments", {"paid_at": {"$regex": f"^{period}"}})

    # Pengeluaran periode + breakdown kategori — via aggregation ($group), bukan scan penuh.
    exp_rows = await db.expenses.aggregate([
        {"$match": {"created_at": {"$regex": f"^{period}"}}},
        {"$group": {"_id": "$category", "amount": {"$sum": {"$ifNull": ["$amount", 0]}}}},
    ]).to_list(100)
    expense_total = sum(float(r["amount"]) for r in exp_rows)
    by_cat = {c: 0.0 for c in EXPENSE_CATEGORIES}
    for r in exp_rows:
        cat = r["_id"] if r["_id"] in EXPENSE_CATEGORIES else "other"
        by_cat[cat] += float(r["amount"])
    expense_by_category = [{"category": c, "amount": round(v, 2)} for c, v in by_cat.items()]

    profit = round(revenue - expense_total, 2)
    margin = round((profit / revenue * 100), 1) if revenue > 0 else 0.0

    # Laba-rugi per trip — batch Σ expenses per trip_id (hindari N+1).
    trips = await db.trips.find(
        {}, {"_id": 0, "id": 1, "booking_id": 1, "dest_name": 1, "revenue": 1}
    ).to_list(5000)
    exp_trip_rows = await db.expenses.aggregate([
        {"$match": {"trip_id": {"$ne": None}}},
        {"$group": {"_id": "$trip_id", "amount": {"$sum": {"$ifNull": ["$amount", 0]}}}},
    ]).to_list(5000)
    exp_by_trip = {r["_id"]: float(r["amount"]) for r in exp_trip_rows}
    by_trip = []
    for t in trips:
        rev = float(t.get("revenue", 0) or 0)
        ex = exp_by_trip.get(t.get("id"), 0.0)
        by_trip.append({
            "trip_id": t.get("id"), "booking_id": t.get("booking_id"),
            "dest_name": t.get("dest_name"), "revenue": round(rev, 2),
            "expenses": round(ex, 2), "profit": round(rev - ex, 2),
        })

    return {
        "period": period,
        "revenue": round(revenue, 2),
        "expenses": round(expense_total, 2),
        "profit": profit,
        "margin": margin,
        "expense_by_category": expense_by_category,
        "by_trip": by_trip,
    }


async def accounts_receivable(db) -> dict:
    """Piutang: booking belum lunas (total - paid > 0), kecuali cancelled.
    Outstanding dihitung di pipeline ($round agar identik dgn pembulatan per-baris)."""
    pipeline = [
        {"$match": {"status": {"$ne": "cancelled"}}},
        {"$addFields": {"outstanding": {"$round": [{"$max": [
            {"$subtract": [{"$ifNull": ["$total_amount", 0]}, {"$ifNull": ["$paid_amount", 0]}]}, 0]}, 2]}}},
        {"$match": {"outstanding": {"$gt": 0}}},
        {"$sort": {"outstanding": -1}},
        {"$limit": 1000},
    ]
    raw = await db.bookings.aggregate(pipeline).to_list(1000)
    rows = []
    total_out = 0.0
    for b in raw:
        outstanding = float(b.get("outstanding", 0) or 0)
        total_out += outstanding
        rows.append({
            "booking_id": b.get("id"), "code": b.get("code"), "customer_name": b.get("customer_name"),
            "total_amount": round(float(b.get("total_amount", 0) or 0), 2),
            "paid_amount": round(float(b.get("paid_amount", 0) or 0), 2),
            "outstanding": outstanding, "payment_status": b.get("payment_status"),
            "start_datetime": b.get("start_datetime"),
        })
    return {"total_outstanding": round(total_out, 2), "count": len(rows), "items": rows}
