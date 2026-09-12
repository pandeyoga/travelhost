"""services/landing_blocks.py — SSOT skema blok Landing Page Builder (advanced CMS).

Halaman iklan dibangun dari BLOK, bukan HTML bebas. Alasan:
  1. Keamanan: HTML bebas dari editor = celah XSS pada situs publik. Rich text disaring ketat
     lewat allowlist tag/atribut (`sanitize_html`).
  2. Kecepatan (halaman iklan = Core Web Vitals): setiap blok punya kontrak render yang bisa
     dioptimalkan (hero preload, video lazy + poster wajib, tanpa skrip pihak ketiga liar).
  3. Dua segmen yang diminta user — fokus ARMADA & fokus DESTINASI — cukup dibedakan oleh
     kumpulan blok default pada template, bukan cabang kode terpisah.

Setiap blok: {id, type, hidden?, device? (all|desktop|mobile), props{...}}.
Validasi bersifat KOREKTIF (buang props tak dikenal, isi default) + mengumpulkan peringatan,
supaya editor tak pernah menyimpan bentuk yang bisa merusak render publik.

BUG-0111 (F8): `_trust` dulu memanggil `.get()` pada item yang berupa STRING → AttributeError →
HTTP 500 saat membuat halaman dari template. Pelajarannya bukan sekadar menambal satu fungsi:
`validate_blocks` sekarang MEMAGARI setiap builder dengan try/except sehingga bentuk props aneh
apa pun (dari template lama, impor, atau editor) turun menjadi peringatan — BUKAN 5xx
(kontrak INV-5XX-01 + docstring lama yang sudah menjanjikan "tidak melempar").

Nama props di sini adalah KANONIK dan dipakai apa adanya oleh `landing_templates.py` dan
renderer frontend. Guardrail `verify_landing_contract.py` (INV-LP-02) menolak template yang
mengirim key di luar daftar kanonik — supaya tidak ada lagi fitur yang "hilang senyap".
"""
import hashlib
import re
from html.parser import HTMLParser

from core_utils import new_id

# --- allowlist rich text -------------------------------------------------------------------
ALLOWED_TAGS = {"b", "strong", "i", "em", "u", "s", "p", "br", "ul", "ol", "li",
                "h2", "h3", "h4", "a", "span", "blockquote"}
ALLOWED_ATTRS = {"a": {"href", "target", "rel"}, "span": {"class"}, "p": {"class"}}
_SAFE_HREF = re.compile(r"^(https?://|/|mailto:|tel:|https://wa\.me/)", re.I)


