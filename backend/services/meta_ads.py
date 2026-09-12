"""services/meta_ads.py — klien Meta Marketing API (Graph v26.0) untuk ERP.

Cakupan (semua lewat SATU wrapper `_call` supaya perilaku konsisten):
  * metadata akun iklan  : currency & timezone WAJIB dibaca — akun bisa USD/SGD, JANGAN asumsi IDR.
  * Ads Insights         : biaya/impresi/klik/aksi per campaign|adset|ad, harian (time_increment=1),
                           plus jalur ASYNC (report_run_id + polling) untuk rentang besar.
  * entitas iklan        : daftar campaign/adset/ad (nama, status, budget) untuk dashboard & builder.
  * tulis (F7)           : campaign/adset/creative/ad + ubah status/budget — SELALU via ads_safety.
  * audiens (F6)         : Custom Audience, unggah anggota (users/usersreplace), Lookalike.
  * Lead Ads (F5)        : ambil lead per id & backfill per form (butuh Page access token).

Aturan keras:
  - `appsecret_proof` disertakan bila app secret tersedia (rekomendasi keamanan Meta).
  - Tanpa kredensial -> `{"status": "not_configured", "reason": "..."}` (Bahasa Indonesia), NEVER 5xx.
  - Token kedaluwarsa/dicabut (kode 190/102/104/463/467) juga dipetakan ke `not_configured`.
  - Tidak pernah melempar exception ke pemanggil; error jaringan pun jadi status 'error'.
  - Header pemakaian kuota (X-Business-Use-Case-Usage, X-FB-Ads-Insights-Throttle) dikembalikan
    agar bisa ditampilkan/di-backoff.
"""
import asyncio
import hashlib
import hmac
import json
import logging

import httpx

from services import ads_safety as safety

logger = logging.getLogger("travel_fleet.meta_ads")

DEFAULT_VERSION = "v26.0"
GRAPH = "https://graph.facebook.com"
NOT_CONFIGURED = "not_configured"
USAGE_HEADERS = ("x-business-use-case-usage", "x-ad-account-usage", "x-fb-ads-insights-throttle")
TOKEN_ERROR_CODES = {102, 104, 190, 463, 467}

INSIGHTS_FIELDS = ("account_id", "campaign_id", "campaign_name", "adset_id", "adset_name",
                   "ad_id", "ad_name", "spend", "impressions", "clicks", "reach", "ctr",
                   "cpc", "cpm", "actions", "action_values")
LEVELS = ("campaign", "adset", "ad")
# tujuan kampanye yang didukung UI (nilai sah pada versi API saat ini)
OBJECTIVES = ("OUTCOME_LEADS", "OUTCOME_SALES", "OUTCOME_TRAFFIC", "OUTCOME_ENGAGEMENT")
# preset tujuan iklan -> (destination_type, optimization_goal)
DESTINATIONS = {
    "whatsapp": ("WHATSAPP", "CONVERSATIONS"),
    "lead_form": ("ON_AD", "LEAD_GENERATION"),
    "website": ("WEBSITE", "LANDING_PAGE_VIEWS"),
    "website_conversion": ("WEBSITE", "OFFSITE_CONVERSIONS"),
}


def appsecret_proof(token: str, app_secret: str) -> str:
    return hmac.new((app_secret or "").encode(), (token or "").encode(), hashlib.sha256).hexdigest()


def act(account_id) -> str:
    """Edge ad-account WAJIB berprefiks 'act_'; ID objek lain TIDAK boleh diberi prefiks."""
    raw = str(account_id or "").strip()
    if not raw:
        return ""
    return raw if raw.startswith("act_") else f"act_{raw}"


def build_insights_params(since: str, until: str, *, level: str = "campaign",
                          breakdowns=None, time_increment: str = "1") -> dict:
    if level not in LEVELS:
        level = "campaign"
    params = {
        "time_range": json.dumps({"since": since, "until": until}),
        "time_increment": str(time_increment),
        "level": level,
        "fields": ",".join(INSIGHTS_FIELDS),
        "limit": "500",
    }
    if breakdowns:
        params["breakdowns"] = ",".join(breakdowns)
    return params


# --------------------------------------------------------------------- builder payload (pure)
def build_campaign_payload(name: str, objective: str, *, special_categories=None) -> dict:
    obj = objective if objective in OBJECTIVES else "OUTCOME_LEADS"
    return {"name": (name or "").strip()[:200], "objective": obj,
            "special_ad_categories": list(special_categories or []),
            "buying_type": "AUCTION"}


