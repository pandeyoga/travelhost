"""services/media_lib.py — SSOT logika Media Library (Media Manager v2).

Kenapa modul ini ada
--------------------
Sampai F8b sistem punya **DUA dunia media** yang tidak saling tahu:

1. `POST /api/uploads/cms` (routers/content.py) — folder rata `backend/uploads/cms/`, maks 6 MB,
   GAMBAR saja, TANPA metadata di Mongo. Akibatnya aset CMS tidak bisa dicari, tidak punya teks
   alternatif, tidak bisa dipakai ulang, dan tidak pernah terlihat di Media Library.
2. `GET/POST /api/landing/media` (routers/landing.py) — punya metadata (`media_assets`), thumbnail,
   alt, soft-delete, TAPI di balik section RBAC `landing` = {owner, marketing_admin}. `ops_admin`
   yang justru memegang CMS **tidak bisa memakainya sama sekali**.

Modul ini menjadi SSOT tunggal: folder, daftar, pemakaian ("dipakai di mana"), unduh, ganti berkas,
crop, aksi massal, dan impor aset lama. Router `media.py` (section `media`) dan router lama
`landing.py` (section `landing`, dipertahankan karena dikunci guardrail INV-MEDIA-02) sama-sama
memanggil fungsi di sini — jadi tidak mungkin lagi ada dua perilaku berbeda untuk satu aset.

Keputusan desain penting (dan alasannya)
----------------------------------------
* **Folder = metadata saja** (`media_folders.parent_id` + `media_assets.folder_id`). Berkas di disk
  TIDAK dipindah saat aset berpindah folder. Alasan: pindah/rename jadi instan & atomik (satu update
  Mongo), tidak ada jendela waktu "berkas sudah pindah tapi database belum" yang membuat gambar 404,
  dan tidak menambah satu pun permukaan baru untuk path traversal.
* **Hapus folder tidak boleh menghapus aset.** Aset & subfolder naik ke folder induk. Menghapus 200
  foto karena salah klik satu folder adalah kerusakan yang tak bisa dibatalkan.
* **Ganti berkas menaikkan `version`.** `GET /api/public/media/{id}` memakai cache 1 hari; tanpa
  penanda versi, foto yang sudah diganti akan tetap tampil lama sampai sehari — gagal senyap yang
  paling membingungkan pengguna ("saya sudah ganti, kok masih yang lama?").
* **Impor aset lama MENYALIN berkas** ke penyimpanan library, dan `legacy_url` lama DIPERTAHANKAN.
  Alasan: dokumen CMS yang sudah tayang menyimpan URL lama sebagai string; kalau berkas lama
  dipindah/dihapus, halaman publik yang sudah hidup langsung kehilangan gambar.
"""
import hashlib
import json
import logging
import re
from pathlib import Path

from core_utils import new_id, now_iso, safe_doc
from services import media_store as ms

logger = logging.getLogger("travel_fleet.media_lib")

MEDIA = "media_assets"
FOLDERS = "media_folders"
LANDING_PAGES = "landing_pages"

ROOT = ""                 # folder_id kosong = akar (bukan None, agar query Mongo konsisten)
MAX_FOLDER_DEPTH = 4      # cukup untuk "Kampanye › 2026 › Lebaran"; lebih dalam = navigasi menyiksa
MAX_BULK = 200            # batas satu aksi massal (lindungi memori & waktu request)

# Koleksi CMS yang memakai media lewat URL string (bukan media_id).
# Dipakai oleh `usage()` supaya pengguna tidak menghapus foto yang sedang tayang di website.
CONTENT_RESOURCES = {
    "destinations": ("Destinasi", ("name", "slug")),
    "packages": ("Paket Wisata", ("name", "slug")),
    "articles": ("Artikel", ("title", "slug")),
    "testimonials": ("Testimoni", ("name",)),
    "promos": ("Promo", ("title", "code")),
}


class MediaLibError(ValueError):
    """Kesalahan yang WAJIB dilaporkan sebagai 4xx berALASAN (bukan 5xx senyap)."""


# --------------------------------------------------------------------------- URL & bentuk publik
def media_url(media_id: str, version: int = 1) -> str:
    """URL baca aset (publik, tanpa login). SSOT bentuk URL media seluruh aplikasi.

    `?v=` bukan hiasan: endpoint publik memakai ETag+Cache-Control berbasis versi, sehingga URL
    berversi boleh di-cache selamanya sementara URL tanpa versi tetap divalidasi ulang. Tanpa ini,
    "Ganti berkas" tampak tidak berefek sampai cache browser kedaluwarsa.
    """
    base = f"/api/public/media/{media_id}"
    try:
        v = int(version or 1)
    except (TypeError, ValueError):
        v = 1
    return f"{base}?v={v}" if v > 1 else base


