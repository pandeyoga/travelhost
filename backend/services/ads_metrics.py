"""services/ads_metrics.py — normalisasi & penyimpanan metrik iklan + penggabungan ROAS NYATA.

Mengapa modul ini ada: platform (Meta/Google) hanya tahu biaya & klik; ERP yang tahu booking
dikonfirmasi dan DP masuk. Nilai bisnis muncul saat KEDUANYA disandingkan pada level yang sama
(kampanye → adset → iklan). Modul ini:

  1. `normalize_meta_rows` / `normalize_google_rows` — mengubah bentuk mentah tiap platform ke
     SATU skema (`ads_metrics_daily`). Nilai uang disimpan MENTAH sebagai micros + kode mata uang
     akun (akun iklan bisa USD/SGD — JANGAN asumsi IDR, jangan konversi diam-diam).
  2. `upsert_metrics` — idempoten via unique (provider, level, entity_id, date): menarik ulang
     rentang yang sama TIDAK menggandakan biaya (kesalahan klasik pelaporan iklan).
  3. `performance` — menggabungkan metrik platform dengan lead ber-atribusi, booking terkonfirmasi,
     dan pembayaran nyata dari ERP → CPL, CAC, ROAS, dan rasio lead→booking per entitas.
"""
import logging
from datetime import datetime, timedelta, timezone

from core_utils import money, new_id, now_iso

logger = logging.getLogger("travel_fleet.ads_metrics")

COLL_ACCOUNTS = "ads_accounts"
COLL_ENTITIES = "ads_entities"
COLL_METRICS = "ads_metrics_daily"
COLL_RUNS = "ads_sync_runs"
COLL_TOUCH = "ad_touches"

LEVELS = ("campaign", "adset", "ad")
# level ERP -> field atribusi pada dokumen lead
LEVEL_FIELD = {"campaign": "ad_campaign_id", "adset": "ad_adset_id", "ad": "ad_id"}
# aksi Meta yang dianggap konversi bisnis (nama aksi resmi Meta)
META_LEAD_ACTIONS = ("lead", "onsite_conversion.lead_grouped", "offsite_conversion.fb_pixel_lead")
META_PURCHASE_ACTIONS = ("purchase", "offsite_conversion.fb_pixel_purchase")
BOOKING_REVENUE_STATUS = ("confirmed", "ongoing", "completed")


async def ensure_indexes(db):
    await db[COLL_METRICS].create_index(
        [("provider", 1), ("level", 1), ("entity_id", 1), ("date", 1)],
        unique=True, name="uniq_metric_day")
    await db[COLL_METRICS].create_index([("date", -1)], name="metric_recent")
    await db[COLL_ENTITIES].create_index([("provider", 1), ("level", 1), ("entity_id", 1)],
                                         unique=True, name="uniq_entity")
    await db[COLL_ACCOUNTS].create_index([("provider", 1), ("account_id", 1)],
                                         unique=True, name="uniq_account")
    await db[COLL_RUNS].create_index([("created_at", -1)], name="run_recent")
    await db[COLL_TOUCH].create_index([("click_id", 1)], unique=True, sparse=True,
                                      name="uniq_click")
    await db[COLL_TOUCH].create_index([("created_at", -1)], name="touch_recent")