def build_adset_payload(name: str, campaign_id: str, *, daily_budget_minor: int,
                        destination: str = "whatsapp", page_id: str = "", pixel_id: str = "",
                        whatsapp_number: str = "", countries=None, age_min: int = 18,
                        age_max: int = 65, custom_audience_ids=None) -> dict:
    dest_type, goal = DESTINATIONS.get(destination, DESTINATIONS["website"])
    targeting = {
        "geo_locations": {"countries": list(countries or ["ID"])},
        "age_min": int(age_min), "age_max": int(age_max),
        "device_platforms": ["mobile", "desktop"],
    }
    if custom_audience_ids:
        targeting["custom_audiences"] = [{"id": str(a)} for a in custom_audience_ids]
    promoted = {}
    if dest_type == "WHATSAPP":
        promoted = {"page_id": str(page_id or "")}
        if whatsapp_number:
            promoted["whatsapp_phone_number"] = str(whatsapp_number)
    elif goal == "LEAD_GENERATION":
        promoted = {"page_id": str(page_id or "")}
    elif goal == "OFFSITE_CONVERSIONS" and pixel_id:
        promoted = {"pixel_id": str(pixel_id), "custom_event_type": "LEAD"}
    payload = {
        "name": (name or "").strip()[:200], "campaign_id": str(campaign_id),
        "daily_budget": str(int(daily_budget_minor)), "billing_event": "IMPRESSIONS",
        "optimization_goal": goal, "destination_type": dest_type, "targeting": targeting,
    }
    if promoted:
        payload["promoted_object"] = promoted
    return payload


def build_creative_payload(name: str, page_id: str, *, destination: str = "whatsapp",
                          message: str = "", headline: str = "", description: str = "",
                          link: str = "", image_hash: str = "", whatsapp_number: str = "") -> dict:
    if destination == "whatsapp":
        cta = {"type": "WHATSAPP_MESSAGE",
               "value": {"link": link or "https://api.whatsapp.com/send",
                         "app_destination": "WHATSAPP"}}
        final_link = link or (f"https://api.whatsapp.com/send?phone={whatsapp_number}"
                              if whatsapp_number else "https://api.whatsapp.com/send")
    elif destination == "lead_form":
        cta = {"type": "SIGN_UP", "value": {"link": link or ""}}
        final_link = link or ""
    else:
        cta = {"type": "LEARN_MORE", "value": {"link": link or ""}}
        final_link = link or ""
    link_data = {"link": final_link, "message": (message or "")[:2000],
                 "name": (headline or "")[:255], "description": (description or "")[:255],
                 "call_to_action": cta}
    if image_hash:
        link_data["image_hash"] = image_hash
    return {"name": (name or "").strip()[:200],
            "object_story_spec": {"page_id": str(page_id or ""), "link_data": link_data}}


def build_ad_payload(name: str, adset_id: str, creative_id: str) -> dict:
    return {"name": (name or "").strip()[:200], "adset_id": str(adset_id),
            "creative": {"creative_id": str(creative_id)}}


def build_audience_payload(name: str, description: str = "") -> dict:
    return {"name": (name or "").strip()[:200], "subtype": "CUSTOM",
            "description": (description or "")[:400],
            "customer_file_source": "USER_PROVIDED_ONLY"}


def build_lookalike_payload(name: str, origin_audience_id: str, *, ratio: float = 0.01,
                           country: str = "ID") -> dict:
    safe_ratio = min(max(float(ratio or 0.01), 0.01), 0.20)
    return {"name": (name or "").strip()[:200], "subtype": "LOOKALIKE",
            "origin_audience_id": str(origin_audience_id),
            "lookalike_spec": {"type": "similarity", "ratio": safe_ratio, "country": country}}