def public_doc(doc: dict) -> dict:
    """Bentuk aset untuk klien: buang jalur penyimpanan internal, tambahkan URL siap pakai."""
    if not doc:
        return {}
    out = {k: v for k, v in dict(doc).items() if k not in ("_id", "storage_path", "thumb_path", "sha256")}
    mid = out.get("id") or ""
    ver = int(doc.get("version") or 1)
    out["version"] = ver
    out["url"] = media_url(mid, ver)
    out["thumb_url"] = f"{media_url(mid, ver)}{'&' if ver > 1 else '?'}thumb=1" if doc.get("thumb_path") \
        else media_url(mid, ver)
    out["folder_id"] = doc.get("folder_id") or ROOT
    return out


def sanitize_text(value, limit: int = 160) -> str:
    """Buang tag HTML & karakter kendali dari input teks bebas (nama folder, alt, nama berkas).

    Nama folder tampil di banyak tempat (sidebar, breadcrumb, badge). Membiarkan `<img onerror=…>`
    masuk berarti membuka XSS tersimpan di panel admin.
    """
    text = re.sub(r"<[^>]*>", "", str(value or ""))
    text = re.sub(r"[\x00-\x1f\x7f]", " ", text)
    return re.sub(r"\s+", " ", text).strip()[:limit]


def safe_display_name(value, fallback: str = "media") -> str:
    """Nama tampilan berkas: aman untuk header Content-Disposition dan untuk dirender di UI."""
    name = sanitize_text(value, 120).replace('"', "").replace("\\", "").replace("/", "-")
    name = re.sub(r"[^\w .()\[\]-]+", "-", name, flags=re.UNICODE).strip(" .-")
    return name or fallback


# --------------------------------------------------------------------------- indeks
async def ensure_indexes(db):
    await db[MEDIA].create_index([("folder_id", 1), ("deleted", 1), ("created_at", -1)])
    await db[MEDIA].create_index([("source", 1)])
    await db[MEDIA].create_index("legacy_url", sparse=True)
    # Impor aset lama harus IDEMPOTEN di tingkat database: dua klik "Daftarkan aset CMS lama"
    # tidak boleh menghasilkan dua entri untuk berkas yang sama. Unik-parsial pada sidik jari
    # berkas lama (bukan sekadar cek-lalu-tulis yang bisa balapan).
    await db[MEDIA].create_index(
        "legacy_key", unique=True,
        partialFilterExpression={"legacy_key": {"$type": "string"}})
    await db[FOLDERS].create_index([("parent_id", 1), ("name", 1)])


# --------------------------------------------------------------------------- folder
async def folder_or_404(db, folder_id: str):
    fid = str(folder_id or "").strip()
    if not fid or fid == ROOT:
        return None
    doc = await db[FOLDERS].find_one({"id": fid}, {"_id": 0})
    if not doc:
        raise MediaLibError("Folder tidak ditemukan")
    return doc


async def _ancestors(db, folder_id: str) -> list:
    """Rantai induk dari folder ke akar (dengan pagar kedalaman anti data rusak/siklus lama)."""
    chain, cur, guard = [], str(folder_id or "").strip(), 0
    while cur and guard < 32:
        doc = await db[FOLDERS].find_one({"id": cur}, {"_id": 0, "id": 1, "name": 1, "parent_id": 1})
        if not doc:
            break
        chain.append(doc)
        cur = str(doc.get("parent_id") or "").strip()
        guard += 1
    return chain


async def _depth(db, parent_id: str) -> int:
    return len(await _ancestors(db, parent_id))


