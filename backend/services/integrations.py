"""services/integrations.py — SSOT konfigurasi integrasi platform (Meta / Google) + kesiapan.

Dipisahkan dari `routers/marketing.py` (fase F3) karena kini DIPAKAI BERSAMA oleh:
  * halaman Integrasi (menyimpan kredensial ter-enkripsi),
  * pengirim konversi server-side (`services/conversions.py`),
  * dashboard & campaign builder iklan (`routers/ads.py`, `routers/ads_manage.py`),
  * webhook Lead Ads (butuh app secret + verify token).

Aturan yang dipaksa di sini:
  - field `public` boleh terlihat di API; field `secrets` SELALU terenkripsi (AES-256-GCM) dan
    hanya dikembalikan sebagai `<field>_set` + `<field>_masked`.
  - `readiness()` menjelaskan dalam Bahasa Indonesia APA yang belum lengkap — supaya user tahu
    persis kolom mana yang harus diisi, bukan sekadar "belum aktif".
"""
from services import secrets_vault as vault
from services.google_ads import DEFAULT_VERSION as GOOGLE_VERSION
from services.google_ads import GoogleAdsClient
from services.meta_ads import DEFAULT_VERSION as META_VERSION
from services.meta_ads import MetaAdsClient

# SSOT bentuk konfigurasi: field publik (boleh terlihat) vs rahasia (selalu terenkripsi).
PROVIDERS = {
    "meta_ads": {
        "key": "meta_ads_config",
        "label": "Meta Ads (Pixel + Conversions API + Marketing API)",
        "public": {"enabled": False, "api_version": META_VERSION, "app_id": "", "pixel_id": "",
                   "dataset_id": "", "ad_account_id": "", "page_id": "", "waba_id": "",
                   "whatsapp_number": "", "lead_form_ids": [], "ldu_enabled": False,
                   "test_mode": False, "max_daily_budget_minor": 0},
        "secrets": ("access_token", "app_secret", "test_event_code",
                    "system_user_token", "page_access_token", "lead_verify_token"),
        "required": ("pixel_id", "access_token"),
        # syarat tambahan agar fitur Ads (Insights/kampanye/audiens) bisa dipakai
        "ads_required": ("ad_account_id", "system_user_token"),
    },
    "google_ads": {
        "key": "google_ads_config",
        "label": "Google Ads + GA4 (Data Manager API)",
        "public": {"enabled": False, "api_version": GOOGLE_VERSION, "ga4_measurement_id": "",
                   "ads_conversion_id": "",
                   "conversion_labels": {"lead_submitted": "", "booking_confirmed": "", "deposit_received": ""},
                   "conversion_action_ids": {"lead_submitted": "", "booking_confirmed": "", "deposit_received": ""},
                   "customer_id": "", "login_customer_id": "", "test_mode": False,
                   "max_daily_budget_micros": 0},
        "secrets": ("oauth_client_id", "oauth_client_secret", "oauth_refresh_token",
                    "developer_token", "ga4_api_secret"),
        "required": ("customer_id", "oauth_refresh_token"),
        "ads_required": ("customer_id", "developer_token"),
    },
}
# nama internal (dipakai outbox konversi) <-> kunci provider di settings
# `ga4` memakai dokumen konfigurasi Google yang sama, tetapi menjadi provider outbox TERSENDIRI
# supaya kesiapan & status kirimnya terlihat terpisah dari Google Ads di halaman Kesehatan Pelacakan.
PROVIDER_ALIASES = (("meta_ads", "meta"), ("google_ads", "google"), ("google_ads", "ga4"))
CONSENT_KEY = "tracking_consent_config"
DEFAULT_CONSENT = {"require_consent": True, "consent_mode": "advanced", "banner_enabled": True,
                   "banner_text": "Kami memakai cookie untuk mengukur efektivitas iklan & meningkatkan layanan.",
                   "privacy_url": "/about"}
FIELD_LABELS = {
    "pixel_id": "Pixel ID", "access_token": "Access Token Meta",
    "ad_account_id": "Ad Account ID", "system_user_token": "System User Token",
    "page_access_token": "Page Access Token", "customer_id": "Customer ID Google Ads",
    "oauth_refresh_token": "Refresh Token OAuth", "developer_token": "Developer Token",
}


def label_of(field: str) -> str:
    return FIELD_LABELS.get(field, field)


async def load_provider(db, provider: str):
    """-> (spec, cfg gabungan default+tersimpan termasuk field *_enc)."""
    spec = PROVIDERS[provider]
    doc = await db.settings.find_one({"key": spec["key"]}, {"_id": 0}) or {}
    value = doc.get("value") or {}
    merged = {**spec["public"], **{k: v for k, v in value.items() if k in spec["public"]}}
    merged.update({k: v for k, v in value.items() if k.endswith(vault.ENC_SUFFIX)})
    return spec, merged


def readiness(spec, cfg, *, requirement: str = "required") -> dict:
    missing = []
    for field in spec.get(requirement) or ():
        if field in spec["secrets"]:
            if not cfg.get(field + vault.ENC_SUFFIX):
                missing.append(field)
        elif not cfg.get(field):
            missing.append(field)
    return {"ready": not missing and bool(cfg.get("enabled")),
            "missing": missing,
            "missing_labels": [label_of(f) for f in missing],
            "mode": "live" if (not missing and cfg.get("enabled")) else "mock"}


async def consent_cfg(db) -> dict:
    doc = await db.settings.find_one({"key": CONSENT_KEY}, {"_id": 0}) or {}
    return {**DEFAULT_CONSENT, **(doc.get("value") or {})}


async def active_configs(db) -> dict:
    """Konfigurasi + rahasia TERDEKRIPSI untuk pemakaian INTERNAL (pengirim konversi/klien API)."""
    out = {}
    for provider, mapped in PROVIDER_ALIASES:
        spec, cfg = await load_provider(db, provider)
        out[mapped] = {**{k: v for k, v in cfg.items() if not k.endswith(vault.ENC_SUFFIX)},
                       "_secrets": vault.secrets_bundle(cfg, spec["secrets"])}
    return out


async def clients(db):
    """-> (MetaAdsClient, GoogleAdsClient, cfgs). Tetap dibuat walau kredensial kosong:
    kliennya sendiri yang melaporkan `not_configured` + alasan (anti-5xx)."""
    cfgs = await active_configs(db)
    meta_cfg = cfgs.get("meta") or {}
    goog_cfg = cfgs.get("google") or {}
    meta = MetaAdsClient(meta_cfg, meta_cfg.get("_secrets") or {})
    google = GoogleAdsClient(goog_cfg, goog_cfg.get("_secrets") or {})
    return meta, google, cfgs


async def ads_readiness(db) -> dict:
    """Kesiapan khusus fitur Ads (Insights, kampanye, audiens) per provider."""
    out = {}
    for provider, mapped in PROVIDER_ALIASES:
        spec, cfg = await load_provider(db, provider)
        status = readiness(spec, cfg, requirement="ads_required")
        status["label"] = spec["label"]
        out[mapped] = status
    return out


async def secret_of(db, provider: str, field: str) -> str:
    """Ambil satu rahasia terdekripsi (mis. app_secret untuk verifikasi webhook)."""
    spec, cfg = await load_provider(db, provider)
    if field not in spec["secrets"]:
        return ""
    return vault.read_secret(cfg, field)
