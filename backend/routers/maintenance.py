"""routers/maintenance.py — Maintenance armada (Phase 6).

Dokumen & servis: jadwal/riwayat servis + window perawatan yang MEMBLOK availability
(INV-21) + reminder KIR/pajak/servis (H-30/14/7/overdue).
List/detail: semua role login (driver read-only). Mutasi: owner/ops_admin.
Urutan rute: literal (/reminders, /summary) sebelum /{maintenance_id}.
"""
from fastapi import APIRouter, Depends, HTTPException, Query

from core_utils import money, new_id, now_iso, safe_doc
from db import get_db
from dependencies import require_role, require_section
from schemas import MaintenanceComplete, MaintenanceCreate, MaintenanceUpdate
from services.audit import record
from services.refs import must_exist
from services.availability import (
    MAINT_BLOCKING_STATUSES,
    find_conflicts,
    vehicle_lock,
)
from services.maintenance import (
    MAINT_STATUSES,
    MAINT_TYPES,
    build_doc_reminders,
    derive_status,
    summary,
)
from services import preventive as preventive_svc

router = APIRouter(prefix="/api", tags=["maintenance"])
MANAGER = require_role("owner", "ops_admin")
# RBAC-SECT-01: permukaan BACA modul ini WAJIB lewat pintu section, bukan sekadar "sudah login".
# Sebelum perbaikan ini `marketing_admin` mendapat HTTP 200 di seluruh GET di bawah (nama
# pelanggan, nominal booking, telepon sopir, posisi GPS) padahal menunya memang tidak
# pernah ditampilkan untuk peran itu — SSOT `permissions_config.SECTION_ACCESS` + FE
# `ROLE_MENU_ALLOWLIST` sama-sama mengecualikannya. Kelas bug BUG-0107 terulang: peran BARU
# (marketing_admin, lahir di FASE F) tidak pernah diuji ulang terhadap endpoint BACA LAMA.
MAINT = require_section("maintenance")


async def _vehicle_or_400(db, vehicle_id):
    v = await db.vehicles.find_one({"id": vehicle_id}, {"_id": 0})
    if not v:
        raise HTTPException(status_code=400, detail="Armada tidak ditemukan")
    return v


async def _restore_vehicle_if_free(db, vehicle_id, exclude_id=None):
    """Kembalikan armada 'available' HANYA bila tak ada perawatan in_progress LAIN.

    Cacat logic lama: selesai/hapus/ubah SATU catatan langsung memulihkan armada padahal
    catatan in_progress lain utk armada yang sama masih berjalan → status armada tidak
    sinkron dgn kenyataan bengkel (armada 'available' padahal masih dibongkar)."""
    q = {"vehicle_id": vehicle_id, "status": "in_progress"}
    if exclude_id:
        q["id"] = {"$ne": exclude_id}
    if await db.maintenance_records.find_one(q, {"_id": 0, "id": 1}):
        return False
    veh = await db.vehicles.find_one({"id": vehicle_id}, {"_id": 0, "status": 1})
    if veh and veh.get("status") == "maintenance":
        await db.vehicles.update_one({"id": vehicle_id}, {"$set": {"status": "available"}})
    return True


def _blocking_window(status, start_date, end_date) -> bool:
    """True bila window perawatan ini MEMBLOK ketersediaan armada (INV-21)."""
    return bool(status in MAINT_BLOCKING_STATUSES and start_date and end_date)


