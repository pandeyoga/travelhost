"""routers/invoices.py — invoice DP / pelunasan / penuh dari booking + kwitansi pembayaran.

Koleksi `invoices` (booking_id wajib). Nomor dari services.numbering (aturan terkonfigurasi).
PDF dari services.documents (kop, naskah, baris biaya terkonfigurasi). Akses section 'finance'.
Kwitansi = nomor resmi yang ditempel pada dokumen `payments` (receipt_no) saat diterbitkan.
"""
import base64
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response, StreamingResponse

from core_utils import money, new_id, now_iso, safe_doc
from db import get_db
from dependencies import require_section
from schemas import InvoiceCreate, InvoiceStatusUpdate
from services import documents as docs
from services import numbering as nb
from services.audit import record
from services.exporter import invoice_xlsx

router = APIRouter(prefix="/api", tags=["invoices"])
FIN = require_section("finance")
VALID_STATUS = {"draft", "sent", "partial", "paid", "void"}


@router.get("/invoices")
async def list_invoices(status: str = Query(default=None), kind: str = Query(default=None), booking_id: str = Query(default=None),
                        limit: int = Query(default=300, le=1000), skip: int = Query(default=0, ge=0), user=Depends(FIN)):
    query = {}
    if status:
        query["status"] = status
    if kind:
        query["kind"] = kind
    if booking_id:
        query["booking_id"] = booking_id
    docs_ = await get_db().invoices.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).to_list(limit)
    return safe_doc(docs_)


@router.get("/invoices/quote")
async def quote_invoice(booking_id: str, kind: str = "dp", dp_percent: float = None, user=Depends(FIN)):
    """Hitung usulan nominal/jatuh tempo SEBELUM invoice dibuat (untuk formulir)."""
    db = get_db()
    booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
    if not booking:
        raise HTTPException(status_code=404, detail="Booking tidak ditemukan")
    cfg = await docs.invoice_config(db)
    return _compute(booking, cfg, kind, dp_percent, None)


def _compute(booking: dict, cfg: dict, kind: str, dp_percent, dp_amount) -> dict:
    total = money(booking.get("total_amount") or 0)
    paid = money(booking.get("paid_amount") or 0)
    pct = float(dp_percent if dp_percent is not None else (booking.get("dp_percent") or cfg.get("dp_percent_default") or 30))
    dp_amt = money(dp_amount) if dp_amount else money(total * pct / 100.0)
    if kind == "dp":
        amount = max(dp_amt - paid, 0)
    elif kind == "settlement":
        amount = max(total - paid, 0)
    else:
        amount = max(total - paid, 0)
        dp_amt = money(booking.get("dp_amount") or dp_amt)
    return {"kind": kind, "subtotal": total, "paid_before": paid, "dp_percent": round(pct, 2), "dp_amount": dp_amt,
            "amount": amount, "outstanding_after": max(total - paid - amount, 0),
            "due_at": docs.default_due(kind, cfg, booking), "items": docs.booking_items(booking),
            "bank_accounts": cfg.get("bank_accounts") or [], "terms": cfg.get("payment_terms") or ""}