class _Sanitizer(HTMLParser):
    # Tag yang ISI-nya harus dibuang total (bukan hanya tag-nya), agar kode tidak bocor
    # menjadi teks yang terlihat di halaman publik.
    DROP_CONTENT = {"script", "style", "iframe", "object", "embed", "noscript"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []
        self._open = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.DROP_CONTENT:
            self._skip_depth += 1
            return
        if self._skip_depth or tag not in ALLOWED_TAGS:
            return
        allowed = ALLOWED_ATTRS.get(tag, set())
        kept = []
        for k, v in attrs:
            if k.lower().startswith("on"):
                continue  # buang handler event (onclick dst)
            if k.lower() not in allowed:
                continue
            if k.lower() == "href" and not _SAFE_HREF.match((v or "").strip()):
                continue
            kept.append((k.lower(), (v or "").replace('"', "&quot;")))
        if tag == "a":
            keys = {k for k, _ in kept}
            if "target" in keys and "rel" not in keys:
                kept.append(("rel", "noopener noreferrer"))
        attr_str = "".join(f' {k}="{v}"' for k, v in kept)
        if tag == "br":
            self.out.append("<br />")
            return
        self.out.append(f"<{tag}{attr_str}>")
        self._open.append(tag)

    def handle_endtag(self, tag):
        if tag in self.DROP_CONTENT:
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if self._skip_depth:
            return
        if tag in ALLOWED_TAGS and tag != "br" and tag in self._open:
            self.out.append(f"</{tag}>")
            self._open.reverse()
            self._open.remove(tag)
            self._open.reverse()

    def handle_data(self, data):
        if self._skip_depth:
            return
        self.out.append(data.replace("<", "&lt;").replace(">", "&gt;"))

    def result(self):
        for tag in reversed(self._open):
            self.out.append(f"</{tag}>")
        return "".join(self.out)


def sanitize_html(value: str, limit: int = 8000) -> str:
    s = _Sanitizer()
    s.feed(str(value or "")[:limit])
    s.close()
    return s.result()


def plain(value, limit=300) -> str:
    if isinstance(value, (dict, list, tuple, set)):
        return ""  # bentuk tak masuk akal untuk teks → kosong, jangan cetak repr objek ke halaman
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _bool(v, default=False):
    if v is None:
        return default
    return bool(v) if not isinstance(v, str) else v.strip().lower() in ("1", "true", "ya", "yes", "on")


def _int(v, default=0, lo=None, hi=None):
    try:
        n = int(float(v))
    except Exception:  # noqa: BLE001
        n = default
    if lo is not None:
        n = max(lo, n)
    if hi is not None:
        n = min(hi, n)
    return n


def _first(raw: dict, *keys, default=None):
    """Ambil nilai pertama yang terisi dari beberapa nama key (dukung data lama/alias)."""
    for k in keys:
        v = (raw or {}).get(k)
        if v not in (None, "", [], {}):
            return v
    return default


def _dict(v):
    return v if isinstance(v, dict) else {}


def _list(v):
    return v if isinstance(v, list) else []


def _cta(raw):
    """Tombol CTA: target internal situs, WhatsApp, atau URL absolut. Atribusi diteruskan."""
    r = _dict(raw)
    kind = str(r.get("kind") or "internal").lower()
    if kind not in ("internal", "whatsapp", "external", "anchor"):
        kind = "internal"
    return {
        "label": plain(r.get("label") or "Pesan Sekarang", 60),
        "kind": kind,
        "target": plain(r.get("target") or ("" if kind == "whatsapp" else "/booking"), 400),
        "message": plain(r.get("message") or "", 300),
        "style": "secondary" if str(r.get("style") or "primary") == "secondary" else "primary",
        "keep_attribution": _bool(r.get("keep_attribution"), True),
    }


def _ctas(raw_list, single=None, limit=2):
    """Normalkan daftar CTA; menerima juga satu CTA tunggal (`cta`) agar data lama tetap hidup."""
    items = [_cta(c) for c in _list(raw_list) if isinstance(c, dict)][:limit]
    if not items and isinstance(single, dict):
        items = [_cta(single)]
    return items


def _media(raw):
    r = _dict(raw)
    return {
        "media_id": plain(r.get("media_id"), 40),
        "src": str(r.get("src") or "").strip()[:600],
        "alt": plain(r.get("alt"), 160),
        "poster": str(r.get("poster") or "").strip()[:600],
        "embed_url": str(r.get("embed_url") or "").strip()[:600],
        "kind": "video" if str(r.get("kind") or "image") == "video" else "image",
    }


# --- kontrak per tipe blok -----------------------------------------------------------------
def _hero(p):
    return {"eyebrow": plain(p.get("eyebrow"), 80), "title": plain(p.get("title") or "Judul utama", 160),
            "subtitle": plain(p.get("subtitle"), 300), "media": _media(p.get("media")),
            "overlay": _int(p.get("overlay"), 45, 0, 90), "align": "center" if p.get("align") == "center" else "left",
            "ctas": _ctas(p.get("ctas"), p.get("cta"))}


def _value_props(p):
    items = []
    for it in _list(p.get("items"))[:6]:
        if isinstance(it, str):
            icon, title, text = "check", plain(it, 80), ""
        else:
            d = _dict(it)
            icon = plain(d.get("icon") or "check", 24)
            title, text = plain(d.get("title"), 80), plain(d.get("text"), 200)
        if title or text:
            items.append({"icon": icon, "title": title, "text": text})
    return {"title": plain(p.get("title"), 120), "items": items}


def _fleet_grid(p):
    return {"title": plain(p.get("title") or "Armada Kami", 120),
            "subtitle": plain(p.get("subtitle"), 200),
            "ids": [plain(x, 40) for x in _list(p.get("ids"))][:12],
            "limit": _int(p.get("limit"), 6, 1, 12),
            "show_price": _bool(p.get("show_price"), True),
            "vehicle_type": plain(p.get("vehicle_type"), 40),
            "cta": _cta(p.get("cta"))}


def _destination_grid(p):
    return {"title": plain(p.get("title") or "Destinasi Populer", 120),
            "subtitle": plain(p.get("subtitle"), 200),
            "ids": [plain(x, 40) for x in _list(p.get("ids"))][:12],
            "limit": _int(p.get("limit"), 6, 1, 12),
            "show_price": _bool(p.get("show_price"), True),
            "region": plain(p.get("region"), 40),
            "cta": _cta(p.get("cta"))}


def _route_grid(p):
    """Rute antar-jemput bertarif FLAT dari master ERP (`/api/public/booking/config` → routes[]).
    Data rute TIDAK disalin ke props: blok hanya menyimpan pilihan (ids/limit), harga & nama rute
    selalu dibaca dari master sehingga perubahan tarif langsung tampil di halaman iklan."""
    return {"title": plain(p.get("title") or "Rute Antar-Jemput Bandara", 120),
            "subtitle": plain(p.get("subtitle"), 200),
            "ids": [plain(x, 40) for x in _list(p.get("ids"))][:12],
            "limit": _int(p.get("limit"), 6, 1, 12),
            "show_price": _bool(p.get("show_price"), True),
            "cta": _cta(p.get("cta"))}


def _gallery(p):
    return {"title": plain(p.get("title"), 120),
            "items": [_media(m) for m in _list(p.get("items"))][:12],
            "columns": _int(p.get("columns"), 3, 1, 4)}


def _testimonials(p):
    return {"title": plain(p.get("title") or "Kata Pelanggan", 120),
            "ids": [plain(x, 40) for x in _list(p.get("ids"))][:8],
            "limit": _int(p.get("limit"), 3, 1, 8)}


def _price_estimator(p):
    return {"title": plain(p.get("title") or "Hitung Estimasi Biaya", 120),
            "subtitle": plain(p.get("subtitle"), 200),
            "default_pax": _int(p.get("default_pax"), 10, 1, 60)}


def _faq(p):
    items = []
    for it in _list(p.get("items"))[:12]:
        d = _dict(it)
        items.append({"q": plain(d.get("q"), 200), "a": sanitize_html(d.get("a"), 1500)})
    return {"title": plain(p.get("title") or "Pertanyaan Umum", 120), "items": items}


def _cta_band(p):
    return {"title": plain(p.get("title") or "Siap berangkat?", 160), "text": plain(p.get("text"), 240),
            "ctas": _ctas(p.get("ctas"), p.get("cta")),
            "tone": "light" if str(p.get("tone") or "dark") == "light" else "dark"}


def _wa_cta(p):
    return {"title": plain(p.get("title") or "Tanya via WhatsApp", 120),
            "text": plain(p.get("text"), 200), "cta": _cta({**_dict(p.get("cta")), "kind": "whatsapp"})}


LEAD_FIELDS = ("name", "phone", "email", "origin", "destination", "start", "end", "pax",
               "vehicle_type", "message")


def _lead_form(p):
    fields = [f for f in _list(p.get("fields")) if f in LEAD_FIELDS]
    if not fields:
        fields = ["name", "phone", "start", "pax", "message"]
    if "name" not in fields:
        fields.insert(0, "name")
    if "phone" not in fields:
        fields.insert(1, "phone")
    return {"title": plain(p.get("title") or "Minta Penawaran", 120),
            "subtitle": plain(p.get("subtitle"), 200),
            "fields": fields[:10],
            "submit_label": plain(p.get("submit_label") or "Kirim Permintaan", 40),
            "consent_text": plain(_first(p, "consent_text", default=
                                  "Saya setuju dihubungi via WhatsApp/telepon untuk penawaran ini."), 300),
            "require_consent": _bool(p.get("require_consent"), True),
            "success_text": plain(_first(p, "success_text", "thank_you", default=
                                  "Terima kasih! Tim kami segera menghubungi Anda."), 200)}


def _countdown(p):
    return {"title": plain(p.get("title") or "Promo berakhir dalam", 120),
            "subtitle": plain(_first(p, "subtitle", "text", default=""), 200),
            "deadline": plain(_first(p, "deadline", "until", default=""), 40)}


def _trust(p):
    """Menerima item berupa STRING ("500+ trip") maupun objek {label, icon}. Dulu hanya objek →
    template yang mengirim string membuat endpoint 500 (BUG-0111)."""
    items = []
    for it in _list(p.get("items"))[:6]:
        if isinstance(it, str):
            label, icon = plain(it, 60), "shield"
        else:
            d = _dict(it)
            label, icon = plain(d.get("label"), 60), plain(d.get("icon") or "shield", 24)
        if label:
            items.append({"label": label, "icon": icon})
    return {"title": plain(p.get("title"), 120), "items": items}


def _rich_text(p):
    return {"title": plain(p.get("title"), 120), "html": sanitize_html(p.get("html"), 8000),
            "width": "wide" if str(p.get("width") or "narrow") == "wide" else "narrow"}


def _video(p):
    return {"title": plain(p.get("title"), 120), "media": _media({**_dict(p.get("media")), "kind": "video"}),
            "autoplay": _bool(p.get("autoplay"), False), "loop": _bool(p.get("loop"), False)}


def _spacer(p):
    return {"size": _int(p.get("size"), 32, 8, 160)}


def _search_hero(p):
    """Hero + widget pencarian (pola Traveloka/OTA): latar gambar, tab kategori, chip cepat,
    dan baris form (tujuan · tanggal · jumlah orang) + tombol cari.

    Kenapa blok ini penting untuk iklan: pengunjung dari iklan datang dengan niat spesifik.
    Menaruh formulir langsung di layar pertama memangkas satu langkah menuju lead."""
    tabs = []
    for t in _list(p.get("tabs"))[:7]:
        t = _dict(t)
        tabs.append({"label": plain(t.get("label") or "Kategori", 28),
                     "icon": plain(t.get("icon") or "bus", 24),
                     "target": plain(t.get("target") or "", 300),
                     "badge": plain(t.get("badge"), 14)})
    chips = [plain(c, 32) for c in _list(p.get("chips"))[:6] if plain(c, 32)]
    fields = []
    for f in _list(p.get("fields"))[:4]:
        f = _dict(f)
        ftype = str(f.get("type") or "text").lower()
        fields.append({"type": ftype if ftype in ("text", "date", "daterange", "number", "select") else "text",
                       "name": plain(f.get("name") or "destination", 24),
                       "label": plain(f.get("label") or "Tujuan", 40),
                       "placeholder": plain(f.get("placeholder"), 60),
                       "icon": plain(f.get("icon") or "map-pin", 24),
                       "options": [plain(o, 40) for o in _list(f.get("options"))[:12]]})
    return {"eyebrow": plain(p.get("eyebrow"), 80),
            "title": plain(p.get("title") or "Cari armada & paket wisata", 160),
            "subtitle": plain(p.get("subtitle"), 300),
            "media": _media(p.get("media")),
            "overlay": _int(p.get("overlay"), 40, 0, 90),
            "tabs": tabs, "active_tab": _int(p.get("active_tab"), 0, 0, 6),
            "chips": chips, "fields": fields,
            "search_label": plain(p.get("search_label") or "Cari", 24),
            "cta": _cta(p.get("cta")),
            "note": plain(p.get("note"), 160)}


THEME_PRESETS = {
    "biru-laut": {"primary": "#0B7BD3", "accent": "#FF7A00", "text": "#10233A", "bg": "#F5F8FC"},
    "hijau-tropis": {"primary": "#0F8A5F", "accent": "#FFB300", "text": "#0E2A22", "bg": "#F4FAF7"},
    "malam-premium": {"primary": "#1F2B48", "accent": "#E0A81C", "text": "#111827", "bg": "#F6F7F9"},
    "merah-berani": {"primary": "#C2261C", "accent": "#F5A524", "text": "#2A1210", "bg": "#FDF6F4"},
}
_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def _color(value, fallback):
    v = str(value or "").strip()
    return v if _HEX.match(v) else fallback


def sanitize_theme(raw):
    """Tema halaman: warna & sudut. Nilai non-hex ditolak (cegah CSS injection lewat style)."""
    r = _dict(raw)
    preset = THEME_PRESETS.get(str(r.get("preset") or ""), THEME_PRESETS["biru-laut"])
    return {
        "preset": str(r.get("preset") or "biru-laut")[:24],
        "primary": _color(r.get("primary"), preset["primary"]),
        "accent": _color(r.get("accent"), preset["accent"]),
        "text": _color(r.get("text"), preset["text"]),
        "bg": _color(r.get("bg"), preset["bg"]),
        "radius": _int(r.get("radius"), 16, 0, 32),
        "font_scale": _int(r.get("font_scale"), 100, 85, 120),
        "button_shape": "pill" if str(r.get("button_shape") or "rounded") == "pill" else "rounded",
    }


BLOCK_TYPES = {
    "hero_media": _hero,
    "search_hero": _search_hero,
    "value_props": _value_props,
    "fleet_grid": _fleet_grid,
    "destination_grid": _destination_grid,
    "route_grid": _route_grid,
    "gallery": _gallery,
    "testimonials": _testimonials,
    "price_estimator": _price_estimator,
    "faq": _faq,
    "cta_band": _cta_band,
    "wa_cta": _wa_cta,
    "lead_form": _lead_form,
    "countdown": _countdown,
    "trust_badges": _trust,
    "rich_text": _rich_text,
    "video": _video,
    "spacer": _spacer,
}
CONVERSION_BLOCKS = ("lead_form", "cta_band", "wa_cta", "hero_media", "search_hero")


def canonical_props(btype: str) -> set:
    """Key props kanonik untuk satu tipe blok (dipakai guardrail INV-LP-02)."""
    builder = BLOCK_TYPES.get(btype)
    return set(builder({}).keys()) if builder else set()


def validate_blocks(blocks):
    """Kembalikan (blocks_bersih, peringatan). TIDAK PERNAH melempar — editor tidak boleh 5xx.

    Pagar try/except per blok disengaja: props bisa datang dari template lama, impor, atau
    editor pihak ketiga. Satu bentuk aneh cukup diturunkan jadi peringatan, bukan mematikan
    seluruh permintaan simpan (pelajaran BUG-0111).
    """
    clean, warnings = [], []
    for raw in _list(blocks)[:60]:
        b = raw if isinstance(raw, dict) else {}
        btype = str(b.get("type") or "").strip()
        if btype not in BLOCK_TYPES:
            warnings.append(f"Blok '{btype or '(kosong)'}' tidak dikenal — dilewati.")
            continue
        try:
            props = BLOCK_TYPES[btype](_dict(b.get("props")))
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"Isi blok '{btype}' tidak dikenali ({type(exc).__name__}) — "
                            f"dikembalikan ke setelan bawaan. Silakan isi ulang.")
            try:
                props = BLOCK_TYPES[btype]({})
            except Exception:  # noqa: BLE001
                continue
        device = str(b.get("device") or "all").lower()
        clean.append({
            "id": plain(b.get("id"), 40) or new_id("blk"),
            "type": btype,
            "hidden": _bool(b.get("hidden"), False),
            "device": device if device in ("all", "desktop", "mobile") else "all",
            "props": props,
        })
    return clean, warnings


