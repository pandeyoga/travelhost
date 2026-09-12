"""services/documents.py — konteks & PDF invoice (DP / pelunasan / penuh) dan kwitansi.
Angka selalu dari booking + payments (satu sumber), tampilan dari doc_layout, naskah dari doc_script.
"""
from datetime import datetime, timedelta, timezone

from core_utils import money, now_iso
from services import doc_layout as dl
from services import doc_script as ds
from services import pdf_layout as pl

KIND_CODE = {"dp": "INVOICE_DP", "settlement": "INVOICE_SETTLEMENT", "full": "INVOICE"}
KIND_LABEL = {"dp": "Uang Muka (DP)", "settlement": "Pelunasan", "full": "Tagihan Penuh"}
KIND_RULE = {"dp": "invoice_dp", "settlement": "invoice_settlement", "full": "invoice"}
METHOD_LABEL = {"transfer": "Transfer bank", "cash": "Tunai", "qris": "QRIS", "ewallet": "E-wallet", "card": "Kartu"}
TYPE_LABEL = {"dp": "Uang muka (DP)", "settlement": "Pelunasan", "full": "Pembayaran penuh", "refund": "Pengembalian"}
INVOICE_CONFIG_DEFAULT = {
    "dp_percent_default": 30, "dp_due_days": 3, "settlement_due_days": 7, "settlement_due_before_start_days": 1,
    "bank_accounts": [], "payment_terms": ("DP bersifat mengikat jadwal & armada. Pelunasan paling lambat H-1 keberangkatan. "
                                           "Pembatalan mengikuti kebijakan perusahaan."),
    "footer_note": "Dokumen ini diterbitkan otomatis oleh sistem dan sah tanpa tanda tangan basah.",
}
_BULAN = ["", "Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember"]
_SATUAN = ["", "satu", "dua", "tiga", "empat", "lima", "enam", "tujuh", "delapan", "sembilan", "sepuluh", "sebelas"]


def fdate(value) -> str:
    if not value:
        return "-"
    try:
        d = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return f"{d.day} {_BULAN[d.month]} {d.year}"
    except Exception:  # noqa: BLE001
        return str(value)[:10]


