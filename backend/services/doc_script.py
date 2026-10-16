"""services/doc_script.py — naskah dokumen per jenis (isi yang tercetak) + placeholder yang sah.
Disimpan di `document_templates` {code, content, version}. Placeholder asing DITOLAK saat simpan.
"""
import re

from core_utils import new_id, now_iso

_PH = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")

INVOICE_TOKENS = ("doc_number", "date", "due_date", "org_name", "customer_name", "customer_phone", "booking_code",
                  "vehicle_name", "driver_name", "origin", "destination", "start_date", "end_date", "total",
                  "dp_percent", "dp_amount", "paid", "billed", "outstanding", "bank_accounts", "terms", "notes",
                  "kind_label", "issuer_name", "tabel_rincian", "tabel_biaya")
RECEIPT_TOKENS = ("doc_number", "date", "org_name", "customer_name", "customer_phone", "booking_code", "vehicle_name",
                  "start_date", "amount", "amount_words", "method", "payment_type", "note", "total", "paid",
                  "outstanding", "issuer_name", "tabel_biaya")
TOKENS_BY_CODE = {"INVOICE_DP": INVOICE_TOKENS, "INVOICE_SETTLEMENT": INVOICE_TOKENS, "INVOICE": INVOICE_TOKENS,
                  "KWITANSI": RECEIPT_TOKENS, "__default__": INVOICE_TOKENS}

LABELS = {
    "doc_number": "Nomor dokumen", "date": "Tanggal terbit", "due_date": "Jatuh tempo", "org_name": "Nama perusahaan",
    "customer_name": "Nama pelanggan", "customer_phone": "Telepon pelanggan", "booking_code": "Kode booking",
    "vehicle_name": "Armada", "driver_name": "Driver", "origin": "Asal", "destination": "Tujuan",
    "start_date": "Tanggal mulai", "end_date": "Tanggal selesai", "total": "Total biaya sewa",
    "dp_percent": "Persen DP", "dp_amount": "Nominal DP", "paid": "Sudah dibayar", "billed": "Jumlah tagihan ini",
    "outstanding": "Sisa tagihan", "bank_accounts": "Daftar rekening", "terms": "Syarat pembayaran",
    "notes": "Catatan invoice", "kind_label": "Jenis tagihan", "issuer_name": "Nama penerbit",
    "tabel_rincian": "Tabel rincian item (otomatis)", "tabel_biaya": "Tabel ringkasan biaya (otomatis)",
    "amount": "Jumlah diterima", "amount_words": "Terbilang", "method": "Metode bayar",
    "payment_type": "Jenis pembayaran", "note": "Catatan pembayaran",
}

def _inv_body(intro: str, closing: str) -> str:
    return ("Kepada Yth. {{customer_name}},\n\n" + intro + "\n\n{{tabel_rincian}}\n\n{{tabel_biaya}}\n\n"
            "Pembayaran dapat ditransfer ke rekening berikut:\n{{bank_accounts}}\n\n"
            "Mohon melakukan pembayaran paling lambat <b>{{due_date}}</b>. " + closing + "\n\n{{terms}}")


DEFAULTS = {
    "INVOICE_DP": _inv_body(
        "Berikut kami sampaikan tagihan <b>uang muka (DP) sebesar {{dp_percent}}</b> dari total biaya sewa untuk "
        "pemesanan {{booking_code}} — {{vehicle_name}}, rute {{origin}} → {{destination}}, "
        "{{start_date}} s.d. {{end_date}}.",
        "Pemesanan Anda dikonfirmasi setelah DP kami terima."),
    "INVOICE_SETTLEMENT": _inv_body(
        "Berikut kami sampaikan tagihan <b>pelunasan</b> pemesanan {{booking_code}} — {{vehicle_name}}, rute "
        "{{origin}} → {{destination}}, {{start_date}} s.d. {{end_date}}. Total biaya {{total}}, sudah dibayar "
        "{{paid}}, sisa yang harus dilunasi <b>{{billed}}</b>.",
        "Terima kasih atas kepercayaan Anda."),
    "INVOICE": _inv_body(
        "Berikut kami sampaikan tagihan pemesanan {{booking_code}} — {{vehicle_name}}, rute {{origin}} → "
        "{{destination}}, {{start_date}} s.d. {{end_date}} dengan total <b>{{total}}</b>.",
        "Terima kasih atas kepercayaan Anda."),
    "KWITANSI": ("Telah diterima dari : {{customer_name}}\n"
                 "Uang sejumlah : <b>{{amount}}</b>\n"
                 "Terbilang : {{amount_words}}\n"
                 "Untuk pembayaran : {{payment_type}} pemesanan {{booking_code}} ({{vehicle_name}}, {{start_date}})\n"
                 "Metode pembayaran : {{method}}\n\n"
                 "{{tabel_biaya}}\n\n"
                 "Kwitansi ini sah sebagai bukti penerimaan pembayaran dan dicetak dari sistem {{org_name}}."),
}
DEFAULTS["__default__"] = DEFAULTS["INVOICE"]


def placeholders(code: str) -> list:
    return [{"token": t, "label": LABELS.get(t, t)} for t in TOKENS_BY_CODE.get(code, INVOICE_TOKENS)]


def validate(code: str, content: str) -> list:
    allowed = set(TOKENS_BY_CODE.get(code, INVOICE_TOKENS))
    return sorted({t for t in _PH.findall(content or "") if t not in allowed})


async def get_script(db, code: str) -> dict:
    doc = await db.document_templates.find_one({"code": code}, {"_id": 0})
    return {"code": code, "content": (doc or {}).get("content", DEFAULTS.get(code, "")),
            "default_content": DEFAULTS.get(code, ""), "customized": bool(doc),
            "version": (doc or {}).get("version"), "updated_at": (doc or {}).get("updated_at"),
            "placeholders": placeholders(code)}


async def save_script(db, code: str, content: str, actor: str) -> dict:
    bad = validate(code, content)
    if bad:
        raise ValueError("Placeholder tidak dikenal untuk dokumen ini: " + ", ".join(f"{{{{{b}}}}}" for b in bad))
    ts = now_iso()
    cur = await db.document_templates.find_one({"code": code}, {"_id": 0})
    doc = {"content": content, "updated_by": actor, "updated_at": ts, "version": int((cur or {}).get("version") or 0) + 1}
    if cur:
        await db.document_templates.update_one({"code": code}, {"$set": doc})
    else:
        await db.document_templates.insert_one({"id": new_id("tpl"), "code": code, "created_at": ts, **doc})
    return await get_script(db, code)


async def reset_script(db, code: str) -> dict:
    await db.document_templates.delete_one({"code": code})
    return await get_script(db, code)


def substitute(content: str, ctx: dict) -> str:
    """Ganti {{key}}; marker tabel dibiarkan (dirender mesin PDF); yang tak dikenal ditandai mencolok."""
    def sub(m):
        k = m.group(1)
        if k in ("tabel_rincian", "tabel_biaya"):
            return m.group(0)
        if k in ctx and ctx[k] not in (None, ""):
            return str(ctx[k])
        return "-" if k in LABELS else f"[{k} TIDAK TERISI]"
    return _PH.sub(sub, content or "")