def has_conversion_block(blocks) -> bool:
    return any(b.get("type") in CONVERSION_BLOCKS and not b.get("hidden") for b in _list(blocks))


# --- uji A/B --------------------------------------------------------------------------------
AB_OVERRIDE_FIELDS = ("title", "subtitle", "eyebrow", "cta_label")
AB_GOALS = ("lead", "cta_click")


def sanitize_ab(raw):
    """Setelan uji A/B halaman. Varian pertama SELALU 'A' tanpa override (halaman asli) agar
    perbandingan punya titik nol yang jujur; varian B/C hanya menimpa headline & label tombol
    (bagian yang paling berpengaruh pada konversi dan paling murah diuji)."""
    r = _dict(raw)
    variants, seen = [], set()
    for i, v in enumerate(_list(r.get("variants"))[:3]):
        v = _dict(v)
        vid = (plain(v.get("id"), 4) or chr(65 + i)).upper()[:4]
        if vid in seen:
            continue
        seen.add(vid)
        ov_raw = _dict(v.get("overrides"))
        overrides = {k: plain(ov_raw.get(k), 200) for k in AB_OVERRIDE_FIELDS if plain(ov_raw.get(k), 200)}
        variants.append({"id": vid, "name": plain(v.get("name") or f"Varian {vid}", 40),
                         "weight": _int(v.get("weight"), 50, 0, 100),
                         "overrides": {} if i == 0 else overrides})
    goal = str(r.get("goal") or "lead")
    return {
        "enabled": _bool(r.get("enabled"), False) and len(variants) >= 2,
        "goal": goal if goal in AB_GOALS else "lead",
        "min_sample": _int(r.get("min_sample"), 30, 5, 5000),
        "variants": variants,
    }


