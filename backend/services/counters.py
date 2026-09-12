"""services/counters.py — Atomic sequence counters (Phase 8 / A2).

Mencegah duplikasi nomor seri (INV-8: bookings.code & invoices.number) saat ada
request bersamaan, dengan `find_one_and_update($inc)` yang ATOMIK pada koleksi
`counters`. Mengganti pola lama `max(...)+1` / scan-distinct yang rawan balapan.

Dokumen counter: { id: <scope>, seq: <int> }
  - scope 'booking'         -> BK-0001, BK-0002, ...
  - scope 'invoice:<YYYY>'  -> reset per tahun (lihat services.finance.next_invoice_number)

Seed menginisialisasi counter agar nilai berikutnya tidak menabrak data awal.
Catatan: nomor invoice dirakit di `services.finance.next_invoice_number`
(memakai next_seq di sini) — JANGAN duplikasi format di file ini.
"""
from pymongo import ReturnDocument


async def next_seq(db, scope: str) -> int:
    """Naikkan & kembalikan nilai urut atomik untuk `scope` (mulai dari 1)."""
    doc = await db.counters.find_one_and_update(
        {"id": scope},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return int(doc["seq"])


async def next_booking_code(db) -> str:
    """Kode booking unik berurutan: BK-0001, BK-0002, ... (atomik)."""
    return f"BK-{await next_seq(db, 'booking'):04d}"
