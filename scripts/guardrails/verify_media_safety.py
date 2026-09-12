#!/usr/bin/env python3
"""INV-MEDIA-02 — Penyimpanan media aman & URL bacanya benar (anti "gambar 404" & anti path traversal).

Kelas bug yang ditutup (nyata, ditemukan di fase F8):
  1. `routers/landing.py` menyimpan `url = "/api/media/{id}"` padahal rute yang ADA adalah
     `/api/public/media/{id}`. Unggah SUKSES, database benar, tetapi SETIAP gambar & video di
     halaman iklan 404 — tanpa satu pun error di backend. Halaman iklan tanpa gambar = uang
     iklan terbakar.
  2. Penyimpanan lokal membaca berkas dari jalur yang berasal dari database/klien. Tanpa pagar,
     `../../etc/passwd` bisa dibaca lewat endpoint media PUBLIK.

Penjaga STATIK + EKSEKUSI RINGAN (tanpa DB/jaringan):
  (1) URL yang ditulis router HARUS memakai prefix rute publik yang benar-benar terdaftar,
  (2) endpoint pembaca media wajib ada di router publik (tanpa auth) — halaman iklan tak login,
  (3) `media_store.fetch` menolak path traversal / jalur kosong / NUL byte,
  (4) nama berkas hasil unggah TIDAK memakai nama dari pengguna (anti tabrakan & anti tebak),
  (5) validasi MIME + batas ukuran tetap ada (INV-MEDIA-01 tidak boleh melemah),
  (6) unggah/hapus media tetap di balik `require_section("landing")`,
  (7) penyimpanan punya status kesiapan yang JUJUR (`storage_info`) sehingga UI bisa menjelaskan
      sebabnya, bukan gagal senyap.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from _common import BACKEND, Guard  # noqa: E402

sys.path.insert(0, str(BACKEND))

LANDING = BACKEND / "routers" / "landing.py"
PUBLIC = BACKEND / "routers" / "public.py"
STORE = BACKEND / "services" / "media_store.py"


def read(path):
    return path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""


def signature(text: str, fn: str) -> str:
    """Ambil tanda tangan fungsi dengan MENYEIMBANGKAN tanda kurung.

    Regex `[^)]*` tidak bisa dipakai di sini: `File(...)`/`Query(default=...)` memuat tanda
    kurung bersarang sehingga tanda tangan terpotong dan penjaga melaporkan temuan PALSU
    (pelajaran: jangan mem-parsing Python dengan regex naif).
    """
    marker = f"async def {fn}("
    start = text.find(marker)
    if start < 0:
        return ""
    i = start + len(marker) - 1
    depth = 0
    for j in range(i, len(text)):
        if text[j] == "(":
            depth += 1
        elif text[j] == ")":
            depth -= 1
            if depth == 0:
                return text[i:j + 1]
    return ""


def main() -> int:
    g = Guard("INV-MEDIA-02", "Penyimpanan media aman + URL baca media benar (tak ada gambar 404)")
    landing_txt, public_txt, store_txt = read(LANDING), read(PUBLIC), read(STORE)

    g.bump()
    if not store_txt:
        g.add("services/media_store.py TIDAK ADA — Media Library mati total.")
        return g.finish()

    # (2) rute publik pembaca media harus ada (prefix router publik + path)
    prefix = ""
    m = re.search(r'APIRouter\(prefix="([^"]+)"', public_txt)
    if m:
        prefix = m.group(1)
    g.bump()
    media_route = re.search(r'@router\.get\("(/media/\{[a-z_]+\})"', public_txt)
    if not media_route:
        g.add("routers/public.py tidak punya GET /media/{id} — halaman iklan (tanpa login) "
              "tidak bisa memuat gambar/video sama sekali.")
    expected = f"{prefix}{media_route.group(1).split('{')[0]}" if media_route else ""

    # (1) URL yang ditulis router landing HARUS cocok dengan rute yang benar-benar ada
    g.bump()
    urls = re.findall(r'f"(/api/[^"]*media/[^"]*)"', landing_txt)
    if not urls:
        g.add("routers/landing.py tidak membangun URL media — klien tidak tahu cara memuat aset.")
    for url in urls:
        g.bump()
        base = url.split("{")[0]
        if expected and not base.startswith(expected):
            g.add(f"URL media '{url}' TIDAK cocok dengan rute publik yang ada ('{expected}...') → "
                  f"semua gambar & video halaman iklan akan 404 tanpa error backend (BUG-0112).")

    # (3) pagar path traversal benar-benar bekerja (dieksekusi, bukan sekadar dibaca)
    try:
        from services import media_store as ms
        blocked = 0
        evil_paths = ("../../../etc/passwd", "/etc/passwd", "a/../../../../etc/hosts", "", "\x00x",
                      "..\\..\\windows\\system32")
        for evil in evil_paths:
            g.bump()
            try:
                ms.fetch(evil, backend="local")
                g.add(f"media_store.fetch('{evil!r}') TIDAK ditolak → endpoint media publik bisa "
                      f"membaca berkas sistem (path traversal).")
            except ms.MediaError:
                blocked += 1
            except Exception as exc:  # noqa: BLE001
                # error lain masih menolak baca, tetapi pesannya bukan pesan yang dirancang
                if isinstance(exc, (FileNotFoundError, IsADirectoryError, PermissionError, OSError)):
                    blocked += 1
                else:
                    g.add(f"media_store.fetch('{evil!r}') melempar {type(exc).__name__} "
                          f"(bukan MediaError) → endpoint bisa balas 500 alih-alih 404.")
        g.bump()
        if blocked < len(evil_paths):
            g.add(f"hanya {blocked}/{len(evil_paths)} jalur berbahaya yang tertolak.")

        # (4) nama berkas hasil unggah tidak boleh memakai nama pengguna
        g.bump()
        path = ms.build_path("image", ".png", folder="landing")
        if not re.search(r"/[0-9a-f]{16,}\.png$", path):
            g.add(f"build_path menghasilkan '{path}' — nama berkas harus acak (UUID), bukan turunan "
                  f"nama unggahan pengguna (anti tabrakan & anti tebak).")

        # (5) validasi MIME + batas ukuran masih hidup
        g.bump()
        kind, _ext, _limit = ms.classify("application/x-msdownload")
        if kind is not None:
            g.add("media_store.classify menerima tipe berkas eksekutabel — INV-MEDIA-01 melemah.")
        g.bump()
        if not (0 < ms.MAX_IMAGE_BYTES <= 25 * 1024 * 1024 and 0 < ms.MAX_VIDEO_BYTES <= 200 * 1024 * 1024):
            g.add("batas ukuran unggah media tidak masuk akal (halaman iklan jadi lambat / disk penuh).")

        # (7) status penyimpanan jujur & tanpa rahasia
        g.bump()
        info = ms.storage_info()
        if not {"backend", "ready", "reason", "max_image_mb"} <= set(info):
            g.add("storage_info() tidak melaporkan status kesiapan lengkap → UI tidak bisa "
                  "menjelaskan kenapa unggah gagal (gagal senyap).")
        g.bump()
        if any(str(v) and str(v) in str(info) for v in [os.environ.get("EMERGENT_LLM_KEY") or "\u0000"] if v):
            g.add("storage_info() membocorkan kunci rahasia ke klien (INV-SEC-01).")
    except Exception as exc:  # noqa: BLE001
        g.bump()
        g.add(f"gagal menguji media_store secara langsung: {type(exc).__name__}: {exc}")

    # (6) RBAC: unggah & hapus media hanya untuk pengelola halaman iklan
    for fn in ("upload_media", "delete_media", "list_media", "update_media"):
        g.bump()
        sig = signature(landing_txt, fn)
        if not sig or "Depends(LANDING)" not in sig:
            g.add(f"routers/landing.py::{fn} tidak memakai Depends(LANDING) → media halaman iklan "
                  f"bisa diubah peran yang tidak berhak (INV-MEDIA-01).")

    # endpoint publik media harus read-only (tidak ada POST/DELETE di router publik)
    g.bump()
    if re.search(r'@router\.(post|delete|patch|put)\("/media', public_txt):
        g.add("router publik punya endpoint TULIS pada /media — siapa pun bisa mengubah aset.")

    return g.finish()


if __name__ == "__main__":
    sys.exit(main())
