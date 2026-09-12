"""services/media_store.py — Media Library (gambar & video) untuk Landing Page Builder & CMS.

DUA backend penyimpanan, dipilih lewat env `MEDIA_BACKEND` (default **local**):

* **local** (DEFAULT) — berkas ditulis ke disk pod di bawah `backend/uploads/media/`.
  Dipilih sebagai default karena Media Library harus HIDUP tanpa kredensial apa pun; marketing
  admin tidak boleh terhalang unggah foto hanya karena kunci integrasi belum dipasang.
  Direktori berada di dalam `/app` sehingga bertahan selama pod hidup.
  BATAS JUJUR: bila pod dibuat ulang dari repo bersih, berkas biner TIDAK ikut (di-gitignore).
  Metadata selalu tersimpan di Mongo (`media_assets`) beserta `storage_backend`, sehingga
  migrasi ke object storage = unggah ulang berkas lalu tukar backend per aset (tanpa migrasi skema).

* **objstore** — object storage platform (butuh `EMERGENT_LLM_KEY`). Batasan resmi yang dihormati:
  init sekali -> `storage_key` (session-scoped; 403/404 di tengah sesi = kunci mati -> init(force)),
  TIDAK ada presigned URL (semua akses lewat backend), TIDAK ada API hapus (soft-delete di Mongo),
  TIDAK ada rename (unggah ke path baru), tulis ke path sama = overwrite.

Karena tanpa presigned URL, SEMUA akses baca melalui `GET /api/public/media/{id}`
(lihat routers/public.py). Video besar tidak boleh di-proxy (buruk untuk Core Web Vitals halaman
iklan): batas unggah video 50MB + wajib poster; video berat memakai embed URL (YouTube/Vimeo).

Keamanan (INV-MEDIA-01/02): MIME + ukuran divalidasi sebelum tulis, nama berkas dibuang dan
diganti UUID (tidak ada nama dari pengguna di jalur berkas), dan setiap pembacaan lokal
dipagari `_local_abs()` supaya `../` tidak bisa keluar dari direktori media.
"""
import io
import logging
import os
import re
import time
import uuid
from pathlib import Path

import requests

logger = logging.getLogger("travel_fleet.media")

_BASE = (os.environ.get("INTEGRATION_PROXY_URL") or "").strip() or "https://integrations.emergentagent.com"
STORAGE_URL = _BASE.rstrip("/") + "/objstore/api/v1/storage"
APP_PREFIX = "rahaza-travel"

IMAGE_TYPES = {
    "image/jpeg": ".jpg", "image/jpg": ".jpg", "image/png": ".png",
    "image/webp": ".webp", "image/avif": ".avif", "image/gif": ".gif",
}
VIDEO_TYPES = {"video/mp4": ".mp4", "video/webm": ".webm", "video/quicktime": ".mov",
               "video/x-m4v": ".mp4"}
EXT_TYPES = {v: k for k, v in {**IMAGE_TYPES, **VIDEO_TYPES}.items()}
EXT_TYPES.update({".jpeg": "image/jpeg", ".m4v": "video/mp4"})
MAX_IMAGE_BYTES = 10 * 1024 * 1024   # 10 MB
MAX_VIDEO_BYTES = 50 * 1024 * 1024   # 50 MB (batas sadar-performa, lihat docstring)
THUMB_MAX = 480                       # sisi terpanjang thumbnail grid Media Library

BACKEND_DIR = Path(__file__).resolve().parent.parent
LOCAL_DIR = Path(os.environ.get("MEDIA_LOCAL_DIR") or (BACKEND_DIR / "uploads" / "media"))

_storage_key = None


class MediaError(RuntimeError):
    """Kegagalan penyimpanan objek yang harus dilaporkan jelas ke pengguna (bukan 5xx senyap)."""


# --------------------------------------------------------------------- pemilihan backend
def backend_name() -> str:
    name = (os.environ.get("MEDIA_BACKEND") or "local").strip().lower()
    return "objstore" if name in ("objstore", "object", "emergent", "platform") else "local"


def _emergent_key() -> str:
    return (os.environ.get("EMERGENT_LLM_KEY") or "").strip()


def storage_ready() -> bool:
    """Apakah unggah media bisa dilakukan sekarang (tanpa menyentuh jaringan)."""
    if backend_name() == "objstore":
        return bool(_emergent_key())
    try:
        LOCAL_DIR.mkdir(parents=True, exist_ok=True)
        probe = LOCAL_DIR / ".write-probe"
        probe.write_bytes(b"ok")
        probe.unlink(missing_ok=True)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("direktori media lokal tidak bisa ditulis: %s", exc)
        return False


