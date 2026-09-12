"""services/google_ads.py — klien Google Ads API v25 (REST/GAQL) + Data Manager API v1.

Mengapa REST langsung (bukan SDK google-ads): kita hanya butuh beberapa endpoint, butuh async
httpx, dan butuh kontrol penuh atas dry-run + redaksi log. SDK menambah dependensi besar.

Cakupan:
  * OAuth       : refresh_token -> access_token (scope adwords + datamanager).
  * Laporan     : GAQL `googleAds:searchStream` (campaign & ad_group harian, metadata customer).
  * Tulis (F7)  : campaignBudgets/campaigns/adGroups/adGroupAds/adGroupCriteria `:mutate`
                  dengan `validateOnly` + `partialFailure` (SELALU via ads_safety).
  * Audiens(F6) : userLists:mutate + offlineUserDataJobs (Customer Match).
  * Geo         : geoTargetConstants:suggest (JANGAN hardcode criterion id).

Aturan keras: tanpa kredensial -> `not_configured` + alasan Bahasa Indonesia; error Google
dipetakan ke bentuk stabil `{status:'google_error', code, message, request_id}` (bukan 5xx).
Biaya datang sebagai `cost_micros` (1/1.000.000 mata uang AKUN) — mata uang bisa non-IDR.
"""
import logging

import httpx

from services import ads_safety as safety
from services.pii import digits_only

logger = logging.getLogger("travel_fleet.google_ads")

DEFAULT_VERSION = "v25"
ADS_BASE = "https://googleads.googleapis.com"
DATA_MANAGER_URL = "https://datamanager.googleapis.com/v1/events:ingest"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPES = ("https://www.googleapis.com/auth/adwords",
          "https://www.googleapis.com/auth/datamanager")
NOT_CONFIGURED = "not_configured"

METRIC_FIELDS = ("metrics.cost_micros", "metrics.impressions", "metrics.clicks",
                 "metrics.conversions", "metrics.conversions_value")


def gaql_customer_meta() -> str:
    return ("SELECT customer.id, customer.descriptive_name, customer.currency_code, "
            "customer.time_zone FROM customer LIMIT 1")


def gaql_campaign_list() -> str:
    """Daftar kampanye + budget (untuk builder & tombol jeda/ubah budget)."""
    return ("SELECT campaign.id, campaign.name, campaign.status, campaign.resource_name, "
            "campaign.advertising_channel_type, campaign_budget.resource_name, "
            "campaign_budget.amount_micros FROM campaign ORDER BY campaign.id")


def gaql_daily(since: str, until: str, *, level: str = "campaign") -> str:
    metrics = ", ".join(METRIC_FIELDS)
    if level == "ad_group":
        return (f"SELECT campaign.id, campaign.name, ad_group.id, ad_group.name, ad_group.status, "
                f"{metrics}, segments.date FROM ad_group "
                f"WHERE segments.date BETWEEN '{since}' AND '{until}' "
                f"ORDER BY segments.date")
    return (f"SELECT campaign.id, campaign.name, campaign.status, "
            f"campaign.advertising_channel_type, {metrics}, segments.date FROM campaign "
            f"WHERE segments.date BETWEEN '{since}' AND '{until}' "
            f"ORDER BY segments.date")


# --------------------------------------------------------------------- builder operasi (pure)
def build_budget_op(name: str, amount_micros: int) -> dict:
    return {"create": {"name": (name or "")[:200], "deliveryMethod": "STANDARD",
                       "amountMicros": str(int(amount_micros))}}


def build_campaign_op(name: str, budget_resource: str, *,
                      channel_type: str = "SEARCH") -> dict:
    return {"create": {
        "name": (name or "")[:200], "status": safety.PAUSED,
        "advertisingChannelType": channel_type, "campaignBudget": budget_resource,
        "manualCpc": {},
        "networkSettings": {"targetGoogleSearch": True, "targetSearchNetwork": True,
                            "targetContentNetwork": False, "targetPartnerSearchNetwork": False},
        "geoTargetTypeSetting": {"positiveGeoTargetType": "PRESENCE_OR_INTEREST",
                                 "negativeGeoTargetType": "PRESENCE_OR_INTEREST"},
    }}


def build_adgroup_op(name: str, campaign_resource: str, *, cpc_bid_micros: int = 0) -> dict:
    create = {"campaign": campaign_resource, "name": (name or "")[:200],
              "status": safety.PAUSED, "type": "SEARCH_STANDARD"}
    if cpc_bid_micros:
        create["cpcBidMicros"] = str(int(cpc_bid_micros))
    return {"create": create}


def build_rsa_op(adgroup_resource: str, final_url: str, headlines, descriptions,
                 *, path1: str = "", path2: str = "") -> dict:
    rsa = {"headlines": [{"text": str(h)[:30]} for h in (headlines or [])[:15]],
           "descriptions": [{"text": str(d)[:90]} for d in (descriptions or [])[:4]]}
    if path1:
        rsa["path1"] = str(path1)[:15]
    if path2:
        rsa["path2"] = str(path2)[:15]
    return {"create": {"adGroup": adgroup_resource, "status": safety.PAUSED,
                       "ad": {"finalUrls": [final_url], "responsiveSearchAd": rsa}}}


