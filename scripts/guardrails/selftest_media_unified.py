#!/usr/bin/env python3
"""selftest_media_unified.py — SELF-TEST (uji MUTASI) untuk penjaga INV-MEDIA-03.

Kenapa file ini ada
-------------------
Sebuah penjaga yang **belum pernah terlihat MERAH** tidak bisa dibedakan dari `return 0`.
Itu bentuk kegagalan terburuk pada sistem gate: hijau, meyakinkan, dan sama sekali tidak
melindungi. Penjaga bisa berhenti "menggigit" tanpa satu pun error, misalnya karena:

  * regex-nya tak lagi cocok setelah kode diformat ulang (dekorator jadi multi-baris),
  * nama fungsi yang dicari berubah → potongan badan fungsi jadi string kosong → semua cek
    "tidak ada X di string kosong" jadi ... tetap lolos di jalur yang salah,
  * blok cek dipindah ke dalam `if` yang tak pernah benar (mis. folder `frontend/src` tak ada),
  * seseorang "memperbaiki gate" dengan melunakkan cek, bukan memperbaiki kode.

Sesi sebelumnya melakukan self-test secara MANUAL (rusakkan kode → lihat MERAH → revert) dan
mencatat hasilnya di `memory/INVARIANTS.md`. Masalahnya: bukti manual itu kedaluwarsa sejak
detik kode berubah, dan sesi berikutnya TIDAK punya cara memverifikasi ulang selain mengulang
seluruh prosedur dengan tangan. Skrip ini mengubah self-test menjadi **otomatis, berulang, dan
ikut gate**: setiap kali gate berjalan, penjaga INV-MEDIA-03 dibuktikan MASIH menggigit.

Cara kerja (aman: TIDAK menyentuh kode nyata)
---------------------------------------------
1. Membuat SANDBOX di direktori sementara: salinan `scripts/guardrails`, `backend`,
   dan `frontend/src` (tanpa `node_modules`/`uploads`/`__pycache__`).
2. Menjalankan penjaga di sandbox tanpa perubahan → WAJIB HIJAU (kalibrasi dasar).
3. Untuk setiap MUTASI (masing-masing memperkenalkan kembali satu kelas bug NYATA yang pernah
   terjadi), menyuntikkan perubahan ke salinan, menjalankan penjaga, lalu memulihkan berkas:
   penjaga WAJIB MERAH **dan** pesannya WAJIB memuat penjelasan yang benar.
4. Setiap mutasi juga memvalidasi dirinya sendiri: bila teks sasaran tak ditemukan (kode sudah
   berubah), itu dilaporkan sebagai KEGAGALAN "mutasi basi" — bukan lolos diam-diam. Tanpa aturan
   ini, refactor biasa akan mengosongkan self-test tanpa ada yang sadar.

Keluar 0 = penjaga terbukti menggigit di SEMUA kelas bug yang diklaimnya.
Keluar 1 = ada lubang: penjaga tetap hijau padahal bug sudah disuntikkan (atau self-test basi).
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from _common import B, C, G, R, ROOT, X, Y  # noqa: E402

GUARD_REL = "scripts/guardrails/verify_media_unified.py"
COPY = ("scripts/guardrails", "backend", "frontend/src")
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", "node_modules", "uploads",
                                ".git", "*.log", "venv", ".venv")
ANSI = re.compile(r"\x1b\[[0-9;]*m")

BE = "backend"
FE = "frontend/src"

# ---------------------------------------------------------------------------------------------
# MUTASI = kelas bug nyata yang pernah menyakiti sistem ini. `expect` sengaja mengutip potongan
# pesan penjaga: memaksa penjaga tidak cuma MERAH, tapi merah dengan ALASAN yang benar (pesan
# salah = sesi berikutnya memperbaiki hal yang salah).
# ---------------------------------------------------------------------------------------------
MUTATIONS = [
    dict(
        key="M01 dua-dunia-media (router menulis berkas sendiri)",
        file=f"{BE}/routers/content.py",
        old='meta = ms.upload_bytes(blob, ctype, filename=image.filename, folder="cms")',
        new='dest = Path("uploads/cms") / image.filename; dest.write_bytes(blob); meta = {}',
        expect="menulis berkas SENDIRI",
        impact="aset CMS kembali tak tercatat di Mongo → tak bisa dicari/dipakai ulang, ratusan "
               "berkas 'tak terlihat' di disk.",
    ),
    dict(
        key="M02 aset tak didaftarkan ke Media Library",
        file=f"{BE}/routers/content.py",
        old='doc = await ml.register_asset(db, meta, user, folder_id="", alt="", source="cms")',
        new='doc = {"id": "med_x", "original_filename": image.filename}',
        expect="register_asset",
        impact="unggahan CMS baru tidak akan pernah muncul di Media Library.",
    ),
    dict(
        key="M03 router lain menulis berkas media langsung",
        file=f"{BE}/routers/landing.py",
        old="from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Query, UploadFile",
        new="from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Query, UploadFile\n"
            'from pathlib import Path as _P\n_SHORTCUT = _P("uploads/landing/x.jpg").write_bytes(b"")',
        expect="menulis berkas langsung",
        impact="validasi MIME/ukuran & pagar path-traversal di media_store dilewati lewat jalan pintas.",
    ),
    dict(
        key="M04 endpoint media tanpa RBAC Depends(MEDIA)",
        file=f"{BE}/routers/media.py",
        old="async def download_media(media_id: str, user=Depends(MEDIA)):",
        new="async def download_media(media_id: str, user=Depends(get_current_user)):",
        expect="TIDAK memakai Depends(MEDIA)",
        impact="siapa pun yang login (termasuk sopir) bisa mengunduh berkas asli aset perusahaan.",
    ),
    dict(
        key="M05 RBAC hilang di dekorator MULTI-BARIS (uji anti-regex)",
        file=f"{BE}/routers/media.py",
        old='@router.get("/media/{media_id}/usage")\nasync def media_usage(media_id: str, user=Depends(MEDIA)):',
        new='@router.get(\n    "/media/{media_id}/usage",\n    response_model=dict,\n)\n'
            "async def media_usage(media_id: str, user=Depends(get_current_user)):",
        expect="TIDAK memakai Depends(MEDIA)",
        impact="format dekorator saja berubah → penjaga versi regex berhenti memindai rute itu "
               "(hijau-palsu). Ini alasan pemindaian rute memakai AST.",
    ),
    dict(
        key="M06 unduh memakai nama berkas mentah (header injection)",
        file=f"{BE}/routers/media.py",
        old='name = ml.safe_display_name(doc.get("original_filename") or media_id, media_id)',
        new='name = doc.get("original_filename") or media_id',
        expect="header injection",
        impact="nama berkas dari input pengguna masuk header HTTP tanpa sanitasi.",
    ),
    dict(
        key="M07 ETag hilang di endpoint media publik",
        file=f"{BE}/routers/public.py",
        old='"ETag": etag',
        new='"X-Media-Tag": etag',
        count=2,
        expect="tidak mengirim ETag",
        impact="setelah 'Ganti berkas', foto lama tetap tampil sampai cache kedaluwarsa.",
    ),
    dict(
        key="M08 cache membeku (kembali ke max-age panjang tanpa revalidasi)",
        file=f"{BE}/routers/public.py",
        old='cache = "public, max-age=31536000, immutable" if fresh else "public, max-age=60, must-revalidate"',
        new='cache = "public, max-age=86400"',
        expect="membeku di cache browser",
        impact="keluhan klasik 'sudah saya ganti kok tidak berubah' selama sehari penuh.",
    ),
    dict(
        key="M09 version tidak naik saat berkas diganti",
        file=f"{BE}/services/media_lib.py",
        old='patch["version"] = int(doc.get("version") or 1) + 1',
        new='patch["version"] = int(doc.get("version") or 1)',
        expect="tidak menaikkan",
        impact="penanda versi jadi hiasan → URL berversi tak pernah berubah → cache tak pernah batal.",
    ),
    dict(
        key="M10 berkas lama tidak dibuang saat diganti",
        file=f"{BE}/services/media_lib.py",
        old='ms.remove(path, backend=doc.get("storage_backend") or "")',
        new="pass  # berkas lama dibiarkan menumpuk",
        expect="menumpuk sampah di disk",
        impact="disk penuh = SEMUA unggahan gagal, termasuk yang sedang dikejar tenggat iklan.",
    ),
    dict(
        key="M11 jalur penyimpanan internal bocor ke klien",
        file=f"{BE}/services/media_lib.py",
        old='if k not in ("_id", "storage_path", "thumb_path", "sha256")',
        new='if k not in ("_id", "sha256")',
        expect="jalur penyimpanan internal",
        impact="struktur penyimpanan terekspos → memudahkan penebakan/penyalahgunaan.",
    ),
    dict(
        key="M12 folder bisa dipindah ke dalam cucunya (pulau terputus)",
        file=f"{BE}/services/media_lib.py",
        old="if folder_id in chain:",
        new="if False:  # cek siklus dimatikan",
        expect="cucunya sendiri",
        impact="folder + seluruh isinya hilang dari daftar padahal datanya masih ada.",
    ),
    dict(
        key="M13 hapus folder MENGHAPUS aset di dalamnya",
        file=f"{BE}/services/media_lib.py",
        old='moved = await db[MEDIA].update_many({"folder_id": folder_id},\n'
            '                                        {"$set": {"folder_id": parent, "updated_at": now_iso()}})',
        new='moved = await db[MEDIA].update_many({"folder_id": folder_id},\n'
            '                                        {"$set": {"deleted": True, "updated_at": now_iso()}})',
        expect="MENGHAPUS aset di dalam folder",
        impact="satu klik salah memusnahkan ratusan foto yang sedang tayang — tak bisa dibatalkan.",
    ),
    dict(
        key="M14 dua folder bernama sama di satu lokasi",
        file=f"{BE}/services/media_lib.py",
        old='dup = await db[FOLDERS].find_one({"parent_id": parent, "name": clean}, {"_id": 0, "id": 1})',
        new="dup = None",
        expect="dua folder bernama sama",
        impact="pengguna tak bisa membedakan folder tujuan saat memindahkan aset.",
    ),
    dict(
        key="M15 impor aset lama tak lagi idempoten (indeks unik hilang)",
        file=f"{BE}/services/media_lib.py",
        old='"legacy_key", unique=True,',
        new='"legacy_key", sparse=True,',
        expect="aset ganda",
        impact="dua klik 'Daftarkan aset CMS lama' menghasilkan dua entri untuk satu berkas.",
    ),
    dict(
        key="M16 URL lama tidak disimpan saat impor",
        file=f"{BE}/services/media_lib.py",
        old='"legacy_url": f"/api/uploads/cms/{path.name}"',
        new='"legacy_url": ""',
        expect="URL lama",
        impact="pemakaian aset di konten yang sudah tayang tak bisa dilacak sebelum aset dihapus.",
    ),
    dict(
        key="M17 batas sisi hasil potong tidak ditegakkan",
        file=f"{BE}/services/media_store.py",
        old="if tw > MAX_CROP_SIDE or th > MAX_CROP_SIDE:\n"
            '            raise MediaError(f"Ukuran akhir maksimal {MAX_CROP_SIDE} piksel per sisi.")',
        new="if False:\n            pass",
        expect="batas sisi hasil potong",
        impact="permintaan potong 60000px membuat server kehabisan memori (seluruh aplikasi mati).",
    ),
    dict(
        key="M18 konsumen media kembali pakai kotak unggah sendiri",
        file=f"{FE}/components/cms/GalleryManager.jsx",
        old="components/media/MediaPickerDialog",
        new="components/cms/LegacyUrlBox",
        expect="MediaPickerDialog",
        impact="penyatuan pemilih media terkikis satu komponen per ronde sampai kembali seperti semula.",
    ),
    dict(
        key="M19 menu Media Library hilang dari navigasi",
        file=f"{FE}/config/navigationConfig.js",
        old='{ id: "media", label: "Media Library", icon: Images, path: "/app/media" },',
        new="",
        expect='"/app/media"',
        impact="backend hidup tapi pengguna tak punya jalan masuk — fitur mati diam-diam.",
    ),
    dict(
        key="M20 ops_admin dicabut dari Media Library (dua dunia media kembali)",
        file=f"{FE}/config/navigationConfig.js",
        old='"reports", "ads", "cms", "media"]',
        new='"reports", "ads", "cms"]',
        expect="ops_admin",
        impact="pemegang CMS kembali tak bisa memakai Media Library — pemisahan yang justru dihapus.",
    ),
    dict(
        key="M21 route /app/media dicabut dari App.js",
        file=f"{FE}/App.js",
        old='<Route path="media" element={<RoleGuard section="media"><MediaManager /></RoleGuard>} />',
        new="",
        expect="route `media`",
        impact="menu tampil tapi klik menghasilkan halaman kosong.",
    ),
    dict(
        key="M22 impor picker HANYA dikomentari (bukan dipakai)",
        file=f"{FE}/components/cms/GalleryManager.jsx",
        old='import MediaPickerDialog from "@/components/media/MediaPickerDialog";',
        new='// import MediaPickerDialog from "@/components/media/MediaPickerDialog";',
        expect="MediaPickerDialog",
        impact="cek 'ada teksnya' bisa dipenuhi baris yang sudah dimatikan → gate hijau, fitur mati.",
    ),
    dict(
        key="M23 header ETag diganti nama, kata 'ETag' cuma tinggal di docstring",
        file=f"{BE}/routers/public.py",
        old='headers={"Cache-Control": cache, "ETag": etag})',
        new='headers={"Cache-Control": cache, "X-Media-Tag": etag})',
        expect="tidak mengirim ETag",
        impact="LUBANG NYATA yang ditemukan self-test ini: penjaga dulu puas karena kata 'ETag' "
               "masih ada di DOCSTRING fungsi, padahal header aslinya sudah hilang.",
    ),
    dict(
        key="M24 .strip() pada nilai klien tanpa str() (kelas bug HTTP 500 nyata)",
        file=f"{BE}/routers/media.py",
        old='fid = str(body.get("folder_id") or "").strip()',
        new='fid = (body.get("folder_id") or "").strip()',
        count=2,
        expect="HTTP 500 alih-alih 4xx",
        impact="klien mengirim `folder_id: 5` → AttributeError → HTTP 500. Bug ini NYATA: "
               "ditemukan gate RUNTIME Fase 3 pada PATCH /api/media/{id} dan sudah diperbaiki.",
    ),
]


def strip_ansi(text: str) -> str:
    return ANSI.sub("", text or "")


def build_sandbox(dst: Path):
    for rel in COPY:
        src = ROOT / rel
        if not src.exists():
            print(f"{R}[FATAL]{X} sumber `{rel}` tidak ada — sandbox tak bisa dibangun.")
            return False
        shutil.copytree(src, dst / rel, ignore=IGNORE, symlinks=False)
    return True


def run_guard(sandbox: Path):
    proc = subprocess.run([sys.executable, str(sandbox / GUARD_REL)], cwd=str(sandbox),
                          capture_output=True, text=True, timeout=180)
    return proc.returncode, strip_ansi(proc.stdout + proc.stderr)


def main() -> int:  # noqa: C901
    t0 = time.time()
    print(f"{C}{B}== SELF-TEST INV-MEDIA-03 — uji mutasi penjaga verify_media_unified.py =={X}")
    tmp = Path(tempfile.mkdtemp(prefix="selftest_media_"))
    failures = []
    try:
        sandbox = tmp / "root"
        sandbox.mkdir(parents=True)
        if not build_sandbox(sandbox):
            return 1

        rc, out = run_guard(sandbox)
        checks = re.search(r"(\d+) cek lolos", out)
        if rc != 0:
            print(f"{R}[FATAL]{X} baseline (kode BERSIH) sudah MERAH — self-test tak bisa "
                  f"membedakan mutasi dari kerusakan yang sudah ada. Perbaiki penjaga/kode dulu:")
            print("    " + "\n    ".join(out.strip().splitlines()[-12:]))
            return 1
        print(f"  {G}✓{X} baseline kode bersih: HIJAU ({checks.group(1) if checks else '?'} cek)")

        for mut in MUTATIONS:
            target = sandbox / mut["file"]
            label = mut["key"]
            if not target.exists():
                failures.append(f"{label}: berkas sasaran `{mut['file']}` tidak ada (self-test basi).")
                print(f"  {R}✗{X} {label} — berkas sasaran hilang")
                continue
            original = target.read_text(encoding="utf-8")
            want = int(mut.get("count", 1))
            got = original.count(mut["old"])
            if got != want:
                failures.append(
                    f"{label}: teks sasaran ditemukan {got}x (diharapkan {want}x) di `{mut['file']}` "
                    f"→ MUTASI BASI: kode sudah berubah sehingga kelas bug ini TIDAK lagi diuji. "
                    f"Perbarui `old` di scripts/guardrails/selftest_media_unified.py.")
                print(f"  {R}✗{X} {label} — mutasi basi (sasaran {got}x, mau {want}x)")
                continue
            try:
                target.write_text(original.replace(mut["old"], mut["new"]), encoding="utf-8")
                rc, out = run_guard(sandbox)
            finally:
                target.write_text(original, encoding="utf-8")

            if rc == 0:
                failures.append(
                    f"{label}: penjaga TETAP HIJAU padahal bug sudah disuntikkan → LUBANG penjaga. "
                    f"Dampak bila lolos ke produksi: {mut['impact']}")
                print(f"  {R}✗{X} {label} — penjaga tetap HIJAU (lubang)")
            elif mut["expect"] not in out:
                failures.append(
                    f"{label}: penjaga MERAH tetapi pesannya tidak memuat `{mut['expect']}` → sesi "
                    f"berikutnya bisa memperbaiki hal yang salah. Pesan: "
                    f"{' | '.join(l.strip() for l in out.splitlines() if '✗' in l)[:300]}")
                print(f"  {Y}~{X} {label} — MERAH tapi pesan tidak spesifik")
            else:
                print(f"  {G}✓{X} {label} — MERAH sesuai harapan")

        rc, out = run_guard(sandbox)
        if rc != 0:
            failures.append("sandbox tidak bersih setelah semua mutasi dipulihkan (harness bocor) — "
                            "hasil self-test tak bisa dipercaya.")
            print(f"  {R}✗{X} pemulihan sandbox GAGAL")
        else:
            print(f"  {G}✓{X} sandbox pulih bersih (penjaga HIJAU kembali)")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    dur = time.time() - t0
    print(f"{C}{B}-- ringkasan self-test INV-MEDIA-03 ({len(MUTATIONS)} mutasi, {dur:.1f}s) --{X}")
    if not failures:
        print(f"{G}[PASS]{X} {len(MUTATIONS)}/{len(MUTATIONS)} kelas bug terbukti DITANGKAP penjaga "
              f"(bukan sekadar hijau).")
        return 0
    print(f"{R}[FAIL]{X} {len(failures)} lubang/keusangan pada penjaga INV-MEDIA-03:")
    for f in failures:
        print(f"  {R}✗{X} {f}")
    print(f"{Y}→ Penjaga yang tak menggigit = perlindungan palsu. Perbaiki penjaga "
          f"(scripts/guardrails/verify_media_unified.py), JANGAN melunakkan self-test.{X}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