def usage_bytes() -> int:
    """Total byte terpakai penyimpanan lokal (0 untuk objstore — tidak ada API kuota)."""
    if backend_name() == "objstore" or not LOCAL_DIR.exists():
        return 0
    total = 0
    try:
        for p in LOCAL_DIR.rglob("*"):
            if p.is_file():
                total += p.stat().st_size
    except Exception:  # noqa: BLE001
        return total
    return total


def storage_info() -> dict:
    """Ringkasan status penyimpanan untuk ditampilkan di UI Media Library (tanpa rahasia)."""
    backend = backend_name()
    ready = storage_ready()
    if backend == "objstore":
        reason = "" if ready else "EMERGENT_LLM_KEY belum diset di server."
        label = "Object storage platform"
    else:
        reason = "" if ready else "Direktori media lokal tidak bisa ditulis."
        label = "Disk lokal server"
    return {
        "backend": backend, "backend_label": label, "ready": ready, "reason": reason,
        "max_image_mb": MAX_IMAGE_BYTES // (1024 * 1024),
        "max_video_mb": MAX_VIDEO_BYTES // (1024 * 1024),
        "used_mb": round(usage_bytes() / (1024 * 1024), 2),
        "accepted": {"image": sorted({e.lstrip(".") for e in IMAGE_TYPES.values()}),
                     "video": sorted({e.lstrip(".") for e in VIDEO_TYPES.values()})},
    }


# --------------------------------------------------------------------- object storage platform
def init_storage(force: bool = False) -> str:
    global _storage_key
    if _storage_key and not force:
        return _storage_key
    key = _emergent_key()
    if not key:
        raise MediaError("EMERGENT_LLM_KEY belum diset — unggah ke object storage tidak tersedia.")
    resp = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": key}, timeout=30)
    if resp.status_code != 200:
        raise MediaError(f"Gagal inisialisasi penyimpanan objek (HTTP {resp.status_code}).")
    _storage_key = resp.json().get("storage_key")
    if not _storage_key:
        raise MediaError("Respons /init tidak memuat storage_key.")
    logger.info("Object storage siap")
    return _storage_key


def _put_objstore(path: str, data: bytes, content_type: str) -> dict:
    """Unggah objek. Tahan gangguan sesaat: 403/404 -> perbarui storage key; 5xx/timeout -> ulang
    dengan backoff. Alasan: unggahan video besar (belasan MB) kadang ditolak proxy penyimpanan
    dengan HTTP 500 sesaat — sekali gagal berarti pengguna kehilangan berkas yang sudah lama
    ter-upload, padahal percobaan kedua biasanya berhasil."""
    key = init_storage()
    last = ""
    for attempt in range(1, 4):
        try:
            r = requests.put(f"{STORAGE_URL}/objects/{path}",
                             headers={"X-Storage-Key": key, "Content-Type": content_type},
                             data=data, timeout=180)
        except requests.RequestException as exc:
            last = f"jaringan: {type(exc).__name__}"
            time.sleep(1.5 * attempt)
            continue
        if r.status_code in (403, 404):
            key = init_storage(force=True)
            last = f"HTTP {r.status_code} (kunci diperbarui)"
            continue
        if r.status_code >= 500:
            last = f"HTTP {r.status_code}"
            logger.warning("Unggah media gagal sesaat (%s) — percobaan %s/3", last, attempt)
            time.sleep(1.5 * attempt)
            continue
        if r.status_code >= 400:
            raise MediaError(f"Unggah gagal (HTTP {r.status_code}).")
        try:
            return r.json()
        except ValueError:
            return {}
    raise MediaError(f"Unggah gagal setelah 3 percobaan ({last}). Coba lagi beberapa saat.")


