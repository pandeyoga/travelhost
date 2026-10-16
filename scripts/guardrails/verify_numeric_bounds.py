#!/usr/bin/env python3
"""INV-NUM-01 \u2014 Semua field numerik uang/kuantitas WAJIB ber-bound (ge=/gt=).

Kelas bug yang dicegah: 'negative-value' (Putaran 11: 57/63 field menerima nilai negatif).
Statik: scan AST backend/schemas.py; tiap field int/float harus punya Field(..., ge=/gt=)
ATAU terdaftar eksplisit di ALLOW_UNBOUNDED (dengan alasan). Field baru yang lupa dibatasi
=> gate MERAH otomatis, walau ditambahkan oleh sesi/kontributor yang tak tahu aturan ini.
"""
import ast
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from _common import BACKEND, Guard  # noqa: E402

# Field numerik yang MEMANG boleh tak-berbound (bukan uang/kuantitas) \u2014 wajib beralasan.
ALLOW_UNBOUNDED = {
    "LocationCreate.lat": "koordinat GPS (boleh negatif)",
    "LocationCreate.lng": "koordinat GPS (boleh negatif)",
    "LocationCreate.heading": "arah kompas 0-360 dari device",
    "CheckinRequest.lat": "koordinat GPS (boleh negatif)",
    "CheckinRequest.lng": "koordinat GPS (boleh negatif)",
    "VehicleCreate.year": "tahun kendaraan (bukan uang/kuantitas)",
    "VehicleUpdate.year": "tahun kendaraan (bukan uang/kuantitas)",
}


def is_numeric(ann: str) -> bool:
    return bool(re.search(r"\b(int|float)\b", ann))


def main() -> int:
    g = Guard("INV-NUM-01", "Field numerik uang/kuantitas wajib ber-bound (ge=/gt=)")
    # Pindai SEMUA modul schema (`schemas.py`, `schemas_landing.py`, dst). Dulu hanya `schemas.py`:
    # begitu kontrak dipecah ke modul baru, penjaga jadi BUTA tanpa satu pun tanda peringatan —
    # kelas kegagalan "daftar manual tertinggal dari pertumbuhan kode".
    files = sorted(BACKEND.glob("schemas*.py"))
    if not files:
        g.add("tidak ada modul schema `backend/schemas*.py` ditemukan (regresi struktur?).")
        return g.finish()
    nodes = []
    for f in files:
        for node in ast.walk(ast.parse(f.read_text())):
            nodes.append((f.name, node))
    for fname, node in nodes:
        if not isinstance(node, ast.ClassDef):
            continue
        for stmt in node.body:
            if not isinstance(stmt, ast.AnnAssign) or not isinstance(stmt.target, ast.Name):
                continue
            ann = ast.unparse(stmt.annotation)
            if not is_numeric(ann):
                continue
            key = f"{node.name}.{stmt.target.id}"
            val = ast.unparse(stmt.value) if stmt.value is not None else ""
            bounded = bool(re.search(r"\b(ge|gt)\s*=", val))
            g.bump()
            if bounded or key in ALLOW_UNBOUNDED:
                continue
            g.add(f"{fname}::{key} ({ann}) TANPA ge=/gt= \u2192 menerima nilai negatif. "
                  f"Tambahkan Field(..., ge=0), atau daftarkan di ALLOW_UNBOUNDED dgn alasan.")
    return g.finish()


if __name__ == "__main__":
    sys.exit(main())