def _num(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _int(value, default=0):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def next_day(date_str: str) -> str:
    """'2026-08-10' -> '2026-08-11' (batas atas eksklusif untuk filter timestamp ISO)."""
    try:
        d = datetime.strptime(str(date_str)[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        return (d + timedelta(days=1)).strftime("%Y-%m-%d")
    except Exception:  # noqa: BLE001
        return str(date_str)


def _actions_map(rows):
    out = {}
    for item in rows or []:
        key = str(item.get("action_type") or "")
        if key:
            out[key] = _num(item.get("value"))
    return out


def _sum_actions(actions: dict, wanted) -> float:
    return sum(v for k, v in (actions or {}).items() if k in wanted)


def normalize_meta_rows(rows, *, level: str = "campaign", currency: str = "") -> list:
    """Baris `/insights` Meta -> dokumen `ads_metrics_daily`."""
    level = level if level in LEVELS else "campaign"
    id_field = {"campaign": "campaign_id", "adset": "adset_id", "ad": "ad_id"}[level]
    name_field = {"campaign": "campaign_name", "adset": "adset_name", "ad": "ad_name"}[level]
    parent_field = {"campaign": "", "adset": "campaign_id", "ad": "adset_id"}[level]
    out = []
    for row in rows or []:
        entity_id = str(row.get(id_field) or "").strip()
        if not entity_id:
            continue
        actions = _actions_map(row.get("actions"))
        values = _actions_map(row.get("action_values"))
        spend = _num(row.get("spend"))
        out.append({
            "provider": "meta", "level": level, "entity_id": entity_id,
            "entity_name": str(row.get(name_field) or "")[:200],
            "parent_id": str(row.get(parent_field) or "") if parent_field else "",
            "date": str(row.get("date_start") or "")[:10],
            "currency": (currency or "").upper(),
            "spend": round(spend, 2), "spend_micros": int(round(spend * 1_000_000)),
            "impressions": _int(row.get("impressions")), "clicks": _int(row.get("clicks")),
            "reach": _int(row.get("reach")),
            "platform_leads": _sum_actions(actions, META_LEAD_ACTIONS),
            "platform_purchases": _sum_actions(actions, META_PURCHASE_ACTIONS),
            "platform_conversion_value": _sum_actions(values, META_PURCHASE_ACTIONS),
            "actions": actions,
        })
    return [d for d in out if d["date"]]


def normalize_google_rows(rows, *, level: str = "campaign", currency: str = "") -> list:
    """Baris GAQL (REST camelCase) -> dokumen `ads_metrics_daily`. `cost_micros` sudah micros."""
    out = []
    erp_level = "adset" if level in ("ad_group", "adset") else "campaign"
    for row in rows or []:
        campaign = row.get("campaign") or {}
        group = row.get("adGroup") or row.get("ad_group") or {}
        metrics = row.get("metrics") or {}
        segments = row.get("segments") or {}
        if erp_level == "adset":
            entity_id, entity_name = str(group.get("id") or ""), str(group.get("name") or "")
            parent_id = str(campaign.get("id") or "")
        else:
            entity_id, entity_name = str(campaign.get("id") or ""), str(campaign.get("name") or "")
            parent_id = ""
        if not entity_id:
            continue
        cost_micros = _int(metrics.get("costMicros") or metrics.get("cost_micros"))
        out.append({
            "provider": "google", "level": erp_level, "entity_id": entity_id,
            "entity_name": entity_name[:200], "parent_id": parent_id,
            "date": str(segments.get("date") or "")[:10],
            "currency": (currency or "").upper(),
            "spend": round(cost_micros / 1_000_000, 2), "spend_micros": cost_micros,
            "impressions": _int(metrics.get("impressions")),
            "clicks": _int(metrics.get("clicks")), "reach": 0,
            "platform_leads": _num(metrics.get("conversions")),
            "platform_purchases": 0.0,
            "platform_conversion_value": _num(metrics.get("conversionsValue")
                                              or metrics.get("conversions_value")),
            "actions": {},
        })
    return [d for d in out if d["date"]]


async def upsert_metrics(db, docs) -> dict:
    """Idempoten: kunci (provider, level, entity_id, date). Tarik ulang = timpa, bukan tambah."""
    stats = {"upserted": 0, "modified": 0}
    for doc in docs or []:
        key = {"provider": doc["provider"], "level": doc["level"],
               "entity_id": doc["entity_id"], "date": doc["date"]}
        res = await db[COLL_METRICS].update_one(
            key, {"$set": {**doc, "updated_at": now_iso()},
                  "$setOnInsert": {"id": new_id("adm"), "created_at": now_iso()}}, upsert=True)
        if res.upserted_id is not None:
            stats["upserted"] += 1
        elif res.modified_count:
            stats["modified"] += 1
    return stats


async def upsert_entities(db, docs) -> int:
    count = 0
    for doc in docs or []:
        key = {"provider": doc["provider"], "level": doc["level"], "entity_id": doc["entity_id"]}
        await db[COLL_ENTITIES].update_one(
            key, {"$set": {**doc, "updated_at": now_iso()},
                  "$setOnInsert": {"id": new_id("ade"), "created_at": now_iso()}}, upsert=True)
        count += 1
    return count


async def save_account(db, provider: str, info: dict) -> dict:
    doc = {"provider": provider, "account_id": str(info.get("account_id") or ""),
           "name": info.get("name") or "", "currency": (info.get("currency") or "").upper(),
           "timezone": info.get("timezone") or "", "status": info.get("status") or "",
           "synced_at": now_iso()}
    await db[COLL_ACCOUNTS].update_one(
        {"provider": provider, "account_id": doc["account_id"]},
        {"$set": doc, "$setOnInsert": {"id": new_id("adacc")}}, upsert=True)
    return doc


async def account_currency(db, provider: str) -> str:
    doc = await db[COLL_ACCOUNTS].find_one({"provider": provider}, {"_id": 0},
                                          sort=[("synced_at", -1)])
    return (doc or {}).get("currency") or ""


async def record_run(db, provider: str, *, since: str, until: str, level: str,
                     status: str, rows: int = 0, reason: str = "", usage=None) -> dict:
    doc = {"id": new_id("adr"), "provider": provider, "since": since, "until": until,
           "level": level, "status": status, "rows": int(rows), "reason": reason or "",
           "usage": usage or {}, "created_at": now_iso()}
    await db[COLL_RUNS].insert_one(dict(doc))
    return doc


async def last_runs(db, limit: int = 10) -> list:
    return await db[COLL_RUNS].find({}, {"_id": 0}).sort("created_at", -1).to_list(limit)


async def record_touch(db, touch: dict):
    """Simpan klik iklan teridentifikasi (gclid/fbclid/ctwa_clid) -> dipakai atribusi ad-level."""
    click_id = str(touch.get("click_id") or "").strip()
    if not click_id:
        return None
    doc = {"id": new_id("adt"), "created_at": now_iso(), **touch, "click_id": click_id}
    await db[COLL_TOUCH].update_one({"click_id": click_id},
                                    {"$set": {k: v for k, v in doc.items() if k != "id"},
                                     "$setOnInsert": {"id": doc["id"]}}, upsert=True)
    return doc


async def _metrics_by_entity(db, since, until, *, provider=None, level="campaign"):
    match = {"level": level, "date": {"$gte": since[:10], "$lte": until[:10]}}
    if provider:
        match["provider"] = provider
    rows = await db[COLL_METRICS].aggregate([
        {"$match": match},
        {"$group": {
            "_id": {"provider": "$provider", "entity_id": "$entity_id"},
            "entity_name": {"$last": "$entity_name"}, "currency": {"$last": "$currency"},
            "parent_id": {"$last": "$parent_id"},
            "spend": {"$sum": "$spend"}, "spend_micros": {"$sum": "$spend_micros"},
            "impressions": {"$sum": "$impressions"}, "clicks": {"$sum": "$clicks"},
            "platform_leads": {"$sum": "$platform_leads"},
            "platform_conversion_value": {"$sum": "$platform_conversion_value"},
            "days": {"$sum": 1},
        }},
    ]).to_list(1000)
    return rows


async def _lead_stats(db, since, until, *, level="campaign", provider=None):
    field = LEVEL_FIELD.get(level, "ad_campaign_id")
    match = {"created_at": {"$gte": since[:10], "$lt": next_day(until)},
             field: {"$nin": [None, ""]}}
    if provider:
        match["ad_platform"] = provider
    rows = await db.leads.aggregate([
        {"$match": match},
        {"$group": {
            "_id": {"provider": {"$ifNull": ["$ad_platform", ""]}, "entity_id": f"${field}"},
            "leads": {"$sum": 1},
            "won": {"$sum": {"$cond": [{"$eq": ["$stage", "won"]}, 1, 0]}},
            "lead_value": {"$sum": {"$ifNull": ["$value", 0]}},
            "customer_ids": {"$addToSet": "$converted_customer_id"},
        }},
    ]).to_list(1000)
    return rows


async def _booking_revenue(db, customer_ids, since, until):
    ids = [c for c in customer_ids if c]
    if not ids:
        return {"bookings": 0, "revenue": 0, "paid": 0}
    rows = await db.bookings.aggregate([
        {"$match": {"customer_id": {"$in": ids},
                    "status": {"$in": list(BOOKING_REVENUE_STATUS)},
                    "created_at": {"$gte": since[:10], "$lt": next_day(until)}}},
        {"$group": {"_id": None, "bookings": {"$sum": 1},
                    "revenue": {"$sum": "$total_amount"}, "paid": {"$sum": "$paid_amount"}}},
    ]).to_list(1)
    if not rows:
        return {"bookings": 0, "revenue": 0, "paid": 0}
    row = rows[0]
    return {"bookings": int(row.get("bookings") or 0),
            "revenue": money(row.get("revenue")), "paid": money(row.get("paid"))}


def _ratio(numerator, denominator, digits=2):
    try:
        if not denominator:
            return None
        return round(float(numerator) / float(denominator), digits)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


async def performance(db, since: str, until: str, *, provider=None, level="campaign") -> dict:
    """Gabungan metrik platform + hasil bisnis ERP per entitas iklan (ROAS nyata)."""
    level = level if level in LEVELS else "campaign"
    metrics = await _metrics_by_entity(db, since, until, provider=provider, level=level)
    leads = await _lead_stats(db, since, until, level=level, provider=provider)
    by_key = {}
    for row in metrics:
        key = (row["_id"]["provider"], row["_id"]["entity_id"])
        by_key[key] = {
            "provider": key[0], "entity_id": key[1], "level": level,
            "name": row.get("entity_name") or key[1], "parent_id": row.get("parent_id") or "",
            "currency": row.get("currency") or "",
            "spend": round(float(row.get("spend") or 0), 2),
            "impressions": int(row.get("impressions") or 0),
            "clicks": int(row.get("clicks") or 0),
            "platform_leads": round(float(row.get("platform_leads") or 0), 2),
            "platform_conversion_value": round(float(row.get("platform_conversion_value") or 0), 2),
            "days": int(row.get("days") or 0),
            "leads": 0, "won": 0, "lead_value": 0, "bookings": 0, "revenue": 0, "paid": 0,
        }
    for row in leads:
        key = (row["_id"].get("provider") or "", row["_id"]["entity_id"])
        target = by_key.get(key)
        if target is None:
            target = by_key.setdefault(key, {
                "provider": key[0], "entity_id": key[1], "level": level, "name": key[1],
                "parent_id": "", "currency": "", "spend": 0.0, "impressions": 0, "clicks": 0,
                "platform_leads": 0.0, "platform_conversion_value": 0.0, "days": 0,
                "leads": 0, "won": 0, "lead_value": 0, "bookings": 0, "revenue": 0, "paid": 0})
        target["leads"] = int(row.get("leads") or 0)
        target["won"] = int(row.get("won") or 0)
        target["lead_value"] = money(row.get("lead_value"))
        rev = await _booking_revenue(db, row.get("customer_ids") or [], since, until)
        target.update(rev)

    rows = []
    totals = {"spend": 0.0, "clicks": 0, "impressions": 0, "leads": 0, "won": 0,
              "bookings": 0, "revenue": 0, "paid": 0}
    for item in by_key.values():
        revenue = item["revenue"] or item["lead_value"]
        item["cpl"] = _ratio(item["spend"], item["leads"])
        item["cac"] = _ratio(item["spend"], item["bookings"] or item["won"])
        item["roas"] = _ratio(revenue, item["spend"])
        item["cpc"] = _ratio(item["spend"], item["clicks"])
        item["lead_to_booking"] = _ratio((item["bookings"] or item["won"]) * 100, item["leads"], 1)
        rows.append(item)
        for key in totals:
            totals[key] += item.get(key) or 0
    rows.sort(key=lambda r: (-(r.get("spend") or 0), -(r.get("leads") or 0)))
    totals["spend"] = round(totals["spend"], 2)
    totals["cpl"] = _ratio(totals["spend"], totals["leads"])
    totals["cac"] = _ratio(totals["spend"], totals["bookings"] or totals["won"])
    totals["roas"] = _ratio(totals["revenue"], totals["spend"])
    currencies = sorted({r["currency"] for r in rows if r.get("currency")})
    return {"range": {"since": since[:10], "until": until[:10]}, "level": level,
            "rows": rows, "totals": totals, "currencies": currencies}


async def daily_series(db, since: str, until: str, *, provider=None) -> list:
    match = {"level": "campaign", "date": {"$gte": since[:10], "$lte": until[:10]}}
    if provider:
        match["provider"] = provider
    rows = await db[COLL_METRICS].aggregate([
        {"$match": match},
        {"$group": {"_id": "$date", "spend": {"$sum": "$spend"},
                    "clicks": {"$sum": "$clicks"}, "impressions": {"$sum": "$impressions"}}},
        {"$sort": {"_id": 1}},
    ]).to_list(400)
    return [{"date": r["_id"], "spend": round(float(r.get("spend") or 0), 2),
             "clicks": int(r.get("clicks") or 0),
             "impressions": int(r.get("impressions") or 0)} for r in rows]
