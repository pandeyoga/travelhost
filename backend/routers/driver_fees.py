"""routers/driver_fees.py — fee driver PER KEBERANGKATAN + pencairan (withdrawal).

Alur:
  1) Rate fee /hari ditetapkan saat ASSIGN dispatch (boleh beda tiap keberangkatan)
     → tersimpan di trip (driver_fee_rate/days/total).
  2) Saat trip SELESAI, fee dikreditkan otomatis ke saldo driver
     (services.trips.finalize_trip_completion → koleksi driver_fee_entries, idempotent per trip).
  3) Driver mengajukan PENCAIRAN (≤ saldo tersedia; saldo langsung DIRESERVASI).
  4) Finance MEMBAYAR — WAJIB unggah bukti transfer → expense kategori gaji_driver (paid)
     → saldo berkurang permanen. TOLAK mengembalikan saldo.

Saldo tersedia = total fee earned − dicairkan (paid) − sedang diajukan (requested).
Section: permukaan driver 'driver-workspace' (owner/ops_admin boleh atas nama driver),
permukaan finance 'finance'.
"""
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile

from core_utils import money, new_id, now_iso, safe_doc
from db import get_db
from dependencies import require_section
from schemas_ops import WithdrawCreate, WithdrawReject
from services import media_lib as ml
from services import media_store as ms
from services.audit import record

router = APIRouter(prefix="/api", tags=["driver-fees"])
WORKSPACE = require_section("driver-workspace")
FIN = require_section("finance")


async def _target_driver(db, user, driver_id=None):
    """Driver efektif: owner/ops_admin boleh menunjuk driver lain via driver_id."""
    if driver_id and user.get("role") in ("owner", "ops_admin"):
        return await db.drivers.find_one({"id": driver_id}, {"_id": 0})
    from services.rbac_scope import resolve_driver
    return await resolve_driver(db, user)


async def _fee_numbers(db, driver_id):
    entries = await db.driver_fee_entries.find({"driver_id": driver_id}, {"_id": 0, "amount": 1}).to_list(5000)
    wds = await db.driver_withdrawals.find({"driver_id": driver_id}, {"_id": 0, "amount": 1, "status": 1}).to_list(2000)
    earned = money(sum(float(e.get("amount") or 0) for e in entries))
    paid = money(sum(float(w.get("amount") or 0) for w in wds if w.get("status") == "paid"))
    requested = money(sum(float(w.get("amount") or 0) for w in wds if w.get("status") == "requested"))
    return {"earned_total": earned, "paid_total": paid, "requested_total": requested,
            "available": money(earned - paid - requested)}


@router.get("/driver/fees")
async def my_fees(driver_id: str = Query(default=None), user=Depends(WORKSPACE)):
    db = get_db()
    drv = await _target_driver(db, user, driver_id)
    if not drv:
        return {"is_driver": False, "earned_total": 0, "paid_total": 0, "requested_total": 0,
                "available": 0, "entries": [], "withdrawals": []}
    nums = await _fee_numbers(db, drv["id"])
    entries = await db.driver_fee_entries.find({"driver_id": drv["id"]}, {"_id": 0}).sort("created_at", -1).to_list(50)
    wds = await db.driver_withdrawals.find({"driver_id": drv["id"]}, {"_id": 0}).sort("created_at", -1).to_list(50)
    return {"is_driver": True, "driver_id": drv["id"], "driver_name": drv.get("name"),
            **nums, "entries": safe_doc(entries), "withdrawals": safe_doc(wds)}


@router.post("/driver/fees/withdraw")
async def request_withdraw(body: WithdrawCreate, user=Depends(WORKSPACE)):
    db = get_db()
    drv = await _target_driver(db, user, body.driver_id)
    if not drv:
        raise HTTPException(status_code=403, detail="Akun Anda belum tertaut ke data driver")
    amount = money(body.amount)
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Nominal pencairan harus lebih dari 0")
    nums = await _fee_numbers(db, drv["id"])
    if amount > nums["available"]:
        raise HTTPException(status_code=400,
                            detail=f"Saldo tersedia hanya Rp {int(nums['available']):,}".replace(",", "."))
    doc = {
        "id": new_id("wdr"), "driver_id": drv["id"], "driver_name": drv.get("name"),
        "amount": amount, "bank_name": body.bank_name.strip(),
        "account_number": body.account_number.strip(), "account_name": body.account_name.strip(),
        "note": (body.note or "").strip(), "status": "requested",
        "requested_by": user.get("id"), "proof_url": None, "expense_id": None,
        "created_at": now_iso(), "updated_at": now_iso(),
    }
    await db.driver_withdrawals.insert_one(dict(doc))
    await record(db, actor=user, action="create", entity_type="driver_withdrawal", entity_id=doc["id"],
                 after=doc, summary=f"Pengajuan pencairan fee {drv.get('name')} Rp {int(amount):,}".replace(",", "."))
    return safe_doc(doc)


