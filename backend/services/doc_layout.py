"""services/doc_layout.py — konfigurasi tampilan dokumen (kop, footer, baris biaya, tanda
tangan, gaya tabel, opsi) per jenis dokumen; `__default__` = identitas & gaya semua dokumen.
Disimpan di `document_layouts`; setiap kode hanya menyimpan yang berbeda dari bawaan.
"""
import logging
import os
from pathlib import Path

from core_utils import new_id, now_iso

logger = logging.getLogger("travel_fleet.doc_layout")

DEFAULT_CODE = "__default__"
UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", str(Path(__file__).resolve().parent.parent / "uploads")))

TARGETS = {
    DEFAULT_CODE: ("Bawaan seluruh dokumen (identitas & gaya)", "letter"),
    "INVOICE_DP": ("Invoice Uang Muka (DP)", "letter"),
    "INVOICE_SETTLEMENT": ("Invoice Pelunasan", "letter"),
    "INVOICE": ("Invoice Penuh (tagihan total)", "letter"),
    "KWITANSI": ("Kwitansi penerimaan pembayaran", "letter"),
}
TITLES = {"INVOICE_DP": "INVOICE UANG MUKA (DP)", "INVOICE_SETTLEMENT": "INVOICE PELUNASAN",
          "INVOICE": "INVOICE", "KWITANSI": "KWITANSI", DEFAULT_CODE: "DOKUMEN CONTOH"}

MONEY_ROWS = {
    "invoice": [("TOTAL_BOOKING", "Total biaya sewa"), ("DP_AMOUNT", "Uang muka (DP)"),
                ("PAID_BEFORE", "Sudah dibayar"), ("BILLED", "Jumlah tagihan ini"),
                ("OUTSTANDING", "Sisa setelah tagihan ini")],
    "receipt": [("AMOUNT", "Jumlah diterima"), ("TOTAL_BOOKING", "Total biaya sewa"),
                ("PAID_TOTAL", "Total sudah dibayar"), ("OUTSTANDING", "Sisa tagihan")],
}
SECTIONS = [("identitas", "Identitas pelanggan & pemesanan"), ("ketentuan", "Naskah dokumen"),
            ("termin", "Tabel rincian item"), ("biaya", "Tabel ringkasan biaya"),
            ("bank", "Rekening pembayaran"), ("catatan", "Catatan penutup")]


def _rows_for(code: str) -> list:
    return MONEY_ROWS["receipt" if code == "KWITANSI" else "invoice"]


def _brand_default() -> dict:
    return {
        "company_name": "", "tagline": "Travel & Rental Armada", "address": "", "phone": "",
        "email": "", "website": "", "npwp": "",
        "logo_file_id": None, "header_image_file_id": None, "footer_image_file_id": None,
        "header_mode": "system", "footer_mode": "system",
        "accent_color": "#007AFF", "text_color": "#1C1C1E", "footer_text": "", "show_page_numbers": True,
        "paper": "A4", "margin_top_mm": 34, "margin_bottom_mm": 24, "margin_left_mm": 20, "margin_right_mm": 20,
        "watermark_text": "", "watermark_file_id": None, "watermark_opacity": 8,
    }


def _table_default() -> dict:
    return {"grid": "full", "show_header": True, "header_fill": True, "zebra": True,
            "total_highlight": True, "font_size": 8.5, "grid_color": "#E2E8F0", "width_pct": 100, "alignment": "left"}


def default_layout(code: str = DEFAULT_CODE) -> dict:
    keys = [k for k, _ in SECTIONS]
    return {
        "code": code, "brand": _brand_default(), "table": _table_default(),
        "sections": [{"key": k, "label": lbl, "visible": True, "order": keys.index(k) * 10} for k, lbl in SECTIONS],
        "money_rows": [{"code": c, "label": lbl, "visible": True, "order": i * 10,
                        "hide_if_zero": c not in ("BILLED", "AMOUNT", "TOTAL_BOOKING"), "manual": False, "amount": None}
                       for i, (c, lbl) in enumerate(_rows_for(code))],
        "signatures": [
            {"title": "Hormat kami", "name": "", "position": "Finance / Admin", "show_stamp": True,
             "stamp_file_id": None, "sign_file_id": None, "auto_from_issuer": True},
        ] + ([{"title": "Penyetor", "name": "", "position": "", "show_stamp": False, "stamp_file_id": None,
               "sign_file_id": None, "auto_from_issuer": False}] if code == "KWITANSI" else []),
        "options": {
            "show_materai": False, "materai_note": "Bermeterai cukup", "show_place_date": True, "place": "",
            "show_doc_number": True, "show_title": True, "hide_zero_rows": True, "closing_note": "",
            "show_generated_note": True, "show_terbilang": True, "show_qr": False,
        },
    }