async def _assert_no_departure_clash(db, vehicle_id, start_date, end_date, veh_name=""):
    """INV-21 (arah sebaliknya): window perawatan TIDAK boleh menabrak keberangkatan AKTIF.

    Celah lama (terbukti di POC `test_core_conflict.py`): jalur booking sudah menolak armada
    yang sedang dirawat, tetapi jalur perawatan TIDAK memeriksa booking — sehingga ops bisa
    menjadwalkan perawatan di atas keberangkatan yang sudah dikonfirmasi (invariant INV-21
    jadi merah & armada dobel-pakai di lapangan). Sekarang ditolak keras (400).
    """
    conflicts = await find_conflicts(db, vehicle_id, start_date, end_date)
    if conflicts:
        codes = ", ".join(c.get("code", c.get("id")) for c in conflicts[:5])
        raise HTTPException(
            status_code=400,
            detail=f"Perawatan bertabrakan dengan keberangkatan aktif: {codes}. "
                   f"Jadwalkan ulang keberangkatan tersebut dulu, atau ubah tanggal perawatan.")


@router.get("/maintenance")
async def list_maintenance(vehicle_id: str = Query(default=None), status: str = Query(default=None),
                           type: str = Query(default=None), limit: int = Query(default=300, le=1000),
                           skip: int = Query(default=0, ge=0), user=Depends(MAINT)):
    query = {}
    if vehicle_id:
        query["vehicle_id"] = vehicle_id
    if status:
        query["status"] = status
    if type:
        query["type"] = type
    docs = await get_db().maintenance_records.find(query, {"_id": 0}).sort(
        "scheduled_date", -1).skip(skip).to_list(limit)
    return safe_doc(docs)


@router.get("/maintenance/reminders")
async def maintenance_reminders(user=Depends(MAINT)):
    """Reminder dokumen armada (KIR/pajak/servis) due-soon + overdue dgn bucket urgensi."""
    reminders = await build_doc_reminders(get_db())
    return {
        "reminders": reminders,
        "total": len(reminders),
        "overdue": sum(1 for r in reminders if r.get("overdue")),
    }


@router.get("/maintenance/summary")
async def maintenance_summary(user=Depends(MAINT)):
    return await summary(get_db())


@router.get("/maintenance/preventive")
async def preventive_list(user=Depends(MAINT)):
    """Servis preventif terjadwal — status jatuh tempo per armada (km + waktu)."""
    db = get_db()
    items = await preventive_svc.list_preventive(db)
    return {"items": items, "summary": await preventive_svc.summary(db)}


@router.post("/maintenance/preventive/{vehicle_id}/schedule")
async def preventive_schedule(vehicle_id: str, user=Depends(MANAGER)):
    """Buat catatan perawatan 'servis' terjadwal dari interval preventif armada."""
    db = get_db()
    veh = await _vehicle_or_400(db, vehicle_id)
    plan = preventive_svc.vehicle_preventive(veh)
    if not plan:
        raise HTTPException(status_code=400,
                            detail="Armada belum punya interval servis — atur interval dulu")
    sched = (plan.get("date") or {}).get("due_date") or now_iso()
    doc = {
        "id": new_id("mnt"), "vehicle_id": vehicle_id, "vehicle_name": veh.get("name"),
        "type": "servis", "title": "Servis preventif berkala",
        "description": "Dibuat otomatis dari modul Servis Preventif (interval km/waktu).",
        "scheduled_date": sched, "start_date": None, "end_date": None,
        "odometer": float(veh.get("odometer") or 0), "cost": 0,
        "workshop": "", "workshop_id": None, "status": "scheduled",
        "note": f"Status preventif saat dibuat: {plan.get('status')}.",
        "completed_at": None, "created_by": user["id"], "created_at": now_iso(),
    }
    await db.maintenance_records.insert_one(doc)
    await record(db, actor=user, action="create", entity_type="maintenance", entity_id=doc["id"],
                 after=doc, summary=f"Jadwalkan servis preventif {veh.get('name')}")
    return safe_doc(doc)


