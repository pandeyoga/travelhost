"""routers/transfer_routes.py — CRUD RUTE ANTAR-JEMPUT BANDARA + tarif flat.

Koleksi `transfer_routes` (id berprefiks `trt_`). Satu dokumen = satu rute (mis. "Bandung →
Soekarno-Hatta") dengan tarif FLAT per TIPE armada:

    {"rates": {"hiace_premio": 1800000, "avanza": 950000}}

Tipe armada yang TIDAK punya tarif di rute itu memang TIDAK dilayani — mesin harga
mengembalikan "tidak melayani rute ini", bukan diam-diam memakai tarif lain. Ini disengaja:
mengarang tarif adalah cacat yang sedang kita berantas, bukan kemudahan.

RBAC: tarif = permukaan Pengaturan (owner), sama seperti `pricing_rules`. Pembacaan untuk
pengunjung web lewat `/api/public/booking/config` (tanpa auth, hanya field yang perlu).
"""
from fastapi import APIRouter, Depends, HTTPException, Query

from core_utils import money, new_id, now_iso, safe_doc
from db import get_db
from dependencies import require_section
from schemas_booking import TransferRouteUpsert
from services.audit import record
from services.pricing import VEHICLE_TYPE_LABELS, type_label
from services.refs import vehicle_rates_or_400

router = APIRouter(prefix="/api", tags=["transfer-routes"])
SETTINGS = require_section("settings")


def _clean_rates(raw) -> dict:
    """Hanya tipe armada yang DIKENAL + tarif > 0 (tolak yang lain dgn 400 berALASAN).

    Catatan audit 2026-08-12: versi pertama fungsi ini MENJANJIKAN "hanya tipe armada yang
    dikenal" di docstring-nya, tetapi tidak pernah memeriksa kuncinya — `{"ngawur": 500000}`
    tersimpan apa adanya. Rute lalu tampak "sudah bertarif" di Pengaturan padahal mesin harga
    tidak akan pernah bisa menjualnya. Sekarang validasinya diturunkan dari SSOT tipe armada
    (`services/refs.vehicle_rates_or_400` → `pricing.VEHICLE_TYPE_LABELS`).
    """
    return vehicle_rates_or_400(raw)


def _public(doc: dict) -> dict:
    rates = doc.get("rates") or {}
    return {**safe_doc(doc),
            "rate_rows": [{"vehicle_type": k, "label": type_label(k), "amount": money(v)}
                          for k, v in sorted(rates.items(), key=lambda kv: money(kv[1]))],
            "from_price": min([money(v) for v in rates.values() if money(v) > 0] or [0])}


@router.get("/transfer-routes")
async def list_routes(active: str = Query(default=""), user=Depends(SETTINGS)):
    db = get_db()
    query = {}
    if active in ("true", "1"):
        query["active"] = {"$ne": False}
    elif active in ("false", "0"):
        query["active"] = False
    rows = await db.transfer_routes.find(query, {"_id": 0}).sort(
        [("position", 1), ("name", 1)]).to_list(200)
    return {"routes": [_public(r) for r in rows], "total": len(rows),
            "vehicle_type_labels": VEHICLE_TYPE_LABELS}


@router.post("/transfer-routes")
async def create_route(body: TransferRouteUpsert, user=Depends(SETTINGS)):
    db = get_db()
    rates = _clean_rates(body.rates)
    if not rates:
        raise HTTPException(status_code=400,
                            detail="Isi minimal satu tarif tipe armada agar rute bisa dijual")
    code = (body.code or "").strip().upper()[:24]
    if code and await db.transfer_routes.find_one({"code": code}, {"_id": 0, "id": 1}):
        raise HTTPException(status_code=409, detail=f"Kode rute '{code}' sudah dipakai")
    doc = {
        "id": new_id("trt"), "code": code, "name": body.name.strip()[:120],
        "from_label": body.from_label.strip()[:120], "to_label": body.to_label.strip()[:120],
        "airport_code": (body.airport_code or "").strip().upper()[:8],
        "rates": rates, "duration_minutes": int(body.duration_minutes or 180),
        "notes": (body.notes or "")[:400], "active": bool(body.active is not False),
        "position": int(body.position or 0),
        "created_at": now_iso(), "updated_at": now_iso(),
    }
    await db.transfer_routes.insert_one(dict(doc))
    await record(db, actor=user, action="create", entity_type="transfer_route",
                 entity_id=doc["id"], after=doc, summary=f"Tambah rute antar-jemput {doc['name']}")
    return _public(doc)


@router.patch("/transfer-routes/{route_id}")
async def update_route(route_id: str, body: TransferRouteUpsert, user=Depends(SETTINGS)):
    db = get_db()
    before = await db.transfer_routes.find_one({"id": route_id}, {"_id": 0})
    if not before:
        raise HTTPException(status_code=404, detail="Rute tidak ditemukan")
    rates = _clean_rates(body.rates)
    if not rates:
        raise HTTPException(status_code=400, detail="Isi minimal satu tarif tipe armada")
    code = (body.code or "").strip().upper()[:24]
    if code and await db.transfer_routes.find_one({"code": code, "id": {"$ne": route_id}},
                                                 {"_id": 0, "id": 1}):
        raise HTTPException(status_code=409, detail=f"Kode rute '{code}' sudah dipakai")
    patch = {
        "code": code, "name": body.name.strip()[:120],
        "from_label": body.from_label.strip()[:120], "to_label": body.to_label.strip()[:120],
        "airport_code": (body.airport_code or "").strip().upper()[:8], "rates": rates,
        "duration_minutes": int(body.duration_minutes or 180), "notes": (body.notes or "")[:400],
        "active": bool(body.active is not False), "position": int(body.position or 0),
        "updated_at": now_iso(),
    }
    await db.transfer_routes.update_one({"id": route_id}, {"$set": patch})
    after = await db.transfer_routes.find_one({"id": route_id}, {"_id": 0})
    await record(db, actor=user, action="update", entity_type="transfer_route",
                 entity_id=route_id, before=before, after=after,
                 summary=f"Ubah rute antar-jemput {patch['name']}")
    return _public(after)


@router.delete("/transfer-routes/{route_id}")
async def delete_route(route_id: str, user=Depends(SETTINGS)):
    """Nonaktifkan rute (soft) — booking lama tetap menyimpan `route_id` & nama rutenya."""
    db = get_db()
    before = await db.transfer_routes.find_one({"id": route_id}, {"_id": 0})
    if not before:
        raise HTTPException(status_code=404, detail="Rute tidak ditemukan")
    used = await get_db().bookings.count_documents({"route_id": route_id})
    if used:
        await db.transfer_routes.update_one({"id": route_id},
                                           {"$set": {"active": False, "updated_at": now_iso()}})
        await record(db, actor=user, action="update", entity_type="transfer_route",
                     entity_id=route_id, summary=f"Nonaktifkan rute {before.get('name')} "
                                                 f"(dipakai {used} booking)")
        return {"deactivated": True, "deleted": False, "used_by_bookings": used}
    await db.transfer_routes.delete_one({"id": route_id})
    await record(db, actor=user, action="delete", entity_type="transfer_route",
                 entity_id=route_id, before=before,
                 summary=f"Hapus rute antar-jemput {before.get('name')}")
    return {"deleted": True, "deactivated": False, "used_by_bookings": 0}