# ----------------------------------------------------------------- sisi FINANCE
@router.get("/payroll/fee-balances")
async def fee_balances(user=Depends(FIN)):
    db = get_db()
    ids = set(await db.driver_fee_entries.distinct("driver_id"))
    ids.update(await db.driver_withdrawals.distinct("driver_id"))
    out = []
    for did in ids:
        drv = await db.drivers.find_one({"id": did}, {"_id": 0, "name": 1})
        nums = await _fee_numbers(db, did)
        out.append({"driver_id": did, "driver_name": (drv or {}).get("name") or did, **nums})
    out.sort(key=lambda r: -r["available"])
    return safe_doc(out)


@router.get("/payroll/withdrawals")
async def list_withdrawals(status: str = Query(default=None), user=Depends(FIN)):
    q = {"status": status} if status else {}
    docs = await get_db().driver_withdrawals.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)
    return safe_doc(docs)


@router.post("/payroll/withdrawals/{withdrawal_id}/pay")
async def pay_withdrawal(withdrawal_id: str, proof: UploadFile = File(...),
                         note: str = Form(default=""), user=Depends(FIN)):
    db = get_db()
    doc = await db.driver_withdrawals.find_one({"id": withdrawal_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Pengajuan pencairan tidak ditemukan")
    if doc.get("status") != "requested":
        raise HTTPException(status_code=400, detail="Hanya pengajuan berstatus 'requested' yang bisa dibayar")
    blob = await proof.read()
    if not blob:
        raise HTTPException(status_code=400, detail="Bukti transfer wajib diunggah")
    # INV-MEDIA-03: penulisan berkas SATU PINTU via media_store (validasi MIME/ukuran/path).
    try:
        meta = ms.upload_bytes(blob, (proof.content_type or "").lower(),
                               filename=proof.filename or "bukti-transfer", folder="withdrawals")
    except ms.MediaError as exc:
        raise HTTPException(status_code=400, detail=f"Bukti transfer ditolak: {exc}") from None
    asset = await ml.register_asset(db, meta, user, folder_id="", alt="Bukti transfer pencairan fee",
                                    source="withdrawal")
    proof_url = ml.public_doc(asset).get("url")
    paid_at = now_iso()
    # ATOMIK anti double-pay: klaim status requested→paid dgn compare-and-set DULU,
    # baru catat expense — dua kasir paralel tak mungkin sama-sama membayar.
    patch = {"status": "paid", "paid_at": paid_at, "paid_by": user.get("id"),
             "paid_by_name": user.get("name"), "proof_url": proof_url,
             "admin_note": (note or "").strip(), "updated_at": paid_at}
    claim = await db.driver_withdrawals.update_one(
        {"id": withdrawal_id, "status": "requested"}, {"$set": patch})
    if not claim.modified_count:
        raise HTTPException(status_code=400, detail="Pengajuan sudah diproses (dibayar/ditolak) oleh pengguna lain")
    # Integrasi keuangan: expense kategori gaji_driver, langsung realisasi kas (paid).
    exp = {
        "id": new_id("exp"), "booking_id": None, "trip_id": None,
        "category": "gaji_driver", "amount": money(doc["amount"]),
        "note": f"Pencairan fee driver {doc.get('driver_name')} ({withdrawal_id})",
        "withdrawal_id": withdrawal_id, "driver_id": doc.get("driver_id"),
        "paid": True, "paid_at": paid_at, "created_at": paid_at,
    }
    await db.expenses.insert_one(dict(exp))
    await db.driver_withdrawals.update_one({"id": withdrawal_id}, {"$set": {"expense_id": exp["id"]}})
    patch["expense_id"] = exp["id"]
    await record(db, actor=user, action="pay", entity_type="driver_withdrawal", entity_id=withdrawal_id,
                 before=doc, after={**doc, **patch},
                 summary=f"Bayar pencairan fee {doc.get('driver_name')} Rp {int(doc['amount']):,}".replace(",", "."))
    doc.update(patch)
    return safe_doc(doc)


@router.post("/payroll/withdrawals/{withdrawal_id}/reject")
async def reject_withdrawal(withdrawal_id: str, body: WithdrawReject, user=Depends(FIN)):
    db = get_db()
    doc = await db.driver_withdrawals.find_one({"id": withdrawal_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Pengajuan pencairan tidak ditemukan")
    if doc.get("status") != "requested":
        raise HTTPException(status_code=400, detail="Hanya pengajuan berstatus 'requested' yang bisa ditolak")
    patch = {"status": "rejected", "reject_reason": body.reason.strip(),
             "rejected_by": user.get("id"), "updated_at": now_iso()}
    await db.driver_withdrawals.update_one({"id": withdrawal_id}, {"$set": patch})
    await record(db, actor=user, action="reject", entity_type="driver_withdrawal", entity_id=withdrawal_id,
                 before=doc, after={**doc, **patch},
                 summary=f"Tolak pencairan fee {doc.get('driver_name')}: {body.reason.strip()[:80]}")
    doc.update(patch)
    return safe_doc(doc)