def default_ab():
    return sanitize_ab({"enabled": False, "variants": [
        {"id": "A", "name": "Asli", "weight": 50, "overrides": {}},
        {"id": "B", "name": "Varian B", "weight": 50, "overrides": {}},
    ]})


def pick_variant(ab, seed: str = ""):
    """Pilih varian secara DETERMINISTIK dari `seed` (id pengunjung). Deterministik penting:
    pengunjung yang me-refresh halaman harus melihat versi yang sama, kalau tidak statistik
    tampilan-vs-lead menjadi campur aduk. Sebaran mengikuti bobot karena seed di-hash rata."""
    ab = _dict(ab)
    variants = _list(ab.get("variants"))
    if not variants:
        return {"id": "A", "name": "Asli", "weight": 100, "overrides": {}}
    if not ab.get("enabled") or len(variants) < 2:
        return variants[0]
    weights = [max(0, _int(v.get("weight"), 0)) for v in variants]
    total = sum(weights) or len(variants)
    if not sum(weights):
        weights = [1] * len(variants)
    point = int(hashlib.sha256(str(seed or "").encode("utf-8")).hexdigest()[:8], 16) % total
    acc = 0
    for v, w in zip(variants, weights):
        acc += w
        if point < acc:
            return v
    return variants[-1]


