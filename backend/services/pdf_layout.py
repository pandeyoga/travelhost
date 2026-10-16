"""services/pdf_layout.py — mesin cetak dokumen berkop (satu renderer untuk invoice, kwitansi,
dan PRATINJAU konfigurasi). Kop/footer/watermark/tanda tangan/tabel dibaca dari layout.
"""
import io
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4, LETTER, legal
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Image as RLImage
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

PAPER = {"A4": A4, "LETTER": LETTER, "LEGAL": legal}
_ALLOWED_TAGS = ("b", "i", "u", "br")


def _hex(value, fallback="#007AFF"):
    try:
        return colors.HexColor(value or fallback)
    except (ValueError, AttributeError):
        return colors.HexColor(fallback)


def rp(v) -> str:
    if v is None:
        return "belum ditetapkan"
    return f"Rp {int(round(float(v))):,}".replace(",", ".")


def _safe(text) -> str:
    """Escape teks pemakai tapi izinkan <b>/<i>/<u>/<br> sederhana."""
    s = escape("" if text is None else str(text))
    for t in _ALLOWED_TAGS:
        s = s.replace(f"&lt;{t}&gt;", f"<{t}/>" if t == "br" else f"<{t}>").replace(f"&lt;/{t}&gt;", f"</{t}>")
    return s.replace("&lt;br/&gt;", "<br/>")


def _reader(data):
    try:
        return ImageReader(io.BytesIO(data))
    except Exception:  # noqa: BLE001
        return None


class _Frame:
    def __init__(self, layout, imgs):
        self.b, self.o, self.imgs = layout.get("brand") or {}, layout.get("options") or {}, imgs or {}

    def __call__(self, canvas, doc):
        canvas.saveState()
        self._watermark(canvas, doc)
        self._header(canvas, doc)
        self._footer(canvas, doc)
        canvas.restoreState()

    def _header(self, canvas, doc):
        w, h = doc.pagesize
        mode = self.b.get("header_mode") or "system"
        if mode == "none":
            return
        if mode == "image" and self.imgs.get("header_image"):
            img = _reader(self.imgs["header_image"])
            if img:
                iw, ih = img.getSize()
                tinggi = min(30 * mm, (w * ih) / max(iw, 1))
                canvas.drawImage(img, 0, h - tinggi, width=w, height=tinggi, preserveAspectRatio=True, anchor="n", mask="auto")
                return
        left = float(self.b.get("margin_left_mm") or 20) * mm
        right = w - float(self.b.get("margin_right_mm") or 20) * mm
        top, x = h - 14 * mm, left
        if self.imgs.get("logo"):
            img = _reader(self.imgs["logo"])
            if img:
                iw, ih = img.getSize()
                lh = 16 * mm
                lw = min(40 * mm, (lh * iw) / max(ih, 1))
                canvas.drawImage(img, left, top - lh + 3 * mm, width=lw, height=lh, preserveAspectRatio=True, anchor="sw", mask="auto")
                x = left + lw + 5 * mm
        canvas.setFillColor(_hex(self.b.get("text_color"), "#1C1C1E"))
        canvas.setFont("Helvetica-Bold", 13)
        canvas.drawString(x, top - 3 * mm, str(self.b.get("company_name") or ""))
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#64748b"))
        baris = [self.b.get("tagline"), self.b.get("address"),
                 " · ".join(t for t in [self.b.get("phone"), self.b.get("email"), self.b.get("website")] if t),
                 f"NPWP {self.b.get('npwp')}" if self.b.get("npwp") else None]
        y = top - 8 * mm
        for line in [b for b in baris if b]:
            canvas.drawString(x, y, str(line)[:110])
            y -= 3.6 * mm
        canvas.setStrokeColor(_hex(self.b.get("accent_color")))
        canvas.setLineWidth(1.6)
        garis = min(y + 1.5 * mm, top - 9 * mm)
        canvas.line(left, garis, right, garis)

    def _footer(self, canvas, doc):
        w, _h = doc.pagesize
        left = float(self.b.get("margin_left_mm") or 20) * mm
        right = w - float(self.b.get("margin_right_mm") or 20) * mm
        mode = self.b.get("footer_mode") or "system"
        if mode == "image" and self.imgs.get("footer_image"):
            img = _reader(self.imgs["footer_image"])
            if img:
                iw, ih = img.getSize()
                tinggi = min(22 * mm, (w * ih) / max(iw, 1))
                canvas.drawImage(img, 0, 0, width=w, height=tinggi, preserveAspectRatio=True, anchor="s", mask="auto")
                return
        if mode == "none":
            return
        canvas.setStrokeColor(colors.HexColor("#e2e8f0"))
        canvas.setLineWidth(0.6)
        canvas.line(left, 15 * mm, right, 15 * mm)
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#64748b"))
        teks = self.b.get("footer_text") or " · ".join(
            t for t in [self.b.get("company_name"), self.b.get("address"), self.b.get("phone"), self.b.get("website")] if t)
        canvas.drawString(left, 11 * mm, str(teks)[:150])
        if self.b.get("show_page_numbers", True):
            canvas.drawRightString(right, 11 * mm, f"Halaman {canvas.getPageNumber()}")

    def _watermark(self, canvas, doc):
        w, h = doc.pagesize
        alpha = max(0, min(int(self.b.get("watermark_opacity") or 8), 60)) / 100.0
        if self.imgs.get("watermark"):
            img = _reader(self.imgs["watermark"])
            if img:
                canvas.saveState()
                canvas.setFillAlpha(alpha)
                canvas.drawImage(img, w * 0.15, h * 0.3, width=w * 0.7, height=h * 0.35, preserveAspectRatio=True, anchor="c", mask="auto")
                canvas.restoreState()
                return
        teks = (self.b.get("watermark_text") or "").strip()
        if not teks:
            return
        canvas.saveState()
        canvas.setFillAlpha(alpha)
        canvas.setFillColor(_hex(self.b.get("accent_color")))
        canvas.setFont("Helvetica-Bold", 64)
        canvas.translate(w / 2, h / 2)
        canvas.rotate(38)
        canvas.drawCentredString(0, 0, teks[:28])
        canvas.restoreState()


