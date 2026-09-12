"""routers/finance.py — agregasi keuangan: laba-rugi, piutang (AR), ringkasan (Phase 5).

Read-only kecuali aksi E5 (sync status invoice, kirim reminder AR).
Logika di services/finance.py, services/finance_automation.py (E5) & services/reports.py.
Akses section 'finance' (owner/ops_admin).
"""
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from db import get_db
from dependencies import require_section
from services.finance import accounts_receivable, profit_loss
from services import finance_automation as fa
from services.finance_export import finance_report_pdf, finance_report_xlsx

router = APIRouter(prefix="/api", tags=["finance"])
FIN = require_section("finance")


@router.get("/finance/profit-loss")
async def get_profit_loss(period: str = Query(default=None), user=Depends(FIN)):
    return await profit_loss(get_db(), period)


@router.get("/finance/ar")
async def get_ar(user=Depends(FIN)):
    return await accounts_receivable(get_db())


# ----------------------------------------------------------------- E5 Finance Automation
@router.get("/finance/pl-full")
async def get_pl_full(period: str = Query(default=None), user=Depends(FIN)):
    """P&L komprehensif: revenue - opex - maintenance, total & per unit (G4)."""
    return await fa.pl_full(get_db(), period)


@router.get("/finance/reconciliation")
async def get_reconciliation(user=Depends(FIN)):
    """Rekonsiliasi invoice ↔ pembayaran + ringkasan selisih (G5)."""
    return await fa.reconciliation(get_db())


@router.post("/finance/reconciliation/sync")
async def post_reconciliation_sync(user=Depends(FIN)):
    """Selaraskan status invoice mengikuti pembayaran (paid/partial/sent)."""
    return await fa.sync_invoice_statuses(get_db())


@router.get("/finance/cashflow")
async def get_cashflow(months: int = Query(default=6, ge=1, le=24),
                       horizon: int = Query(default=3, ge=0, le=12), user=Depends(FIN)):
    return await fa.cashflow(get_db(), months_back=months, horizon=horizon)


@router.get("/finance/ar/overdue")
async def get_ar_overdue(user=Depends(FIN)):
    return await fa.ar_overdue(get_db())


@router.post("/finance/ar/{booking_id}/remind")
async def post_ar_remind(booking_id: str, user=Depends(FIN)):
    db = get_db()
    if not await db.bookings.find_one({"id": booking_id}, {"_id": 1}):
        raise HTTPException(status_code=404, detail="Booking tidak ditemukan")
    return await fa.send_ar_reminder(db, booking_id)


@router.post("/finance/ar/remind-all")
async def post_ar_remind_all(user=Depends(FIN)):
    return await fa.send_bulk_ar_reminders(get_db())


@router.get("/finance/export")
async def export_finance(format: str = Query(default="excel"), period: str = Query(default=None),
                         user=Depends(FIN)):
    data = await fa.assemble_finance_report(get_db(), period)
    label = data.get("period", "")
    if format == "pdf":
        blob = finance_report_pdf(data)
        return StreamingResponse(
            BytesIO(blob), media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="laporan-keuangan-{label}.pdf"'})
    blob = finance_report_xlsx(data)
    return StreamingResponse(
        BytesIO(blob),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="laporan-keuangan-{label}.xlsx"'})


@router.get("/finance/summary")
async def get_summary(period: str = Query(default=None), user=Depends(FIN)):
    db = get_db()
    pl = await profit_loss(db, period)
    ar = await accounts_receivable(db)
    invoices_total = await db.invoices.count_documents({})
    invoices_unpaid = await db.invoices.count_documents({"status": {"$ne": "paid"}})
    return {
        "period": pl["period"],
        "revenue": pl["revenue"],
        "expenses": pl["expenses"],
        "profit": pl["profit"],
        "margin": pl["margin"],
        "outstanding_ar": ar["total_outstanding"],
        "ar_count": ar["count"],
        "invoices_total": invoices_total,
        "invoices_unpaid": invoices_unpaid,
    }