@router.post("/invoices")
async def create_invoice(body: InvoiceCreate, user=Depends(FIN)):
    db = get_db()
    booking = await db.bookings.find_one({"id": body.booking_id}, {"_id": 0})
    if not booking:
        raise HTTPException(status_code=400, detail="Booking tidak ditemukan")
    if booking.get("status") == "cancelled":
        raise HTTPException(status_code=400, detail="Booking dibatalkan — invoice ditolak")
    kind = body.kind if body.kind in docs.KIND_CODE else "full"
    cfg = await docs.invoice_config(db)
    calc = _compute(booking, cfg, kind, body.dp_percent, body.dp_amount)
    if body.amount is not None and kind != "dp":
        calc["amount"] = money(body.amount)
        calc["outstanding_after"] = max(calc["subtotal"] - calc["paid_before"] - calc["amount"], 0)
    if calc["amount"] <= 0:
        raise HTTPException(status_code=400, detail="Tidak ada sisa tagihan untuk jenis invoice ini (sudah terbayar).")
    if body.bank_account_ids:
        calc["bank_accounts"] = [a for a in cfg.get("bank_accounts") or [] if a.get("id") in body.bank_account_ids]
    cust = await db.customers.find_one({"id": booking.get("customer_id")}, {"_id": 0, "phone": 1}) or {}
    vehicle = await db.vehicles.find_one({"id": booking.get("vehicle_id")}, {"_id": 0, "plate": 1, "plate_number": 1}) or {}
    number = await nb.generate(db, docs.KIND_RULE[kind], {
        "booking_code": booking.get("code"), "customer_name": booking.get("customer_name"),
        "vehicle_code": vehicle.get("plate") or vehicle.get("plate_number")})
    doc = {
        "id": new_id("inv"), "number": number, "kind": kind, "kind_label": docs.KIND_LABEL[kind],
        "booking_id": body.booking_id, "booking_code": booking.get("code"),
        "customer_id": booking.get("customer_id"), "customer_name": booking.get("customer_name"),
        "customer_phone": booking.get("customer_phone") or cust.get("phone"),
        **calc, "due_at": body.due_at or calc["due_at"], "status": "draft",
        "issued_at": now_iso(), "notes": body.notes or "", "terms": body.terms if body.terms is not None else calc["terms"],
        "created_by": user.get("id"), "created_by_name": user.get("name"), "created_at": now_iso(),
    }
    await db.invoices.insert_one(dict(doc))
    await record(db, actor=user, action="create", entity_type="invoice", entity_id=doc["id"], after=doc,
                 summary=f"Terbitkan invoice {kind} {number} (Rp {doc['amount']:,})".replace(",", "."))
    return safe_doc(doc)


async def _get(db, invoice_id):
    inv = await db.invoices.find_one({"id": invoice_id}, {"_id": 0})
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice tidak ditemukan")
    return inv


@router.get("/invoices/{invoice_id}/pdf")
async def invoice_pdf_inline(invoice_id: str, user=Depends(FIN)):
    db = get_db()
    inv = await _get(db, invoice_id)
    pdf = await docs.invoice_pdf(db, inv, issuer=user)
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{inv["number"].replace("/", "-")}.pdf"'})


@router.get("/invoices/{invoice_id}/export")
async def export_invoice(invoice_id: str, format: str = Query(default="pdf"), user=Depends(FIN)):
    db = get_db()
    inv = await _get(db, invoice_id)
    fname = inv.get("number", "invoice").replace("/", "-")
    if format == "excel":
        data, media, fname = invoice_xlsx(inv), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", f"{fname}.xlsx"
    else:
        data, media, fname = await docs.invoice_pdf(db, inv, issuer=user), "application/pdf", f"{fname}.pdf"
    return StreamingResponse(BytesIO(data), media_type=media, headers={"Content-Disposition": f'attachment; filename="{fname}"'})


async def _resolve_customer_phone(db, inv):
    if inv.get("customer_phone"):
        return inv["customer_phone"]
    booking = await db.bookings.find_one({"id": inv.get("booking_id")}, {"_id": 0}) or {}
    phone = booking.get("customer_phone") or ""
    cust_id = inv.get("customer_id") or booking.get("customer_id")
    if not phone and cust_id:
        cust = await db.customers.find_one({"id": cust_id}, {"_id": 0, "phone": 1})
        phone = (cust or {}).get("phone") or ""
    return phone


async def _send_pdf_wa(db, phone, pdf, caption, filename, customer_id, customer_name, source, user):
    data_url = "data:application/pdf;base64," + base64.b64encode(pdf).decode()
    from services.whatsapp import send_wa
    res = await send_wa(db, phone, text=caption, customer_id=customer_id, contact_name=customer_name, source=source,
                        author_id=user.get("id"), media_data=data_url, media_filename=filename)
    if res.get("status") == "skipped":
        raise HTTPException(status_code=400, detail="Kontak telah opt-out WhatsApp")
    if res.get("status") not in ("sent", "delivered", "read"):
        raise HTTPException(status_code=400, detail=res.get("error") or "Gagal mengirim via WhatsApp")
    return res