async def list_folders(db) -> list:
    """Semua folder + jumlah aset aktif per folder + label jalur lengkap (untuk breadcrumb)."""
    rows = await db[FOLDERS].find({}, {"_id": 0}).sort("name", 1).to_list(500)
    by_id = {r["id"]: r for r in rows}
    counts = {}
    pipeline = [{"$match": {"deleted": {"$ne": True}}},
                {"$group": {"_id": "$folder_id", "n": {"$sum": 1}}}]
    async for row in db[MEDIA].aggregate(pipeline):
        counts[row["_id"] or ROOT] = int(row["n"])

    def path_label(fid):
        parts, cur, guard = [], fid, 0
        while cur and cur in by_id and guard < 32:
            parts.append(by_id[cur]["name"])
            cur = str(by_id[cur].get("parent_id") or "").strip()
            guard += 1
        return " › ".join(reversed(parts))

    out = []
    for r in rows:
        depth = 0
        cur, guard = str(r.get("parent_id") or "").strip(), 0
        while cur and cur in by_id and guard < 32:
            depth += 1
            cur = str(by_id[cur].get("parent_id") or "").strip()
            guard += 1
        out.append({**safe_doc(r), "asset_count": counts.get(r["id"], 0),
                    "depth": depth, "path_label": path_label(r["id"])})
    out.sort(key=lambda f: (f["path_label"] or "").lower())
    return out


async def create_folder(db, name: str, parent_id: str, user: dict) -> dict:
    clean = sanitize_text(name, 60)
    if not clean:
        raise MediaLibError("Nama folder wajib diisi")
    parent = str(parent_id or "").strip()
    if parent:
        await folder_or_404(db, parent)
        if await _depth(db, parent) >= MAX_FOLDER_DEPTH:
            raise MediaLibError(f"Kedalaman folder maksimal {MAX_FOLDER_DEPTH} tingkat")
    dup = await db[FOLDERS].find_one({"parent_id": parent, "name": clean}, {"_id": 0, "id": 1})
    if dup:
        raise MediaLibError(f"Folder '{clean}' sudah ada di lokasi ini")
    doc = {"id": new_id("mdf"), "name": clean, "parent_id": parent,
           "created_by": (user or {}).get("email") or "", "created_at": now_iso(),
           "updated_at": now_iso()}
    await db[FOLDERS].insert_one(dict(doc))
    return safe_doc(doc)


async def update_folder(db, folder_id: str, name=None, parent_id=None) -> dict:
    doc = await folder_or_404(db, folder_id)
    if not doc:
        raise MediaLibError("Folder tidak ditemukan")
    patch = {}
    new_parent = doc.get("parent_id") or ROOT
    if parent_id is not None:
        new_parent = str(parent_id or "").strip()
        if new_parent:
            if new_parent == folder_id:
                raise MediaLibError("Folder tidak bisa dipindahkan ke dalam dirinya sendiri")
            await folder_or_404(db, new_parent)
            chain = [a["id"] for a in await _ancestors(db, new_parent)]
            if folder_id in chain:
                # Tanpa cek ini, folder + seluruh isinya HILANG dari daftar (jadi pulau terputus
                # dari akar) padahal datanya masih ada — kerusakan yang sulit dijelaskan pengguna.
                raise MediaLibError("Folder tidak bisa dipindahkan ke dalam anak/cucunya sendiri")
            if await _depth(db, new_parent) >= MAX_FOLDER_DEPTH:
                raise MediaLibError(f"Kedalaman folder maksimal {MAX_FOLDER_DEPTH} tingkat")
        patch["parent_id"] = new_parent
    if name is not None:
        clean = sanitize_text(name, 60)
        if not clean:
            raise MediaLibError("Nama folder wajib diisi")
        patch["name"] = clean
    if not patch:
        return safe_doc(doc)
    dup = await db[FOLDERS].find_one(
        {"parent_id": patch.get("parent_id", doc.get("parent_id") or ROOT),
         "name": patch.get("name", doc.get("name")), "id": {"$ne": folder_id}}, {"_id": 0, "id": 1})
    if dup:
        raise MediaLibError("Sudah ada folder dengan nama itu di lokasi tujuan")
    patch["updated_at"] = now_iso()
    await db[FOLDERS].update_one({"id": folder_id}, {"$set": patch})
    return safe_doc({**doc, **patch})


async def delete_folder(db, folder_id: str) -> dict:
    """Hapus folder. Aset & subfolder DINAIKKAN ke induk — tidak ada aset yang ikut terhapus."""
    doc = await folder_or_404(db, folder_id)
    if not doc:
        raise MediaLibError("Folder tidak ditemukan")
    parent = doc.get("parent_id") or ROOT
    moved = await db[MEDIA].update_many({"folder_id": folder_id},
                                        {"$set": {"folder_id": parent, "updated_at": now_iso()}})
    subs = await db[FOLDERS].update_many({"parent_id": folder_id},
                                         {"$set": {"parent_id": parent, "updated_at": now_iso()}})
    await db[FOLDERS].delete_one({"id": folder_id})
    return {"deleted": True, "id": folder_id, "moved_assets": int(moved.modified_count),
            "moved_folders": int(subs.modified_count), "moved_to": parent}


