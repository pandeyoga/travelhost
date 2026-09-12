"""routers/drivers.py — master driver: CRUD penuh (Phase 2).

List/detail: semua role login. Mutasi: owner/ops_admin.
DELETE diblokir bila driver masih terkait booking aktif.
"""
from fastapi import APIRouter, Depends, HTTPException, Query

from core_utils import hash_password, new_id, now_iso, safe_doc
from db import get_db
from dependencies import require_role, require_section
from schemas import DriverCreate, DriverUpdate
from services.audit import record
from services.refs import DRIVER_STATUSES, must_be_choice, must_exist
from services.rbac_scope import can_view_driver, scope_drivers_query
from services.trips import driver_stats

router = APIRouter(prefix="/api", tags=["drivers"])
MANAGER = require_role("owner", "ops_admin")
# RBAC-SECT-01: permukaan BACA modul ini WAJIB lewat pintu section, bukan sekadar "sudah login".
# Sebelum perbaikan ini `marketing_admin` mendapat HTTP 200 di seluruh GET di bawah (nama
# pelanggan, nominal booking, telepon sopir, posisi GPS) padahal menunya memang tidak
# pernah ditampilkan untuk peran itu — SSOT `permissions_config.SECTION_ACCESS` + FE
# `ROLE_MENU_ALLOWLIST` sama-sama mengecualikannya. Kelas bug BUG-0107 terulang: peran BARU
# (marketing_admin, lahir di FASE F) tidak pernah diuji ulang terhadap endpoint BACA LAMA.
DRIVERS = require_section("drivers")


async def _account_link(db, body, driver_id=None, driver_name="", driver_phone=""):
    """Resolusi akun login utk driver. Return dict update ({} = tidak ada perubahan).
    - account_email + account_password → buat user role=driver baru, tautkan.
    - user_id "" → lepas tautan; user_id terisi → wajib user role=driver & belum dipakai driver lain.
    """
    email = (body.account_email or "").lower().strip()
    if email:
        if not body.account_password or len(body.account_password) < 6:
            raise HTTPException(status_code=400, detail="Kata sandi akun driver minimal 6 karakter")
        if await db.users.find_one({"email": email}):
            raise HTTPException(status_code=400, detail="Email akun sudah terdaftar")
        udoc = {"id": new_id("usr"), "name": driver_name, "email": email,
                "password_hash": hash_password(body.account_password), "role": "driver",
                "phone": driver_phone or "", "status": "active", "created_at": now_iso()}
        await db.users.insert_one(udoc)
        return {"user_id": udoc["id"]}
    if body.user_id is None:
        return {}
    if body.user_id == "":
        return {"user_id": None}
    u = await db.users.find_one({"id": body.user_id, "role": "driver"}, {"_id": 0, "id": 1})
    if not u:
        raise HTTPException(status_code=400, detail="Akun login tidak ditemukan / bukan peran driver")
    other = await db.drivers.find_one({"user_id": body.user_id, "id": {"$ne": driver_id}}, {"_id": 0, "name": 1})
    if other:
        raise HTTPException(status_code=400, detail=f"Akun ini sudah terpaut ke driver '{other.get('name')}'")
    return {"user_id": body.user_id}


async def _with_accounts(db, docs):
    """Sematkan email akun login (account_email) ke tiap driver utk tabel."""
    ids = [d.get("user_id") for d in docs if d.get("user_id")]
    users = {u["id"]: u async for u in db.users.find({"id": {"$in": ids}}, {"_id": 0, "id": 1, "email": 1, "status": 1})} if ids else {}
    for d in docs:
        u = users.get(d.get("user_id"))
        d["account_email"] = u.get("email") if u else None
        d["account_status"] = u.get("status") if u else None
    return docs


@router.get("/drivers/accounts")
async def driver_accounts(user=Depends(MANAGER)):
    """Daftar user role=driver + driver_id yang sudah terpaut (utk dropdown form driver)."""
    db = get_db()
    users = await db.users.find({"role": "driver"}, {"_id": 0, "id": 1, "name": 1, "email": 1, "status": 1}).sort("name", 1).to_list(500)
    links = {d["user_id"]: d["id"] async for d in db.drivers.find({"user_id": {"$ne": None}}, {"_id": 0, "id": 1, "user_id": 1})}
    for u in users:
        u["driver_id"] = links.get(u["id"])
    return safe_doc(users)


@router.get("/drivers")
async def list_drivers(status: str = Query(default=None), limit: int = Query(default=200, le=500),
                       skip: int = Query(default=0, ge=0), user=Depends(DRIVERS)):
    query = {}
    if status:
        query["status"] = status
    # INV-RBAC-05: peran driver hanya melihat profilnya sendiri (SSOT §3 '👁️ profil sendiri').
    query = await scope_drivers_query(get_db(), user, query)
    docs = await get_db().drivers.find(query, {"_id": 0}).sort("name", 1).skip(skip).to_list(limit)
    return safe_doc(await _with_accounts(get_db(), docs))


