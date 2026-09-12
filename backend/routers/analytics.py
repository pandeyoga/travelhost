"""routers/analytics.py — E4 BI & Management Cockpit (read-only + export).

Section RBAC 'analytics' (owner/ops_admin). Logika di services/analytics.py.
Semua respons OBJEK/ARRAY telanjang (tanpa envelope). Rentang via days / start+end.

Kontrak rute (semua /api):
  GET /analytics/summary    ?days|start&end   -> {range, metrics{...value/prev/delta_pct}}
  GET /analytics/funnel                         -> {range, stages[], overall_conversion}
  GET /analytics/channels                       -> {range, channels[], totals}  (pakai marketing_spend)
  GET /analytics/fleet                          -> {range, vehicles[], active/idle}
  GET /analytics/drivers                        -> {range, drivers[]}
  GET /analytics/ar-aging                       -> {total_outstanding, buckets[]}
  GET /analytics/retention                      -> {repeat_rate, by_rfm[], ...}
  GET /analytics/forecast   ?metric=revenue     -> {history[], forecast[]}
  GET /analytics/ad-spend                       -> {items[], spend_map}
  PUT /analytics/ad-spend   <- {items[], note}  -> {items[], spend_map}
  GET /analytics/export     ?format=pdf|excel   -> file
"""
from io import BytesIO

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from db import get_db
from dependencies import require_section
from schemas import MarketingSpendUpdate
from services import analytics
from services.analytics_export import cockpit_pdf, cockpit_xlsx

router = APIRouter(prefix="/api", tags=["analytics"])
AN = require_section("analytics")


def _rng(days, start, end):
    return analytics.parse_range(days=days, start=start, end=end)


@router.get("/analytics/summary")
async def get_summary(days: int = Query(default=30), start: str = Query(default=None),
                      end: str = Query(default=None), user=Depends(AN)):
    return await analytics.summary_kpis(get_db(), _rng(days, start, end))


@router.get("/analytics/funnel")
async def get_funnel(days: int = Query(default=30), start: str = Query(default=None),
                     end: str = Query(default=None), user=Depends(AN)):
    return await analytics.funnel(get_db(), _rng(days, start, end))


@router.get("/analytics/channels")
async def get_channels(days: int = Query(default=30), start: str = Query(default=None),
                       end: str = Query(default=None), user=Depends(AN)):
    db = get_db()
    spend = await analytics.get_marketing_spend(db)
    return await analytics.channels_roi(db, _rng(days, start, end), spend_map=spend["spend_map"])


@router.get("/analytics/fleet")
async def get_fleet(days: int = Query(default=30), start: str = Query(default=None),
                    end: str = Query(default=None), user=Depends(AN)):
    return await analytics.fleet_roi(get_db(), _rng(days, start, end))


@router.get("/analytics/drivers")
async def get_drivers(days: int = Query(default=30), start: str = Query(default=None),
                      end: str = Query(default=None), user=Depends(AN)):
    return await analytics.driver_performance(get_db(), _rng(days, start, end))


@router.get("/analytics/ar-aging")
async def get_ar_aging(user=Depends(AN)):
    return await analytics.ar_aging(get_db())


@router.get("/analytics/retention")
async def get_retention(days: int = Query(default=30), start: str = Query(default=None),
                        end: str = Query(default=None), user=Depends(AN)):
    return await analytics.retention(get_db(), _rng(days, start, end))


@router.get("/analytics/forecast")
async def get_forecast(metric: str = Query(default="revenue"), user=Depends(AN)):
    metric = metric if metric in ("revenue", "bookings") else "revenue"
    return await analytics.forecast(get_db(), months_back=6, horizon=3, metric=metric)


@router.get("/analytics/ad-spend")
async def get_ad_spend(user=Depends(AN)):
    return await analytics.get_marketing_spend(get_db())


@router.put("/analytics/ad-spend")
async def put_ad_spend(payload: MarketingSpendUpdate, user=Depends(AN)):
    items = [{"channel": i.channel, "amount": i.amount} for i in payload.items]
    return await analytics.set_marketing_spend(get_db(), items, note=payload.note or "")


@router.get("/analytics/export")
async def export_cockpit(format: str = Query(default="excel"), days: int = Query(default=30),
                         start: str = Query(default=None), end: str = Query(default=None),
                         user=Depends(AN)):
    db = get_db()
    rng = _rng(days, start, end)
    data = await analytics.assemble_cockpit(db, rng)
    label = rng["label"].replace(" \u2192 ", "_").replace(" ", "")
    if format == "pdf":
        blob = cockpit_pdf(data)
        return StreamingResponse(
            BytesIO(blob), media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="bi-cockpit-{label}.pdf"'},
        )
    blob = cockpit_xlsx(data)
    return StreamingResponse(
        BytesIO(blob),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="bi-cockpit-{label}.xlsx"'},
    )