async def _send_invoice_wa(db, inv, user):
    phone = await _resolve_customer_phone(db, inv)
    if not phone:
        raise HTTPException(status_code=400, detail="Nomor WhatsApp pelanggan tidak ditemukan")
    pdf = await docs.invoice_pdf(db, inv, issuer=user)
    due = docs.fdate(inv.get("due_at"))
    caption = (f"Halo {inv.get('customer_name') or 'Pelanggan'}, berikut invoice {inv.get('kind_label', '').lower()} "
               f"{inv.get('number')} sebesar Rp {money(inv.get('amount')):,} untuk booking {inv.get('booking_code')}. "
               f"Jatuh tempo {due}. Terima kasih! 🙏").replace(",", ".")
    res = await _send_pdf_wa(db, phone, pdf, caption, f"{inv.get('number', 'invoice').replace('/', '-')}.pdf",
                             inv.get("customer_id"), inv.get("customer_name"), "invoice", user)
    if inv.get("status") == "draft":
        await db.invoices.update_one({"id": inv["id"]}, {"$set": {"status": "sent", "sent_at": now_iso()}})
    await record(db, actor=user, action="send", entity_type="invoice", entity_id=inv["id"],
                 summary=f"Kirim invoice {inv.get('number')} via WhatsApp ke {phone}")
    return {"ok": True, "number": inv.get("number"), **res}


@router.post("/invoices/{invoice_id}/send-wa")
async def send_invoice_wa(invoice_id: str, user=Depends(FIN)):
    db = get_db()
    return await _send_invoice_wa(db, await _get(db, invoice_id), user)


@router.post("/bookings/{booking_id}/send-invoice-wa")
async def send_booking_invoice_wa(booking_id: str, user=Depends(FIN)):
    db = get_db()
    inv = await db.invoices.find_one({"booking_id": booking_id, "status": {"$ne": "void"}}, {"_id": 0}, sort=[("created_at", -1)])
    if not inv:
        raise HTTPException(status_code=404, detail="Belum ada invoice untuk booking ini — buat dulu di Keuangan → Invoice")
    return await _send_invoice_wa(db, inv, user)


@router.patch("/invoices/{invoice_id}")
async def update_invoice(invoice_id: str, body: InvoiceStatusUpdate, user=Depends(FIN)):
    db = get_db()
    inv = await _get(db, invoice_id)
    updates = {}
    if body.status is not None:
        if body.status not in VALID_STATUS:
            raise HTTPException(status_code=400, detail="Status invoice tidak sah")
        updates["status"] = body.status
    if body.amount is not None:
        if inv.get("status") in ("paid", "void"):
            raise HTTPException(status_code=400, detail="Nominal invoice lunas/batal tidak bisa diubah")
        if money(body.amount) <= 0:
            raise HTTPException(status_code=400, detail="Nominal invoice harus lebih dari 0")
        updates["amount"] = money(body.amount)
        updates["outstanding_after"] = max(money(inv.get("subtotal") or 0) - money(inv.get("paid_before") or 0) - updates["amount"], 0)
    for f in ("due_at", "notes", "terms"):
        v = getattr(body, f)
        if v is not None:
            updates[f] = v
    if not updates:
        return safe_doc(inv)
    await db.invoices.update_one({"id": invoice_id}, {"$set": updates})
    after = await db.invoices.find_one({"id": invoice_id}, {"_id": 0})
    summary = (f"Ubah status invoice {inv.get('number')} → {body.status}" if body.status
               else f"Ubah invoice {inv.get('number')}")
    await record(db, actor=user, action="update", entity_type="invoice", entity_id=invoice_id,
                 before=inv, after=after, summary=summary)
    return safe_doc(after)


@router.delete("/invoices/{invoice_id}")
async def delete_invoice(invoice_id: str, user=Depends(FIN)):
    db = get_db()
    inv = await _get(db, invoice_id)
    if inv.get("status") not in ("draft", "void"):
        raise HTTPException(status_code=400, detail="Hanya invoice draft/batal yang bisa dihapus — ubah status ke Batal dulu")
    await db.invoices.delete_one({"id": invoice_id})
    await record(db, actor=user, action="delete", entity_type="invoice", entity_id=invoice_id, before=inv,
                 summary=f"Hapus invoice {inv.get('number')}")
    return {"ok": True}


@router.get("/invoices/{invoice_id}")
async def get_invoice(invoice_id: str, user=Depends(FIN)):
    return safe_doc(await _get(get_db(), invoice_id))