def _styles(layout):
    b = layout.get("brand") or {}
    s = getSampleStyleSheet()
    width = PAPER.get(b.get("paper") or "A4", A4)[0] - (float(b.get("margin_left_mm") or 20) + float(b.get("margin_right_mm") or 20)) * mm - 12
    return {
        "width": width,
        "title": ParagraphStyle("t", parent=s["Title"], fontSize=15, spaceAfter=1, textColor=_hex(b.get("text_color"), "#1C1C1E")),
        "num": ParagraphStyle("n", parent=s["Normal"], fontSize=9, alignment=TA_CENTER, textColor=colors.HexColor("#64748b")),
        "body": ParagraphStyle("b", parent=s["Normal"], fontSize=10, leading=15),
        "small": ParagraphStyle("s", parent=s["Normal"], fontSize=8, textColor=colors.HexColor("#64748b")),
        "right": ParagraphStyle("r", parent=s["Normal"], fontSize=9.5, alignment=TA_RIGHT),
        "sec": ParagraphStyle("sec", parent=s["Normal"], fontSize=10.5, spaceBefore=8, spaceAfter=3,
                              textColor=_hex(b.get("accent_color")), fontName="Helvetica-Bold"),
    }


def _kv(rows, st):
    t = Table([[Paragraph(f"<b>{_safe(k)}</b>", st["body"]), Paragraph(_safe(v), st["body"])] for k, v in rows],
              colWidths=[st["width"] * .3, st["width"] * .7])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 2),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 2), ("LINEBELOW", (0, 0), (-1, -2), 0.3, colors.HexColor("#eef2f7"))]))
    return t


def _tcfg(layout):
    t = dict((layout or {}).get("table") or {})
    return {"grid": t.get("grid") or "full", "show_header": t.get("show_header", True) is not False,
            "header_fill": t.get("header_fill", True) is not False, "zebra": t.get("zebra", True) is not False,
            "total_highlight": t.get("total_highlight", True) is not False, "font_size": float(t.get("font_size") or 8.5),
            "grid_color": t.get("grid_color") or "#e2e8f0", "width_pct": float(t.get("width_pct") or 100),
            "alignment": t.get("alignment") or "left"}


def _table_style(cfg, accent, *, has_header, has_total):
    style = [("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
    warna = _hex(cfg["grid_color"], "#e2e8f0")
    if cfg["grid"] == "full":
        style.append(("GRID", (0, 0), (-1, -1), 0.3, warna))
    elif cfg["grid"] == "horizontal":
        style.append(("LINEBELOW", (0, 0), (-1, -2), 0.3, warna))
    if has_header and cfg["header_fill"]:
        style += [("BACKGROUND", (0, 0), (-1, 0), accent), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white)]
    if cfg["zebra"]:
        style.append(("ROWBACKGROUNDS", (0, 1 if has_header else 0), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]))
    if has_total and cfg["total_highlight"]:
        style.append(("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#ecfdf5")))
    return style


