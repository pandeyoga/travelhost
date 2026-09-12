"""services/analytics.py — E4 BI & Management Cockpit (read-only aggregations).

Tidak menulis DB (kecuali set_marketing_spend ke `settings`). Semua berbasis rentang
tanggal (start/end ISO YYYY-MM-DD) + pembanding periode sebelumnya. Reuse helper finance.

Panel: exec KPI (+delta), sales funnel (cohort lead), channel mix + ROAS/CPL/CAC
(ad-spend manual dari settings.marketing_spend), fleet ROI/utilisasi, driver performance,
AR aging buckets, retention/cohort, forecast moving-average.
"""
from datetime import datetime, timedelta, timezone

from services.finance import accounts_receivable
from services.attribution import channel_label as _channel_label

# Progres tahap lead (untuk funnel cohort monotonic).
STAGE_RANK = {"new": 0, "contacted": 1, "quoted": 2, "negotiation": 3, "won": 4, "lost": 0}
DEFAULT_CHANNELS = ["website", "whatsapp", "manual", "meta_ads", "google_ads", "instagram", "tiktok"]


# ----------------------------------------------------------------------------- range
def _today():
    return datetime.now(timezone.utc).date()


def parse_range(days=None, start=None, end=None):
    """Kembalikan dict rentang sekarang + sebelumnya (string YYYY-MM-DD, end eksklusif)."""
    today = _today()
    if start and end:
        try:
            s = datetime.fromisoformat(start).date()
            e = datetime.fromisoformat(end).date()
        except Exception:
            s, e = today - timedelta(days=29), today
        if e < s:
            s, e = e, s
        length = (e - s).days + 1
    else:
        length = int(days or 30)
        if length <= 0:
            length = 30
        e = today
        s = today - timedelta(days=length - 1)
    end_excl = e + timedelta(days=1)
    prev_end = s
    prev_start = s - timedelta(days=length)
    return {
        "start": s.isoformat(), "end": e.isoformat(), "end_excl": end_excl.isoformat(),
        "prev_start": prev_start.isoformat(), "prev_end_excl": s.isoformat(),
        "days": length,
        "label": f"{s.isoformat()} \u2192 {e.isoformat()}",
    }


def _rmatch(field, s, e_excl):
    return {field: {"$gte": s, "$lt": e_excl}}


async def _sum(db, coll, field, match):
    rows = await db[coll].aggregate([
        {"$match": match},
        {"$group": {"_id": None, "t": {"$sum": {"$ifNull": [f"${field}", 0]}}}},
    ]).to_list(1)
    return float(rows[0]["t"]) if rows else 0.0


async def _count(db, coll, match):
    return await db[coll].count_documents(match)


def _delta(cur, prev):
    cur = float(cur or 0)
    prev = float(prev or 0)
    if prev == 0:
        return 100.0 if cur > 0 else 0.0
    return round((cur - prev) / prev * 100, 1)


# ----------------------------------------------------------------------------- KPIs
async def _kpis_for(db, s, e_excl):
    revenue = await _sum(db, "payments", "amount", _rmatch("paid_at", s, e_excl))
    expenses = await _sum(db, "expenses", "amount", _rmatch("created_at", s, e_excl))
    bookings = await _count(db, "bookings", {**_rmatch("created_at", s, e_excl),
                                             "status": {"$ne": "cancelled"}})
    leads = await _count(db, "leads", _rmatch("created_at", s, e_excl))
    won = await _count(db, "leads", {**_rmatch("created_at", s, e_excl), "stage": "won"})
    profit = round(revenue - expenses, 2)
    return {
        "revenue": round(revenue, 2),
        "expenses": round(expenses, 2),
        "profit": profit,
        "margin": round((profit / revenue * 100), 1) if revenue > 0 else 0.0,
        "bookings": bookings,
        "leads": leads,
        "won": won,
        "conversion_rate": round((won / leads * 100), 1) if leads > 0 else 0.0,
        "avg_booking_value": round((revenue / bookings), 2) if bookings > 0 else 0.0,
    }


