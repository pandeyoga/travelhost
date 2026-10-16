#!/usr/bin/env python3
"""INV-RACE-01 \u2014 Reservasi armada/sopir wajib di-serial (vehicle_lock / driver_lock).

Kelas bug yang dicegah: race / TOCTOU double-book (Putaran 11: dispatch.assign, quotations.convert,
subcharters, PATCH driver menulis reservasi tanpa mutex).

Dua lapis:
  (1) AUTO-DISCOVERY \u2014 tiap fungsi router MUTATING (post/put/patch/delete) yang memanggil
      conflict-finder armada (find_conflicts / find_subcharter_conflicts) WAJIB memegang
      vehicle_lock; yang memanggil find_driver_conflicts WAJIB memegang vehicle_lock ATAU
      driver_lock. Menangkap write-path BARU otomatis.
  (2) REGISTRY REGRESSION \u2014 daftar jalur reservasi yang diketahui harus TETAP terkunci
      (menangkap bila lock dihapus dari jalur lama).
Pengecualian aman-by-design didaftarkan eksplisit di ALLOW (dengan alasan).
"""
import ast
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from _common import BACKEND, Guard  # noqa: E402

VEHICLE_FINDERS = ("find_conflicts(", "find_subcharter_conflicts(")
DRIVER_FINDER = "find_driver_conflicts("
LOCKS = ("vehicle_lock(", "driver_lock(")
MUTATING = ("post", "put", "patch", "delete")

# Aman-by-design (tak mereservasi armada baru) \u2014 wajib beralasan.
ALLOW = {
    "public.public_booking_request": "buat booking 'pending' vehicle_id=None; armada di-assign saat approve (sudah ber-vehicle_lock)",
    "driver.checkin": "pakai armada yang SUDAH ter-assign ke booking/trip; ownership-guarded; tak assign armada baru",
}

# Jalur reservasi yang DIKETAHUI \u2014 harus tetap memegang lock ini (anchor anti-regresi).
REGISTRY = {
    "bookings.create_booking": "vehicle_lock",
    "bookings.create_group_booking": "vehicle_lock",
    "bookings.confirm_booking": "vehicle_lock",
    "bookings.reschedule_booking": "vehicle_lock",
    "bookings.approve_booking": "vehicle_lock",
    "bookings.update_booking": "driver_lock",
    "dispatch.assign_trip": "vehicle_lock",
    "quotations.convert_quotation": "vehicle_lock",
    "subcharters.create_subcharter": "vehicle_lock",
    "subcharters.update_subcharter": "vehicle_lock",
}


def route_method(node):
    for dec in node.decorator_list:
        try:
            s = ast.unparse(dec)
        except Exception:
            s = ""
        m = re.search(r"router\.(get|post|put|patch|delete)", s)
        if m:
            return m.group(1)
    return None


def funcs(path):
    txt = (BACKEND / path).read_text()
    tree = ast.parse(txt)
    lines = txt.splitlines()
    out = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
            start = node.lineno - 1
            end = getattr(node, "end_lineno", start + 80)
            out.append((node.name, route_method(node), "\n".join(lines[start:end])))
    return out


def main() -> int:
    g = Guard("INV-RACE-01", "Reservasi armada/sopir wajib di-serial (vehicle_lock/driver_lock)")
    seen = {}
    for f in sorted((BACKEND / "routers").glob("*.py")):
        module = f.stem
        for name, method, src in funcs(f"routers/{f.name}"):
            key = f"{module}.{name}"
            seen[key] = src
            if method not in MUTATING or key in ALLOW:
                continue
            uses_vfinder = any(x in src for x in VEHICLE_FINDERS)
            uses_dfinder = DRIVER_FINDER in src
            has_vlock = "vehicle_lock(" in src
            has_anylock = any(x in src for x in LOCKS)
            if uses_vfinder or uses_dfinder:
                g.bump()
            if uses_vfinder and not has_vlock:
                g.add(f"{key}: memanggil conflict-finder armada TANPA vehicle_lock \u2192 risiko TOCTOU double-book. "
                      f"Bungkus cek-final + tulis dgn `async with vehicle_lock(db, vehicle_id):`.")
            elif uses_dfinder and not has_anylock:
                g.add(f"{key}: cek konflik driver TANPA lock \u2192 TOCTOU. Bungkus dgn vehicle_lock/driver_lock.")
    # Registry regression
    for key, need in REGISTRY.items():
        g.bump()
        src = seen.get(key)
        if src is None:
            g.add(f"REGISTRY: jalur reservasi '{key}' tak ditemukan (di-rename/dihapus?). "
                  f"Perbarui REGISTRY & pastikan penguncian tetap ada.")
        elif (need + "(") not in src:
            g.add(f"REGISTRY: '{key}' kehilangan `{need}` (REGRESI penguncian!). Kembalikan `{need}`.")
    return g.finish()


if __name__ == "__main__":
    sys.exit(main())
