#!/usr/bin/env python3
"""INV-AUD-01 — Sinkron audiens ke platform iklan WAJIB menyaring izin pemasaran (consent).

Kelas bug yang dicegah: mengunggah kontak pelanggan ke Meta/Google adalah pemrosesan data
pribadi. Bila filter `marketing_consent` lupa dipasang (atau di-bypass karena "hanya untuk uji"),
seluruh basis pelanggan bisa terkirim tanpa izin — pelanggaran privasi yang TIDAK menimbulkan
error apa pun dan tidak bisa ditarik kembali.

Penjaga STATIK memastikan:
  1. `services/audiences.py` punya `split_by_consent` yang membaca field `marketing_consent`.
  2. `sync_segment` memanggil `split_by_consent` SEBELUM membangun payload unggahan.
  3. Payload dibangun dari daftar `eligible` (hasil filter), bukan dari `members` mentah.
  4. Identitas di-hash (tidak ada plaintext email/telepon dikirim).
  5. Batas batch Meta 10.000 dihormati + `last_batch_flag` dipakai.
  6. Router audiens memakai `services/audiences.sync_segment` (tidak membangun payload sendiri)
     dan melaporkan jumlah yang tersaring (`consent_filtered`) supaya terlihat di UI/audit.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from _common import BACKEND, Guard  # noqa: E402


def read(path):
    return path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""


def main() -> int:
    g = Guard("INV-AUD-01", "Sinkron audiens wajib menyaring consent + identitas ter-hash")
    aud = read(BACKEND / "services" / "audiences.py")
    manage = read(BACKEND / "routers" / "ads_manage.py")

    g.bump()
    if not aud:
        g.add("services/audiences.py TIDAK ADA — tidak ada jalur sinkron audiens yang terjaga.")
        return g.finish()

    g.bump()
    if 'marketing_consent' not in aud:
        g.add("services/audiences.py tidak membaca field `marketing_consent` → kontak tanpa izin "
              "bisa ikut terunggah ke platform.")
    g.bump()
    if "def split_by_consent" not in aud:
        g.add("services/audiences.py tidak punya `split_by_consent` (SSOT filter izin).")

    # (2)(3) sync_segment memakai hasil filter
    body = aud.split("async def sync_segment", 1)[-1] if "async def sync_segment" in aud else ""
    g.bump()
    if "split_by_consent" not in body:
        g.add("audiences.sync_segment tidak memanggil split_by_consent → payload dibangun dari "
              "SELURUH anggota segmen tanpa memeriksa izin.")
    g.bump()
    if not re.search(r"hash_rows_meta\(eligible\)", body) or not re.search(r"google_operations\(eligible\)", body):
        g.add("audiences.sync_segment membangun payload BUKAN dari daftar `eligible` hasil filter "
              "consent (Meta dan/atau Google) → filter jadi hiasan.")

    # (4) hashing
    g.bump()
    if not re.search(r"pii\.hash_email", aud) or not re.search(r"pii\.hash_phone_(meta|google)", aud):
        g.add("services/audiences.py tidak memakai helper hash `services/pii.py` → risiko mengirim "
              "email/telepon mentah ke platform.")

    # (5) batas batch Meta
    g.bump()
    if "10_000" not in aud and "10000" not in aud:
        g.add("services/audiences.py tidak menghormati batas 10.000 baris/permintaan Meta → "
              "unggahan besar akan ditolak sebagian tanpa jejak.")
    g.bump()
    if "last_batch_flag" not in aud:
        g.add("services/audiences.py tidak memakai `last_batch_flag` pada session batching → "
              "audiens bisa tertahan tidak pernah selesai diproses Meta.")

    # (6) router memakai service & melaporkan hasil saring
    g.bump()
    if "aud.sync_segment" not in manage and "audiences.sync_segment" not in manage:
        g.add("routers/ads_manage.py tidak memakai audiences.sync_segment → kemungkinan membangun "
              "payload sendiri tanpa filter consent.")
    g.bump()
    if "consent_filtered" not in manage:
        g.add("routers/ads_manage.py tidak melaporkan `consent_filtered` → jumlah kontak yang "
              "disaring tak terlihat di UI/audit (tidak transparan).")
    return g.finish()


if __name__ == "__main__":
    sys.exit(main())