async def summary_kpis(db, rng):
    cur = await _kpis_for(db, rng["start"], rng["end_excl"])
    prev = await _kpis_for(db, rng["prev_start"], rng["prev_end_excl"])
    ar = await accounts_receivable(db)
    metrics = {}
    for k, v in cur.items():
        metrics[k] = {"value": v, "prev": prev.get(k, 0), "delta_pct": _delta(v, prev.get(k, 0))}
    metrics["outstanding_ar"] = {"value": ar["total_outstanding"], "prev": None, "delta_pct": None}
    metrics["ar_count"] = {"value": ar["count"], "prev": None, "delta_pct": None}
    return {"range": rng, "metrics": metrics}


# ----------------------------------------------------------------------------- funnel
async def funnel(db, rng):
    match = _rmatch("created_at", rng["start"], rng["end_excl"])
    docs = await db.leads.find(match, {"_id": 0, "stage": 1, "converted_customer_id": 1}).to_list(5000)
    total = len(docs)
    contacted = sum(1 for d in docs if STAGE_RANK.get(d.get("stage"), 0) >= 1)
    quoted = sum(1 for d in docs if STAGE_RANK.get(d.get("stage"), 0) >= 2)
    won = sum(1 for d in docs if d.get("stage") == "won")
    converted = sum(1 for d in docs if d.get("converted_customer_id"))

    def rate(a, b):
        return round((a / b * 100), 1) if b > 0 else 0.0

    stages = [
        {"key": "lead", "label": "Lead Masuk", "count": total, "rate": 100.0},
        {"key": "contacted", "label": "Dihubungi", "count": contacted, "rate": rate(contacted, total)},
        {"key": "quotation", "label": "Penawaran", "count": quoted, "rate": rate(quoted, total)},
        {"key": "won", "label": "Menang (Deal)", "count": won, "rate": rate(won, total)},
    ]
    return {"range": rng, "stages": stages, "bookings_from_leads": converted,
            "overall_conversion": rate(won, total)}


# ----------------------------------------------------------------------------- channels
async def channels_roi(db, rng, spend_map=None):
    spend_map = spend_map or {}
    match = _rmatch("created_at", rng["start"], rng["end_excl"])
    rows = await db.leads.aggregate([
        {"$match": match},
        {"$group": {
            # E-ADS: kelompokkan per channel ber-atribusi; fallback ke source lalu 'lainnya'
            "_id": {"$ifNull": ["$channel", {"$ifNull": ["$source", "lainnya"]}]},
            "leads": {"$sum": 1},
            "won": {"$sum": {"$cond": [{"$eq": ["$stage", "won"]}, 1, 0]}},
            "revenue": {"$sum": {"$cond": [{"$eq": ["$stage", "won"]},
                                           {"$ifNull": ["$value", 0]}, 0]}},
        }},
    ]).to_list(100)
    by_src = {r["_id"]: r for r in rows}
    channels = sorted(set(list(by_src.keys()) + list(spend_map.keys())))
    out = []
    tot = {"leads": 0, "won": 0, "revenue": 0.0, "spend": 0.0}
    for ch in channels:
        r = by_src.get(ch, {"leads": 0, "won": 0, "revenue": 0.0})
        leads = int(r.get("leads", 0))
        won = int(r.get("won", 0))
        revenue = round(float(r.get("revenue", 0) or 0), 2)
        spend = round(float(spend_map.get(ch, 0) or 0), 2)
        out.append({
            "channel": ch, "label": _channel_label(ch),
            "leads": leads, "won": won, "revenue": revenue, "spend": spend,
            "cpl": round(spend / leads, 2) if (spend > 0 and leads > 0) else None,
            "cac": round(spend / won, 2) if (spend > 0 and won > 0) else None,
            "roas": round(revenue / spend, 2) if spend > 0 else None,
        })
        tot["leads"] += leads
        tot["won"] += won
        tot["revenue"] += revenue
        tot["spend"] += spend
    out.sort(key=lambda x: (-x["leads"], x["channel"]))
    totals = {
        "leads": tot["leads"], "won": tot["won"], "revenue": round(tot["revenue"], 2),
        "spend": round(tot["spend"], 2),
        "cpl": round(tot["spend"] / tot["leads"], 2) if (tot["spend"] > 0 and tot["leads"] > 0) else None,
        "cac": round(tot["spend"] / tot["won"], 2) if (tot["spend"] > 0 and tot["won"] > 0) else None,
        "roas": round(tot["revenue"] / tot["spend"], 2) if tot["spend"] > 0 else None,
    }
    return {"range": rng, "channels": out, "totals": totals}


