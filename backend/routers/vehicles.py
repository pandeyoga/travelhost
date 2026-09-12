"""routers/vehicles.py — master armada: CRUD penuh (Phase 2).

List/detail: semua role login (driver read-only). Mutasi: owner/ops_admin.
DELETE diblokir bila armada masih terkait booking (guard RC-13, jaga FK).
"""
from fastapi import APIRouter, Depends, HTTPException, Query

from core_utils import new_id, now_iso, safe_doc
from db import get_db
from dependencies import require_role, require_section
from schemas import VehicleCreate, VehicleUpdate
from services.audit import record
from services.refs import (VEHICLE_OWNERSHIPS, VEHICLE_STATUSES, must_be_choice,
                           vehicle_type_or_400)
from services.trips import vehicle_stats

router = APIRouter(prefix="/api", tags=["vehicles"])
MANAGER = require_role("owner", "ops_admin")
# RBAC-SECT-01: permukaan BACA modul ini WAJIB lewat pintu section, bukan sekadar "sudah login".
# Sebelum perbaikan ini `marketing_admin` mendapat HTTP 200 di seluruh GET di bawah (nama
# pelanggan, nominal booking, telepon sopir, posisi GPS) padahal menunya memang tidak
# pernah ditampilkan untuk peran itu — SSOT `permissions_config.SECTION_ACCESS` + FE
# `ROLE_MENU_ALLOWLIST` sama-sama mengecualikannya. Kelas bug BUG-0107 terulang: peran BARU
# (marketing_admin, lahir di FASE F) tidak pernah diuji ulang terhadap endpoint BACA LAMA.
VEHICLES = require_section("vehicles")


async def _next_code(db):
    codes = set(await db.vehicles.distinct("code"))
    n = 1
    while f"V-{n:02d}" in codes:
        n += 1
    return f"V-{n:02d}"


@router.get("/vehicles")
async def list_vehicles(status: str = Query(default=None), limit: int = Query(default=200, le=500),
                        skip: int = Query(default=0, ge=0), user=Depends(VEHICLES)):
    db = get_db()
    query = {}
    if status:
        query["status"] = status
    docs = await db.vehicles.find(query, {"_id": 0}).sort("code", 1).skip(skip).to_list(limit)
    # Tabel Armada menampilkan pemilik unit mitra. Tanpa penambahan NAMA di sini, kolomnya
    # hanya bisa menulis "Mitra" tanpa menyebut siapa — informasi yang justru dibutuhkan saat
    # menagih/meminjam unit. Satu query untuk semua (bukan N+1).
    partner_ids = [d.get("partner_id") for d in docs if d.get("partner_id")]
    names = {}
    if partner_ids:
        for p in await db.partners.find({"id": {"$in": list(set(partner_ids))}},
                                       {"_id": 0, "id": 1, "name": 1}).to_list(200):
            names[p["id"]] = p.get("name") or ""
    for d in docs:
        if d.get("partner_id"):
            d["partner_name"] = names.get(d["partner_id"], "")
    return safe_doc(docs)


@router.post("/vehicles")
async def create_vehicle(body: VehicleCreate, user=Depends(MANAGER)):
    db = get_db()
    plate = (body.plate_number or "").strip()
    if plate and await db.vehicles.find_one({"plate_number": plate}):
        raise HTTPException(status_code=400, detail="Nomor plat sudah terdaftar")
    if body.partner_id and not await db.partners.find_one({"id": body.partner_id}, {"_id": 1}):
        raise HTTPException(status_code=400, detail="Mitra tidak ditemukan")
    # INV-REF-01: pilihan WAJIB dari daftar yang benar-benar dipakai runtime. `type` diambil
    # dari SSOT mesin harga (VEHICLE_TYPE_LABELS) — tipe di luar daftar membuat unit tak punya
    # tarif; `ownership` di luar daftar membuat unit HILANG dari katalog publik tanpa pesan.
    vtype = vehicle_type_or_400(body.type, default="hiace")
    vstatus = must_be_choice(body.status, VEHICLE_STATUSES, field_label="Status armada",
                             default="available")
    vown = must_be_choice(body.ownership, VEHICLE_OWNERSHIPS, field_label="Kepemilikan",
                          default="owned")
    if vown == "partner" and not body.partner_id:
        raise HTTPException(status_code=400,
                            detail="Unit milik mitra wajib memilih mitranya (partner_id)")
    doc = {
        "id": new_id("veh"), "code": (body.code or "").strip() or await _next_code(db),
        "name": body.name.strip(), "plate_number": plate, "type": vtype,
        "capacity": int(body.capacity or 0), "status": vstatus,
        "kir_expiry": body.kir_expiry, "tax_expiry": body.tax_expiry,
        "last_service_date": body.last_service_date, "next_service_date": body.next_service_date,
        "odometer": float(body.odometer or 0), "features": body.features or [],
        "photos": body.photos or [], "gallery": body.gallery or [],
        "tour_scenes": body.tour_scenes or [], "specs": body.specs or [],
        "highlights": body.highlights or [], "year": body.year, "color": body.color,
        # RC-B (INV-PRICE-02): tarif per unit TIDAK ditulis dari form armada.
        # Unit baru lahir tanpa override (0 = pakai tarif tipe); ubah via Master Harga.
        "price_from": None,
        "day_rate": 0,
        "publish_to_web": bool(body.publish_to_web is not False),
        "ownership": vown,
        "partner_id": body.partner_id or None,
        "notes": body.notes or "", "created_at": now_iso(),
    }
    await db.vehicles.insert_one(doc)
    await record(db, actor=user, action="create", entity_type="vehicle", entity_id=doc["id"],
                 after=doc, summary=f"Tambah armada {doc.get('name')} ({doc.get('code')})")
    return safe_doc(doc)