# --------------------------------------------------------------------------- aset
async def asset_or_404(db, media_id: str, include_deleted: bool = False) -> dict:
    query = {"id": str(media_id or "").strip()}
    if not include_deleted:
        query["deleted"] = {"$ne": True}
    doc = await db[MEDIA].find_one(query, {"_id": 0})
    if not doc:
        raise MediaLibError("Aset media tidak ditemukan")
    return doc


async def list_assets(db, q=None, kind=None, folder_id=None, limit=60, offset=0) -> dict:
    query = {"deleted": {"$ne": True}}
    if kind in ("image", "video"):
        query["kind"] = kind
    if folder_id is not None:
        query["folder_id"] = (folder_id or ROOT) if folder_id != "__all__" else {"$exists": True}
        if folder_id == "__all__":
            query.pop("folder_id")
    if str(q or "").strip():
        rx = re.escape(str(q).strip())
        query["$or"] = [{"original_filename": {"$regex": rx, "$options": "i"}},
                        {"alt": {"$regex": rx, "$options": "i"}}]
    limit = max(1, min(int(limit or 60), 200))
    offset = max(0, int(offset or 0))
    total = await db[MEDIA].count_documents(query)
    rows = await db[MEDIA].find(query, {"_id": 0}).sort("created_at", -1) \
        .skip(offset).limit(limit).to_list(limit)
    counts = {
        "image": await db[MEDIA].count_documents({"deleted": {"$ne": True}, "kind": "image"}),
        "video": await db[MEDIA].count_documents({"deleted": {"$ne": True}, "kind": "video"}),
    }
    counts["all"] = counts["image"] + counts["video"]
    return {"assets": safe_doc([public_doc(r) for r in rows]), "total": total,
            "limit": limit, "offset": offset, "counts": counts}


async def register_asset(db, meta: dict, user: dict, folder_id: str = ROOT, alt: str = "",
                         source: str = "landing", extra: dict = None) -> dict:
    """Simpan metadata aset baru (berkas sudah ditulis oleh media_store)."""
    fid = str(folder_id or ROOT).strip()
    if fid:
        await folder_or_404(db, fid)
    doc = {"id": new_id("med"), **meta,
           "folder_id": fid, "version": 1, "source": source,
           "alt": sanitize_text(alt, 200), "deleted": False,
           "uploaded_by": (user or {}).get("email") or "", "created_at": now_iso(),
           "updated_at": now_iso()}
    if extra:
        doc.update(extra)
    doc["original_filename"] = safe_display_name(doc.get("original_filename"), "media")
    await db[MEDIA].insert_one(dict(doc))
    return doc


async def move_assets(db, ids: list, folder_id: str) -> int:
    clean_ids = [str(i).strip() for i in (ids or []) if str(i).strip()][:MAX_BULK]
    if not clean_ids:
        raise MediaLibError("Pilih minimal satu aset")
    fid = str(folder_id or ROOT).strip()
    if fid:
        await folder_or_404(db, fid)
    res = await db[MEDIA].update_many({"id": {"$in": clean_ids}, "deleted": {"$ne": True}},
                                      {"$set": {"folder_id": fid, "updated_at": now_iso()}})
    return int(res.modified_count)


async def soft_delete_assets(db, ids: list) -> dict:
    clean_ids = [str(i).strip() for i in (ids or []) if str(i).strip()][:MAX_BULK]
    if not clean_ids:
        raise MediaLibError("Pilih minimal satu aset")
    rows = await db[MEDIA].find({"id": {"$in": clean_ids}, "deleted": {"$ne": True}},
                                {"_id": 0, "id": 1, "original_filename": 1}).to_list(MAX_BULK)
    if not rows:
        raise MediaLibError("Aset media tidak ditemukan")
    found = [r["id"] for r in rows]
    await db[MEDIA].update_many({"id": {"$in": found}},
                                {"$set": {"deleted": True, "deleted_at": now_iso()}})
    used = 0
    for mid in found:
        info = await usage(db, mid)
        used += info["total"]
    return {"deleted": len(found), "ids": found, "used_by": used,
            "names": [r.get("original_filename") or r["id"] for r in rows]}