# ----------------------------------------------------------------------------- fleet
async def fleet_roi(db, rng):
    match = _rmatch("created_at", rng["start"], rng["end_excl"])
    trips = await db.trips.find(match, {"_id": 0, "id": 1, "vehicle_id": 1, "revenue": 1,
                                        "distance_km": 1, "status": 1}).to_list(5000)
    trip_ids_by_veh = {}
    rev_by_veh = {}
    cnt_by_veh = {}
    dist_by_veh = {}
    all_trip_ids = []
    for t in trips:
        v = t.get("vehicle_id")
        if not v:
            continue
        trip_ids_by_veh.setdefault(v, []).append(t["id"])
        all_trip_ids.append(t["id"])
        rev_by_veh[v] = rev_by_veh.get(v, 0.0) + float(t.get("revenue", 0) or 0)
        cnt_by_veh[v] = cnt_by_veh.get(v, 0) + 1
        dist_by_veh[v] = dist_by_veh.get(v, 0.0) + float(t.get("distance_km", 0) or 0)
    exp_by_veh = {}
    if all_trip_ids:
        exp_rows = await db.expenses.aggregate([
            {"$match": {"trip_id": {"$in": all_trip_ids}}},
            {"$group": {"_id": "$trip_id", "amount": {"$sum": {"$ifNull": ["$amount", 0]}}}},
        ]).to_list(5000)
        exp_by_trip = {r["_id"]: float(r["amount"]) for r in exp_rows}
        for v, tids in trip_ids_by_veh.items():
            exp_by_veh[v] = sum(exp_by_trip.get(t, 0.0) for t in tids)
    vehicles = await db.vehicles.find({}, {"_id": 0, "id": 1, "name": 1, "code": 1}).to_list(1000)
    out = []
    for v in vehicles:
        vid = v["id"]
        revenue = round(rev_by_veh.get(vid, 0.0), 2)
        expenses = round(exp_by_veh.get(vid, 0.0), 2)
        profit = round(revenue - expenses, 2)
        out.append({
            "vehicle_id": vid, "vehicle_name": v.get("name") or v.get("code"),
            "trips": cnt_by_veh.get(vid, 0), "distance_km": round(dist_by_veh.get(vid, 0.0), 1),
            "revenue": revenue, "expenses": expenses, "profit": profit,
            "roi_pct": round((profit / expenses * 100), 1) if expenses > 0 else None,
            "utilization": cnt_by_veh.get(vid, 0),
        })
    out.sort(key=lambda x: (-x["revenue"], x["vehicle_name"] or ""))
    return {"range": rng, "vehicles": out, "active_units": sum(1 for o in out if o["trips"] > 0),
            "idle_units": sum(1 for o in out if o["trips"] == 0)}


