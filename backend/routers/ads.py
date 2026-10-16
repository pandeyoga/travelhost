"""routers/ads.py — Dashboard Iklan (BACA) + sinkron metrik dari Meta Ads & Google Ads.

Nilai bisnis halaman ini: menyandingkan **biaya iklan dari platform** dengan **booking &
pembayaran NYATA dari ERP** pada level yang sama (kampanye → adset → iklan), sehingga terlihat
iklan mana yang benar-benar untung — bukan hanya yang ramai klik.

RBAC: `require_section("ads")` (owner, ops_admin, marketing_admin) untuk BACA;
sinkron/mutasi butuh `owner` atau `marketing_admin` (ops_admin read-only).

Tanpa kredensial: semua endpoint tetap 200 dengan status `not_configured` + alasan Bahasa
Indonesia, dan dashboard otomatis memakai **input biaya manual** (`settings.marketing_spend`)
sebagai sumber cadangan — jadi halaman tetap berguna sejak hari pertama.
"""
from fastapi import APIRouter, Body, Depends, Query

from core_utils import now_iso, safe_doc
from db import get_db
from dependencies import require_role, require_section
from services import ads_metrics as am
from services import analytics
from services import integrations as integ
from services.audit import record
from services.google_ads import gaql_campaign_list

router = APIRouter(prefix="/api", tags=["ads"])
READ = require_section("ads")
WRITE = require_role("owner", "marketing_admin")
META_LEVELS = ("campaign", "adset", "ad")


def _dates(days, since, until):
    rng = analytics.parse_range(days=days, start=since, end=until)
    return rng, str(rng["start"])[:10], str(rng["end"])[:10]


@router.get("/ads/overview")
async def ads_overview(days: int = Query(default=30), since: str = Query(default=None),
                       until: str = Query(default=None), level: str = Query(default="campaign"),
                       provider: str = Query(default=None), user=Depends(READ)):
    """Ringkasan lengkap untuk halaman Dashboard Iklan (satu panggilan, hemat round-trip)."""
    db = get_db()
    rng, start, end = _dates(days, since, until)
    prov = provider if provider in ("meta", "google") else None
    perf = await am.performance(db, start, end, provider=prov, level=level)
    spend = await analytics.get_marketing_spend(db)
    accounts = await db[am.COLL_ACCOUNTS].find({}, {"_id": 0}).to_list(10)
    state = await db.settings.find_one({"key": "ads_sync_state"}, {"_id": 0}) or {}
    return {
        "range": {"since": start, "until": end, "days": rng.get("days") or days},
        "readiness": await integ.ads_readiness(db),
        "accounts": safe_doc(accounts),
        "performance": perf,
        "series": await am.daily_series(db, start, end, provider=prov),
        "runs": safe_doc(await am.last_runs(db, 8)),
        "channels": await analytics.channels_roi(db, rng, spend_map=spend["spend_map"]),
        "manual_spend": spend,
        "sync_state": state.get("value") or {},
        "can_manage": user.get("role") in ("owner", "marketing_admin"),
    }


@router.get("/ads/entities")
async def ads_entities(provider: str = Query(default=None), level: str = Query(default=None),
                       limit: int = Query(default=200, le=500), user=Depends(READ)):
    """Daftar kampanye/adset/iklan hasil sinkron (dipakai builder & filter dashboard)."""
    query = {}
    if provider in ("meta", "google"):
        query["provider"] = provider
    if level in ("campaign", "adset", "ad"):
        query["level"] = level
    rows = await get_db()[am.COLL_ENTITIES].find(query, {"_id": 0}) \
        .sort("updated_at", -1).to_list(limit)
    return {"entities": safe_doc(rows), "total": len(rows)}


@router.get("/ads/accounts")
async def ads_accounts(user=Depends(READ)):
    db = get_db()
    rows = await db[am.COLL_ACCOUNTS].find({}, {"_id": 0}).to_list(10)
    return {"accounts": safe_doc(rows), "readiness": await integ.ads_readiness(db)}


async def _sync_meta(db, client, start, end):
    """Tarik metadata akun + insights 3 level Meta. Selalu mengembalikan laporan (tanpa raise)."""
    report = {"provider": "meta", "status": "ok", "rows": 0, "currency": "", "levels": {},
              "reason": ""}
    info = await client.account_info()
    if info.get("status") != "ok":
        report.update({"status": info.get("status"), "reason": info.get("reason", "")})
        await am.record_run(db, "meta", since=start, until=end, level="account",
                            status=report["status"], reason=report["reason"])
        return report
    data = info.get("data") or {}
    account = await am.save_account(db, "meta", {
        "account_id": client.account, "name": data.get("name"),
        "currency": data.get("currency"), "timezone": data.get("timezone_name"),
        "status": str(data.get("account_status", ""))})
    report["currency"] = account["currency"]
    for level in META_LEVELS:
        res = await client.insights(start, end, level=level)
        if res.get("status") != "ok":
            report["levels"][level] = {"status": res.get("status"), "reason": res.get("reason", "")}
            await am.record_run(db, "meta", since=start, until=end, level=level,
                                status=res.get("status", "error"), reason=res.get("reason", ""))
            continue
        rows = (res.get("data") or {}).get("data") or []
        docs = am.normalize_meta_rows(rows, level=level, currency=account["currency"])
        stats = await am.upsert_metrics(db, docs)
        report["rows"] += len(docs)
        report["levels"][level] = {"status": "ok", "rows": len(docs), **stats}
        await am.record_run(db, "meta", since=start, until=end, level=level, status="ok",
                            rows=len(docs), usage=res.get("usage"))
        ents = await client.list_entities(level)
        if ents.get("status") == "ok":
            await am.upsert_entities(db, [{
                "provider": "meta", "level": level, "entity_id": str(e.get("id")),
                "name": e.get("name") or "", "status": e.get("status") or "",
                "effective_status": e.get("effective_status") or "",
                "objective": e.get("objective") or "",
                "parent_id": str(e.get("campaign_id") or e.get("adset_id") or ""),
                "daily_budget": e.get("daily_budget") or "",
                "currency": account["currency"],
            } for e in ((ents.get("data") or {}).get("data") or []) if e.get("id")])
    return report