def _terbilang(n: int) -> str:
    if n < 12:
        return _SATUAN[n]
    if n < 20:
        return _SATUAN[n - 10] + " belas"
    if n < 100:
        return _SATUAN[n // 10] + " puluh" + (f" {_terbilang(n % 10)}" if n % 10 else "")
    if n < 200:
        return "seratus" + (f" {_terbilang(n - 100)}" if n > 100 else "")
    if n < 1000:
        return _SATUAN[n // 100] + " ratus" + (f" {_terbilang(n % 100)}" if n % 100 else "")
    if n < 2000:
        return "seribu" + (f" {_terbilang(n - 1000)}" if n > 1000 else "")
    for div, nama in ((10 ** 12, "triliun"), (10 ** 9, "miliar"), (10 ** 6, "juta"), (1000, "ribu")):
        if n >= div:
            return _terbilang(n // div) + f" {nama}" + (f" {_terbilang(n % div)}" if n % div else "")
    return str(n)


def terbilang(v) -> str:
    n = money(v)
    if n <= 0:
        return "nol rupiah"
    return (_terbilang(n) + " rupiah").capitalize()


async def invoice_config(db) -> dict:
    doc = await db.settings.find_one({"key": "invoice_config"}, {"_id": 0}) or {}
    return {**INVOICE_CONFIG_DEFAULT, **(doc.get("value") or {})}


async def org_name(db) -> str:
    doc = await db.settings.find_one({"key": "company_info"}, {"_id": 0}) or {}
    return (doc.get("value") or {}).get("name") or "Perusahaan"


def bank_lines(accounts: list) -> list:
    return [f"{a.get('bank', '')} {a.get('account_no', '')} a.n. {a.get('account_name', '')}".strip() for a in accounts or []]


def default_due(kind: str, cfg: dict, booking: dict) -> str:
    now = datetime.now(timezone.utc)
    if kind == "dp":
        return (now + timedelta(days=int(cfg.get("dp_due_days") or 3))).isoformat()
    try:
        start = datetime.fromisoformat(str(booking.get("start_datetime")).replace("Z", "+00:00"))
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        cand = start - timedelta(days=int(cfg.get("settlement_due_before_start_days") or 1))
        if cand > now:
            return cand.isoformat()
    except Exception:  # noqa: BLE001
        pass
    return (now + timedelta(days=int(cfg.get("settlement_due_days") or 7))).isoformat()


def booking_items(booking: dict) -> list:
    """Baris rincian dari booking: harga dasar + add-on."""
    items = []
    base = money(booking.get("base_price") or 0)
    label = f"Sewa {booking.get('vehicle_name') or 'armada'}"
    if booking.get("origin") or booking.get("destination"):
        label += f" · {booking.get('origin') or '-'} → {booking.get('destination') or '-'}"
    items.append({"label": label, "qty": 1, "unit_price": base, "amount": base})
    for a in booking.get("add_ons") or []:
        if isinstance(a, dict):
            amt = money(a.get("amount") or a.get("price") or 0)
            items.append({"label": a.get("label") or a.get("name") or "Tambahan", "qty": int(a.get("qty") or 1),
                          "unit_price": amt, "amount": amt * int(a.get("qty") or 1)})
    total = money(booking.get("total_amount") or 0)
    diff = total - sum(i["amount"] for i in items)
    if diff:
        items.append({"label": "Penyesuaian / diskon" if diff < 0 else "Biaya lainnya", "qty": 1, "unit_price": diff, "amount": diff})
    return items


async def _driver_name(db, booking):
    if booking.get("driver_name"):
        return booking["driver_name"]
    return "-"


async def invoice_context(db, inv: dict, booking: dict, cfg: dict, issuer: str) -> dict:
    total = money(inv.get("subtotal") or booking.get("total_amount") or 0)
    return {
        "doc_number": inv.get("number"), "date": fdate(inv.get("issued_at")), "due_date": fdate(inv.get("due_at")),
        "org_name": await org_name(db), "customer_name": inv.get("customer_name") or booking.get("customer_name"),
        "customer_phone": inv.get("customer_phone") or "-", "booking_code": booking.get("code"),
        "vehicle_name": booking.get("vehicle_name") or "-", "driver_name": await _driver_name(db, booking),
        "origin": booking.get("origin") or "-", "destination": booking.get("destination") or "-",
        "start_date": fdate(booking.get("start_datetime")), "end_date": fdate(booking.get("end_datetime")),
        "total": pl.rp(total), "dp_percent": f"{float(inv.get('dp_percent') or 0):g}%", "dp_amount": pl.rp(inv.get("dp_amount") or 0),
        "paid": pl.rp(inv.get("paid_before") or 0), "billed": pl.rp(inv.get("amount") or 0),
        "outstanding": pl.rp(inv.get("outstanding_after") or 0),
        "bank_accounts": "\n".join(bank_lines(inv.get("bank_accounts") or cfg.get("bank_accounts"))) or "-",
        "terms": inv.get("terms") or cfg.get("payment_terms") or "", "notes": inv.get("notes") or "-",
        "kind_label": KIND_LABEL.get(inv.get("kind"), "Tagihan"), "issuer_name": issuer or "-",
    }


async def invoice_pdf(db, inv: dict, issuer: dict = None) -> bytes:
    booking = await db.bookings.find_one({"id": inv.get("booking_id")}, {"_id": 0}) or {}
    cfg = await invoice_config(db)
    code = KIND_CODE.get(inv.get("kind"), "INVOICE")
    layout = await dl.get_layout(db, code)
    issuer_name = (issuer or {}).get("name") or inv.get("created_by_name") or ""
    ctx = await invoice_context(db, inv, booking, cfg, issuer_name)
    script = (await ds.get_script(db, code))["content"]
    content = ds.substitute(script, ctx)
    amounts = {"TOTAL_BOOKING": money(inv.get("subtotal") or 0), "DP_AMOUNT": money(inv.get("dp_amount") or 0),
               "PAID_BEFORE": money(inv.get("paid_before") or 0), "BILLED": money(inv.get("amount") or 0),
               "OUTSTANDING": money(inv.get("outstanding_after") or 0)}
    items = inv.get("items") or booking_items(booking)
    rows = [[i["label"], str(i.get("qty") or 1), pl.rp(i.get("unit_price")), pl.rp(i.get("amount"))] for i in items]
    total_row = ["TOTAL", "", "", pl.rp(inv.get("subtotal") or 0)]
    meta = [("Kepada", ctx["customer_name"]), ("Telepon", ctx["customer_phone"]), ("Booking", ctx["booking_code"]),
            ("Armada", ctx["vehicle_name"]), ("Rute", f"{ctx['origin']} → {ctx['destination']}"),
            ("Jadwal", f"{ctx['start_date']} s.d. {ctx['end_date']}"), ("Jenis tagihan", ctx["kind_label"]),
            ("Tanggal terbit", ctx["date"]), ("Jatuh tempo", ctx["due_date"]), ("Status", STATUS_LABEL.get(inv.get("status"), inv.get("status")))]
    layout.setdefault("options", {})["doc_date"] = ctx["date"]
    banks = bank_lines(inv.get("bank_accounts") or cfg.get("bank_accounts")) if dl.section_visible(layout, "bank") and "{{bank_accounts}}" not in script else None
    return pl.render_letter(
        layout, await dl.images(db, layout), title=layout["title"], doc_number=inv.get("number"), content=content,
        meta=meta if dl.section_visible(layout, "identitas") else None,
        money_rows=dl.money_rows_for(layout, amounts), item_table=(["Deskripsi", "Qty", "Harga", "Jumlah"], rows, total_row),
        bank_lines=banks, note=cfg.get("footer_note") or "", terbilang=terbilang(inv.get("amount") or 0),
        signatures_override=dl.signatures_for(layout, issuer_name=issuer_name, issuer_position=(issuer or {}).get("role")))


STATUS_LABEL = {"draft": "Draft", "sent": "Terkirim", "partial": "Dibayar sebagian", "paid": "Lunas", "void": "Dibatalkan"}


async def receipt_context(db, pay: dict, booking: dict, issuer: str) -> dict:
    total = money(booking.get("total_amount") or 0)
    paid = money(booking.get("paid_amount") or 0)
    return {
        "doc_number": pay.get("receipt_no"), "date": fdate(pay.get("receipt_issued_at") or pay.get("paid_at")),
        "org_name": await org_name(db), "customer_name": booking.get("customer_name") or "-",
        "customer_phone": pay.get("customer_phone") or "-", "booking_code": booking.get("code") or "-",
        "vehicle_name": booking.get("vehicle_name") or "-", "start_date": fdate(booking.get("start_datetime")),
        "amount": pl.rp(pay.get("amount") or 0), "amount_words": terbilang(pay.get("amount") or 0),
        "method": METHOD_LABEL.get(pay.get("method"), pay.get("method") or "-"),
        "payment_type": TYPE_LABEL.get(pay.get("type"), pay.get("type") or "Pembayaran"), "note": pay.get("note") or "-",
        "total": pl.rp(total), "paid": pl.rp(paid), "outstanding": pl.rp(max(total - paid, 0)), "issuer_name": issuer or "-",
    }


async def receipt_pdf(db, pay: dict, issuer: dict = None) -> bytes:
    booking = await db.bookings.find_one({"id": pay.get("booking_id")}, {"_id": 0}) or {}
    cust = await db.customers.find_one({"id": booking.get("customer_id")}, {"_id": 0, "phone": 1}) or {}
    pay = {**pay, "customer_phone": cust.get("phone")}
    layout = await dl.get_layout(db, "KWITANSI")
    issuer_name = (issuer or {}).get("name") or ""
    ctx = await receipt_context(db, pay, booking, issuer_name)
    content = ds.substitute((await ds.get_script(db, "KWITANSI"))["content"], ctx)
    total, paid = money(booking.get("total_amount") or 0), money(booking.get("paid_amount") or 0)
    amounts = {"AMOUNT": money(pay.get("amount") or 0), "TOTAL_BOOKING": total, "PAID_TOTAL": paid, "OUTSTANDING": max(total - paid, 0)}
    meta = [("Diterima dari", ctx["customer_name"]), ("Booking", ctx["booking_code"]), ("Armada", ctx["vehicle_name"]),
            ("Jenis pembayaran", ctx["payment_type"]), ("Tanggal", ctx["date"])]
    layout.setdefault("options", {})["doc_date"] = ctx["date"]
    cfg = await invoice_config(db)
    return pl.render_letter(
        layout, await dl.images(db, layout), title=layout["title"], doc_number=pay.get("receipt_no"), content=content,
        meta=meta if dl.section_visible(layout, "identitas") else None, money_rows=dl.money_rows_for(layout, amounts),
        note=cfg.get("footer_note") or "", terbilang=ctx["amount_words"],
        signatures_override=dl.signatures_for(layout, issuer_name=issuer_name, issuer_position=(issuer or {}).get("role")))


async def preview_pdf(db, code: str, layout: dict, script: str, issuer: dict = None) -> bytes:
    """Pratinjau dengan data CONTOH memakai mesin cetak yang sama."""
    s = dl.sample_context(code)
    content = ds.substitute(script if script is not None else (await ds.get_script(db, code))["content"], s["ctx"])
    layout.setdefault("options", {})["doc_date"] = s["ctx"]["date"]
    meta = s["meta"] if code != "KWITANSI" else [("Diterima dari", s["ctx"]["customer_name"]), ("Booking", s["ctx"]["booking_code"]),
                                                 ("Jenis pembayaran", s["ctx"]["payment_type"]), ("Tanggal", s["ctx"]["date"])]
    return pl.render_letter(
        layout, await dl.images(db, layout), title=layout.get("title") or dl.TITLES.get(code, code) + " (CONTOH)",
        doc_number=s["ctx"]["doc_number"], content=content, meta=meta if dl.section_visible(layout, "identitas") else None,
        money_rows=dl.money_rows_for(layout, s["amounts"]),
        item_table=(["Deskripsi", "Qty", "Harga", "Jumlah"], s["items"], ["TOTAL", "", "", s["ctx"]["total"]]) if code != "KWITANSI" else None,
        bank_lines=s["ctx"]["bank_accounts"].split("\n") if code != "KWITANSI" and dl.section_visible(layout, "bank") and "{{bank_accounts}}" not in (script or "") else None,
        note="PRATINJAU dengan data contoh — bukan dokumen sah.", terbilang=s["ctx"]["amount_words"],
        signatures_override=dl.signatures_for(layout, issuer_name=(issuer or {}).get("name"), issuer_position=(issuer or {}).get("role")))


async def sync_invoice_status(db, booking_id: str):
    """Setelah pembayaran: invoice booking → partial/paid berdasarkan paid_amount booking."""
    booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0, "paid_amount": 1})
    if not booking:
        return
    paid = money(booking.get("paid_amount") or 0)
    async for inv in db.invoices.find({"booking_id": booking_id, "status": {"$nin": ["void"]}}, {"_id": 0}):
        target = money(inv.get("paid_before") or 0) + money(inv.get("amount") or 0)
        covered = paid - money(inv.get("paid_before") or 0)
        new = "paid" if paid >= target and target > 0 else ("partial" if covered > 0 else None)
        if new and new != inv.get("status"):
            await db.invoices.update_one({"id": inv["id"]}, {"$set": {"status": new, "paid_at": now_iso() if new == "paid" else None}})