def _merge(base: dict, over: dict) -> dict:
    out = {k: (dict(v) if isinstance(v, dict) else list(v) if isinstance(v, list) else v) for k, v in base.items()}
    for key, val in (over or {}).items():
        if key in ("brand", "options", "table") and isinstance(val, dict):
            out[key] = {**out.get(key, {}), **{k: v for k, v in val.items() if v is not None}}
        elif key in ("sections", "money_rows", "signatures") and isinstance(val, list) and val:
            out[key] = val
        elif key not in ("code", "id", "_id"):
            out[key] = val
    return out


async def _company_brand(db) -> dict:
    doc = await db.settings.find_one({"key": "company_info"}, {"_id": 0}) or {}
    ci = doc.get("value") or {}
    return {k: v for k, v in {"company_name": ci.get("name"), "address": ci.get("address"),
                              "phone": ci.get("phone") or ci.get("whatsapp"), "email": ci.get("email"),
                              "website": ci.get("website")}.items() if v}


async def get_layout(db, code: str = DEFAULT_CODE) -> dict:
    """Layout efektif: bawaan kode → identitas perusahaan (settings) → `__default__` → override kode."""
    base = default_layout(code)
    base["brand"].update(await _company_brand(db))
    org_doc = await db.document_layouts.find_one({"code": DEFAULT_CODE}, {"_id": 0})
    if org_doc:
        over = dict(org_doc.get("layout") or {})
        if code != DEFAULT_CODE:
            over.pop("money_rows", None)  # baris biaya berbeda per jenis dokumen
        base = _merge(base, over)
    if code != DEFAULT_CODE:
        own = await db.document_layouts.find_one({"code": code}, {"_id": 0})
        if own:
            base = _merge(base, own.get("layout") or {})
            base["overridden"] = True
    base["code"] = code
    base["label"], base["kind"] = TARGETS.get(code, (code, "letter"))
    base["title"] = TITLES.get(code, code)
    return base


async def save_layout(db, code: str, layout: dict, actor: str) -> dict:
    ts = now_iso()
    cur = await db.document_layouts.find_one({"code": code}, {"_id": 0})
    doc = {"layout": layout, "updated_by": actor, "updated_at": ts, "version": int((cur or {}).get("version") or 0) + 1}
    if cur:
        await db.document_layouts.update_one({"id": cur["id"]}, {"$set": doc})
    else:
        await db.document_layouts.insert_one({"id": new_id("dl"), "code": code, "created_at": ts, **doc})
    return await get_layout(db, code)


async def reset_layout(db, code: str) -> dict:
    await db.document_layouts.delete_one({"code": code})
    return await get_layout(db, code)


async def list_targets(db) -> list:
    from services import doc_script as ds
    rows = {d["code"]: d for d in await db.document_layouts.find({}, {"_id": 0}).to_list(100)}
    scripts = {d["code"]: d for d in await db.document_templates.find({}, {"_id": 0}).to_list(100)}
    return [{"code": c, "label": lbl, "kind": kind,
             "has_script": bool((scripts.get(c) or {}).get("content")) or c in ds.DEFAULTS,
             "script_customized": c in scripts,
             "customized": c in rows, "version": (rows.get(c) or {}).get("version"),
             "updated_at": (rows.get(c) or {}).get("updated_at"), "updated_by": (rows.get(c) or {}).get("updated_by")}
            for c, (lbl, kind) in TARGETS.items()]


def money_rows_for(layout: dict, amounts: dict) -> list:
    hide_zero = bool((layout.get("options") or {}).get("hide_zero_rows", True))
    out = []
    for row in sorted(layout.get("money_rows") or [], key=lambda r: r.get("order") or 0):
        if not row.get("visible", True):
            continue
        if row.get("manual"):
            nilai = row.get("amount")
        else:
            if row["code"] not in amounts:
                continue
            nilai = amounts.get(row["code"])
        if nilai == 0 and hide_zero and row.get("hide_if_zero", True):
            continue
        out.append({"code": row.get("code"), "label": row.get("label"), "amount": nilai, "manual": bool(row.get("manual"))})
    return out