# --------------------------------------------------------------------------- "dipakai di mana"
async def usage(db, media_id: str, legacy_url: str = "") -> dict:
    """Daftar halaman iklan & konten website yang memakai aset ini.

    Halaman iklan menyimpan `media_id` (bisa di-query langsung). Konten CMS menyimpan **URL string**
    di banyak bentuk (field tunggal, array galeri, scene tur 360, badan artikel), jadi tidak ada satu
    jalur Mongo yang bisa di-query. Karena itu dokumen CMS diperiksa dengan pencocokan teks pada
    dokumen (jumlah dokumen konten kecil: puluhan, bukan jutaan) — pilihan sadar: lebih lambat
    sedikit, tetapi TIDAK PERNAH melewatkan satu pun tempat pemakaian. Melewatkan satu tempat
    berarti pengguna menghapus foto yang masih tayang di website.
    """
    mid = str(media_id or "").strip()
    out = {"landing_pages": [], "content": [], "total": 0}
    if not mid:
        return out
    lp_rows = await db[LANDING_PAGES].find(
        {"$or": [{"blocks.props.media.media_id": mid},
                 {"blocks.props.media.poster_media_id": mid},
                 {"blocks.props.items.media_id": mid}]},
        {"_id": 0, "id": 1, "title": 1, "slug": 1, "status": 1}).to_list(50)
    out["landing_pages"] = [{"id": r.get("id"), "title": r.get("title") or r.get("slug"),
                             "slug": r.get("slug"), "status": r.get("status")} for r in lp_rows]

    needles = [mid]
    if str(legacy_url or "").strip():
        needles.append(str(legacy_url).strip())
    for resource, (label, name_fields) in CONTENT_RESOURCES.items():
        try:
            rows = await db[resource].find({}, {"_id": 0}).to_list(500)
        except Exception:  # noqa: BLE001 — koleksi belum ada = tidak dipakai
            continue
        for row in rows:
            blob = json.dumps(row, default=str)
            if any(n and n in blob for n in needles):
                title = next((row.get(f) for f in name_fields if row.get(f)), row.get("id"))
                out["content"].append({"resource": resource, "resource_label": label,
                                       "id": row.get("id"), "title": title})
    out["total"] = len(out["landing_pages"]) + len(out["content"])
    return out


# --------------------------------------------------------------------------- ganti berkas & crop
async def replace_file(db, media_id: str, data: bytes, content_type: str, filename: str,
                       user: dict) -> dict:
    """Ganti berkas sebuah aset. `id` & URL dasar TETAP; `version` naik agar cache tidak membeku."""
    doc = await asset_or_404(db, media_id)
    kind, _ext, _limit = ms.classify(content_type)
    if not kind:
        raise MediaLibError("Tipe berkas tidak didukung. Gambar: jpg/png/webp/avif/gif. "
                            "Video: mp4/webm/mov.")
    if kind != doc.get("kind"):
        raise MediaLibError(
            f"Aset ini bertipe {'foto' if doc.get('kind') == 'image' else 'video'}; "
            f"berkas pengganti bertipe {'foto' if kind == 'image' else 'video'}. "
            f"Ganti berkas hanya boleh dengan tipe yang sama agar blok/halaman yang memakainya "
            f"tidak rusak — unggah sebagai aset baru bila memang ingin mengganti jenis media.")
    meta = ms.upload_bytes(data, content_type, filename=filename or doc.get("original_filename"),
                           folder=doc.get("source") or "landing")
    old_paths = [doc.get("storage_path"), doc.get("thumb_path")]
    patch = {k: meta[k] for k in ("storage_path", "thumb_path", "size", "width", "height",
                                 "content_type", "etag", "storage_backend")}
    patch["version"] = int(doc.get("version") or 1) + 1
    patch["updated_at"] = now_iso()
    patch["replaced_at"] = now_iso()
    patch["replaced_by"] = (user or {}).get("email") or ""
    await db[MEDIA].update_one({"id": media_id}, {"$set": patch})
    # Berkas lama dibuang SETELAH database menunjuk berkas baru (urutan ini penting: kalau dibalik,
    # kegagalan update meninggalkan aset tanpa berkas = gambar 404 di halaman yang sudah tayang).
    for path in old_paths:
        if path:
            ms.remove(path, backend=doc.get("storage_backend") or "")
    return {**doc, **patch}