class MetaAdsClient:
    """Klien tipis & defensif. `cfg` = bagian publik konfigurasi, `secrets` = rahasia terdekripsi."""

    def __init__(self, cfg=None, secrets=None, *, timeout: int = 30):
        self.cfg = dict(cfg or {})
        self.secrets = dict(secrets or {})
        self.timeout = timeout
        self.version = str(self.cfg.get("api_version") or DEFAULT_VERSION)

    # ------------------------------------------------------------------ kesiapan
    @property
    def token(self) -> str:
        return (self.secrets.get("system_user_token")
                or self.secrets.get("access_token") or "").strip()

    @property
    def account(self) -> str:
        return act(self.cfg.get("ad_account_id"))

    def reason(self) -> str:
        """Alasan (Bahasa Indonesia) mengapa klien belum siap; '' bila siap."""
        if not self.cfg.get("enabled"):
            return "Integrasi Meta belum diaktifkan di Pengaturan → Integrasi."
        if not self.token:
            return "Access token Meta (System User) belum diisi di Pengaturan → Integrasi."
        if not self.account:
            return "Ad Account ID Meta (act_...) belum diisi di Pengaturan → Integrasi."
        return ""

    def configured(self) -> bool:
        return not self.reason()

    def not_ready(self) -> dict:
        return {"status": NOT_CONFIGURED, "reason": self.reason(), "provider": "meta"}

    # ------------------------------------------------------------------ transport
    async def _call(self, method: str, path: str, *, params=None, body=None) -> dict:
        if not self.configured():
            return self.not_ready()
        query = dict(params or {})
        query["access_token"] = self.token
        secret = (self.secrets.get("app_secret") or "").strip()
        if secret:
            query["appsecret_proof"] = appsecret_proof(self.token, secret)
        url = f"{GRAPH}/{self.version}{path}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.request(method, url, params=query, json=body)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Meta %s %s gagal: %s", method, path, exc)
            return {"status": "error", "provider": "meta",
                    "reason": f"Gagal menghubungi Meta ({type(exc).__name__}). Coba lagi."}
        usage = {k: v for k, v in resp.headers.items() if k.lower() in USAGE_HEADERS}
        try:
            data = resp.json()
        except Exception:  # noqa: BLE001
            data = {"raw": (resp.text or "")[:400]}
        if resp.status_code >= 400:
            err = (data or {}).get("error") or {}
            code = err.get("code")
            message = err.get("message") or f"HTTP {resp.status_code}"
            if code in TOKEN_ERROR_CODES:
                return {"status": NOT_CONFIGURED, "provider": "meta", "usage": usage,
                        "reason": "Token Meta tidak valid/kedaluwarsa — perbarui di "
                                  "Pengaturan → Integrasi.", "detail": message}
            return {"status": "error", "provider": "meta", "http": resp.status_code,
                    "reason": message, "code": code, "usage": usage,
                    "detail": (err.get("error_user_msg") or "")[:300]}
        return {"status": "ok", "provider": "meta", "data": data, "usage": usage}

    # ------------------------------------------------------------------ baca
    async def account_info(self) -> dict:
        return await self._call("GET", f"/{self.account}", params={
            "fields": "name,currency,timezone_name,account_status,amount_spent,business_name"})

    async def insights(self, since: str, until: str, *, level: str = "campaign",
                       breakdowns=None) -> dict:
        return await self._call("GET", f"/{self.account}/insights",
                                params=build_insights_params(since, until, level=level,
                                                             breakdowns=breakdowns))

    async def insights_async(self, since: str, until: str, *, level: str = "campaign",
                             poll_seconds: float = 3.0, max_polls: int = 20) -> dict:
        """Jalur ASYNC untuk rentang besar: buat job -> polling -> ambil hasil."""
        params = build_insights_params(since, until, level=level)
        params["async"] = "true"
        created = await self._call("POST", f"/{self.account}/insights", params=params)
        if created.get("status") != "ok":
            return created
        run_id = ((created.get("data") or {}).get("report_run_id") or "")
        if not run_id:
            return {"status": "error", "provider": "meta",
                    "reason": "Meta tidak mengembalikan report_run_id."}
        for _ in range(max_polls):
            state = await self._call("GET", f"/{run_id}", params={
                "fields": "async_status,async_percent_completion"})
            if state.get("status") != "ok":
                return state
            info = state.get("data") or {}
            if info.get("async_status") == "Job Completed":
                return await self._call("GET", f"/{run_id}/insights", params={"limit": "500"})
            if info.get("async_status") in ("Job Failed", "Job Skipped"):
                return {"status": "error", "provider": "meta",
                        "reason": f"Laporan Meta gagal ({info.get('async_status')})."}
            await asyncio.sleep(poll_seconds)
        return {"status": "error", "provider": "meta",
                "reason": "Laporan Meta belum selesai setelah menunggu — coba tarik lagi."}

    async def list_entities(self, level: str = "campaign", *, limit: int = 200) -> dict:
        edge = {"campaign": "campaigns", "adset": "adsets", "ad": "ads"}.get(level, "campaigns")
        fields = {
            "campaigns": "id,name,status,effective_status,objective,daily_budget,lifetime_budget,created_time",
            "adsets": "id,name,status,effective_status,campaign_id,daily_budget,optimization_goal,destination_type",
            "ads": "id,name,status,effective_status,adset_id,campaign_id,creative{id}",
        }[edge]
        return await self._call("GET", f"/{self.account}/{edge}",
                                params={"fields": fields, "limit": str(limit)})

    # ------------------------------------------------------------------ tulis (F7)
    async def create_object(self, kind: str, payload: dict, *, mode: str = "validate") -> dict:
        edge = {"campaign": "campaigns", "adset": "adsets",
                "creative": "adcreatives", "ad": "ads"}.get(kind)
        if not edge:
            return {"status": "error", "reason": f"Jenis objek Meta tidak dikenal: {kind}"}
        body = safety.meta_write_payload(payload, mode=mode, kind=kind)
        res = await self._call("POST", f"/{self.account}/{edge}", body=body)
        res["safety"] = safety.summary(mode)
        res["sent_payload"] = body
        return res

    async def update_object(self, object_id: str, fields: dict, *, mode: str = "validate") -> dict:
        body = safety.meta_write_payload(fields, mode=mode, kind="update")
        res = await self._call("POST", f"/{object_id}", body=body)
        res["safety"] = safety.summary(mode)
        res["sent_payload"] = body
        return res

    # ------------------------------------------------------------------ audiens (F6)
    async def create_audience(self, name: str, description: str = "", *,
                              mode: str = "validate") -> dict:
        return await self.create_audience_raw(build_audience_payload(name, description), mode=mode)

    async def create_audience_raw(self, payload: dict, *, mode: str = "validate") -> dict:
        if safety.is_dry_run(mode):
            return {"status": "dry_run", "provider": "meta", "sent_payload": payload,
                    "safety": safety.summary(mode)}
        return await self._call("POST", f"/{self.account}/customaudiences", body=payload)

    async def upload_audience_users(self, audience_id: str, payload: dict, *,
                                    replace: bool = False, mode: str = "validate") -> dict:
        if safety.is_dry_run(mode):
            return {"status": "dry_run", "provider": "meta", "sent_payload": payload,
                    "safety": safety.summary(mode)}
        edge = "usersreplace" if replace else "users"
        return await self._call("POST", f"/{audience_id}/{edge}", body=payload)

    # ------------------------------------------------------------------ Lead Ads (F5)
    async def fetch_lead(self, leadgen_id: str, *, page_token: str = "") -> dict:
        token = (page_token or self.secrets.get("page_access_token") or "").strip()
        if not token:
            return {"status": NOT_CONFIGURED,
                    "reason": "Page Access Token belum diisi — tidak bisa membaca isi Lead Ads."}
        url = f"{GRAPH}/{self.version}/{leadgen_id}"
        params = {"access_token": token,
                  "fields": "id,created_time,ad_id,adset_id,campaign_id,form_id,field_data"}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(url, params=params)
            data = resp.json()
        except Exception as exc:  # noqa: BLE001
            return {"status": "error", "reason": f"Gagal mengambil lead dari Meta ({type(exc).__name__})."}
        if resp.status_code >= 400:
            return {"status": "error", "http": resp.status_code,
                    "reason": ((data or {}).get("error") or {}).get("message") or "Gagal ambil lead"}
        return {"status": "ok", "data": data}

    async def list_form_leads(self, form_id: str, *, page_token: str = "", limit: int = 100) -> dict:
        token = (page_token or self.secrets.get("page_access_token") or "").strip()
        if not token:
            return {"status": NOT_CONFIGURED,
                    "reason": "Page Access Token belum diisi — backfill Lead Ads tidak bisa dijalankan."}
        url = f"{GRAPH}/{self.version}/{form_id}/leads"
        params = {"access_token": token, "limit": str(limit),
                  "fields": "id,created_time,ad_id,adset_id,campaign_id,form_id,field_data"}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(url, params=params)
            data = resp.json()
        except Exception as exc:  # noqa: BLE001
            return {"status": "error", "reason": f"Gagal backfill Lead Ads ({type(exc).__name__})."}
        if resp.status_code >= 400:
            return {"status": "error", "http": resp.status_code,
                    "reason": ((data or {}).get("error") or {}).get("message") or "Gagal backfill"}
        return {"status": "ok", "data": data}