def apply_variant(blocks, variant):
    """Terapkan override varian ke blok hero pertama (+ label CTA banner) tanpa mengubah data
    tersimpan. Sengaja hanya blok pertama: itulah yang dilihat pengunjung di layar awal."""
    overrides = _dict(_dict(variant).get("overrides"))
    if not overrides:
        return blocks
    out, hero_done = [], False
    for b in _list(blocks):
        nb = {**b, "props": dict(_dict(b.get("props")))}
        p = nb["props"]
        if not hero_done and b.get("type") in ("search_hero", "hero_media"):
            for key in ("title", "subtitle", "eyebrow"):
                if overrides.get(key):
                    p[key] = overrides[key]
            label = overrides.get("cta_label")
            if label:
                if isinstance(p.get("cta"), dict):
                    p["cta"] = {**p["cta"], "label": label}
                if _list(p.get("ctas")):
                    p["ctas"] = [{**_dict(p["ctas"][0]), "label": label}, *p["ctas"][1:]]
            hero_done = True
        elif b.get("type") == "cta_band" and overrides.get("cta_label") and _list(p.get("ctas")):
            p["ctas"] = [{**_dict(p["ctas"][0]), "label": overrides["cta_label"]}, *p["ctas"][1:]]
        out.append(nb)
    return out