def section_visible(layout: dict, key: str) -> bool:
    for s in layout.get("sections") or []:
        if s.get("key") == key:
            return bool(s.get("visible", True))
    return True


def signatures_for(layout: dict, *, issuer_name=None, issuer_position=None) -> list:
    out = []
    for s in layout.get("signatures") or []:
        name, pos = s.get("name") or "", s.get("position") or ""
        if s.get("auto_from_issuer"):
            name, pos = issuer_name or name, issuer_position or pos
        out.append({**s, "name": name, "position": pos})
    return out


async def images(db, layout: dict) -> dict:
    """Bytes gambar layout (logo/kop/footer/watermark/cap/ttd) dari uploads/docs; yang hilang dilewati."""
    b = layout.get("brand") or {}
    ids = {k: b.get(f"{k}_file_id") for k in ("logo", "header_image", "footer_image", "watermark")}
    for i, s in enumerate(layout.get("signatures") or []):
        ids[f"sig{i}_stamp"] = s.get("stamp_file_id")
        ids[f"sig{i}_sign"] = s.get("sign_file_id")
    out = {}
    for key, fid in ids.items():
        if not fid:
            continue
        rec = await db.doc_assets.find_one({"id": fid}, {"_id": 0})
        if not rec:
            continue
        path = UPLOAD_DIR / "docs" / rec["filename"]
        try:
            out[key] = path.read_bytes()
        except OSError as e:
            logger.warning("gambar layout %s gagal dibaca: %s", key, e)
    return out


def sample_context(code: str) -> dict:
    """Data CONTOH untuk pratinjau — ditandai jelas agar tidak disangka dokumen nyata."""
    ctx = {"doc_number": "0001/CONTOH/VI/2026", "date": "15 Juni 2026", "due_date": "22 Juni 2026",
           "org_name": "Perusahaan Anda", "customer_name": "Budi Santoso (CONTOH)", "customer_phone": "0812-3456-7890",
           "booking_code": "BK-0001", "vehicle_name": "Hiace Premio · D 1234 AB", "driver_name": "Pak Asep",
           "origin": "Bandung", "destination": "Yogyakarta", "start_date": "20 Juni 2026", "end_date": "22 Juni 2026",
           "total": "Rp 7.500.000", "dp_percent": "30%", "dp_amount": "Rp 2.250.000", "paid": "Rp 0",
           "billed": "Rp 2.250.000", "outstanding": "Rp 5.250.000", "kind_label": "Uang Muka (DP)",
           "bank_accounts": "BCA 1234567890 a.n. PT Contoh Travel\nMandiri 9876543210 a.n. PT Contoh Travel",
           "terms": "Pembayaran DP mengikat jadwal. Pelunasan paling lambat H-1 keberangkatan.",
           "notes": "-", "issuer_name": "Admin Keuangan", "amount": "Rp 2.250.000",
           "amount_words": "Dua juta dua ratus lima puluh ribu rupiah", "method": "Transfer bank",
           "payment_type": "Uang muka (DP)", "note": "-"}
    items = [["Sewa Hiace Premio 3 hari", "3", "Rp 2.000.000", "Rp 6.000.000"],
             ["Driver & BBM", "1", "Rp 1.500.000", "Rp 1.500.000"]]
    if code == "KWITANSI":
        amounts = {"AMOUNT": 2250000, "TOTAL_BOOKING": 7500000, "PAID_TOTAL": 2250000, "OUTSTANDING": 5250000}
    else:
        amounts = {"TOTAL_BOOKING": 7500000, "DP_AMOUNT": 2250000, "PAID_BEFORE": 0, "BILLED": 2250000, "OUTSTANDING": 5250000}
    meta = [("Kepada", ctx["customer_name"]), ("Telepon", ctx["customer_phone"]), ("Booking", ctx["booking_code"]),
            ("Armada", ctx["vehicle_name"]), ("Rute", f"{ctx['origin']} → {ctx['destination']}"),
            ("Jadwal", f"{ctx['start_date']} s.d. {ctx['end_date']}"), ("Tanggal terbit", ctx["date"]),
            ("Jatuh tempo", ctx["due_date"])]
    return {"ctx": ctx, "items": items, "amounts": amounts, "meta": meta}
