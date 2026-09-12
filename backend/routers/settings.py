"""routers/settings.py — Pengaturan sistem (Phase 7).

Koleksi `settings` (keyed docs {key,value}). Kunci: company_info, pricing_defaults,
operational (holidays/work_hours), map_provider. Akses owner (section 'settings').
Kompatibel dgn public `/api/public/company` yang membaca `company_info`.
"""
from fastapi import APIRouter, Depends, HTTPException

from db import get_db
from dependencies import require_section
from schemas import SettingsUpdate
from services.audit import record
from services import booking_flow as bf
from services.pricing import DEFAULT_PRICING_RULES

router = APIRouter(prefix="/api", tags=["settings"])
SETTINGS = require_section("settings")

# SET-1: field tarif numerik yang tak boleh negatif (dipakai langsung dlm perkalian harga →
# nilai negatif = harga negatif; non-numerik = 0 senyap). Validasi di titik-tulis → 400 jelas.
_RULE_NON_NEG = ["default_day_rate", "driver_fee_per_day", "fuel_per_km",
                 "toll_parking_per_day", "weekend_surcharge_percent",
                 "holiday_surcharge_percent", "rounding"]


def _num_or_400(field, value):
    """Koersi ke angka; tolak non-numerik (mis. 'gratis') & boolean dgn 400 (mirip R6-5)."""
    if isinstance(value, bool):
        raise HTTPException(status_code=400, detail=f"Field '{field}' harus berupa angka")
    try:
        return float(value)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail=f"Field '{field}' harus berupa angka")


def _validate_pricing(updates: dict):
    """SET-1: validasi tarif/persen pada pricing_rules + pricing_defaults → 400 bila tak valid."""
    rules = updates.get("pricing_rules")
    if isinstance(rules, dict):
        day_rates = rules.get("day_rates")
        if isinstance(day_rates, dict):
            for vt, v in day_rates.items():
                if v is None:
                    continue
                if _num_or_400(f"day_rates.{vt}", v) < 0:
                    raise HTTPException(status_code=400, detail=f"Tarif 'day_rates.{vt}' tidak boleh negatif")
        for f in _RULE_NON_NEG:
            if rules.get(f) is not None and _num_or_400(f, rules[f]) < 0:
                raise HTTPException(status_code=400, detail=f"Nilai '{f}' tidak boleh negatif")
        if rules.get("dp_percent") is not None and not (0 <= _num_or_400("dp_percent", rules["dp_percent"]) <= 100):
            raise HTTPException(status_code=400, detail="'dp_percent' harus antara 0–100")
    pd = updates.get("pricing_defaults")
    if isinstance(pd, dict):
        if pd.get("dp_percent") is not None and not (0 <= _num_or_400("dp_percent", pd["dp_percent"]) <= 100):
            raise HTTPException(status_code=400, detail="'dp_percent' harus antara 0–100")
        if pd.get("min_rental_hours") is not None and _num_or_400("min_rental_hours", pd["min_rental_hours"]) < 0:
            raise HTTPException(status_code=400, detail="'min_rental_hours' tidak boleh negatif")

DEFAULTS = {
    "company_info": {},
    "pricing_defaults": {"dp_percent": 30, "cancellation_policy": "", "min_rental_hours": 12},
    "pricing_rules": DEFAULT_PRICING_RULES,
    "operational": {"work_hours": {"open": "08:00", "close": "17:00"}, "holidays": []},
    "map_provider": "leaflet_osm",
    "theme_config": {"preset": "azure", "mode": "light"},  # P10: tema situs publik
    "booking_flow": bf.DEFAULT_FLOW,  # alur pemesanan online (mode/hold/instruksi DP)
}


async def _all(db):
    docs = await db.settings.find({}, {"_id": 0}).to_list(100)
    out = dict(DEFAULTS)
    for d in docs:
        if d.get("key"):
            out[d["key"]] = d.get("value")
    return out


@router.get("/settings")
async def get_settings(user=Depends(SETTINGS)):
    return await _all(get_db())


@router.patch("/settings")
async def update_settings(body: SettingsUpdate, user=Depends(SETTINGS)):
    db = get_db()
    before = await _all(db)
    updates = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    _validate_pricing(updates)  # SET-1: tolak tarif/persen tak valid sebelum simpan (400, bukan harga absurd)
    if updates.get("booking_flow") is not None:
        try:
            bf.validate_patch(updates["booking_flow"])
        except bf.FlowError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        # PATCH bersifat TAMBAL, bukan ganti-total: gabungkan di atas nilai TERSIMPAN, bukan
        # di atas default. Tanpa ini, owner yang hanya mengubah `mode` akan kehilangan daftar
        # rekening & instruksi transfer yang sudah diisi (halaman status pelanggan langsung
        # kosong tanpa ada yang menghapusnya) — BUG-0114, ditemukan POC pemesanan online.
        current = await db.settings.find_one({"key": "booking_flow"}, {"_id": 0})
        merged = dict((current or {}).get("value") or {})
        incoming = dict(updates["booking_flow"])
        if isinstance(incoming.get("payment"), dict) and isinstance(merged.get("payment"), dict):
            payment = dict(merged["payment"])
            payment.update({k: v for k, v in incoming["payment"].items() if v is not None})
            incoming["payment"] = payment
        merged.update({k: v for k, v in incoming.items() if v is not None})
        updates["booking_flow"] = bf.merge_flow(merged)
    # SATU SUMBER DP: `pricing_rules.dp_percent` adalah SSOT (services.pricing.get_dp_percent).
    # `pricing_defaults.dp_percent` hanya cermin untuk data/UI lama → disinkronkan otomatis di
    # sini supaya tidak mungkin lagi ada dua angka DP yang berbeda di web dan di ERP.
    dp_new = None
    if isinstance(updates.get("pricing_rules"), dict) and \
            updates["pricing_rules"].get("dp_percent") is not None:
        dp_new = updates["pricing_rules"]["dp_percent"]
    elif isinstance(updates.get("pricing_defaults"), dict) and \
            updates["pricing_defaults"].get("dp_percent") is not None:
        dp_new = updates["pricing_defaults"]["dp_percent"]
        rules_doc = await db.settings.find_one({"key": "pricing_rules"}, {"_id": 0})
        merged_rules = dict((rules_doc or {}).get("value") or {})
        merged_rules["dp_percent"] = dp_new
        updates["pricing_rules"] = merged_rules
    if dp_new is not None:
        pd_doc = await db.settings.find_one({"key": "pricing_defaults"}, {"_id": 0})
        merged_pd = dict(updates.get("pricing_defaults") or (pd_doc or {}).get("value") or {})
        merged_pd["dp_percent"] = dp_new
        updates["pricing_defaults"] = merged_pd
    for key, value in updates.items():
        await db.settings.update_one({"key": key}, {"$set": {"key": key, "value": value}}, upsert=True)
    after = await _all(db)
    if updates:
        await record(db, actor=user, action="update", entity_type="settings",
                     entity_id=",".join(updates.keys()),
                     before={k: before.get(k) for k in updates},
                     after={k: after.get(k) for k in updates},
                     summary=f"Ubah pengaturan: {', '.join(updates.keys())}")
    return after
