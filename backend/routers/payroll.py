"""routers/payroll.py — Driver Payroll / HR Lite (E11 Phase C).

Kompensasi driver (embedded `drivers.comp`) + payout per periode (koleksi `driver_payouts`, dpo_)
dengan alur draft → approved → paid + integrasi Finance (expenses kategori gaji_driver).
Akses section 'finance' (owner/ops_admin). Logika akrual di services/payroll.py.
"""
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from core_utils import now_iso, safe_doc
from db import get_db
from dependencies import require_section
from schemas import DriverCompUpdate, PayoutGenerate, PayoutUpdate, PayoutBulkGenerate
from services import payroll as pr
from services.payroll_export import slip_pdf, slip_xlsx
from services.audit import record

router = APIRouter(prefix="/api", tags=["payroll"])
FIN = require_section("finance")


# ----------------------------------------------------------------- Kompensasi per driver
@router.get("/drivers/{driver_id}/compensation")
async def get_compensation(driver_id: str, user=Depends(FIN)):
    db = get_db()
    drv = await db.drivers.find_one({"id": driver_id}, {"_id": 0})
    if not drv:
        raise HTTPException(status_code=404, detail="Driver tidak ditemukan")
    return {"driver_id": driver_id, "driver_name": drv.get("name"), "comp": pr.get_comp(drv)}


@router.patch("/drivers/{driver_id}/compensation")
async def update_compensation(driver_id: str, body: DriverCompUpdate, user=Depends(FIN)):
    db = get_db()
    drv = await db.drivers.find_one({"id": driver_id}, {"_id": 0})
    if not drv:
        raise HTTPException(status_code=404, detail="Driver tidak ditemukan")
    current = pr.get_comp(drv)
    updates = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    if updates.get("revenue_base") and updates["revenue_base"] not in ("trip", "booking"):
        raise HTTPException(status_code=400, detail="revenue_base harus 'trip' atau 'booking'")
    current.update(updates)
    await db.drivers.update_one({"id": driver_id}, {"$set": {"comp": current}})
    await record(db, actor=user, action="update", entity_type="driver_comp", entity_id=driver_id,
                 after=current, summary=f"Ubah kompensasi driver {drv.get('name')}")
    return {"driver_id": driver_id, "driver_name": drv.get("name"), "comp": current}


# ----------------------------------------------------------------- Payouts
@router.get("/payroll/summary")
async def payroll_summary(user=Depends(FIN)):
    return await pr.summary(get_db())