def _money_table(rows, st, accent, cfg):
    body = ParagraphStyle("mb", parent=st["body"], fontSize=cfg["font_size"], leading=cfg["font_size"] + 3)
    right = ParagraphStyle("mr", parent=st["right"], fontSize=cfg["font_size"], leading=cfg["font_size"] + 3)
    data = []
    if cfg["show_header"]:
        hb = ParagraphStyle("mh", parent=body, textColor=colors.white if cfg["header_fill"] else colors.black)
        data.append([Paragraph("<b>Keterangan</b>", hb), Paragraph("<b>Nilai</b>", ParagraphStyle("mhr", parent=hb, alignment=TA_RIGHT))])
    for r in rows:
        data.append([Paragraph(_safe(r["label"]) + (" *" if r.get("manual") else ""), body), Paragraph(rp(r.get("amount")), right)])
    width = st["width"] * cfg["width_pct"] / 100
    t = Table(data, colWidths=[width * .66, width * .34], hAlign=cfg["alignment"].upper(), repeatRows=1 if cfg["show_header"] else 0)
    t.setStyle(TableStyle(_table_style(cfg, accent, has_header=cfg["show_header"], has_total=False)))
    return t


def _grid(columns, rows, total_row, st, accent, cfg):
    small = ParagraphStyle("g", parent=st["small"], fontSize=cfg["font_size"], leading=cfg["font_size"] + 3, textColor=colors.black)
    right = ParagraphStyle("gr", parent=small, alignment=TA_RIGHT)
    n = max(len(columns), 1)
    data = []
    if cfg["show_header"]:
        hs = ParagraphStyle("gh", parent=small, textColor=colors.white if cfg["header_fill"] else colors.black)
        data.append([Paragraph(f"<b>{_safe(c)}</b>", hs if i == 0 else ParagraphStyle("ghr", parent=hs, alignment=TA_RIGHT if i else 0)) for i, c in enumerate(columns)])
    for r in rows:
        data.append([Paragraph(_safe(c), small if i == 0 else right) for i, c in enumerate(r)])
    if total_row:
        data.append([Paragraph(f"<b>{_safe(c)}</b>", small if i == 0 else right) for i, c in enumerate(total_row)])
    if not data:
        return Spacer(1, 1)
    width = st["width"] * cfg["width_pct"] / 100
    first = width * (0.46 if n > 2 else 0.66)
    rest = (width - first) / max(n - 1, 1)
    t = Table(data, colWidths=[first] + [rest] * (n - 1), hAlign=cfg["alignment"].upper(), repeatRows=1 if cfg["show_header"] else 0)
    t.setStyle(TableStyle(_table_style(cfg, accent, has_header=cfg["show_header"], has_total=bool(total_row))))
    return t


def _signature_block(layout, imgs, st):
    sigs = layout.get("signatures") or []
    if not sigs:
        return []
    o = layout.get("options") or {}
    flow = []
    if o.get("show_place_date", True):
        tempat = (o.get("place") or "").strip()
        flow += [Paragraph(f"{tempat + ', ' if tempat else ''}{o.get('doc_date') or ''}", st["right"]), Spacer(1, 6)]
    cells, lebar = [], st["width"] / max(len(sigs), 1)
    for i, s in enumerate(sigs):
        isi = [Paragraph(f"<b>{_safe(s.get('title'))}</b>", st["body"])]
        spesimen = imgs.get(f"sig{i}_sign") or (imgs.get(f"sig{i}_stamp") if s.get("show_stamp") else None)
        img = _reader(spesimen) if spesimen else None
        if img:
            iw, ih = img.getSize()
            hh = 18 * mm
            isi += [Spacer(1, 3), RLImage(io.BytesIO(spesimen), width=min(34 * mm, hh * iw / max(ih, 1)), height=hh)]
        else:
            isi.append(Spacer(1, 20 * mm))
        if s.get("show_stamp") and o.get("show_materai") and i == 0:
            isi.append(Paragraph(_safe(o.get("materai_note") or "Bermeterai cukup"), st["small"]))
        isi.append(Paragraph(f"<u>{_safe(s.get('name') or '(...............................)')}</u>", st["body"]))
        if s.get("position"):
            isi.append(Paragraph(_safe(s["position"]), st["small"]))
        cells.append(isi)
    t = Table([cells], colWidths=[lebar] * len(sigs))
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 4)]))
    flow.append(t)
    return flow


