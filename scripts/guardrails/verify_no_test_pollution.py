#!/usr/bin/env python3
"""INV-CLEAN-01 — Data uji DILARANG tertinggal di koleksi operasional.

Kelas bug yang dicegah (NYATA — keluhan user 2026-08-13, BUG-0127)
------------------------------------------------------------------
Penjaga & smoke test SENGAJA menulis lewat API sungguhan supaya perilaku server benar-benar
teruji (itu bagus). Yang salah: yang dibersihkan hanya dokumen UTAMA — SIDE-EFFECT-nya tidak.
Setiap kali `gate.sh` jalan, ERP pengguna kebanjiran data hantu:

  * `customers` berisi nama **60.000 karakter "AAAA…"** — lahir dari self-test mutasi
    INV-STR-01 yang sengaja melepas `max_length`, sukses tersimpan, lalu kode di-revert
    TAPI dokumennya tak pernah dihapus;
  * `conversations`/`messages` berisi "Penjaga INV-BOOK-02", "Penjaga INV-PRICE-01",
    "Smoke Customer" → Inbox multi-admin penuh percakapan palsu, sebagian menunjuk customer
    yang sudah dihapus (referensi yatim);
  * `notification_tasks` → lonceng notifikasi ops penuh pengingat pesanan hantu;
  * `events`/`automation_runs` → 35 dari 48 event adalah artefak uji (laporan otomasi bohong);
  * `audit_logs` → satu baris ber-`summary` **60.016 karakter** merusak tata letak Audit Log;
  * `media_assets` → aset `guard-media-*` tertinggal di Media Library.

Semua ini **SENYAP**: tidak ada error, dan gate tetap melaporkan HIJAU 40/40. Yang menemukan
akhirnya PENGGUNA ("ada nama customer aaaaaaaa… itu mengganggu").

Aturan yang dikunci
-------------------
STATIK  : setiap skrip yang menulis lewat API (`scripts/guardrails/verify_*.py`,
          `scripts/mutation_smoke.py`) WAJIB memanggil mesin bersih-bersih bersama
          (`purge_guard_artifacts`/`purge_guard_bookings` dari `_common.py`) — kalau tidak,
          side-effect-nya pasti menumpuk lagi di sesi berikutnya.
RUNTIME : koleksi operasional WAJIB 0 dokumen berpenanda data uji (`GUARD_MARKERS`,
          nomor `0800000xxx`/`0810000000`) dan 0 field identitas melebihi batas wajar
          (`OVERLONG_RULES`). Penjaga ini dijalankan PALING AKHIR di gate — jadi kalau ada
          penjaga lain yang bocor, yang MERAH adalah gate ini (bukan pengguna yang menemukan).

Catatan penting: penjaga ini TIDAK membersihkan apa pun. Membersihkan di sini justru akan
menutupi kebocoran ("hijau-palsu"). Pembersihan adalah tanggung jawab skrip yang membuat.
Untuk perbaikan manual database yang sudah kotor: `python scripts/purge_test_pollution.py`.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from _common import (BACKEND, Guard, ROOT, G, X, GUARD_MARKERS,  # noqa: E402
                     scan_test_pollution)

GUARD_DIR = ROOT / "scripts" / "guardrails"

# Skrip yang MENULIS lewat API → wajib punya panggilan bersih-bersih.
# (nama berkas, alasan kenapa dia menulis)
WRITERS = {
    "verify_pricing_integrity.py": "membuat pesanan uji untuk membandingkan harga tampil vs tersimpan",
    "verify_booking_public.py": "membuat pesanan uji untuk menguji mutex & total server-side",
    "verify_string_bounds.py": "mengirim 60.000 karakter ke permukaan tulis",
    "verify_reference_integrity.py": "menembak FK hantu & enum ngawur ke 20+ endpoint tulis",
    "verify_identity_race.py": "POST /customers paralel untuk menguji index unik",
    "verify_media_runtime.py": "mengunggah aset `guard-media-*` ke Media Library",
    "verify_adversarial_5xx.py": "mengirim payload adversarial ke endpoint tulis",
    "verify_ssot_relations.py": "menembak destinasi di luar master ke POST /bookings (INV-REF-02)",
}
CLEANUP_CALLS = ("purge_guard_artifacts", "purge_guard_bookings")


def code_only(text: str) -> str:
    """Buang docstring & komentar — penjaga tak boleh 'puas oleh prosa'."""
    text = re.sub(r'""".*?"""', "", text, flags=re.S)
    text = re.sub(r"'''.*?'''", "", text, flags=re.S)
    return re.sub(r"(?m)^\s*#.*$", "", text)


def static_checks(g: Guard):
    for name, why in WRITERS.items():
        path = GUARD_DIR / name
        g.bump()
        if not path.exists():
            g.add(f"{name}: TIDAK ADA padahal terdaftar sebagai penulis data uji ({why}) — "
                  f"registri usang, perbarui WRITERS.")
            continue
        src = code_only(path.read_text(encoding="utf-8", errors="ignore"))
        g.bump()
        if not any(call in src for call in CLEANUP_CALLS):
            g.add(f"{name}: {why}, tetapi TIDAK memanggil {' / '.join(CLEANUP_CALLS)} → "
                  f"artefak uji + side-effect-nya (percakapan/notifikasi/event/audit) "
                  f"menumpuk di ERP pengguna setiap kali gate jalan.")
    smoke = ROOT / "scripts" / "mutation_smoke.py"
    g.bump()
    if not smoke.exists():
        g.add("scripts/mutation_smoke.py hilang (regresi struktur gate?).")
    elif not any(call in code_only(smoke.read_text(encoding="utf-8", errors="ignore"))
                 for call in CLEANUP_CALLS):
        g.add("scripts/mutation_smoke.py: membuat customer/armada/booking uji tetapi tidak "
              "memanggil mesin bersih-bersih bersama → percakapan 'Smoke Customer' & "
              "notifikasinya tertinggal di Inbox ops.")
    # Mesin bersih-bersih wajib ada & menyebut penanda (SSOT konvensi identitas data uji).
    common = (GUARD_DIR / "_common.py").read_text(encoding="utf-8", errors="ignore")
    g.bump()
    if "def purge_guard_artifacts" not in common or "GUARD_MARKERS" not in common:
        g.add("_common.py: mesin bersih-bersih bersama (`purge_guard_artifacts` + "
              "`GUARD_MARKERS`) hilang → tiap penjaga akan bikin versi sendiri yang "
              "pasti tidak lengkap (akar BUG-0127).")
    # Produk juga wajib membatasi panjang `summary` audit (baris 60.016 karakter).
    audit = (BACKEND / "services" / "audit.py")
    g.bump()
    if not audit.exists():
        g.add("backend/services/audit.py hilang.")
    elif "_clip" not in audit.read_text(encoding="utf-8", errors="ignore"):
        g.add("services/audit.py: `summary` audit tidak dipotong (`_clip`) → satu aksi "
              "bernama panjang melahirkan baris Audit Log 60.016 karakter yang merusak UI.")


def runtime_checks(g: Guard):
    hits = scan_test_pollution()
    g.bump()
    if hits is None:
        g.add("tidak bisa terhubung ke MongoDB (pymongo/MONGO_URL) — pemeriksaan runtime "
              "WAJIB jalan; ketiadaan sasaran = pelanggaran, bukan skip.")
        return
    by_col = {}
    for h in hits:
        by_col.setdefault(h["collection"], []).append(h)
    for col, items in sorted(by_col.items()):
        g.bump()
        contoh = "; ".join(f"{i['id']} \u2192 {i['label']!r} ({i['reason']})" for i in items[:3])
        g.add(f"{col}: {len(items)} dokumen artefak uji tertinggal di data operasional "
              f"(pengguna melihatnya di ERP). Contoh: {contoh}. "
              f"Perbaiki skrip pembuatnya (wajib purge di `finally`), lalu jalankan "
              f"`python scripts/purge_test_pollution.py` untuk membersihkan sisa.")
    if not hits:
        print(f"    [{G}ok{X}] koleksi operasional bersih: 0 artefak uji "
              f"({len(GUARD_MARKERS)} penanda dipindai)")


def main() -> int:
    g = Guard("INV-CLEAN-01",
              "Data uji penjaga/smoke wajib dibersihkan total (tak boleh bocor ke ERP)")
    static_checks(g)
    runtime_checks(g)
    return g.finish()


if __name__ == "__main__":
    sys.exit(main())