@router.get("/vehicles/{vehicle_id}")
async def get_vehicle(vehicle_id: str, user=Depends(VEHICLES)):
    doc = await get_db().vehicles.find_one({"id": vehicle_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Kendaraan tidak ditemukan")
    return safe_doc(doc)


@router.get("/vehicles/{vehicle_id}/trips")
async def vehicle_trips(vehicle_id: str, user=Depends(VEHICLES)):
    """E9: riwayat trip per armada + total (trip, km, revenue)."""
    db = get_db()
    if not await db.vehicles.find_one({"id": vehicle_id}, {"_id": 0}):
        raise HTTPException(status_code=404, detail="Kendaraan tidak ditemukan")
    totals, trips = await vehicle_stats(db, vehicle_id)
    return {"totals": totals, "trips": safe_doc(trips)}


@router.get("/vehicles/{vehicle_id}/maintenance")
async def vehicle_maintenance(vehicle_id: str, user=Depends(VEHICLES)):
    """E10: riwayat service per armada + total biaya + jadwal servis berikutnya."""
    db = get_db()
    veh = await db.vehicles.find_one({"id": vehicle_id}, {"_id": 0})
    if not veh:
        raise HTTPException(status_code=404, detail="Kendaraan tidak ditemukan")
    recs = await db.maintenance_records.find({"vehicle_id": vehicle_id}, {"_id": 0}).sort("created_at", -1).to_list(500)
    done_cost = round(sum(float(m.get("cost") or 0) for m in recs if m.get("status") == "done"), 2)
    totals = {
        "count": len(recs), "total_cost": done_cost,
        "done": sum(1 for m in recs if m.get("status") == "done"),
        "next_service_date": veh.get("next_service_date"),
        "last_service_date": veh.get("last_service_date"),
    }
    return {"totals": totals, "records": safe_doc(recs)}


@router.patch("/vehicles/{vehicle_id}")
async def update_vehicle(vehicle_id: str, body: VehicleUpdate, user=Depends(MANAGER)):
    db = get_db()
    before = await db.vehicles.find_one({"id": vehicle_id}, {"_id": 0})
    if not before:
        raise HTTPException(status_code=404, detail="Kendaraan tidak ditemukan")
    updates = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    if "plate_number" in updates:
        plate = updates["plate_number"].strip()
        clash = await db.vehicles.find_one({"plate_number": plate, "id": {"$ne": vehicle_id}})
        if clash:
            raise HTTPException(status_code=400, detail="Nomor plat sudah dipakai armada lain")
        updates["plate_number"] = plate
    if updates.get("partner_id") and not await db.partners.find_one({"id": updates["partner_id"]}, {"_id": 1}):
        raise HTTPException(status_code=400, detail="Mitra tidak ditemukan")
    # INV-REF-01: jalur UBAH sama rawannya dengan jalur BUAT (audit menemukan PATCH menerima
    # type/status/ownership 'ngawur' walau POST-nya nanti dijaga).
    if "type" in updates:
        updates["type"] = vehicle_type_or_400(updates["type"], default=before.get("type"))
    if "status" in updates:
        # Status operasional dimiliki modul trip/maintenance — master data hanya lifecycle.
        if updates["status"] in ("on_trip", "maintenance"):
            raise HTTPException(status_code=400,
                                detail="Status 'on_trip'/'maintenance' diatur otomatis oleh trip & Maintenance, bukan dari master data")
        updates["status"] = must_be_choice(updates["status"], VEHICLE_STATUSES,
                                           field_label="Status armada",
                                           default=before.get("status"))
    if "ownership" in updates:
        updates["ownership"] = must_be_choice(updates["ownership"], VEHICLE_OWNERSHIPS,
                                               field_label="Kepemilikan",
                                               default=before.get("ownership"))
        if updates["ownership"] == "partner" and not (updates.get("partner_id")
                                                     or before.get("partner_id")):
            raise HTTPException(status_code=400,
                                detail="Unit milik mitra wajib memilih mitranya (partner_id)")
    if "capacity" in updates:
        updates["capacity"] = int(updates["capacity"])
    if "odometer" in updates:
        updates["odometer"] = float(updates["odometer"])
    # `publish_to_web` = False adalah nilai SAH (sembunyikan dari web); filter `is not None`
    # di atas sudah membuangnya, jadi ambil ulang dari body agar toggle "matikan" berfungsi.
    if body.publish_to_web is not None:
        updates["publish_to_web"] = bool(body.publish_to_web)
    if updates:
        await db.vehicles.update_one({"id": vehicle_id}, {"$set": updates})
    doc = await db.vehicles.find_one({"id": vehicle_id}, {"_id": 0})
    await record(db, actor=user, action="update", entity_type="vehicle", entity_id=vehicle_id,
                 before=before, after=doc, summary=f"Ubah armada {doc.get('name')} ({doc.get('code')})")
    return safe_doc(doc)


@router.delete("/vehicles/{vehicle_id}")
async def delete_vehicle(vehicle_id: str, user=Depends(MANAGER)):
    db = get_db()
    before = await db.vehicles.find_one({"id": vehicle_id}, {"_id": 0})
    if not before:
        raise HTTPException(status_code=404, detail="Kendaraan tidak ditemukan")
    if await db.bookings.count_documents({"vehicle_id": vehicle_id}):
        raise HTTPException(status_code=400, detail="Armada masih terkait booking — tidak bisa dihapus")
    await db.vehicles.delete_one({"id": vehicle_id})
    await record(db, actor=user, action="delete", entity_type="vehicle", entity_id=vehicle_id,
                 before=before, summary=f"Hapus armada {before.get('name')} ({before.get('code')})")
    return {"deleted": True, "id": vehicle_id}
