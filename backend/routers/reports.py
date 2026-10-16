"""routers/reports.py — laporan agregat + export Excel/PDF (Phase 5 + E12 payroll).

Read-only. Logika di services/reports.py & services/payroll_report.py.
Akses section 'reports' (owner/ops_admin).
"""
from io import BytesIO

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from db import get_db
from dependencies import require_section
from services.exporter import report_xlsx
from services.reports import summary as reports_summary
from services import hold_report as hrep
from services import payroll_report as prep
from services import driver_report as drep

router = APIRouter(prefix="/api", tags=["reports"])
REP = require_section("reports")


@router.get("/reports/summary")
async def get_reports_summary(period: str = Query(default=None), user=Depends(REP)):
    db = get_db()
    data = await reports_summary(db, period)
    # E12: sertakan rekap payroll agar tampil langsung di modul Laporan.
    data["payroll"] = await prep.build(db, data.get("period"))
    # E13: sertakan laporan driver (leaderboard + revenue-per-trip).
    data["drivers_report"] = await drep.build(db, data.get("period"))
    return data


@router.get("/reports/export")
async def export_reports(format: str = Query(default="excel"), period: str = Query(default=None),
                         user=Depends(REP)):
    data = await reports_summary(get_db(), period)
    blob = report_xlsx(data)
    return StreamingResponse(
        BytesIO(blob),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="laporan-{data.get("period","")}.xlsx"'},
    )


@router.get("/reports/payroll")
async def get_payroll_report(period: str = Query(default=None), user=Depends(REP)):
    return await prep.build(get_db(), period)


@router.get("/reports/payroll/export")
async def export_payroll_report(format: str = Query(default="excel"), period: str = Query(default=None),
                                user=Depends(REP)):
    db = get_db()
    data = await prep.build(db, period)
    company = (await db.settings.find_one({"key": "company_info"}, {"_id": 0}) or {}).get("value") or {}
    per = data.get("period", "")
    if format == "pdf":
        blob = prep.report_pdf(data, company)
        return StreamingResponse(
            BytesIO(blob), media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="rekap-payroll-{per}.pdf"'})
    blob = prep.report_xlsx(data, company)
    return StreamingResponse(
        BytesIO(blob),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="rekap-payroll-{per}.xlsx"'})


@router.get("/reports/drivers")
async def get_drivers_report(period: str = Query(default=None), user=Depends(REP)):
    return await drep.build(get_db(), period)


@router.get("/reports/hold-expired")
async def get_hold_expired_report(days: int = Query(default=30, ge=1, le=365), user=Depends(REP)):
    """Laporan "hold hangus": reservasi web yang dibatalkan sistem karena DP tak masuk.

    Kenapa laporan terpisah (bukan sekadar notifikasi): pembatalan otomatis sudah berjalan,
    tetapi kerugiannya — unit terkunci berjam-jam untuk pesanan yang batal — tak pernah
    terukur. Lihat `services/hold_report.py` untuk alasan tiap angkanya.
    """
    return await hrep.build(get_db(), days)


@router.get("/reports/hold-expired/export")
async def export_hold_expired_report(days: int = Query(default=30, ge=1, le=365),
                                    user=Depends(REP)):
    """CSV untuk tindak lanjut ops (hubungi ulang tamu yang hold-nya hangus)."""
    data = await hrep.build(get_db(), days)
    body = hrep.to_csv(data)
    return StreamingResponse(
        BytesIO(("\ufeff" + body).encode("utf-8")), media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="hold-hangus-{days}hari.csv"'})


@router.get("/reports/drivers/export")
async def export_drivers_report(format: str = Query(default="excel"), period: str = Query(default=None),
                                user=Depends(REP)):
    db = get_db()
    data = await drep.build(db, period)
    company = (await db.settings.find_one({"key": "company_info"}, {"_id": 0}) or {}).get("value") or {}
    per = data.get("period", "")
    if format == "pdf":
        blob = drep.report_pdf(data, company)
        return StreamingResponse(
            BytesIO(blob), media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="laporan-driver-{per}.pdf"'})
    blob = drep.report_xlsx(data, company)
    return StreamingResponse(
        BytesIO(blob),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="laporan-driver-{per}.xlsx"'})
