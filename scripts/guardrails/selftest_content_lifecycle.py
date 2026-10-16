#!/usr/bin/env python3
"""selftest_content_lifecycle.py — SELF-TEST MUTASI untuk INV-CMS-01.

Penjaga statik mudah "terasa ada" padahal pola pencariannya tak pernah cocok dengan kode nyata.
Skrip ini menyuntikkan tiap kelas bug yang memang pernah TERBUKA di CMS ini (satu per satu),
menuntut penjaga MERAH, lalu memulihkan berkasnya dan menuntut HIJAU kembali.

Jalankan: cd /app && python scripts/guardrails/selftest_content_lifecycle.py
"""
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(__file__))
from _common import BACKEND, FRONTEND, ROOT, G, R, Y, C, B, X  # noqa: E402

GUARD_DIR = ROOT / "scripts" / "guardrails"
SRC = FRONTEND / "src"
HEALTH = os.environ.get("GUARD_BASE_URL", "http://127.0.0.1:8001") + "/api/"

# Dibaca meta-penjaga INV-META-01: klaim "sudah di-self-test" tidak boleh tanpa bukti.
COVERS = ["verify_content_lifecycle.py"]

GUARD = "verify_content_lifecycle.py"

# (kode, berkas, teks_asli, teks_mutasi, dampak yang dicegah)
MUTATIONS = [
    ("L01", BACKEND / "routers" / "content.py",
     "    row = await ctrash.move_to_trash(db, resource, existing, actor=user,\n"
     "                                     slug_field=cfg.get(\"slug_field\"))",
     "    await db[resource].delete_one({\"id\": item_id})\n"
     "    row = await ctrash.move_to_trash(db, resource, existing, actor=user,\n"
     "                                     slug_field=cfg.get(\"slug_field\"))",
     "hapus konten kembali permanen (Tempat Sampah dilewati) — satu salah klik = konten hilang"),
    ("L02", BACKEND / "routers" / "content.py",
     "        redirect_row = await credir.record_slug_change(db, resource, item_id, old_slug,\n"
     "                                                      new_slug, user)",
     "        redirect_row = None",
     "slug berubah tanpa mencatat pengalihan → URL lama mati 404, peringkat pencarian hilang"),
    ("L03", BACKEND / "routers" / "content.py",
     "        await cver.snapshot(db, resource, item_id, after, actor=user, action=\"update\",\n"
     "                            before=existing)",
     "        pass",
     "penyuntingan tanpa jejak versi → isi lama mustahil dipulihkan setelah salah tempel"),
    ("L04", BACKEND / "services" / "content_trash.py",
     '        doc["status"] = "draft"',
     '        doc["status"] = "published"',
     "konten yang pernah dibuang diam-diam TAYANG lagi saat dipulihkan (tanpa diperiksa manusia)"),
    ("L05", BACKEND / "services" / "content_redirects.py",
     "    await db[COLLECTION].update_many(\n"
     "        {\"to_path\": old_path}, {\"$set\": {\"to_path\": new_path, \"updated_at\": now}})",
     "    pass",
     "rantai pengalihan A→B→C tidak diratakan → dua lompatan, mudah putus & lambat"),
    ("L06", BACKEND / "services" / "content_redirects.py",
     '    await db[COLLECTION].delete_many({"from_path": new_path})',
     "    pass",
     "pengalihan berputar (lingkaran) mungkin terjadi saat slug dikembalikan ke nilai lama"),
    ("L07", BACKEND / "server.py",
     "            from services.content_trash import purge_expired as trash_purge\n"
     "            purged = await trash_purge(db)",
     "            purged = 0",
     "tempat sampah tak pernah dikosongkan otomatis → konten terhapus tersimpan selamanya"),
    ("L08", GUARD_DIR / "_common.py",
     '    "content_versions", "content_trash", "content_redirects",\n)',
     '    "content_versions",\n)',
     "artefak data uji tertinggal di Tempat Sampah & tabel pengalihan milik editor (BUG-0127)"),
    ("L09", SRC / "features" / "app" / "ContentManager.jsx",
     'data-testid="content-bulk-bar"',
     'data-testid="content-bulk-strip"',
     "bar aksi massal hilang dari UI → fitur ada di backend, tak bisa dipakai pengguna"),
    ("L10", SRC / "features" / "app" / "ContentManager.jsx",
     'data-testid="content-trash-open"',
     'data-testid="content-trash-button"',
     "tombol Tempat Sampah hilang → editor tidak punya jalan pulang dari salah hapus"),
    ("L11", SRC / "features" / "public" / "BlogDetail.jsx",
     "  const { checking: redirecting } = useSlugRedirect(notFound);",
     "  const { checking: redirecting } = { checking: false };",
     "artikel dengan slug lama tetap jalan buntu meski pengalihan tercatat di server"),
]


