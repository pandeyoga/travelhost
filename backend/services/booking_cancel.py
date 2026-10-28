"""services/booking_cancel.py — pembukuan pembatalan booking (E21/E26).

Dipanggil routers/bookings.cancel_booking SETELAH transisi ke 'cancelled' dimenangkan lewat CAS,
jadi tiap langkah di sini berjalan sekali per booking (dulu cancel paralel me-refund ganda):
  1) tagihan terbuka booking → void (tidak lagi ditagih / ikut piutang);
  2) refund → payment negatif (method="refund") + recompute paid_amount (INV-2/INV-3);
  3) denda → invoice `cancellation_fee` dgn status JUJUR ('paid' hanya bila uang yang
     ditahan = terbayar − refund menutup denda).
"""
from core_utils import money, new_id
from services.finance import next_invoice_number, recompute_booking_payment


async def post_cancellation(db, booking: dict, *, reason: str, cfee: float, refund: float,
                            paid: float, ts: str, user=None) -> None:
    booking_id = booking["id"]
    # Tagihan terbuka booking ini tidak lagi berlaku → void (dulu tetap 'sent' & ikut ditagih/AR).
    await db.invoices.update_many(
        {"booking_id": booking_id, "status": {"$in": ["draft", "sent", "partial"]},
         "type": {"$ne": "cancellation_fee"}},
        {"$set": {"status": "void", "voided_at": ts, "void_reason": "Booking dibatalkan"}})
    # E21-Ledger: post REFUND sbg payment negatif (idempotent per booking).
    # Rekomendasi HANDOFF: refund = payments negatif method="refund"; paid_amount otomatis
    # berkurang via recompute (Σ payments incl. negatif). Denda diposting sbg invoice terpisah
    # utk paper trail (revenue sudah terekam via net payments — TIDAK double-count).
    if refund > 0:
        # Idempotent: cek apakah refund payment utk booking ini sudah ada (mis. retry cancel).
        existing = await db.payments.find_one(
            {"booking_id": booking_id, "type": "refund"}, {"_id": 0}
        )
        if not existing:
            pay_doc = {
                "id": new_id("pay"),
                "booking_id": booking_id,
                "amount": -money(refund),  # negatif → mengurangi paid_amount
                "type": "refund",
                "method": "refund",
                "note": f"Refund pembatalan: {reason}" if reason else "Refund pembatalan",
                "recorded_by": (user or {}).get("id"),
                "paid_at": ts,
            }
            await db.payments.insert_one(pay_doc)
            # Recompute paid_amount + payment_status (INV-2 & INV-3 tetap konsisten).
            await recompute_booking_payment(db, booking_id)
    # E26: auto-invoice DENDA sbg paper trail revenue (idempotent per booking).
    # Revenue sudah terekam via Σ payments (denda = paid_amount - refund_amount setelah cancel);
    # TIDAK double-count di P&L. Status JUJUR: 'paid' hanya bila uang yang ditahan (terbayar −
    # refund) menutup denda; kurang → 'partial'/'sent' (sisa ditagih). Dulu selalu 'paid'.
    if cfee > 0:
        existing_inv = await db.invoices.find_one(
            {"booking_id": booking_id, "type": "cancellation_fee"}, {"_id": 0}
        )
        if not existing_inv:
            retained = money(paid) - money(refund)  # uang yang tetap di perusahaan
            fee_status = "paid" if retained >= money(cfee) else ("partial" if retained > 0 else "sent")
            inv_doc = {
                "id": new_id("inv"),
                "number": await next_invoice_number(db),
                "booking_id": booking_id,
                "customer_id": booking.get("customer_id"),
                "customer_name": booking.get("customer_name"),
                "booking_code": booking.get("code"),
                "amount": money(cfee), "subtotal": money(cfee), "paid_before": 0,
                "type": "cancellation_fee",  # E26: bedakan dari invoice booking normal
                "status": fee_status,
                "issued_at": ts,
                "due_at": ts,
                "paid_at": ts if fee_status == "paid" else None,
                "notes": f"Denda pembatalan: {reason}" if reason else "Denda pembatalan",
                "created_by": (user or {}).get("id"),
                "created_at": ts,
                "reconciled_at": ts,
            }
            await db.invoices.insert_one(inv_doc)
