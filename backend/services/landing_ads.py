"""services/landing_ads.py — jembatan Landing Page <-> kampanye iklan.

Masalah yang diselesaikan: di pembuat kampanye, URL tujuan dulu diisi sebagai TEKS BEBAS. Salah
ketik satu huruf pada slug, atau memilih halaman yang masih DRAF, berarti iklan tetap tayang dan
tetap dibayar sementara pengunjung mendarat di halaman 404. Modul ini membuat halaman tujuan
dipilih dari daftar yang benar-benar TERBIT, menempelkan UTM otomatis, dan memberi **skor
kesiapan iklan** supaya masalah yang menurunkan konversi terlihat SEBELUM uang dibelanjakan.
"""
from urllib.parse import urlencode, urlsplit, urlunsplit

from services import landing_blocks as lb

CONVERSION_BLOCKS = set(lb.CONVERSION_BLOCKS)


def _visible(page):
    return [b for b in (page.get("blocks") or []) if not b.get("hidden")]


def readiness(page: dict, media_ok: bool = True) -> dict:
    """Skor kesiapan iklan 0-100 + daftar temuan yang bisa langsung dikerjakan.

    Bobot dipilih dari dampaknya pada biaya per lead, bukan dari kelengkapan teknis:
    halaman tanpa cara menghubungi (30) jauh lebih merugikan daripada deskripsi SEO kosong (5).
    """
    blocks = _visible(page)
    types = [b.get("type") for b in blocks]
    seo = page.get("seo") or {}
    checks = []

    def add(ok, weight, label, fix, severity="warning"):
        checks.append({"ok": bool(ok), "weight": weight, "label": label, "fix": fix,
                       "severity": "error" if severity == "error" and not ok else severity})

    add(page.get("status") == "published", 25, "Halaman sudah diterbitkan",
        "Terbitkan halaman dulu — iklan ke halaman draf mendarat di 404.", "error")
    has_form = "lead_form" in types
    has_wa = "wa_cta" in types
    add(has_form or has_wa, 30, "Ada cara menghubungi (formulir atau WhatsApp)",
        "Tambahkan blok Formulir Lead atau Tombol WhatsApp — tanpa ini klik iklan tidak bisa "
        "menjadi lead.", "error")
    add(any(t in CONVERSION_BLOCKS for t in types), 5, "Ada blok konversi di layar pertama",
        "Tambahkan hero dengan tombol atau banner CTA.")
    hero = next((b for b in blocks if b.get("type") in ("search_hero", "hero_media")), None)
    hero_media = ((hero or {}).get("props") or {}).get("media") or {}
    add(bool(hero), 5, "Ada blok hero", "Tambahkan blok Hero agar pengunjung langsung paham tawaran.")
    add(bool(hero_media.get("src")), 10, "Hero memakai foto/video",
        "Pasang foto hero dari Media Library — hero tanpa gambar menurunkan kepercayaan.")
    add(media_ok, 5, "Semua media yang dipakai masih tersedia",
        "Ada gambar yang berkasnya hilang. Buka Media Library dan unggah ulang.", "error")
    add(bool((seo.get("title") or "").strip()), 5, "Judul SEO terisi",
        "Isi judul SEO — dipakai pratinjau tautan saat iklan dibagikan.")
    add(bool((seo.get("description") or "").strip()), 5, "Deskripsi SEO terisi",
        "Isi deskripsi SEO (≤160 karakter).")
    add(bool((seo.get("og_image") or "").strip() or hero_media.get("src")), 5,
        "Ada gambar pratinjau tautan", "Isi gambar pratinjau tautan agar tautan iklan tidak tampil polos.")
    add("testimonials" in types or "trust_badges" in types, 5, "Ada bukti sosial",
        "Tambahkan Testimoni atau Lencana Kepercayaan — bukti sosial menaikkan konversi.")

    score = sum(c["weight"] for c in checks if c["ok"])
    blockers = [c for c in checks if not c["ok"] and c["severity"] == "error"]
    level = ("siap" if score >= 85 and not blockers
             else "hampir" if score >= 60 and not blockers else "belum")
    verdict = {
        "siap": "Halaman ini siap dipakai sebagai tujuan iklan.",
        "hampir": "Bisa dipakai, tapi masih ada yang menurunkan konversi — perbaiki dulu bila memungkinkan.",
        "belum": "JANGAN dipakai untuk iklan dulu: ada masalah yang membuat biaya iklan terbuang.",
    }[level]
    return {"score": score, "level": level, "verdict": verdict,
            "checks": checks, "blockers": [c["label"] for c in blockers]}


def ad_url(base_url: str, slug: str, *, utm_source="", utm_medium="", utm_campaign="",
           utm_content="", utm_term="", extra=None) -> str:
    """Bangun URL iklan siap tempel. UTM ditempel di sini (satu tempat) supaya setiap kampanye
    memakai penamaan yang konsisten — UTM yang ditulis tangan per iklan adalah penyebab paling
    umum laporan channel yang berantakan."""
    base = (base_url or "").rstrip("/")
    parts = urlsplit(f"{base}/lp/{str(slug or '').strip('/')}")
    q = {}
    for key, val in (("utm_source", utm_source), ("utm_medium", utm_medium),
                     ("utm_campaign", utm_campaign), ("utm_content", utm_content),
                     ("utm_term", utm_term)):
        v = str(val or "").strip()
        if v:
            q[key] = v
    for k, v in (extra or {}).items():
        if v not in (None, ""):
            q[str(k)] = str(v)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(q), ""))


def preset_utm(provider: str, campaign: str = "") -> dict:
    """Penamaan UTM baku per platform agar cocok dengan pemetaan channel di `services/attribution`."""
    p = (provider or "").lower()
    if p.startswith("meta") or p in ("facebook", "fb", "instagram"):
        return {"utm_source": "meta", "utm_medium": "paid_social", "utm_campaign": campaign}
    if p.startswith("google"):
        return {"utm_source": "google", "utm_medium": "cpc", "utm_campaign": campaign}
    if p.startswith("tiktok"):
        return {"utm_source": "tiktok", "utm_medium": "paid_social", "utm_campaign": campaign}
    return {"utm_source": p or "iklan", "utm_medium": "cpc", "utm_campaign": campaign}
