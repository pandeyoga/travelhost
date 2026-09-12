#!/usr/bin/env python3
"""migrate_money_to_int.py — MIGRASI RC-11: normalisasi semua nilai uang -> INTEGER rupiah.

Rupiah (IDR) tak punya sub-satuan; menyimpan `float` berisiko drift akumulasi (mis. 0.1+0.2).
Skrip ini membulatkan field uang (top-level & nested array) ke bilangan bulat terdekat.

Sifat:
  - IDEMPOTEN: dijalankan berulang aman (int tetap int; hanya ubah bila ada pecahan/typo float).
  - AMAN: hanya menyentuh field uang yang terdaftar; None dilewati; tak mengubah skema.
  - Dipakai di `seed_reset.sh` (pasca-seed) & bisa dijalankan manual untuk data lama.

Usage: cd /app && python scripts/migrate_money_to_int.py
Exit 0 selalu (laporan jumlah dokumen dinormalisasi).
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / "backend" / ".env")
except Exception:
    pass
from pymongo import MongoClient, UpdateOne

G, Y, C, B, X = "\033[92m", "\033[93m", "\033[96m", "\033[1m", "\033[0m"
DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[
    os.environ.get("DB_NAME", "test_database")]

# Field uang TOP-LEVEL per koleksi.
TOP_FIELDS = {
    "bookings": ["total_amount", "paid_amount", "base_price"],
    "payments": ["amount"],
    "expenses": ["amount"],
    "invoices": ["amount"],
    "maintenance_records": ["cost"],
    "trips": ["revenue", "profit"],
    "driver_payouts": ["total", "gross", "bonus_total", "deduction_total", "base_salary",
                       "commission_trip", "commission_pct", "allowance_km", "total_revenue"],
    "leads": ["value", "quotation_amount"],
    "quotations": ["subtotal", "total", "dp_amount"],
    "subcharters": ["cost", "amount"],
    "packages": ["price_from"],
    "settings": [],  # ditangani khusus (pricing_rules) bila perlu — dilewati di sini.
}
# Field uang di dalam ARRAY (list of dict) per koleksi: {koleksi: {array_field: [amount_keys]}}
ARRAY_FIELDS = {
    "bookings": {"add_ons": ["amount"]},
    "driver_payouts": {"bonuses": ["amount"], "deductions": ["amount"]},
    "quotations": {"items": ["amount"]},
}


def _to_int(v):
    try:
        return int(round(float(v)))
    except (TypeError, ValueError):
        return None


def _needs_fix(v):
    """True bila v numerik tapi bukan int bulat (float / pecahan)."""
    if v is None or isinstance(v, bool):
        return False
    if isinstance(v, int):
        return False
    if isinstance(v, float):
        return True  # semua float dijadikan int (idempoten: int dilewati)
    return False


def migrate():
    print(f"\n{B}{'='*60}{X}\n  MIGRASI UANG -> INTEGER (RC-11)\n{B}{'='*60}{X}")
    grand = 0
    for coll, fields in TOP_FIELDS.items():
        arr_map = ARRAY_FIELDS.get(coll, {})
        if not fields and not arr_map:
            continue
        docs = list(DB[coll].find({}, {"_id": 0}))
        ops = []
        changed = 0
        for d in docs:
            setter = {}
            # top-level
            for f in fields:
                v = d.get(f)
                if _needs_fix(v):
                    setter[f] = _to_int(v)
            # nested arrays
            for arr_key, amount_keys in arr_map.items():
                arr = d.get(arr_key)
                if isinstance(arr, list) and arr:
                    new_arr = []
                    touched = False
                    for item in arr:
                        if isinstance(item, dict):
                            it = dict(item)
                            for ak in amount_keys:
                                if _needs_fix(it.get(ak)):
                                    it[ak] = _to_int(it[ak]); touched = True
                            new_arr.append(it)
                        else:
                            new_arr.append(item)
                    if touched:
                        setter[arr_key] = new_arr
            if setter:
                ops.append(UpdateOne({"id": d.get("id")}, {"$set": setter}))
                changed += 1
        if ops:
            DB[coll].bulk_write(ops, ordered=False)
        grand += changed
        tag = f"{G}{changed} diperbaiki{X}" if changed else f"{Y}0 (sudah bulat){X}"
        print(f"  {coll:22s} {len(docs):4d} dok → {tag}")
    print(f"{B}{'='*60}{X}\n  {G}{B}Selesai. Total dokumen dinormalisasi: {grand}{X}\n{B}{'='*60}{X}\n")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(migrate())
    except Exception as ex:  # jangan gagalkan pipeline seed hanya karena migrasi
        print(f"{Y}  Migrasi uang error (dilewati): {ex}{X}")
        sys.exit(0)
