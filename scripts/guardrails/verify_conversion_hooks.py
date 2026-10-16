#!/usr/bin/env python3
"""INV-CONV-01 — Event bisnis bernilai WAJIB terhubung ke outbox konversi iklan.

Kelas bug yang ditutup (nyata, ditemukan di fase F3): `services/conversions.py` lengkap & teruji,
tetapi TIDAK PERNAH dipanggil siapa pun. Akibatnya dua konversi paling bernilai — booking
dikonfirmasi & DP masuk — tak pernah dilaporkan ke Meta/Google, sehingga algoritma iklan hanya
belajar dari "form terkirim" dan biaya per booking membengkak TANPA satu pun error di log.

Penjaga STATIK ini memastikan rantai tetap tersambung walau kode terus tumbuh:
  1. `services/events.py::emit` memanggil `conversion_hooks.handle_event` (satu titik wiring).
  2. `services/conversion_hooks.BUSINESS_EVENTS` memetakan minimal 3 event wajib.
  3. Setiap event wajib itu benar-benar dipancarkan di suatu tempat (`emit(db, "<event>"`).
  4. `conversions.enqueue` idempoten: menangani `DuplicateKeyError` + unique index dibuat.
  5. `dispatch_pending` (pekerja retry) dipanggil scheduler `server.py` — tanpa itu konversi
     gagal sekali akan hilang selamanya.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from _common import BACKEND, Guard  # noqa: E402

REQUIRED_EVENTS = ("lead.created", "booking.confirmed", "payment.recorded")


def read(path):
    return path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""


def main() -> int:
    g = Guard("INV-CONV-01", "Event bisnis bernilai terhubung ke outbox konversi + pekerja retry")
    events = read(BACKEND / "services" / "events.py")
    hooks = read(BACKEND / "services" / "conversion_hooks.py")
    conversions = read(BACKEND / "services" / "conversions.py")
    server = read(BACKEND / "server.py")

    g.bump()
    if not hooks:
        g.add("services/conversion_hooks.py TIDAK ADA — jembatan event bus → outbox konversi hilang.")
        return g.finish()

    # (1) satu titik wiring di event bus
    g.bump()
    if not re.search(r"conversion_hooks\s+import\s+handle_event|conversion_hooks\.handle_event", events):
        g.add("services/events.py::emit tidak memanggil conversion_hooks.handle_event → "
              "SEMUA konversi iklan tidak pernah dijadwalkan (gagal senyap).")

    # (2) daftar event wajib
    for event in REQUIRED_EVENTS:
        g.bump()
        if f'"{event}"' not in hooks:
            g.add(f"conversion_hooks.BUSINESS_EVENTS tidak memetakan '{event}' → konversi untuk "
                  f"event bernilai itu tidak pernah dikirim ke Meta/Google.")

    # (3) event wajib benar-benar dipancarkan di kode produksi
    emitted = ""
    for path in sorted((BACKEND / "routers").glob("*.py")) + sorted((BACKEND / "services").glob("*.py")):
        if path.name.startswith("backend_test") or "test" in path.name:
            continue
        emitted += read(path)
    for event in REQUIRED_EVENTS:
        g.bump()
        if f'emit(db, "{event}"' not in emitted:
            g.add(f"Tidak ada pemanggil `emit(db, \"{event}\"` di router/service → rantai konversi "
                  f"terputus di sumbernya.")

    # (4) idempotensi outbox
    g.bump()
    if "DuplicateKeyError" not in conversions:
        g.add("conversions.enqueue tidak menangani DuplicateKeyError → retry/paralel bisa "
              "menggandakan konversi (Meta/Google menghitung dua kali).")
    g.bump()
    if not re.search(r'create_index\(\s*\[\("provider", 1\), \("event_key", 1\)\][^)]*unique=True', conversions):
        g.add("Unique index (provider, event_key) tidak dibuat di conversions.ensure_indexes → "
              "idempotensi outbox tidak dijamin database.")

    # (5) pekerja retry terjadwal
    g.bump()
    if "dispatch_pending" not in server:
        g.add("server.py scheduler tidak memanggil conversions.dispatch_pending → konversi yang "
              "gagal sekali tidak pernah dicoba ulang (hilang diam-diam).")

    # (6) index outbox dipasang saat boot
    g.bump()
    if not re.search(r"(conversions|_cv)\.ensure_indexes\(db\)", server):
        g.add("server.py tidak memanggil conversions.ensure_indexes saat startup → unique index "
              "bisa tidak ada di deployment baru.")
    return g.finish()


if __name__ == "__main__":
    sys.exit(main())