@router.get("/payroll/payouts")
async def list_payouts(driver_id: str = Query(default=None), status: str = Query(default=None),
                       user=Depends(FIN)):
    q = {}
    if driver_id:
        q["driver_id"] = driver_id
    if status:
        q["status"] = status
    docs = await get_db().driver_payouts.find(q, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return safe_doc(docs)


@router.post("/payroll/payouts/generate")
async def generate_payout(body: PayoutGenerate, user=Depends(FIN)):
    db = get_db()
    if body.period_type not in pr.PERIOD_TYPES:
        raise HTTPException(status_code=400, detail="Tipe periode tidak valid (monthly/weekly/per_trip)")
    if not body.period_start or not body.period_end or body.period_end < body.period_start:
        raise HTTPException(status_code=400, detail="Periode tidak valid (mulai ≤ selesai)")
    drv = await db.drivers.find_one({"id": body.driver_id}, {"_id": 0})
    if not drv:
        raise HTTPException(status_code=404, detail="Driver tidak ditemukan")
    # RC-06: cegah payout dgn periode TUMPANG-TINDIH (bukan hanya kecocokan persis) untuk
    # driver yang sama → trip yg sama tak dihitung di 2 payout (anti beban ganda P&L).
    dup = await db.driver_payouts.find_one({
        "driver_id": body.driver_id,
        "period_start": {"$lte": body.period_end},
        "period_end": {"$gte": body.period_start},
    })
    if dup:
        raise HTTPException(
            status_code=400,
            detail=f"Payout periode tumpang-tindih sudah ada ({dup.get('period_start')}—{dup.get('period_end')})")
    payout = await pr.build_accrual(db, drv, body.period_type, body.period_start, body.period_end)
    await db.driver_payouts.insert_one(dict(payout))
    await record(db, actor=user, action="create", entity_type="driver_payout", entity_id=payout["id"],
                 after=payout, summary=f"Generate payout {drv.get('name')} {body.period_start}—{body.period_end}")
    return safe_doc(payout)


@router.post("/payroll/payouts/generate-bulk")
async def generate_bulk(body: PayoutBulkGenerate, user=Depends(FIN)):
    db = get_db()
    if body.period_type not in pr.PERIOD_TYPES:
        raise HTTPException(status_code=400, detail="Tipe periode tidak valid (monthly/weekly/per_trip)")
    if not body.period_start or not body.period_end or body.period_end < body.period_start:
        raise HTTPException(status_code=400, detail="Periode tidak valid (mulai ≤ selesai)")
    result = await pr.bulk_generate(db, body.period_type, body.period_start, body.period_end, body.driver_ids)
    await record(db, actor=user, action="create", entity_type="driver_payout", entity_id="bulk",
                 after={"period": f"{body.period_start}—{body.period_end}", **{k: result[k] for k in ("created_count", "skipped_count")}},
                 summary=f"Generate payout massal {body.period_start}—{body.period_end}: {result['created_count']} dibuat, {result['skipped_count']} dilewati")
    return result


@router.get("/payroll/payouts/{payout_id}")
async def get_payout(payout_id: str, user=Depends(FIN)):
    doc = await get_db().driver_payouts.find_one({"id": payout_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Payout tidak ditemukan")
    return safe_doc(doc)


@router.patch("/payroll/payouts/{payout_id}")
async def update_payout(payout_id: str, body: PayoutUpdate, user=Depends(FIN)):
    db = get_db()
    doc = await db.driver_payouts.find_one({"id": payout_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Payout tidak ditemukan")
    if doc.get("status") != "draft":
        raise HTTPException(status_code=400, detail="Hanya payout berstatus draft yang bisa diubah")
    updates = body.model_dump(exclude_unset=True)
    if "bonuses" in updates and updates["bonuses"] is not None:
        doc["bonuses"] = [{"label": b.get("label", ""), "amount": float(b.get("amount") or 0)} for b in updates["bonuses"]]
    if "deductions" in updates and updates["deductions"] is not None:
        doc["deductions"] = [{"label": d.get("label", ""), "amount": float(d.get("amount") or 0)} for d in updates["deductions"]]
    if "notes" in updates and updates["notes"] is not None:
        doc["notes"] = updates["notes"]
    pr.compute_totals(doc)
    doc["updated_at"] = now_iso()
    await db.driver_payouts.update_one({"id": payout_id}, {"$set": {
        "bonuses": doc["bonuses"], "deductions": doc["deductions"], "notes": doc["notes"],
        "gross": doc["gross"], "bonus_total": doc["bonus_total"],
        "deduction_total": doc["deduction_total"], "total": doc["total"], "updated_at": doc["updated_at"],
    }})
    return safe_doc(doc)


@router.post("/payroll/payouts/{payout_id}/approve")
async def approve_payout(payout_id: str, user=Depends(FIN)):
    db = get_db()
    doc = await db.driver_payouts.find_one({"id": payout_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Payout tidak ditemukan")
    if doc.get("status") != "draft":
        raise HTTPException(status_code=400, detail="Hanya payout draft yang bisa disetujui")
    # Integrasi Finance: buat expense akrual (masuk P&L) — sekali saja.
    expense_id = doc.get("expense_id") or await pr.create_payout_expense(db, doc)
    patch = {
        "status": "approved", "approver_id": user.get("id"), "approver_name": user.get("name"),
        "approved_at": now_iso(), "expense_id": expense_id, "updated_at": now_iso(),
    }
    await db.driver_payouts.update_one({"id": payout_id}, {"$set": patch})
    await record(db, actor=user, action="approve", entity_type="driver_payout", entity_id=payout_id,
                 before=doc, after={**doc, **patch}, summary=f"Setujui payout {doc.get('driver_name')} ({doc.get('total')})")
    doc.update(patch)
    return safe_doc(doc)


@router.post("/payroll/payouts/{payout_id}/pay")
async def pay_payout(payout_id: str, user=Depends(FIN)):
    db = get_db()
    doc = await db.driver_payouts.find_one({"id": payout_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Payout tidak ditemukan")
    if doc.get("status") != "approved":
        raise HTTPException(status_code=400, detail="Payout harus disetujui sebelum dibayar")
    paid_at = now_iso()
    # Realisasi kas: tandai expense terkait sebagai lunas.
    if doc.get("expense_id"):
        await db.expenses.update_one({"id": doc["expense_id"]}, {"$set": {"paid": True, "paid_at": paid_at}})
    patch = {"status": "paid", "paid_at": paid_at, "updated_at": paid_at}
    await db.driver_payouts.update_one({"id": payout_id}, {"$set": patch})
    await record(db, actor=user, action="pay", entity_type="driver_payout", entity_id=payout_id,
                 before=doc, after={**doc, **patch}, summary=f"Bayar payout {doc.get('driver_name')} ({doc.get('total')})")
    doc.update(patch)
    return safe_doc(doc)


@router.delete("/payroll/payouts/{payout_id}")
async def delete_payout(payout_id: str, user=Depends(FIN)):
    db = get_db()
    doc = await db.driver_payouts.find_one({"id": payout_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Payout tidak ditemukan")
    if doc.get("status") != "draft":
        raise HTTPException(status_code=400, detail="Hanya payout draft yang bisa dihapus")
    await db.driver_payouts.delete_one({"id": payout_id})
    await record(db, actor=user, action="delete", entity_type="driver_payout", entity_id=payout_id,
                 before=doc, summary=f"Hapus payout draft {doc.get('driver_name')}")
    return {"deleted": True, "id": payout_id}


@router.get("/payroll/payouts/{payout_id}/slip")
async def payout_slip(payout_id: str, format: str = Query(default="pdf"), user=Depends(FIN)):
    db = get_db()
    doc = await db.driver_payouts.find_one({"id": payout_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Payout tidak ditemukan")
    company = (await db.settings.find_one({"key": "company_info"}, {"_id": 0}) or {}).get("value") or {}
    safe = safe_doc(doc)
    label = f"{safe.get('driver_name', 'driver')}-{safe.get('period_start', '')}".replace(" ", "_")
    if format == "excel":
        blob = slip_xlsx(safe, company)
        return StreamingResponse(
            BytesIO(blob),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="slip-{label}.xlsx"'})
    blob = slip_pdf(safe, company)
    return StreamingResponse(
        BytesIO(blob), media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="slip-{label}.pdf"'})
