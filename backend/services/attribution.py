"""services/attribution.py — E-ADS atribusi sumber lead (mock-first, deterministik).

Menormalkan UTM/click-id (gclid/fbclid/ttclid) menjadi `channel` kanonik + menyimpan
first-touch & last-touch. Dipakai oleh lead capture publik (form & Lead Ads webhook) dan
`analytics.channels_roi` (CPL/CAC/ROAS). TIDAK menyentuh jaringan & tidak menulis DB.
"""
from core_utils import now_iso

# medium yang menandakan iklan berbayar
PAID_MEDIUMS = {"cpc", "ppc", "paid", "paidsearch", "paid_social", "paid-social", "display", "cpm", "ads", "social-paid"}

# peta source mentah -> channel kanonik
SOURCE_MAP = {
    "google": "google", "google_ads": "google_ads", "adwords": "google_ads", "googleads": "google_ads",
    "facebook": "meta", "fb": "meta", "meta": "meta", "meta_ads": "meta_ads",
    "instagram": "instagram", "ig": "instagram",
    "tiktok": "tiktok", "tiktok_ads": "tiktok_ads", "tt": "tiktok",
    "whatsapp": "whatsapp", "wa": "whatsapp",
    "email": "email", "newsletter": "email", "mailchimp": "email",
    "referral": "referral", "website": "website", "web": "website",
    "organic": "organic", "seo": "organic", "direct": "direct",
}

CHANNEL_LABELS = {
    "google_ads": "Google Ads", "meta_ads": "Meta Ads", "tiktok_ads": "TikTok Ads",
    "google": "Google", "meta": "Meta", "instagram": "Instagram", "tiktok": "TikTok",
    "whatsapp": "WhatsApp", "email": "Email", "referral": "Referral",
    "website": "Website", "organic": "Organik", "direct": "Langsung", "ads": "Iklan",
    "lainnya": "Lainnya",
}

_MEANINGLESS = {None, "", "direct", "lainnya"}


def _clean(v):
    return str(v).strip().lower() if v is not None else ""


def derive_channel(touch):
    """Tentukan channel kanonik dari satu touch (dict). Prioritas: click-id > utm_source(+medium) > referrer."""
    t = touch or {}
    if _clean(t.get("gclid")):
        return "google_ads"
    if _clean(t.get("fbclid")):
        return "meta_ads"
    if _clean(t.get("ttclid")):
        return "tiktok_ads"
    src = _clean(t.get("utm_source")) or _clean(t.get("source"))
    med = _clean(t.get("utm_medium")) or _clean(t.get("medium"))
    if src:
        base = SOURCE_MAP.get(src, src)
        if med in PAID_MEDIUMS and not base.endswith("_ads"):
            return f"{base}_ads"
        return base
    if _clean(t.get("referrer")):
        return "referral"
    return "direct"


def normalize_touch(raw, *, landing_page=None, referrer=None):
    """Bentuk touch standar dari payload mentah (query params / webhook)."""
    raw = raw or {}

    def g(*keys):
        for k in keys:
            v = raw.get(k)
            if v not in (None, ""):
                return str(v)[:300]
        return ""

    touch = {
        "utm_source": g("utm_source", "source"),
        "utm_medium": g("utm_medium", "medium"),
        "utm_campaign": g("utm_campaign", "campaign"),
        "utm_term": g("utm_term", "term"),
        "utm_content": g("utm_content", "content"),
        "gclid": g("gclid"),
        "fbclid": g("fbclid"),
        "ttclid": g("ttclid"),
        "referrer": (referrer if referrer not in (None, "") else g("referrer"))[:300],
        "landing_page": (landing_page if landing_page not in (None, "") else g("landing_page"))[:300],
        "ts": now_iso(),
    }
    touch["channel"] = derive_channel(touch)
    return touch


def build_attribution(payload, *, fallback_source="website"):
    """Dari payload {first_touch?, last_touch?, ...} → struktur tersimpan + channel final.

    Channel final mengutamakan last-touch yang bermakna; bila 'direct'/kosong, mundur ke first-touch;
    bila keduanya kosong → `fallback_source`. Return dict siap-merge ke dokumen lead.
    """
    payload = payload or {}
    first_raw = payload.get("first_touch") if isinstance(payload.get("first_touch"), dict) else {}
    last_raw = payload.get("last_touch") if isinstance(payload.get("last_touch"), dict) else {}
    # toleran: payload datang sebagai satu touch tunggal (tanpa first/last)
    if not first_raw and not last_raw and any(
        k in payload for k in ("utm_source", "source", "gclid", "fbclid", "ttclid", "utm_campaign")
    ):
        first_raw = last_raw = payload

    landing = payload.get("landing_page")
    referrer = payload.get("referrer")
    first = normalize_touch(first_raw, landing_page=landing, referrer=referrer)
    last = normalize_touch(last_raw, landing_page=landing, referrer=referrer)

    channel = last.get("channel")
    if channel in _MEANINGLESS and first.get("channel") not in _MEANINGLESS:
        channel = first.get("channel")
    if channel in _MEANINGLESS:
        channel = fallback_source

    return {
        "attribution": {"first_touch": first, "last_touch": last, "channel": channel},
        "channel": channel,
        "utm_source": last.get("utm_source") or first.get("utm_source") or "",
        "utm_campaign": last.get("utm_campaign") or first.get("utm_campaign") or "",
    }


def channel_label(channel):
    return CHANNEL_LABELS.get(channel, (channel or "lainnya").replace("_", " ").title())


# ── CMS-08: jejak KONTEN (artikel/destinasi/paket) yang dibaca sebelum konversi ──
CONTENT_KINDS = ("article", "destination", "package")


def content_ref(payload) -> dict:
    """Ambil `content_last` dari payload atribusi browser → bentuk tersimpan yang aman.

    Dipakai lead & pesanan publik supaya laporan "konten → lead → pesanan" bisa dihitung
    tanpa menebak. Nilai dibatasi panjang & jenisnya (whitelist kind) agar tak jadi pintu
    penulisan data liar dari klien.
    """
    payload = payload or {}
    raw = payload.get("content_last") or payload.get("content_ref") or {}
    if not isinstance(raw, dict):
        return {}
    kind = str(raw.get("kind") or "").strip().lower().rstrip("s")
    kind = {"artikel": "article", "destinasi": "destination", "paket": "package",
            "blog": "article"}.get(kind, kind)
    slug = str(raw.get("slug") or "").strip()[:200]
    if kind not in CONTENT_KINDS or not slug:
        return {}
    return {
        "kind": kind, "slug": slug,
        "title": str(raw.get("title") or "")[:200],
        "path": str(raw.get("path") or "")[:300],
        "ts": str(raw.get("ts") or "")[:40],
    }