def publish_errors(doc) -> list:
    """Aturan minimum agar halaman layak jadi tujuan iklan (dijaga INV-LP-01)."""
    errs = []
    doc = _dict(doc)
    blocks = _list(doc.get("blocks"))
    if not plain(doc.get("slug")):
        errs.append("Slug (alamat halaman) wajib diisi.")
    if not plain(doc.get("title")):
        errs.append("Judul halaman wajib diisi.")
    if not (_dict(doc.get("seo")).get("title")):
        errs.append("SEO: judul untuk hasil pencarian/preview iklan wajib diisi.")
    if not blocks:
        errs.append("Halaman belum punya blok konten.")
    if not has_conversion_block(blocks):
        errs.append("Halaman iklan wajib punya minimal satu blok konversi "
                    "(Formulir Lead, CTA, WhatsApp, atau Hero dengan tombol).")
    for b in blocks:
        if b.get("type") == "video":
            media = _dict(_dict(b.get("props")).get("media"))
            if media.get("src") and not media.get("poster"):
                errs.append("Blok Video wajib punya gambar poster (agar halaman iklan tetap cepat).")
    return errs


def media_ids(blocks) -> list:
    """Semua media_id yang dipakai blok (hero/video/galeri) — untuk resolusi URL & pembersihan."""
    out = []
    for b in _list(blocks):
        props = _dict(b.get("props"))
        mid = _dict(props.get("media")).get("media_id")
        if mid:
            out.append(mid)
        for item in _list(props.get("items")):
            if isinstance(item, dict) and item.get("media_id"):
                out.append(item["media_id"])
        poster = _dict(props.get("media")).get("poster_media_id")
        if poster:
            out.append(poster)
    return list(dict.fromkeys(out))