# ----------------------------------------------------------------------------- drivers
async def driver_performance(db, rng):
    match = _rmatch("created_at", rng["start"], rng["end_excl"])
    rows = await db.trips.aggregate([
        {"$match": match},
        {"$group": {
            "_id": "$driver_id",
            "trips": {"$sum": 1},
            "revenue": {"$sum": {"$ifNull": ["$revenue", 0]}},
            "distance_km": {"$sum": {"$ifNull": ["$distance_km", 0]}},
            "completed": {"$sum": {"$cond": [{"$eq": ["$status", "completed"]}, 1, 0]}},
        }},
    ]).to_list(1000)
    by_drv = {r["_id"]: r for r in rows}
    drivers = await db.drivers.find({}, {"_id": 0, "id": 1, "name": 1, "phone": 1}).to_list(1000)
    out = []
    for d in drivers:
        r = by_drv.get(d["id"], {})
        trips = int(r.get("trips", 0))
        completed = int(r.get("completed", 0))
        out.append({
            "driver_id": d["id"], "driver_name": d.get("name"), "phone": d.get("phone"),
            "trips": trips, "completed": completed,
            "completion_rate": round((completed / trips * 100), 1) if trips > 0 else 0.0,
            "revenue": round(float(r.get("revenue", 0) or 0), 2),
            "distance_km": round(float(r.get("distance_km", 0) or 0), 1),
        })
    out.sort(key=lambda x: (-x["trips"], -x["revenue"]))
    return {"range": rng, "drivers": out}


# ----------------------------------------------------------------------------- AR aging
def _age_bucket(days):
    if days < 0:
        return "belum_jatuh_tempo"
    if days <= 30:
        return "0-30"
    if days <= 60:
        return "31-60"
    if days <= 90:
        return "61-90"
    return "90+"


BUCKET_ORDER = ["belum_jatuh_tempo", "0-30", "31-60", "61-90", "90+"]
BUCKET_LABEL = {"belum_jatuh_tempo": "Belum jatuh tempo", "0-30": "0-30 hari",
                "31-60": "31-60 hari", "61-90": "61-90 hari", "90+": ">90 hari"}


async def ar_aging(db):
    ar = await accounts_receivable(db)
    today = _today()
    buckets = {b: {"bucket": b, "label": BUCKET_LABEL[b], "amount": 0.0, "count": 0} for b in BUCKET_ORDER}
    for item in ar["items"]:
        sd = item.get("start_datetime") or ""
        try:
            d = datetime.fromisoformat(sd.replace("Z", "+00:00")).date()
            age = (today - d).days
        except Exception:
            age = 0
        b = _age_bucket(age)
        buckets[b]["amount"] = round(buckets[b]["amount"] + float(item.get("outstanding", 0) or 0), 2)
        buckets[b]["count"] += 1
    rows = [buckets[b] for b in BUCKET_ORDER]
    return {"total_outstanding": ar["total_outstanding"], "count": ar["count"], "buckets": rows}


# ----------------------------------------------------------------------------- retention
async def retention(db, rng):
    total = await _count(db, "customers", {})
    returning = await _count(db, "customers", {"total_trips": {"$gte": 2}})
    new_in_range = await _count(db, "customers", _rmatch("created_at", rng["start"], rng["end_excl"]))
    seg_rows = await db.customers.aggregate([
        {"$group": {"_id": {"$ifNull": ["$rfm_segment", "lainnya"]}, "c": {"$sum": 1}}},
    ]).to_list(100)
    life_rows = await db.customers.aggregate([
        {"$group": {"_id": {"$ifNull": ["$lifecycle", "lainnya"]}, "c": {"$sum": 1}}},
    ]).to_list(100)
    return {
        "range": rng,
        "total_customers": total,
        "returning_customers": returning,
        "new_customers": new_in_range,
        "one_time_customers": max(total - returning, 0),
        "repeat_rate": round((returning / total), 3) if total > 0 else 0.0,
        "by_rfm": sorted([{"segment": r["_id"], "count": r["c"]} for r in seg_rows],
                         key=lambda x: -x["count"]),
        "by_lifecycle": sorted([{"lifecycle": r["_id"], "count": r["c"]} for r in life_rows],
                               key=lambda x: -x["count"]),
    }


