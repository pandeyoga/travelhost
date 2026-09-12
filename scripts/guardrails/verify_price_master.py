#!/usr/bin/env python3
"""INV-PRICE-02 — Master Harga TUNGGAL (anti "harga diatur di 2 halaman").

Kelas bug yang ditutup (NYATA — keluhan user 2026-08-29, BUG-0133):
tarif armada bisa DITULIS dari dua permukaan berbeda: (a) Pengaturan → Aturan Harga
(`pricing_rules.day_rates` per tipe) dan (b) form Tambah/Edit Armada (`vehicles.day_rate`
per unit + `price_from` pemasaran). Dua pintu tulis = angka saling menimpa tanpa disadari,
ops bingung mana yang berlaku, dan harga di web bisa berbeda dari niat pemilik.

Konsolidasi yang dikunci penjaga ini:
  1) `schemas.py` VehicleCreate/VehicleUpdate TIDAK boleh punya field `day_rate`/`price_from`
     (form armada bukan lagi pintu tulis harga),
  2) `routers/vehicles.py` TIDAK boleh menulis `day_rate`/`price_from` dari body request,
  3) jalur tulis tarif unit HANYA `PATCH /pricing/unit-rates/{vehicle_id}` di
     `routers/pricing.py` (halaman Master Harga di Pengaturan),
  4) FE `VehicleFormDialog.jsx` TIDAK boleh punya input yang menyetel `day_rate`/`price_from`,
  5) RC-A: `/pricing/quote` WAJIB memakai `resolve_day_rate` (tarif unit menimpa tarif tipe)
     supaya angka yang DILIHAT ops = angka yang DITAGIH mesin.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from _common import BACKEND, FRONTEND, Guard  # noqa: E402

SCHEMAS = BACKEND / "schemas.py"
VEHICLES = BACKEND / "routers" / "vehicles.py"
PRICING = BACKEND / "routers" / "pricing.py"
VFORM = FRONTEND / "src" / "components" / "app" / "VehicleFormDialog.jsx"


def read(p):
    return p.read_text(encoding="utf-8", errors="ignore") if p.exists() else ""


def code_only(text: str) -> str:
    text = re.sub(r'""".*?"""', "", text, flags=re.S)
    return re.sub(r"(?m)^\s*#.*$", "", text)


def _class_block(src: str, cls: str) -> str:
    m = re.search(rf"class {cls}\(BaseModel\):(.*?)(?=\nclass |\Z)", src, flags=re.S)
    return m.group(1) if m else ""


def main() -> int:
    g = Guard("INV-PRICE-02", "Master Harga tunggal — tak ada pintu tulis harga kedua")

    schemas = code_only(read(SCHEMAS))
    for cls in ("VehicleCreate", "VehicleUpdate"):
        block = _class_block(schemas, cls)
        g.bump()
        if not block:
            g.add(f"schemas.py: class {cls} tidak ditemukan (regresi struktur?).")
            continue
        for field in ("day_rate", "price_from"):
            g.bump()
            if re.search(rf"^\s*{field}\s*:", block, flags=re.M):
                g.add(f"schemas.py {cls}: field `{field}` MUNCUL LAGI — form armada kembali "
                      f"jadi pintu tulis harga kedua (BUG-0133 lahir ulang). Tulis tarif unit "
                      f"hanya lewat PATCH /pricing/unit-rates.")

    veh = code_only(read(VEHICLES))
    for pat, msg in (
        (r"body\.day_rate", "routers/vehicles.py membaca `body.day_rate`"),
        (r"body\.price_from", "routers/vehicles.py membaca `body.price_from`"),
        (r"updates\[\s*[\"']day_rate[\"']\s*\]\s*=", "routers/vehicles.py menulis `updates['day_rate']` dari request"),
    ):
        g.bump()
        if re.search(pat, veh):
            g.add(f"{msg} — jalur tulis harga kedua hidup lagi (INV-PRICE-02).")

    pricing = read(PRICING)
    g.bump()
    if "/pricing/unit-rates/{vehicle_id}" not in pricing:
        g.add("routers/pricing.py: endpoint Master Harga `PATCH /pricing/unit-rates/{vehicle_id}` "
              "HILANG — tarif unit jadi tidak bisa diubah sama sekali (atau pindah ke pintu liar).")
    g.bump()
    quote_block = pricing[pricing.find("async def quote"):]
    if "resolve_day_rate" not in quote_block:
        g.add("routers/pricing.py quote(): tidak memakai `resolve_day_rate` — angka 'Hitung "
              "Otomatis' yang dilihat ops kembali BERBEDA dari yang ditagih mesin (BUG-0132).")
    g.bump()
    if "_rate_deviation" not in pricing or "DEVIATION_ALARM_PCT" not in pricing:
        g.add("routers/pricing.py: alarm deviasi harga (`_rate_deviation`/DEVIATION_ALARM_PCT) "
              "hilang — salah ketik tarif unit tidak lagi diperingatkan ke ops.")

    vform = read(VFORM)
    for field in ("day_rate", "price_from"):
        g.bump()
        if re.search(rf"set\(\s*[\"']{field}[\"']", vform):
            g.add(f"VehicleFormDialog.jsx: input `{field}` MUNCUL LAGI — halaman armada kembali "
                  f"jadi pintu tulis harga kedua. Harga hanya diubah di Pengaturan → Master Harga.")

    return g.finish()


if __name__ == "__main__":
    sys.exit(main())