def build_keyword_ops(adgroup_resource: str, keywords, *, match_type: str = "PHRASE"):
    mt = match_type if match_type in ("EXACT", "PHRASE", "BROAD") else "PHRASE"
    return [{"create": {"adGroup": adgroup_resource, "status": "ENABLED",
                        "keyword": {"text": str(k)[:80], "matchType": mt}}}
            for k in (keywords or []) if str(k).strip()]


def build_status_update_op(resource_name: str, status: str) -> dict:
    return {"update": {"resourceName": resource_name, "status": status},
            "updateMask": "status"}


def build_budget_update_op(resource_name: str, amount_micros: int) -> dict:
    return {"update": {"resourceName": resource_name, "amountMicros": str(int(amount_micros))},
            "updateMask": "amountMicros"}


def build_user_list_op(name: str, description: str = "") -> dict:
    return {"create": {"name": (name or "")[:200], "description": (description or "")[:400],
                       "membershipLifeSpan": "540",
                       "crmBasedUserList": {"uploadKeyType": "CONTACT_INFO",
                                            "dataSourceType": "FIRST_PARTY"}}}


def build_offline_job_spec(user_list_resource: str, *, consent_granted: bool = True) -> dict:
    grant = "GRANTED" if consent_granted else "DENIED"
    return {"job": {"type": "CUSTOMER_MATCH_USER_LIST",
                    "customerMatchUserListMetadata": {
                        "userList": user_list_resource,
                        "consent": {"adUserData": grant, "adPersonalization": grant}}}}