# ----------------------------------------------------------------------------- forecast
def _month_keys(n):
    now = datetime.now(timezone.utc)
    y, m = now.year, now.month
    keys = []
    for _ in range(n):
        keys.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    return list(reversed(keys))


def _next_months(last_key, horizon):
    y, m = int(last_key[:4]), int(last_key[5:7])
    out = []
    for _ in range(horizon):
        m += 1
        if m == 13:
            m, y = 1, y + 1
        out.append(f"{y:04d}-{m:02d}")
    return out


async def forecast(db, months_back=6, horizon=3, metric="revenue"):
    coll, field, datefield = ("payments", "amount", "paid_at") if metric == "revenue" else \
        ("bookings", None, "created_at")
    months = _month_keys(months_back)
    if metric == "revenue":
        rows = await db.payments.aggregate([
            {"$group": {"_id": {"$substrBytes": [{"$ifNull": ["$paid_at", ""]}, 0, 7]},
                        "t": {"$sum": {"$ifNull": ["$amount", 0]}}}},
        ]).to_list(1000)
        by_m = {r["_id"]: float(r["t"]) for r in rows}
    else:
        rows = await db.bookings.aggregate([
            {"$match": {"status": {"$ne": "cancelled"}}},
            {"$group": {"_id": {"$substrBytes": [{"$ifNull": ["$created_at", ""]}, 0, 7]},
                        "t": {"$sum": 1}}},
        ]).to_list(1000)
        by_m = {r["_id"]: float(r["t"]) for r in rows}
    history = [{"month": k, "value": round(by_m.get(k, 0.0), 2)} for k in months]
    series = [h["value"] for h in history]
    window = min(3, len([v for v in series if v > 0]) or 1)
    fc_keys = _next_months(months[-1], horizon)
    fc = []
    work = list(series)
    for k in fc_keys:
        tail = [v for v in work[-window:]] if window > 0 else work[-1:]
        pred = round(sum(tail) / len(tail), 2) if tail else 0.0
        fc.append({"month": k, "value": pred})
        work.append(pred)
    return {"metric": metric, "method": "moving_average", "window": window,
            "history": history, "forecast": fc}


# ----------------------------------------------------------------------------- ad-spend (settings)
SPEND_KEY = "marketing_spend"


async def assemble_cockpit(db, rng):
    """Kumpulkan SELURUH panel cockpit (untuk export PDF/Excel)."""
    spend = await get_marketing_spend(db)
    return {
        "range": rng,
        "summary": await summary_kpis(db, rng),
        "funnel": await funnel(db, rng),
        "channels": await channels_roi(db, rng, spend_map=spend["spend_map"]),
        "fleet": await fleet_roi(db, rng),
        "drivers": await driver_performance(db, rng),
        "ar_aging": await ar_aging(db),
        "retention": await retention(db, rng),
        "forecast": await forecast(db, months_back=6, horizon=3, metric="revenue"),
    }


async def get_marketing_spend(db):
    doc = await db.settings.find_one({"key": SPEND_KEY}, {"_id": 0, "value": 1}) or {}
    val = doc.get("value") or {}
    items = val.get("items") or []
    return {"items": items, "note": val.get("note", ""), "updated_at": val.get("updated_at"),
            "spend_map": {i.get("channel"): float(i.get("amount", 0) or 0) for i in items if i.get("channel")}}


async def set_marketing_spend(db, items, note=""):
    from core_utils import now_iso
    clean = []
    for i in items or []:
        ch = (i.get("channel") or "").strip()
        if not ch:
            continue
        clean.append({"channel": ch, "amount": round(float(i.get("amount", 0) or 0), 2)})
    value = {"items": clean, "note": note or "", "updated_at": now_iso()}
    await db.settings.update_one({"key": SPEND_KEY}, {"$set": {"key": SPEND_KEY, "value": value}}, upsert=True)
    return await get_marketing_spend(db)