@router.post("/maintenance")
async def create_maintenance(body: MaintenanceCreate, user=Depends(MANAGER)):
    db = get_db()
    veh = await _vehicle_or_400(db, body.vehicle_id)
    mtype = body.type if body.type in MAINT_TYPES else "lainnya"
    if body.type and body.type not in MAINT_TYPES:
        # E10: izinkan jenis service custom yang aktif (key terdaftar di service_types)
        if await db.service_types.find_one({"key": body.type, "active": True}, {"_id": 0, "key": 1}):
            mtype = body.type
    status = body.status if body.status in MAINT_STATUSES else "scheduled"
    workshop_name = (body.workshop or "").strip()
    # INV-REF-01: bengkel yang dipilih WAJIB ada di koleksi `workshops`. Audit menemukan
    # `workshop_id` hantu diterima (HTTP 200) → riwayat servis menunjuk bengkel yang tidak
    # pernah ada; nama bengkel di tabel & PDF kosong tanpa penjelasan.
    workshop_id = await must_exist(db, "workshops", body.workshop_id)
    if workshop_id and not workshop_name:
        w = await db.workshops.find_one({"id": workshop_id}, {"_id": 0, "name": 1})
        workshop_name = (w or {}).get("name", "")
    doc = {
        "id": new_id("mnt"), "vehicle_id": body.vehicle_id, "vehicle_name": veh.get("name"),
        "type": mtype, "title": (body.title or "").strip() or mtype.capitalize(),
        "description": body.description or "",
        "scheduled_date": body.scheduled_date, "start_date": body.start_date, "end_date": body.end_date,
        "odometer": float(body.odometer or 0), "cost": money(body.cost),
        "workshop": workshop_name, "workshop_id": workshop_id, "status": status, "note": body.note or "",
        "completed_at": None, "created_by": user["id"], "created_at": now_iso(),
    }
    # INV-21: window yang memblok ketersediaan wajib bebas dari keberangkatan aktif.
    # RC-16 (anti-TOCTOU): cek-final + insert diserialkan per armada (mutex sama dengan jalur
    # booking) agar tidak ada balapan "booking baru masuk tepat saat perawatan ditulis".
    if _blocking_window(status, body.start_date, body.end_date):
        async with vehicle_lock(db, body.vehicle_id):
            await _assert_no_departure_clash(db, body.vehicle_id, body.start_date, body.end_date,
                                             veh.get("name"))
            await db.maintenance_records.insert_one(doc)
    else:
        await db.maintenance_records.insert_one(doc)
    # Bila window in_progress aktif → tandai armada 'maintenance'.
    if status == "in_progress":
        await db.vehicles.update_one({"id": body.vehicle_id}, {"$set": {"status": "maintenance"}})
    await record(db, actor=user, action="create", entity_type="maintenance", entity_id=doc["id"],
                 after=doc, summary=f"Tambah perawatan {doc.get('title')} ({veh.get('name')})")
    return safe_doc(doc)


