"""routers/pricing.py — Pricing Engine endpoint internal (Phase 9 / B1) + MASTER HARGA (RC-B).

Dipakai Booking wizard untuk auto-hitung harga (rincian transparan) sebelum simpan.
Sumber tarif = settings.pricing_rules + vehicles.day_rate (services.pricing.resolve_day_rate).

RC-A (BUG-0132): dulu /pricing/quote hanya me-resolve TIPE armada dan mengabaikan
`vehicles.day_rate` (tarif per unit), padahal mesin yang menagih (create_booking/approve,
web publik) memakai `resolve_day_rate` — angka yang DILIHAT ops saat "Hitung Otomatis"
bisa berbeda dari yang DITAGIH. Sekarang quote memakai resolusi tarif yang SAMA.

RC-B (BUG-0133): endpoint `unit-rates` = SATU-SATUNYA jalur tulis tarif per unit
(`vehicles.day_rate`). Form Armada tidak lagi menulis harga (read-only reference).
Dijaga guardrail INV-PRICE-02 (scripts/guardrails/verify_price_master.py).
"""
from fastapi import APIRouter, Depends, HTTPException

from core_utils import safe_doc
from db import get_db
from dependencies import get_current_user, require_section
from schemas import PricingQuoteRequest, UnitDayRateUpdate
from services.audit import record
from services.pricing import compute_quote, get_pricing_rules, resolve_day_rate, type_label

router = APIRouter(prefix="/api", tags=["pricing"])
# Master Harga dikelola dari halaman Pengaturan (owner) — section yang sama.
SETTINGS = require_section("settings")


DEVIATION_ALARM_PCT = 50  # alarm harga aneh: tarif unit menyimpang >±50% dari tarif tipenya


def _rate_deviation(rules, vehicle: dict):
    """(type_rate, deviation_pct, warning) — warning terisi bila override unit menyimpang jauh."""
    override = int(round(float(vehicle.get("day_rate") or 0)))
    type_rate, _b = resolve_day_rate(rules, vehicle={"type": vehicle.get("type")})
    if override <= 0 or type_rate <= 0:
        return type_rate, None, ""
    dev = round((override - type_rate) / type_rate * 100)
    if abs(dev) < DEVIATION_ALARM_PCT:
        return type_rate, dev, ""
    arah = "di ATAS" if dev > 0 else "di BAWAH"
    return type_rate, dev, (f"Tarif unit menyimpang {abs(dev)}% {arah} tarif tipe "
                            f"({type_label(vehicle.get('type'))} Rp {type_rate:,}) — periksa salah ketik.".replace(",", "."))


async def _holidays(db):
    op = await db.settings.find_one({"key": "operational"}, {"_id": 0})
    if op and isinstance(op.get("value"), dict):
        return op["value"].get("holidays", []) or []
    return []


@router.get("/pricing/rules")
async def get_rules(user=Depends(get_current_user)):
    """Aturan harga aktif (gabungan DB + default)."""
    return await get_pricing_rules(get_db())


@router.get("/pricing/unit-rates")
async def list_unit_rates(user=Depends(SETTINGS)):
    """Master Harga: tarif efektif tiap unit + dasarnya (tarif unit/tipe/default)."""
    db = get_db()
    rules = await get_pricing_rules(db)
    rows = await db.vehicles.find(
        {}, {"_id": 0, "id": 1, "code": 1, "name": 1, "plate_number": 1,
             "type": 1, "day_rate": 1}).sort("code", 1).to_list(500)
    out = []
    for v in rows:
        rate, basis = resolve_day_rate(rules, vehicle=v)
        type_rate, dev, warning = _rate_deviation(rules, v)
        out.append({**v, "type_label": type_label(v.get("type")),
                    "effective_rate": rate, "rate_basis": basis,
                    "type_rate": type_rate, "deviation_pct": dev, "warning": warning})
    return safe_doc(out)


@router.patch("/pricing/unit-rates/{vehicle_id}")
async def set_unit_rate(vehicle_id: str, body: UnitDayRateUpdate, user=Depends(SETTINGS)):
    """SATU-SATUNYA jalur tulis tarif per unit. day_rate=0 → hapus override (pakai tarif tipe)."""
    db = get_db()
    vehicle = await db.vehicles.find_one({"id": vehicle_id}, {"_id": 0})
    if not vehicle:
        raise HTTPException(status_code=404, detail="Armada tidak ditemukan")
    new_rate = int(round(float(body.day_rate or 0)))
    await db.vehicles.update_one({"id": vehicle_id}, {"$set": {"day_rate": new_rate}})
    await record(db, actor=user, action="update", entity_type="vehicle", entity_id=vehicle_id,
                 summary=f"Master Harga: tarif unit {vehicle.get('name')} → Rp {new_rate:,}".replace(",", "."))
    rules = await get_pricing_rules(db)
    vehicle["day_rate"] = new_rate
    rate, basis = resolve_day_rate(rules, vehicle=vehicle)
    _type_rate, dev, warning = _rate_deviation(rules, vehicle)
    return {"id": vehicle_id, "day_rate": new_rate, "effective_rate": rate, "rate_basis": basis,
            "deviation_pct": dev, "warning": warning}


@router.post("/pricing/quote")
async def quote(body: PricingQuoteRequest, user=Depends(get_current_user)):
    """Hitung rincian harga ber-item + DP saran — tarif di-resolve SAMA dengan mesin penagih."""
    db = get_db()
    rules = await get_pricing_rules(db)
    vtype = body.vehicle_type
    day_rate = None
    if body.vehicle_id:
        v = await db.vehicles.find_one({"id": body.vehicle_id}, {"_id": 0, "type": 1, "day_rate": 1})
        if v:
            vtype = vtype or v.get("type")
            # RC-A: tarif unit menimpa tarif tipe — identik dengan create/approve booking & web.
            day_rate, _basis = resolve_day_rate(rules, vehicle=v, vehicle_type=vtype)
    return compute_quote(
        rules,
        vehicle_type=vtype,
        days=body.days,
        distance_km=body.distance_km,
        when=body.start_date,
        holidays=await _holidays(db),
        include_travel=True,
        day_rate=day_rate,
    )
