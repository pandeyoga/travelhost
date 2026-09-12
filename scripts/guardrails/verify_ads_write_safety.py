#!/usr/bin/env python3
"""INV-ADS-01 — Semua penulisan ke platform iklan WAJIB lewat pengaman belanja `ads_safety`.

Kelas bug yang dicegah: satu baris kode bisa MEMBAKAR UANG NYATA. Cukup lupa `validate_only`,
lupa `status: PAUSED`, atau langsung memanggil httpx dari router — dan budget berjalan tanpa ada
yang menekan tombol. Ini kelas bug yang tidak menghasilkan error apa pun, hanya tagihan.

Penjaga STATIK memastikan:
  1. `services/meta_ads.py` create/update memakai `safety.meta_write_payload`.
  2. `services/google_ads.py` mutate memakai `safety.google_write_body`.
  3. `ads_safety.meta_write_payload` memaksa `PAUSED` untuk create & menyisipkan `validate_only`.
  4. `ads_safety.google_write_body` mengisi `validateOnly` sesuai mode.
  5. Router `ads*.py` TIDAK memanggil httpx / graph.facebook.com / googleads langsung
     (harus lewat klien service yang sudah berpengaman).
  6. Endpoint publish/aktivasi/budget menuntut konfirmasi (`assert_confirmation` /
     `assert_activation_allowed`) dan plafon budget (`assert_budget_within_cap`).
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from _common import BACKEND, Guard  # noqa: E402

FORBIDDEN_IN_ROUTERS = ("httpx.", "graph.facebook.com", "googleads.googleapis.com",
                        "datamanager.googleapis.com")


def read(path):
    return path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""


def main() -> int:
    g = Guard("INV-ADS-01", "Penulisan iklan wajib lewat pengaman (validate_only + PAUSED + konfirmasi)")
    safety = read(BACKEND / "services" / "ads_safety.py")
    meta = read(BACKEND / "services" / "meta_ads.py")
    google = read(BACKEND / "services" / "google_ads.py")
    manage = read(BACKEND / "routers" / "ads_manage.py")

    g.bump()
    if not safety:
        g.add("services/ads_safety.py TIDAK ADA — pengaman belanja iklan hilang seluruhnya.")
        return g.finish()

    # (3) isi pengaman
    g.bump()
    if not re.search(r'body\["status"\]\s*=\s*PAUSED', safety):
        g.add("ads_safety.meta_write_payload tidak memaksa status PAUSED pada objek create → "
              "kampanye bisa langsung ACTIVE dan membelanjakan budget.")
    g.bump()
    if 'body["execution_options"] = ["validate_only"]' not in safety:
        g.add("ads_safety.meta_write_payload tidak menyisipkan execution_options=['validate_only'] "
              "pada mode validate → 'validasi' malah membuat objek nyata.")
    g.bump()
    if not re.search(r'out\["validateOnly"\]\s*=\s*is_dry_run\(mode\)', safety):
        g.add("ads_safety.google_write_body tidak mengatur validateOnly sesuai mode → mutasi "
              "Google pada mode validate bisa dieksekusi sungguhan.")

    # (1)(2) klien memakai pengaman
    for label, text, needle in (
        ("meta_ads.create_object", meta, "safety.meta_write_payload"),
        ("meta_ads.update_object", meta, "safety.meta_write_payload"),
        ("google_ads.mutate", google, "safety.google_write_body"),
    ):
        g.bump()
        if needle not in text:
            g.add(f"{label} tidak memanggil {needle} → jalur tulis platform tanpa pengaman.")

    # (5) router tidak memanggil API platform langsung
    for path in sorted((BACKEND / "routers").glob("ads*.py")):
        text = read(path)
        for needle in FORBIDDEN_IN_ROUTERS:
            g.bump()
            if needle in text:
                g.add(f"routers/{path.name}: memanggil '{needle}' langsung dari router → "
                      f"lewati pengaman ads_safety. Gunakan services/meta_ads.py atau "
                      f"services/google_ads.py.")

    # (6) konfirmasi & plafon budget di endpoint mutasi
    g.bump()
    if "assert_confirmation" not in manage:
        g.add("routers/ads_manage.py: publish/budget tanpa `assert_confirmation` → objek bisa "
              "diterbitkan/diubah tanpa konfirmasi ketik nama.")
    g.bump()
    if "assert_activation_allowed" not in manage:
        g.add("routers/ads_manage.py: perubahan status tanpa `assert_activation_allowed` → "
              "iklan bisa diaktifkan (mulai belanja) tanpa konfirmasi.")
    g.bump()
    if "assert_budget_within_cap" not in manage:
        g.add("routers/ads_manage.py: budget tanpa `assert_budget_within_cap` → salah ketik nol "
              "bisa melipatgandakan belanja harian.")
    g.bump()
    if "SafetyError" not in manage:
        g.add("routers/ads_manage.py tidak memetakan SafetyError → pelanggaran pengaman muncul "
              "sebagai 5xx, bukan pesan jelas 400 (INV-5XX-01).")
    return g.finish()


if __name__ == "__main__":
    sys.exit(main())