def public_payload(doc, media_map=None, variant=None):
    """Bentuk yang dikirim ke halaman publik: hanya blok terlihat + URL media yang sudah diselesaikan.
    Bila `variant` diberikan, override headline/CTA diterapkan di sini (satu tempat) supaya
    pratinjau editor dan halaman publik tidak mungkin berbeda."""
    media_map = media_map or {}
    doc = _dict(doc)

    def resolve(media):
        m = dict(_dict(media))
        mid = m.get("media_id")
        if mid and mid in media_map:
            asset = media_map[mid]
            m["src"] = asset.get("url") or m.get("src") or ""
            m["kind"] = asset.get("kind") or m.get("kind")
            m["alt"] = m.get("alt") or asset.get("alt") or ""
            m["width"] = asset.get("width") or 0
            m["height"] = asset.get("height") or 0
        elif mid and mid not in media_map:
            m["src"] = ""  # aset dihapus → jangan render tautan mati
        return m

    blocks = []
    for b in _list(doc.get("blocks")):
        if b.get("hidden"):
            continue
        props = dict(_dict(b.get("props")))
        if "media" in props:
            props["media"] = resolve(props["media"])
        if b.get("type") == "gallery":
            props["items"] = [resolve(m) for m in _list(props.get("items"))]
        blocks.append({**b, "props": props})
    if variant:
        blocks = apply_variant(blocks, variant)
    seo = dict(_dict(doc.get("seo")))
    # Halaman iklan default `noindex`: halaman berbayar tidak boleh bersaing dengan halaman SEO
    # utama di hasil pencarian (kanibalisasi kata kunci), dan halaman promo kedaluwarsa yang
    # ter-index merusak kesan merek. Bisa diubah per halaman bila memang ingin dikejar organik.
    seo["noindex"] = bool(seo.get("noindex", True))
    out = {
        "id": doc.get("id"), "slug": doc.get("slug"), "title": doc.get("title"),
        "segment": doc.get("segment"), "theme": sanitize_theme(doc.get("theme")),
        "seo": seo, "blocks": blocks,
        "tracking": _dict(doc.get("tracking")), "published_at": doc.get("published_at"),
    }
    if variant:
        out["variant"] = {"id": variant.get("id"), "name": variant.get("name")}
        out["ab_enabled"] = bool(_dict(doc.get("ab")).get("enabled"))
    return out