def _get_objstore(path: str):
    key = init_storage()
    r = requests.get(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": key}, timeout=120)
    if r.status_code in (403, 404):
        key = init_storage(force=True)
        r = requests.get(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": key}, timeout=120)
    if r.status_code >= 400:
        raise MediaError(f"Unduh gagal (HTTP {r.status_code}).")
    return r.content, r.headers.get("Content-Type", "application/octet-stream")


# --------------------------------------------------------------------- penyimpanan lokal
def _local_abs(rel_path: str) -> Path:
    """Pagar anti path-traversal: hasil resolve WAJIB berada di dalam LOCAL_DIR."""
    rel = str(rel_path or "").strip().replace("\\", "/").lstrip("/")
    if not rel or "\x00" in rel:
        raise MediaError("Jalur berkas media tidak sah.")
    base = LOCAL_DIR.resolve()
    target = (base / rel).resolve()
    if target != base and base not in target.parents:
        raise MediaError("Jalur berkas media tidak sah.")
    return target


def _put_local(path: str, data: bytes, content_type: str) -> dict:
    target = _local_abs(path)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(target.suffix + ".part")
        tmp.write_bytes(data)
        tmp.replace(target)  # tulis-atomik: pembaca tak pernah melihat berkas separuh
    except OSError as exc:
        raise MediaError(f"Gagal menulis berkas media ke disk: {exc.strerror or exc}.") from None
    return {"path": path, "size": len(data), "etag": ""}


def _get_local(path: str):
    target = _local_abs(path)
    if not target.is_file():
        raise MediaError("Berkas media tidak ada di penyimpanan lokal.")
    ctype = EXT_TYPES.get(target.suffix.lower(), "application/octet-stream")
    return target.read_bytes(), ctype


# --------------------------------------------------------------------- API dipakai router
def _write(path: str, data: bytes, content_type: str) -> dict:
    return _put_objstore(path, data, content_type) if backend_name() == "objstore" \
        else _put_local(path, data, content_type)


def safe_stem(filename: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9_-]+", "-", (filename or "").rsplit(".", 1)[0])[:60].strip("-")
    return stem or "media"


def classify(content_type: str):
    ct = (content_type or "").lower().split(";")[0].strip()
    if ct in IMAGE_TYPES:
        return "image", IMAGE_TYPES[ct], MAX_IMAGE_BYTES
    if ct in VIDEO_TYPES:
        return "video", VIDEO_TYPES[ct], MAX_VIDEO_BYTES
    return None, None, None


def resolve_content_type(content_type: str, filename: str = "") -> str:
    """MIME dari browser bila dikenal; kalau kosong/generik (Windows tanpa QuickTime mengirim
    `application/octet-stream` untuk .mov/.webm), tebak dari ekstensi nama berkas."""
    ct = (content_type or "").lower().split(";")[0].strip()
    if classify(ct)[0]:
        return ct
    guessed = guess_content_type(filename)
    return guessed if classify(guessed)[0] else (ct or "application/octet-stream")


def build_path(kind: str, ext: str, folder: str = "landing") -> str:
    safe_folder = re.sub(r"[^a-z0-9_-]+", "-", (folder or "landing").lower())[:32] or "landing"
    return f"{APP_PREFIX}/{safe_folder}/{kind}/{uuid.uuid4().hex}{ext}"


def _dimensions(data: bytes, kind: str):
    if kind != "image":
        return 0, 0
    try:
        from PIL import Image
        with Image.open(io.BytesIO(data)) as im:
            return int(im.width), int(im.height)
    except Exception:  # noqa: BLE001 — format eksotis tetap boleh diunggah, dimensi opsional
        return 0, 0


def _thumbnail(data: bytes, kind: str, path: str) -> str:
    """Thumbnail JPEG untuk grid Media Library. Gagal = bukan error (pakai gambar asli)."""
    if kind != "image":
        return ""
    try:
        from PIL import Image
        with Image.open(io.BytesIO(data)) as im:
            im = im.convert("RGB") if im.mode in ("RGBA", "P", "LA", "CMYK") else im
            im.thumbnail((THUMB_MAX, THUMB_MAX))
            buf = io.BytesIO()
            im.save(buf, format="JPEG", quality=82, optimize=True)
        tpath = f"{path.rsplit('.', 1)[0]}_thumb.jpg"
        _write(tpath, buf.getvalue(), "image/jpeg")
        return tpath
    except Exception as exc:  # noqa: BLE001
        logger.info("thumbnail dilewati (%s)", exc)
        return ""


def upload_bytes(data: bytes, content_type: str, filename: str = "", folder: str = "landing") -> dict:
    """Validasi MIME + ukuran lalu unggah. Mengembalikan metadata untuk koleksi `media_assets`."""
    kind, ext, limit = classify(content_type)
    if not kind:
        raise MediaError("Tipe berkas tidak didukung. Gambar: jpg/png/webp/avif/gif. Video: mp4/webm/mov.")
    if not data:
        raise MediaError("Berkas kosong.")
    if len(data) > limit:
        raise MediaError(f"Ukuran maksimal {'gambar' if kind == 'image' else 'video'} "
                         f"{limit // (1024 * 1024)}MB (berkas Anda {max(1, len(data) // (1024 * 1024))}MB). "
                         f"Untuk video panjang, gunakan tautan YouTube/Vimeo.")
    path = build_path(kind, ext, folder)
    res = _write(path, data, content_type) or {}
    width, height = _dimensions(data, kind)
    return {
        "kind": kind,
        "storage_backend": backend_name(),
        "storage_path": res.get("path") or path,
        "thumb_path": _thumbnail(data, kind, path),
        "size": int(res.get("size") or len(data)),
        "width": width,
        "height": height,
        "content_type": content_type.split(";")[0].strip(),
        "original_filename": safe_stem(filename),
        "etag": res.get("etag") or "",
    }


def fetch(storage_path: str, backend: str = ""):
    """Baca berkas. `backend` per-aset (dari Mongo) menang atas env → aset lama tetap terbaca
    setelah backend default diganti."""
    which = (backend or "").strip().lower() or backend_name()
    return _get_objstore(storage_path) if which == "objstore" else _get_local(storage_path)


# --------------------------------------------------------------------- Media Manager v2
def guess_content_type(filename: str) -> str:
    """Tipe MIME dari ekstensi — dipakai saat mengimpor berkas lama yang tak punya header HTTP."""
    ext = "." + str(filename or "").rsplit(".", 1)[-1].lower() if "." in str(filename or "") else ""
    return EXT_TYPES.get(ext, "application/octet-stream")


def check_file(storage_path: str, backend: str = ""):
    """Status berkas fisik → (state, reason). state: 'ok' | 'missing' | 'unknown'.

    RC-C (BUG-0134): dulu `exists()` mengembalikan bool sehingga SEMUA kegagalan pengecekan
    (kunci objstore tidak diset, gangguan jaringan, path mismatch/tidak sah) dihitung sebagai
    "berkas hilang" → notif MERAH PALSU padahal berkas ada. Sekarang hanya bukti nyata yang
    boleh merah: lokal = file benar-benar tidak ada; objstore = HTTP 404 dari penyimpanan.
    Kasus ambigu (cek gagal) = 'unknown' + alasan → warning kuning, bukan alarm merah.
    """
    which = (backend or "").strip().lower() or backend_name()
    path = str(storage_path or "").strip()
    if not path:
        return "unknown", "Jalur berkas kosong di dokumen aset (path mismatch/data lama)."
    if which == "objstore":
        if not _emergent_key():
            return "unknown", "EMERGENT_LLM_KEY tidak diset — keberadaan berkas objstore tidak bisa dicek."
        try:
            key = init_storage()
            r = requests.get(f"{STORAGE_URL}/objects/{path}",
                             headers={"X-Storage-Key": key}, timeout=20)
            if r.status_code in (401, 403):
                key = init_storage(force=True)
                r = requests.get(f"{STORAGE_URL}/objects/{path}",
                                 headers={"X-Storage-Key": key}, timeout=20)
            if r.status_code == 404:
                return "missing", "Object storage menjawab 404 — berkas terbukti tidak ada."
            if r.status_code < 400:
                return "ok", ""
            return "unknown", f"Object storage menjawab HTTP {r.status_code} — bukan bukti hilang."
        except MediaError as exc:
            return "unknown", f"Pengecekan objstore gagal: {exc}"
        except requests.RequestException as exc:
            return "unknown", f"Gangguan jaringan saat cek objstore: {exc.__class__.__name__}"
    try:
        target = _local_abs(path)
    except MediaError:
        return "unknown", "Jalur berkas tidak sah/di luar direktori media (path mismatch)."
    return ("ok", "") if target.is_file() else ("missing", "Berkas tidak ada di disk lokal server.")


def exists(storage_path: str, backend: str = "") -> bool:
    """Apakah berkas fisiknya benar-benar ada? Dipakai 'Pemulih Media' & panel kesehatan aset.

    Dibutuhkan karena dokumen `media_assets` bisa hidup tanpa berkasnya (pod baru dari repo bersih:
    berkas biner di-gitignore) — tanpa pemeriksaan ini gambar 404 tanpa satu pun error backend.
    Catatan RC-C: untuk PANEL kesehatan pakai `check_file` (tri-state) — bool ini hanya utk
    pemakai lama yang butuh jawaban kasar ('unknown' dianggap ada, agar tidak ada alarm palsu).
    """
    state, _reason = check_file(storage_path, backend=backend)
    return state != "missing"


def remove(storage_path: str, backend: str = "") -> bool:
    """Hapus berkas fisik (hanya penyimpanan lokal; object storage platform tak punya API hapus).

    Dipakai setelah "Ganti berkas": berkas lama harus dibuang, kalau tidak setiap penggantian
    menumpuk sampah di disk sampai penyimpanan penuh (dan penuh = SEMUA unggah gagal).
    """
    which = (backend or "").strip().lower() or backend_name()
    if which == "objstore" or not storage_path:
        return False
    try:
        target = _local_abs(storage_path)
    except MediaError:
        return False
    try:
        if target.is_file():
            target.unlink()
            return True
    except OSError as exc:
        logger.warning("gagal menghapus berkas media lama (%s): %s", storage_path, exc)
    return False


MAX_CROP_SIDE = 6000  # batas sisi hasil potong/ubah-ukuran (lindungi memori server)


def crop_bytes(data: bytes, rect: dict, target: dict = None):
    """Potong (dan opsional ubah ukuran) gambar dari kotak potong yang dikirim klien.

    Mengembalikan `(bytes, content_type, width, height)`.

    Validasi ketat & pesan jelas — bukan 500: kotak potong berasal dari klien, jadi angka nol,
    negatif, bukan-angka, atau melebihi batas gambar HARUS ditolak 4xx dengan alasan yang bisa
    ditampilkan pengguna. Format keluaran mempertahankan JPEG/PNG/WEBP; format eksotis (GIF/AVIF)
    dinormalkan ke PNG (menjaga transparansi) supaya hasil selalu bisa dirender browser.
    """
    from PIL import Image  # impor lokal: PIL hanya dibutuhkan pada jalur ini

    def _int(value, label):
        try:
            out = int(round(float(value)))
        except (TypeError, ValueError):
            raise MediaError(f"Nilai '{label}' pada kotak potong harus berupa angka.") from None
        return out

    rect = rect or {}
    x = _int(rect.get("x", 0), "x")
    y = _int(rect.get("y", 0), "y")
    w = _int(rect.get("width", 0), "width")
    h = _int(rect.get("height", 0), "height")
    if w <= 0 or h <= 0:
        raise MediaError("Kotak potong harus punya lebar & tinggi lebih dari 0 piksel.")
    if x < 0 or y < 0:
        raise MediaError("Kotak potong tidak boleh keluar dari sisi kiri/atas gambar.")
    try:
        im = Image.open(io.BytesIO(data))
        im.load()
    except Exception:  # noqa: BLE001
        raise MediaError("Berkas ini bukan gambar yang bisa dibaca — potong dibatalkan.") from None
    src_format = (im.format or "").upper()
    if x + w > im.width or y + h > im.height:
        raise MediaError(f"Kotak potong ({x},{y} {w}×{h}) melebihi ukuran gambar "
                         f"({im.width}×{im.height}).")
    out = im.crop((x, y, x + w, y + h))
    target = target or {}
    tw, th = target.get("width"), target.get("height")
    if tw or th:
        tw = _int(tw or 0, "target_width")
        th = _int(th or 0, "target_height")
        if tw <= 0 and th <= 0:
            raise MediaError("Ukuran akhir harus lebih dari 0 piksel.")
        if tw <= 0:
            tw = max(1, round(out.width * (th / out.height)))
        if th <= 0:
            th = max(1, round(out.height * (tw / out.width)))
        if tw > MAX_CROP_SIDE or th > MAX_CROP_SIDE:
            raise MediaError(f"Ukuran akhir maksimal {MAX_CROP_SIDE} piksel per sisi.")
        out = out.resize((tw, th), Image.LANCZOS)
    has_alpha = out.mode in ("RGBA", "LA") or (out.mode == "P" and "transparency" in (out.info or {}))
    if src_format == "PNG" or has_alpha:
        fmt, ctype = "PNG", "image/png"
        out = out.convert("RGBA") if has_alpha else out.convert("RGB")
    elif src_format == "WEBP":
        fmt, ctype = "WEBP", "image/webp"
        out = out.convert("RGB")
    else:
        fmt, ctype = "JPEG", "image/jpeg"
        out = out.convert("RGB")
    buf = io.BytesIO()
    save_kwargs = {"quality": 92, "optimize": True} if fmt in ("JPEG", "WEBP") else {"optimize": True}
    out.save(buf, format=fmt, **save_kwargs)
    return buf.getvalue(), ctype, out.width, out.height