# ------------------------------------------------------------------ kwitansi (receipt)
@router.get("/receipts")
async def list_receipts(booking_id: str = Query(default=None), only_issued: bool = Query(default=False),
                        limit: int = Query(default=300, le=1000), user=Depends(FIN)):
    """Daftar pembayaran + status kwitansinya (receipt_no terisi = sudah terbit)."""
    db = get_db()
    q = {}
    if booking_id:
        q["booking_id"] = booking_id
    if only_issued:
        q["receipt_no"] = {"$exists": True, "$ne": None}
    rows = await db.payments.find(q, {"_id": 0}).sort("paid_at", -1).to_list(limit)
    codes = {b["id"]: b for b in await db.bookings.find({"id": {"$in": list({r["booking_id"] for r in rows})}},
                                                         {"_id": 0, "id": 1, "code": 1, "customer_name": 1, "vehicle_name": 1}).to_list(limit)}
    for r in rows:
        b = codes.get(r.get("booking_id")) or {}
        r.update({"booking_code": b.get("code"), "customer_name": b.get("customer_name"), "vehicle_name": b.get("vehicle_name")})
    return safe_doc(rows)


async def _issue_receipt(db, pay: dict, user) -> dict:
    if pay.get("receipt_no"):
        return pay
    booking = await db.bookings.find_one({"id": pay.get("booking_id")}, {"_id": 0}) or {}
    number = await nb.generate(db, "receipt", {"booking_code": booking.get("code"), "customer_name": booking.get("customer_name")})
    upd = {"receipt_no": number, "receipt_issued_at": now_iso(), "receipt_issued_by": user.get("id"), "receipt_issued_by_name": user.get("name")}
    await db.payments.update_one({"id": pay["id"]}, {"$set": upd})
    await record(db, actor=user, action="create", entity_type="receipt", entity_id=pay["id"],
                 summary=f"Terbitkan kwitansi {number} (Rp {money(pay.get('amount')):,}) booking {booking.get('code')}".replace(",", "."))
    return {**pay, **upd}


@router.post("/payments/{payment_id}/receipt")
async def issue_receipt(payment_id: str, user=Depends(FIN)):
    db = get_db()
    pay = await db.payments.find_one({"id": payment_id}, {"_id": 0})
    if not pay:
        raise HTTPException(status_code=404, detail="Pembayaran tidak ditemukan")
    return safe_doc(await _issue_receipt(db, pay, user))


@router.get("/payments/{payment_id}/receipt/pdf")
async def receipt_pdf(payment_id: str, download: bool = Query(default=False), user=Depends(FIN)):
    db = get_db()
    pay = await db.payments.find_one({"id": payment_id}, {"_id": 0})
    if not pay:
        raise HTTPException(status_code=404, detail="Pembayaran tidak ditemukan")
    pay = await _issue_receipt(db, pay, user)
    pdf = await docs.receipt_pdf(db, pay, issuer=user)
    disp = "attachment" if download else "inline"
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'{disp}; filename="{pay["receipt_no"].replace("/", "-")}.pdf"'})


@router.post("/payments/{payment_id}/receipt/send-wa")
async def receipt_send_wa(payment_id: str, user=Depends(FIN)):
    db = get_db()
    pay = await db.payments.find_one({"id": payment_id}, {"_id": 0})
    if not pay:
        raise HTTPException(status_code=404, detail="Pembayaran tidak ditemukan")
    pay = await _issue_receipt(db, pay, user)
    booking = await db.bookings.find_one({"id": pay.get("booking_id")}, {"_id": 0}) or {}
    cust = await db.customers.find_one({"id": booking.get("customer_id")}, {"_id": 0, "phone": 1}) or {}
    phone = booking.get("customer_phone") or cust.get("phone")
    if not phone:
        raise HTTPException(status_code=400, detail="Nomor WhatsApp pelanggan tidak ditemukan")
    pdf = await docs.receipt_pdf(db, pay, issuer=user)
    caption = (f"Halo {booking.get('customer_name') or 'Pelanggan'}, terima kasih. Berikut kwitansi {pay['receipt_no']} "
               f"atas pembayaran Rp {money(pay.get('amount')):,} untuk booking {booking.get('code')}. 🙏").replace(",", ".")
    res = await _send_pdf_wa(db, phone, pdf, caption, f"{pay['receipt_no'].replace('/', '-')}.pdf",
                             booking.get("customer_id"), booking.get("customer_name"), "receipt", user)
    await record(db, actor=user, action="send", entity_type="receipt", entity_id=pay["id"],
                 summary=f"Kirim kwitansi {pay['receipt_no']} via WhatsApp ke {phone}")
    return {"ok": True, "number": pay["receipt_no"], **res}