@router.get("/maintenance/{maintenance_id}")
async def get_maintenance(maintenance_id: str, user=Depends(MAINT)):
    doc = await get_db().maintenance_records.find_one({"id": maintenance_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Catatan perawatan tidak ditemukan")
    return safe_doc(doc)


@router.patch("/maintenance/{maintenance_id}")
async def update_maintenance(maintenance_id: str, body: MaintenanceUpdate, user=Depends(MANAGER)):
    db = get_db()
    rec = await db.maintenance_records.find_one({"id": maintenance_id}, {"_id": 0})
    if not rec:
        raise HTTPException(status_code=404, detail="Catatan perawatan tidak ditemukan")
    updates = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    if "type" in updates and updates["type"] not in MAINT_TYPES:
        updates["type"] = "lainnya"
    if "status" in updates and updates["status"] not in MAINT_STATUSES:
        raise HTTPException(status_code=400, detail="Status perawatan tidak valid")
    if "odometer" in updates:
        updates["odometer"] = float(updates["odometer"])
    if "cost" in updates:
        updates["cost"] = money(updates["cost"])
    # INV-21: re-validasi dgn NILAI EFEKTIF (gabungan rec + updates) — pola sama seperti
    # R6-1 di /subcharters: PATCH tak boleh jadi pintu belakang membuat tabrakan.
    eff_status = updates.get("status", rec.get("status"))
    eff_start = updates.get("start_date", rec.get("start_date"))
    eff_end = updates.get("end_date", rec.get("end_date"))
    if updates and _blocking_window(eff_status, eff_start, eff_end):
        async with vehicle_lock(db, rec["vehicle_id"]):
            await _assert_no_departure_clash(db, rec["vehicle_id"], eff_start, eff_end,
                                             rec.get("vehicle_name"))
            await db.maintenance_records.update_one({"id": maintenance_id}, {"$set": updates})
    elif updates:
        await db.maintenance_records.update_one({"id": maintenance_id}, {"$set": updates})
    doc = await db.maintenance_records.find_one({"id": maintenance_id}, {"_id": 0})
    # Sinkronkan status armada bila window berubah.
    if doc.get("status") == "in_progress":
        await db.vehicles.update_one({"id": doc["vehicle_id"]}, {"$set": {"status": "maintenance"}})
    elif doc.get("status") in ("done", "cancelled"):
        await _restore_vehicle_if_free(db, doc["vehicle_id"], exclude_id=maintenance_id)
    await record(db, actor=user, action="update", entity_type="maintenance", entity_id=maintenance_id,
                 before=rec, after=doc, summary=f"Ubah perawatan {doc.get('title')}")
    return safe_doc(doc)


@router.post("/maintenance/{maintenance_id}/complete")
async def complete_maintenance(maintenance_id: str, body: MaintenanceComplete, user=Depends(MANAGER)):
    db = get_db()
    rec = await db.maintenance_records.find_one({"id": maintenance_id}, {"_id": 0})
    if not rec:
        raise HTTPException(status_code=404, detail="Catatan perawatan tidak ditemukan")
    completed_at = body.completed_at or now_iso()
    updates = {"status": "done", "completed_at": completed_at}
    if body.cost is not None:
        updates["cost"] = money(body.cost)
    if body.note:
        updates["note"] = body.note
    await db.maintenance_records.update_one({"id": maintenance_id}, {"$set": updates})
    # Update armada: kembalikan available (bila tak ada perawatan aktif lain) + catat servis terakhir.
    await _restore_vehicle_if_free(db, rec["vehicle_id"], exclude_id=maintenance_id)
    veh_updates = {}
    if rec.get("type") == "servis":
        veh_updates["last_service_date"] = completed_at
        if body.odometer is not None:
            veh_updates["odometer"] = float(body.odometer)
    if veh_updates:
        await db.vehicles.update_one({"id": rec["vehicle_id"]}, {"$set": veh_updates})
    doc = await db.maintenance_records.find_one({"id": maintenance_id}, {"_id": 0})
    await record(db, actor=user, action="complete", entity_type="maintenance", entity_id=maintenance_id,
                 summary=f"Selesaikan perawatan {doc.get('title')} ({doc.get('vehicle_name')})")
    return safe_doc(doc)


@router.delete("/maintenance/{maintenance_id}")
async def delete_maintenance(maintenance_id: str, user=Depends(MANAGER)):
    db = get_db()
    rec = await db.maintenance_records.find_one({"id": maintenance_id}, {"_id": 0})
    if not rec:
        raise HTTPException(status_code=404, detail="Catatan perawatan tidak ditemukan")
    await db.maintenance_records.delete_one({"id": maintenance_id})
    # Bila armada masih 'maintenance' & tak ada perawatan in_progress lain → available.
    await _restore_vehicle_if_free(db, rec["vehicle_id"], exclude_id=maintenance_id)
    await record(db, actor=user, action="delete", entity_type="maintenance", entity_id=maintenance_id,
                 before=rec, summary=f"Hapus perawatan {rec.get('title')} ({rec.get('vehicle_name')})")
    return {"deleted": True, "id": maintenance_id}