def run_guard():
    proc = subprocess.run([sys.executable, str(GUARD_DIR / GUARD)],
                          capture_output=True, text=True, cwd=str(ROOT))
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def settle(path):
    """Tunggu backend selesai hot-reload sesudah berkas backend disentuh.

    JEBAKAN NYATA (terjadi saat self-test ini pertama dijalankan): menyunting berkas di
    `backend/` memicu uvicorn `--reload`. Bila penjaga langsung dijalankan, probe RUNTIME-nya
    menabrak server yang sedang restart → penjaga MERAH "setelah revert" padahal kode sudah
    pulih. Itu laporan bug PALSU, dan justru kelas kesalahan yang paling membuang waktu.
    """
    try:
        path.relative_to(BACKEND)
    except ValueError:
        return                                  # berkas frontend: tak ada reload backend
    time.sleep(2.5)                             # beri waktu watchfiles memicu reload
    for _ in range(40):
        try:
            with urllib.request.urlopen(HEALTH, timeout=3) as resp:
                if 200 <= resp.status < 500:
                    time.sleep(0.8)             # biarkan modul selesai dimuat
                    return
        except Exception:                        # noqa: BLE001 — masih restart
            pass
        time.sleep(0.5)
    print(f"  {Y}!{X} backend tidak kembali sehat dalam 20s — hasil berikutnya bisa palsu")


def main() -> int:
    print(f"\n{C}{B}SELF-TEST MUTASI — siklus hidup konten CMS (INV-CMS-01){X}")
    failures = []

    rc0, out0 = run_guard()
    if rc0 != 0:
        print(f"  {R}✗{X} penjaga sudah MERAH sebelum mutasi — perbaiki pelanggaran nyata dulu.")
        print(out0[-1200:])
        return 1
    print(f"  {G}✓{X} baseline HIJAU (siklus hidup konten aman sebelum mutasi)")

    for code, path, original, mutated, impact in MUTATIONS:
        if not path.exists():
            failures.append(f"{code}: berkas {path.name} tidak ada — self-test usang.")
            print(f"  {R}✗{X} {code} berkas hilang: {path.name}")
            continue
        src = path.read_text()
        if original not in src:
            failures.append(f"{code}: jangkar mutasi tak ditemukan di {path.name} — self-test "
                            f"usang (kode berubah, mutasi harus diperbarui).")
            print(f"  {R}✗{X} {code} jangkar hilang di {path.name}")
            continue
        path.write_text(src.replace(original, mutated, 1))
        settle(path)
        try:
            rc, _ = run_guard()
        finally:
            path.write_text(src)
            settle(path)
        if rc == 0:
            failures.append(f"{code}: penjaga tetap HIJAU padahal bug disuntikkan → {impact}.")
            print(f"  {R}✗{X} {code} LOLOS penjaga (perlindungan bocor): {impact}")
        else:
            print(f"  {G}✓{X} {code} {impact} — MERAH sesuai harapan")
        rc_back, _ = run_guard()
        if rc_back != 0:
            failures.append(f"{code}: setelah revert penjaga masih MERAH — berkas tidak pulih.")
            print(f"  {R}✗{X} {code} tidak pulih setelah revert")

    if failures:
        print(f"\n{R}{B}[FAIL]{X} {len(failures)} masalah pada pembuktian penjaga:")
        for f in failures:
            print(f"  {R}✗{X} {f}")
        return 1
    print(f"\n{G}{B}[PASS]{X} {len(MUTATIONS)} mutasi: penjaga MERAH saat pelanggaran disuntikkan "
          f"dan HIJAU kembali setelah dipulihkan.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