@router.post("/drivers")
async def create_driver(body: DriverCreate, user=Depends(MANAGER)):
    db = get_db()
    doc = {
        "id": new_id("drv"), "name": body.name.strip(), "phone": body.phone or "",
        "sim_number": body.sim_number or "", "sim_expiry": body.sim_expiry,
        "status": must_be_choice(body.status, DRIVER_STATUSES,
                                 field_label="Status sopir", default="offline"),
        "current_vehicle_id": await must_exist(db, "vehicles", body.current_vehicle_id),
        "rating": float(body.rating or 0),
        "default_fee_rate": float(body.default_fee_rate) if body.default_fee_rate else None,
        "user_id": None,
        "created_at": now_iso(),
    }
    doc.update(await _account_link(db, body, None, doc["name"], doc["phone"]))
    await db.drivers.insert_one(doc)
    await record(db, actor=user, action="create", entity_type="driver", entity_id=doc["id"],
                 after=doc, summary=f"Tambah driver {doc.get('name')}")
    return safe_doc(doc)


@router.get("/drivers/{driver_id}")
async def get_driver(driver_id: str, user=Depends(DRIVERS)):
    if not await can_view_driver(get_db(), user, driver_id):
        raise HTTPException(status_code=403, detail="Akses ditolak: hanya profil Anda sendiri")
    doc = await get_db().drivers.find_one({"id": driver_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Driver tidak ditemukan")
    return safe_doc(doc)


@router.get("/drivers/{driver_id}/performance")
async def driver_performance(driver_id: str, user=Depends(DRIVERS)):
    """E9: statistik kinerja driver (total trip, total km, completion rate, revenue) + riwayat trip."""
    db = get_db()
    if not await can_view_driver(db, user, driver_id):
        raise HTTPException(status_code=403, detail="Akses ditolak: hanya profil Anda sendiri")
    if not await db.drivers.find_one({"id": driver_id}, {"_id": 0}):
        raise HTTPException(status_code=404, detail="Driver tidak ditemukan")
    stats, trips = await driver_stats(db, driver_id)
    return {"stats": stats, "trips": safe_doc(trips)}


@router.patch("/drivers/{driver_id}")
async def update_driver(driver_id: str, body: DriverUpdate, user=Depends(MANAGER)):
    db = get_db()
    before = await db.drivers.find_one({"id": driver_id}, {"_id": 0})
    if not before:
        raise HTTPException(status_code=404, detail="Driver tidak ditemukan")
    updates = {k: v for k, v in body.model_dump(exclude_unset=True).items()
               if v is not None and k not in ("user_id", "account_email", "account_password")}
    updates.update(await _account_link(db, body, driver_id,
                                       updates.get("name", before.get("name")),
                                       updates.get("phone", before.get("phone"))))
    if "rating" in updates:
        updates["rating"] = float(updates["rating"])
    if "default_fee_rate" in updates:
        # 0 = hapus rate default (kembali tanpa prefill).
        updates["default_fee_rate"] = float(updates["default_fee_rate"]) or None
    # INV-REF-01: status wajib dari daftar, dan unit yang ditempelkan ke sopir wajib NYATA
    # (audit menemukan `current_vehicle_id` hantu diterima → "sopir memegang unit" yang
    # tidak pernah ada, dan kolom armada di tabel Driver menampilkan "-" selamanya).
    if "status" in updates:
        updates["status"] = must_be_choice(updates["status"], DRIVER_STATUSES,
                                           field_label="Status sopir",
                                           default=before.get("status"))
    if "current_vehicle_id" in updates:
        updates["current_vehicle_id"] = await must_exist(db, "vehicles",
                                                        updates["current_vehicle_id"])
    if updates:
        await db.drivers.update_one({"id": driver_id}, {"$set": updates})
    doc = await db.drivers.find_one({"id": driver_id}, {"_id": 0})
    await record(db, actor=user, action="update", entity_type="driver", entity_id=driver_id,
                 before=before, after=doc, summary=f"Ubah driver {doc.get('name')}")
    return safe_doc(doc)


@router.delete("/drivers/{driver_id}")
async def delete_driver(driver_id: str, user=Depends(MANAGER)):
    db = get_db()
    if not await db.drivers.find_one({"id": driver_id}):
        raise HTTPException(status_code=404, detail="Driver tidak ditemukan")
    # Referential guard: jangan hapus driver yang masih dirujuk booking "hidup". "Aktif" HARUS
    # mencakup 'hold' (reservasi DP-gate) & 'pending' (permintaan menunggu approve) — bukan hanya
    # confirmed/ongoing. Celah lama: driver di booking 'hold'/'pending' bisa dihapus → FK menggantung
    # (booking merujuk driver yang sudah tiada). Sinkron dgn ACTIVE_BOOKING_STATUSES + pending.
    active = await db.bookings.count_documents(
        {"driver_id": driver_id, "status": {"$in": ["pending", "hold", "confirmed", "ongoing"]}}
    )
    if active:
        raise HTTPException(status_code=400,
                            detail="Driver masih ditugaskan ke booking aktif (pending/hold/confirmed/ongoing)")
    before = await db.drivers.find_one({"id": driver_id}, {"_id": 0})
    await db.drivers.delete_one({"id": driver_id})
    await record(db, actor=user, action="delete", entity_type="driver", entity_id=driver_id,
                 before=before, summary=f"Hapus driver {(before or {}).get('name')}")
    return {"deleted": True, "id": driver_id}