async def crop_asset(db, media_id: str, rect: dict, mode: str, user: dict,
                     target: dict = None) -> dict:
    """Potong/ubah ukuran gambar. `mode='replace'` menimpa aset; `mode='new'` membuat aset baru.

    Pemotongan piksel dilakukan di SERVER (PIL) dari kotak potong yang dikirim browser. Alasan:
    hasil canvas di browser menurunkan kualitas & gagal pada gambar besar di ponsel, sementara
    kotak potong hanya 4 angka yang murah dikirim dan mudah divalidasi.
    """
    doc = await asset_or_404(db, media_id)
    if doc.get("kind") != "image":
        raise MediaLibError("Hanya foto yang bisa dipotong. Untuk video gunakan ganti berkas.")
    try:
        raw, _ctype = ms.fetch(doc.get("storage_path") or "", backend=doc.get("storage_backend") or "")
    except ms.MediaError as exc:
        raise MediaLibError(f"Berkas asli tidak bisa dibaca: {exc}") from None
    cropped, ctype, width, height = ms.crop_bytes(raw, rect, target)
    filename = safe_display_name(doc.get("original_filename") or "media")
    if (mode or "new") == "replace":
        return await replace_file(db, media_id, cropped, ctype, filename, user)
    meta = ms.upload_bytes(cropped, ctype, filename=filename, folder=doc.get("source") or "landing")
    stem = filename.rsplit(".", 1)[0] if "." in filename else filename
    return await register_asset(db, meta, user, folder_id=doc.get("folder_id") or ROOT,
                               alt=doc.get("alt") or "", source=doc.get("source") or "landing",
                               extra={"original_filename": safe_display_name(
                                   f"{stem} (potong {width}x{height})"),
                                   "cropped_from": media_id})


# --------------------------------------------------------------------------- impor aset CMS lama
def _legacy_dir() -> Path:
    import os
    base = Path(os.environ.get("UPLOAD_DIR",
                               str(Path(__file__).resolve().parent.parent / "uploads")))
    return base / "cms"


LEGACY_FOLDER_NAME = "CMS Lama (impor)"


async def _legacy_folder_id(db, user: dict) -> str:
    doc = await db[FOLDERS].find_one({"name": LEGACY_FOLDER_NAME, "parent_id": ROOT}, {"_id": 0, "id": 1})
    if doc:
        return doc["id"]
    created = await create_folder(db, LEGACY_FOLDER_NAME, ROOT, user)
    return created["id"]


async def import_legacy(db, user: dict) -> dict:
    """Daftarkan berkas lama `backend/uploads/cms/*` ke Media Library.

    IDEMPOTEN: kunci `legacy_key` = nama berkas lama (unik-parsial di Mongo), jadi menjalankan ini
    berkali-kali tidak menduplikasi. Berkas lama TIDAK dipindah/dihapus dan URL lama tetap hidup —
    dokumen CMS yang sudah tayang menyimpan URL itu sebagai string biasa.
    """
    directory = _legacy_dir()
    result = {"imported": 0, "skipped": 0, "failed": 0, "total_files": 0, "errors": []}
    if not directory.is_dir():
        return result
    files = sorted([p for p in directory.iterdir() if p.is_file() and not p.name.startswith(".")])
    result["total_files"] = len(files)
    if not files:
        return result
    folder_id = await _legacy_folder_id(db, user)
    for path in files:
        legacy_key = f"cms:{path.name}"
        exists = await db[MEDIA].find_one({"legacy_key": legacy_key}, {"_id": 0, "id": 1})
        if exists:
            result["skipped"] += 1
            continue
        try:
            data = path.read_bytes()
            ctype = ms.guess_content_type(path.name)
            meta = ms.upload_bytes(data, ctype, filename=path.name, folder="cms")
            await register_asset(
                db, meta, user, folder_id=folder_id, alt="", source="cms",
                extra={"legacy_key": legacy_key, "legacy_url": f"/api/uploads/cms/{path.name}",
                       "sha256": hashlib.sha256(data).hexdigest()})
            result["imported"] += 1
        except Exception as exc:  # noqa: BLE001 — satu berkas rusak tidak boleh menggagalkan semua
            # Balapan dua klik: index unik menolak entri kedua → itu "skipped", bukan "failed".
            if "duplicate key" in str(exc).lower():
                result["skipped"] += 1
                continue
            result["failed"] += 1
            if len(result["errors"]) < 10:
                result["errors"].append(f"{path.name}: {exc}")
            logger.warning("impor aset lama gagal (%s): %s", path.name, exc)
    return result