def _content_flow(content, st, markers):
    body = []
    for raw in (content or "").split("\n"):
        line = raw.rstrip()
        key = line.strip()
        if key in markers:
            body.extend(markers[key]())
        elif not key:
            body.append(Spacer(1, 5))
        elif " : " in line:
            k, v = line.split(":", 1)
            body.append(_kv([(k.strip(), v.strip())], st))
        else:
            body.append(Paragraph(_safe(line), st["body"]))
    return body


def _order(layout, keys):
    secs = sorted(layout.get("sections") or [], key=lambda s: s.get("order") or 0)
    known = {s.get("key") for s in secs}
    return [s["key"] for s in secs if s.get("visible", True) and s.get("key") in keys] + [k for k in keys if k not in known]


def render_letter(layout, imgs, *, title, doc_number="", content="", meta=None, money_rows=None, item_table=None,
                  bank_lines=None, note="", signatures_override=None, terbilang="") -> bytes:
    """Invoice/kwitansi: kop, judul, identitas, naskah (+marker tabel), rincian, ringkasan, rekening, ttd."""
    st = _styles(layout)
    o = layout.get("options") or {}
    accent = _hex((layout.get("brand") or {}).get("accent_color"))
    tcfg = _tcfg(layout)
    b = layout.get("brand") or {}
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=PAPER.get(b.get("paper") or "A4", A4),
                            topMargin=float(b.get("margin_top_mm") or 34) * mm, bottomMargin=float(b.get("margin_bottom_mm") or 24) * mm,
                            leftMargin=float(b.get("margin_left_mm") or 20) * mm, rightMargin=float(b.get("margin_right_mm") or 20) * mm,
                            title=doc_number or title)
    flow = []
    if o.get("show_title", True):
        flow.append(Paragraph(_safe(title), st["title"]))
    if doc_number and o.get("show_doc_number", True):
        flow.append(Paragraph(f"Nomor: {_safe(doc_number)}", st["num"]))
    flow.append(Spacer(1, 10))

    def money_block():
        if not money_rows:
            return []
        items = [Paragraph("Ringkasan biaya", st["sec"]), _money_table(money_rows, st, accent, tcfg)]
        if terbilang and o.get("show_terbilang", True):
            items.append(Paragraph(f"<i>Terbilang: {_safe(terbilang)}</i>", st["small"]))
        if any(r.get("manual") for r in money_rows):
            items.append(Paragraph("* baris tambahan yang diisi manual pada konfigurasi dokumen.", st["small"]))
        return [KeepTogether(items + [Spacer(1, 4)])]

    def item_block():
        if not item_table:
            return []
        kolom, baris, total = item_table
        return [Paragraph("Rincian", st["sec"]), _grid(kolom, baris, total, st, accent, tcfg), Spacer(1, 4)]

    inline_money, inline_items = "{{tabel_biaya}}" in (content or ""), "{{tabel_rincian}}" in (content or "")
    blocks = {"identitas": [], "ketentuan": [], "termin": [], "biaya": [], "bank": [], "catatan": []}
    if meta:
        blocks["identitas"] += [_kv(meta, st), Spacer(1, 6)]
    blocks["ketentuan"] = _content_flow(content, st, {"{{tabel_biaya}}": money_block, "{{tabel_rincian}}": item_block})
    if not inline_items:
        blocks["termin"] = item_block()
    if not inline_money:
        blocks["biaya"] = money_block()
    if bank_lines:
        blocks["bank"] = [Paragraph("Rekening pembayaran", st["sec"])] + [Paragraph(_safe(x), st["body"]) for x in bank_lines] + [Spacer(1, 4)]
    if o.get("closing_note"):
        blocks["catatan"] += [Spacer(1, 6), Paragraph(_safe(o["closing_note"]), st["body"])]
    if note and o.get("show_generated_note", True):
        blocks["catatan"] += [Spacer(1, 6), Paragraph(_safe(note), st["small"])]
    for key in _order(layout, list(blocks)):
        flow += blocks.get(key) or []
    flow.append(Spacer(1, 14))
    sig_layout = dict(layout)
    if signatures_override is not None:
        sig_layout["signatures"] = signatures_override
    flow.append(KeepTogether(_signature_block(sig_layout, imgs, st)))
    frame = _Frame(layout, imgs)
    doc.build(flow, onFirstPage=frame, onLaterPages=frame)
    return buf.getvalue()