class GoogleAdsClient:
    """Klien Google Ads/Data Manager. Tidak pernah melempar; selalu mengembalikan dict status."""

    def __init__(self, cfg=None, secrets=None, *, timeout: int = 40):
        self.cfg = dict(cfg or {})
        self.secrets = dict(secrets or {})
        self.timeout = timeout
        self.version = str(self.cfg.get("api_version") or DEFAULT_VERSION)
        self._token = ""

    @property
    def customer_id(self) -> str:
        return digits_only(self.cfg.get("customer_id"))

    @property
    def login_customer_id(self) -> str:
        return digits_only(self.cfg.get("login_customer_id"))

    def reason(self, *, need_developer_token: bool = True) -> str:
        if not self.cfg.get("enabled"):
            return "Integrasi Google belum diaktifkan di Pengaturan → Integrasi."
        if not self.customer_id:
            return "Customer ID Google Ads belum diisi di Pengaturan → Integrasi."
        if not self.secrets.get("oauth_refresh_token"):
            return "Refresh token OAuth Google belum diisi di Pengaturan → Integrasi."
        if not (self.secrets.get("oauth_client_id") and self.secrets.get("oauth_client_secret")):
            return "OAuth client id/secret Google belum diisi di Pengaturan → Integrasi."
        if need_developer_token and not self.secrets.get("developer_token"):
            return ("Developer token Google Ads belum diisi — dibutuhkan untuk membaca metrik & "
                    "mengelola kampanye (Data Manager tidak membutuhkannya).")
        return ""

    def configured(self, *, need_developer_token: bool = True) -> bool:
        return not self.reason(need_developer_token=need_developer_token)

    def not_ready(self, *, need_developer_token: bool = True) -> dict:
        return {"status": NOT_CONFIGURED, "provider": "google",
                "reason": self.reason(need_developer_token=need_developer_token)}

    async def access_token(self) -> str:
        """Tukar refresh token -> access token (di-cache per instance)."""
        if self._token:
            return self._token
        if not self.secrets.get("oauth_refresh_token"):
            return ""
        data = {"grant_type": "refresh_token",
                "client_id": self.secrets.get("oauth_client_id", ""),
                "client_secret": self.secrets.get("oauth_client_secret", ""),
                "refresh_token": self.secrets.get("oauth_refresh_token", "")}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(TOKEN_URL, data=data)
            if resp.status_code != 200:
                logger.warning("Tukar refresh token Google gagal: HTTP %s", resp.status_code)
                return ""
            self._token = (resp.json() or {}).get("access_token", "")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Tukar refresh token Google error: %s", exc)
            return ""
        return self._token

    def _headers(self, token: str, *, data_manager: bool = False) -> dict:
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        if data_manager:
            return headers
        headers["developer-token"] = self.secrets.get("developer_token", "")
        if self.login_customer_id:
            headers["login-customer-id"] = self.login_customer_id
        return headers

    async def _post(self, url: str, body: dict, *, data_manager: bool = False) -> dict:
        need_dev = not data_manager
        if not self.configured(need_developer_token=need_dev):
            return self.not_ready(need_developer_token=need_dev)
        token = await self.access_token()
        if not token:
            return {"status": NOT_CONFIGURED, "provider": "google",
                    "reason": "Refresh token ditolak Google — periksa client id/secret & "
                              "refresh token di Pengaturan → Integrasi."}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(url, headers=self._headers(token, data_manager=data_manager),
                                         json=body)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Google POST %s gagal: %s", url.split("/")[-1], exc)
            return {"status": "error", "provider": "google",
                    "reason": f"Gagal menghubungi Google ({type(exc).__name__}). Coba lagi."}
        try:
            data = resp.json()
        except Exception:  # noqa: BLE001
            data = {"raw": (resp.text or "")[:400]}
        if resp.status_code >= 400:
            return {"status": "google_error", "provider": "google", "http": resp.status_code,
                    "reason": _google_message(data), "request_id": _google_request_id(data),
                    "errors": _google_errors(data)}
        return {"status": "ok", "provider": "google", "data": data}

    # ------------------------------------------------------------------ baca
    async def search_stream(self, query: str) -> dict:
        url = f"{ADS_BASE}/{self.version}/customers/{self.customer_id}/googleAds:searchStream"
        res = await self._post(url, {"query": query})
        if res.get("status") != "ok":
            return res
        payload = res.get("data")
        rows = []
        batches = payload if isinstance(payload, list) else [payload]
        for batch in batches:
            rows.extend((batch or {}).get("results", []) or [])
        return {"status": "ok", "provider": "google", "rows": rows}

    async def customer_meta(self) -> dict:
        return await self.search_stream(gaql_customer_meta())

    async def daily_metrics(self, since: str, until: str, *, level: str = "campaign") -> dict:
        return await self.search_stream(gaql_daily(since, until, level=level))

    # ------------------------------------------------------------------ tulis (F7)
    async def mutate(self, resource: str, operations, *, mode: str = "validate",
                     kind: str = "") -> dict:
        ops = safety.google_force_paused(operations, kind=kind) if kind else list(operations or [])
        body = safety.google_write_body({"operations": ops}, mode=mode)
        url = f"{ADS_BASE}/{self.version}/customers/{self.customer_id}/{resource}:mutate"
        res = await self._post(url, body)
        res["safety"] = safety.summary(mode)
        res["sent_payload"] = body
        return res

    async def suggest_geo(self, names, *, locale: str = "id", country: str = "ID") -> dict:
        url = f"{ADS_BASE}/{self.version}/geoTargetConstants:suggest"
        return await self._post(url, {"locale": locale, "countryCode": country,
                                     "locationNames": {"names": list(names or ["Indonesia"])}})

    # ------------------------------------------------------------------ audiens (F6)
    async def create_user_list(self, name: str, description: str = "", *,
                               mode: str = "validate") -> dict:
        return await self.mutate("userLists", [build_user_list_op(name, description)], mode=mode)

    async def create_offline_job(self, user_list_resource: str, *, consent_granted: bool = True,
                                 mode: str = "validate") -> dict:
        body = build_offline_job_spec(user_list_resource, consent_granted=consent_granted)
        body["validateOnly"] = safety.is_dry_run(mode)
        url = (f"{ADS_BASE}/{self.version}/customers/{self.customer_id}"
               f"/offlineUserDataJobs:create")
        res = await self._post(url, body)
        res["safety"] = safety.summary(mode)
        res["sent_payload"] = body
        return res

    async def add_offline_operations(self, job_resource: str, operations, *,
                                     mode: str = "validate") -> dict:
        body = {"operations": list(operations or []), "enablePartialFailure": True,
                "validateOnly": safety.is_dry_run(mode)}
        url = f"{ADS_BASE}/{self.version}/{job_resource}:addOperations"
        res = await self._post(url, body)
        res["sent_payload"] = body
        return res

    async def run_offline_job(self, job_resource: str, *, mode: str = "validate") -> dict:
        if safety.is_dry_run(mode):
            return {"status": "dry_run", "provider": "google",
                    "safety": safety.summary(mode),
                    "reason": "Mode validasi — job Customer Match tidak dijalankan."}
        return await self._post(f"{ADS_BASE}/{self.version}/{job_resource}:run", {})

    # ------------------------------------------------------------------ Data Manager
    async def ingest_events(self, payload: dict) -> dict:
        """Data Manager TIDAK butuh developer token (playbook resmi)."""
        return await self._post(DATA_MANAGER_URL, payload, data_manager=True)


def _google_failure(data):
    for detail in ((data or {}).get("error") or {}).get("details") or []:
        if "GoogleAdsFailure" in str(detail.get("@type", "")):
            return detail
    return {}


def _google_message(data) -> str:
    failure = _google_failure(data)
    errors = failure.get("errors") or []
    if errors:
        first = errors[0]
        code = first.get("errorCode") or {}
        label = ", ".join(f"{k}={v}" for k, v in code.items()) or "error"
        return f"{first.get('message') or 'Permintaan ditolak Google'} ({label})"
    return ((data or {}).get("error") or {}).get("message") or "Permintaan ditolak Google"


def _google_request_id(data) -> str:
    return _google_failure(data).get("requestId") or ""


def _google_errors(data):
    out = []
    for err in (_google_failure(data).get("errors") or [])[:5]:
        out.append({"message": err.get("message"), "code": err.get("errorCode"),
                    "location": err.get("location")})
    return out