async def _sync_google(db, client, start, end):
    report = {"provider": "google", "status": "ok", "rows": 0, "currency": "", "levels": {},
              "reason": ""}
    meta = await client.customer_meta()
    if meta.get("status") != "ok":
        report.update({"status": meta.get("status"), "reason": meta.get("reason", "")})
        await am.record_run(db, "google", since=start, until=end, level="account",
                            status=report["status"], reason=report["reason"])
        return report
    row = ((meta.get("rows") or [{}])[0] or {}).get("customer") or {}
    account = await am.save_account(db, "google", {
        "account_id": client.customer_id, "name": row.get("descriptiveName"),
        "currency": row.get("currencyCode"), "timezone": row.get("timeZone"), "status": ""})
    report["currency"] = account["currency"]
    for level in ("campaign", "ad_group"):
        res = await client.daily_metrics(start, end, level=level)
        if res.get("status") != "ok":
            report["levels"][level] = {"status": res.get("status"), "reason": res.get("reason", "")}
            await am.record_run(db, "google", since=start, until=end, level=level,
                                status=res.get("status", "error"), reason=res.get("reason", ""))
            continue
        docs = am.normalize_google_rows(res.get("rows") or [], level=level,
                                        currency=account["currency"])
        stats = await am.upsert_metrics(db, docs)
        report["rows"] += len(docs)
        report["levels"][level] = {"status": "ok", "rows": len(docs), **stats}
        await am.record_run(db, "google", since=start, until=end, level=level, status="ok",
                            rows=len(docs))
    listing = await client.search_stream(gaql_campaign_list())
    if listing.get("status") == "ok":
        await am.upsert_entities(db, [{
            "provider": "google", "level": "campaign",
            "entity_id": str((r.get("campaign") or {}).get("id") or ""),
            "name": (r.get("campaign") or {}).get("name") or "",
            "status": (r.get("campaign") or {}).get("status") or "",
            "effective_status": (r.get("campaign") or {}).get("status") or "",
            "objective": (r.get("campaign") or {}).get("advertisingChannelType") or "",
            "parent_id": "",
            "resource_name": (r.get("campaign") or {}).get("resourceName") or "",
            "budget_resource": (r.get("campaignBudget") or {}).get("resourceName") or "",
            "daily_budget": (r.get("campaignBudget") or {}).get("amountMicros") or "",
            "currency": account["currency"],
        } for r in (listing.get("rows") or []) if (r.get("campaign") or {}).get("id")])
    return report


@router.post("/ads/sync")
async def ads_sync(body: dict = Body(default={}), user=Depends(WRITE)):
    """Tarik biaya & metrik dari platform untuk rentang tertentu. Idempoten (tarik ulang aman)."""
    db = get_db()
    payload = body or {}
    _, start, end = _dates(payload.get("days") or 30, payload.get("since"), payload.get("until"))
    meta_client, google_client, _ = await integ.clients(db)
    want = payload.get("providers") or ["meta", "google"]
    reports = {}
    if "meta" in want:
        reports["meta"] = await _sync_meta(db, meta_client, start, end)
    if "google" in want:
        reports["google"] = await _sync_google(db, google_client, start, end)
    total = sum(int(r.get("rows") or 0) for r in reports.values())
    await record(db, actor=user, action="sync", entity_type="ads", entity_id=f"{start}..{end}",
                 summary=f"Tarik metrik iklan {start} s/d {end} — {total} baris")
    await db.settings.update_one({"key": "ads_sync_state"}, {"$set": {
        "key": "ads_sync_state",
        "value": {"last_run_at": now_iso(), "since": start, "until": end, "rows": total}}},
        upsert=True)
    return {"range": {"since": start, "until": end}, "reports": reports, "rows": total}


@router.put("/ads/manual-spend")
async def ads_manual_spend(body: dict = Body(default={}), user=Depends(WRITE)):
    """Input biaya iklan MANUAL per channel — sumber cadangan saat API platform belum aktif."""
    db = get_db()
    items = (body or {}).get("items") or []
    out = await analytics.set_marketing_spend(db, items, note=(body or {}).get("note") or "")
    await record(db, actor=user, action="update", entity_type="settings",
                 entity_id="marketing_spend",
                 summary=f"Ubah biaya iklan manual ({len(items)} channel)")
    return out
