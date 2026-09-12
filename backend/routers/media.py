"""routers/media.py — Media Manager v2 (SATU library media untuk seluruh aplikasi).

Kenapa router ini ada, padahal `routers/landing.py` sudah punya endpoint media?
--------------------------------------------------------------------------------
Endpoint media di `landing.py` terkunci di section RBAC `landing` = {owner, marketing_admin}
(dikunci guardrail INV-MEDIA-02 dan TIDAK boleh dilonggarkan — halaman iklan berbayar tidak boleh
bisa diubah peran yang tidak bertanggung jawab atas anggaran iklan). Akibatnya `ops_admin` yang
memegang CMS website tidak pernah bisa memakai Media Library, sehingga CMS terpaksa memakai
`POST /api/uploads/cms` yang tanpa metadata, tanpa pencarian, tanpa teks alternatif.

Router ini adalah permukaan KANONIK dengan section BARU `media` = {owner, ops_admin,
marketing_admin}. Endpoint lama tetap hidup (kompatibilitas + kontrak guardrail); keduanya memanggil
SSOT `services/media_lib.py` sehingga tidak mungkin ada dua perilaku berbeda untuk satu aset.

Catatan keamanan:
* Semua endpoint di sini menulis/mengubah aset → WAJIB `Depends(MEDIA)`. Tidak ada satu pun jalur
  publik di router ini; pembacaan publik hanya lewat `GET /api/public/media/{id}` (read-only).
* Unduh memakai `Content-Disposition: attachment` dengan nama berkas yang sudah disanitasi
  (nama dari pengguna tidak pernah masuk header mentah — celah header injection).
* Byte berkas hanya boleh ditulis lewat `services/media_store` (dijaga guardrail INV-MEDIA-03),
  karena di situlah pagar anti path-traversal, validasi MIME, dan batas ukuran berada.
"""
import urllib.parse

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Query, Response, UploadFile

from core_utils import safe_doc
from db import get_db
from dependencies import require_section
from services import media_lib as ml
from services import media_store as ms
from services.audit import record

router = APIRouter(prefix="/api", tags=["media"])
MEDIA = require_section("media")


def _bad(exc) -> HTTPException:
    """Ubah kesalahan library menjadi 4xx berALASAN (INV-5XX-01: jangan pernah 5xx senyap)."""
    msg = str(exc)
    code = 404 if "tidak ditemukan" in msg.lower() else 400
    return HTTPException(status_code=code, detail=msg)


# --------------------------------------------------------------------------- folder
@router.get("/media/folders")
async def list_folders(user=Depends(MEDIA)):
    db = get_db()
    folders = await ml.list_folders(db)
    root_count = await db[ml.MEDIA].count_documents({"deleted": {"$ne": True},
                                                     "folder_id": {"$in": ["", None]}})
    return {"folders": folders, "root_count": root_count,
            "max_depth": ml.MAX_FOLDER_DEPTH}


@router.post("/media/folders")
async def create_folder(body: dict = Body(default={}), user=Depends(MEDIA)):
    db = get_db()
    try:
        doc = await ml.create_folder(db, body.get("name"), body.get("parent_id") or "", user)
    except ml.MediaLibError as exc:
        raise _bad(exc) from None
    await record(db, actor=user, action="create", entity_type="media_folder", entity_id=doc["id"],
                 after=doc, summary=f"Buat folder media '{doc['name']}'")
    return doc


@router.patch("/media/folders/{folder_id}")
async def update_folder(folder_id: str, body: dict = Body(default={}), user=Depends(MEDIA)):
    db = get_db()
    try:
        doc = await ml.update_folder(db, folder_id,
                                     name=body.get("name") if "name" in body else None,
                                     parent_id=body.get("parent_id") if "parent_id" in body else None)
    except ml.MediaLibError as exc:
        raise _bad(exc) from None
    await record(db, actor=user, action="update", entity_type="media_folder", entity_id=folder_id,
                 after=doc, summary=f"Ubah folder media '{doc.get('name')}'")
    return doc


@router.delete("/media/folders/{folder_id}")
async def delete_folder(folder_id: str, user=Depends(MEDIA)):
    db = get_db()
    try:
        out = await ml.delete_folder(db, folder_id)
    except ml.MediaLibError as exc:
        raise _bad(exc) from None
    await record(db, actor=user, action="delete", entity_type="media_folder", entity_id=folder_id,
                 summary=f"Hapus folder media (aset dipindah: {out['moved_assets']})")
    return out


# --------------------------------------------------------------------------- aksi massal
@router.post("/media/bulk-move")
async def bulk_move(body: dict = Body(default={}), user=Depends(MEDIA)):
    db = get_db()
    fid = str(body.get("folder_id") or "").strip()  # klien bisa mengirim tipe apa pun
    try:
        moved = await ml.move_assets(db, body.get("ids") or [], fid)
    except ml.MediaLibError as exc:
        raise _bad(exc) from None
    await record(db, actor=user, action="update", entity_type="media_asset", entity_id="bulk",
                 summary=f"Pindahkan {moved} aset media ke folder {fid or 'akar'}")
    return {"moved": moved, "folder_id": fid}


@router.post("/media/bulk-delete")
async def bulk_delete(body: dict = Body(default={}), user=Depends(MEDIA)):
    db = get_db()
    try:
        out = await ml.soft_delete_assets(db, body.get("ids") or [])
    except ml.MediaLibError as exc:
        raise _bad(exc) from None
    await record(db, actor=user, action="delete", entity_type="media_asset", entity_id="bulk",
                 summary=f"Hapus {out['deleted']} aset media ({out['used_by']} pemakaian terdampak)")
    return out


@router.post("/media/import-legacy")
async def import_legacy(user=Depends(MEDIA)):
    """Daftarkan aset CMS lama (`/api/uploads/cms/*`) ke Media Library. Aman dijalankan berulang."""
    db = get_db()
    out = await ml.import_legacy(db, user)
    if out["imported"]:
        await record(db, actor=user, action="create", entity_type="media_asset", entity_id="import",
                     summary=f"Impor {out['imported']} aset CMS lama ke Media Library")
    return out


@router.get("/media/health")
async def media_health(user=Depends(MEDIA)):
    """Aset yang dokumennya ada tetapi BERKASNYA hilang di penyimpanan.

    RC-C (BUG-0134): kesehatan aset kini TRI-STATE per `storage_backend` aset:
      missing = TERBUKTI hilang (404 objstore / file tak ada di disk) → merah,
      unknown = pengecekan GAGAL (kunci tak diset, jaringan, path mismatch) → kuning + alasan.
    Dulu semua kegagalan cek dihitung "hilang" → notif merah palsu padahal berkas ada.
    """
    db = get_db()
    rows = await db[ml.MEDIA].find({"deleted": {"$ne": True}}, {"_id": 0}).to_list(1000)
    missing, unknown = [], []
    for row in rows:
        state, reason = ms.check_file(row.get("storage_path") or "",
                                      backend=row.get("storage_backend") or "")
        if state == "ok":
            continue
        item = {"id": row.get("id"),
                "original_filename": row.get("original_filename") or row.get("id"),
                "kind": row.get("kind"), "folder_id": row.get("folder_id") or "",
                "storage_backend": row.get("storage_backend") or "", "reason": reason}
        (missing if state == "missing" else unknown).append(item)
    return {"total": len(rows), "missing_count": len(missing), "missing": missing[:100],
            "unknown_count": len(unknown), "unknown": unknown[:100],
            "storage": ms.storage_info()}


# --------------------------------------------------------------------------- daftar & unggah
@router.get("/media")
async def list_media(q: str = Query(default=None), kind: str = Query(default=None),
                     folder_id: str = Query(default=None), limit: int = Query(default=60, le=200),
                     offset: int = Query(default=0, ge=0), user=Depends(MEDIA)):
    """Daftar aset. `folder_id` tidak dikirim = semua folder; `folder_id=` (kosong) = akar saja."""
    db = get_db()
    try:
        out = await ml.list_assets(db, q=q, kind=kind, folder_id=folder_id,
                                   limit=limit, offset=offset)
    except ml.MediaLibError as exc:
        raise _bad(exc) from None
    out["storage"] = ms.storage_info()
    out["folders"] = await ml.list_folders(db)
    return out


@router.post("/media")
async def upload_media(file: UploadFile = File(...), folder_id: str = Form(default=""),
                       alt: str = Form(default=""), source: str = Form(default="library"),
                       user=Depends(MEDIA)):
    db = get_db()
    info = ms.storage_info()
    if not info["ready"]:
        raise HTTPException(status_code=400,
                            detail=f"Penyimpanan media belum siap: {info['reason'] or 'tidak diketahui'}")
    data = await file.read()
    try:
        meta = ms.upload_bytes(data, ms.resolve_content_type(file.content_type, file.filename or ""),
                               filename=file.filename or "media", folder="library")
    except ms.MediaError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    try:
        doc = await ml.register_asset(db, meta, user, folder_id=folder_id, alt=alt,
                                      source=(source or "library"))
    except ml.MediaLibError as exc:
        ms.remove(meta.get("storage_path") or "")
        ms.remove(meta.get("thumb_path") or "")
        raise _bad(exc) from None
    await record(db, actor=user, action="create", entity_type="media_asset", entity_id=doc["id"],
                 summary=f"Unggah {meta['kind']} '{doc['original_filename']}' "
                         f"({max(1, meta['size'] // 1024)} KB) ke Media Library")
    return safe_doc(ml.public_doc(doc))


# --------------------------------------------------------------------------- satu aset
@router.get("/media/{media_id}")
async def get_media(media_id: str, user=Depends(MEDIA)):
    db = get_db()
    try:
        doc = await ml.asset_or_404(db, media_id)
    except ml.MediaLibError as exc:
        raise _bad(exc) from None
    out = safe_doc(ml.public_doc(doc))
    out["file_exists"] = ms.exists(doc.get("storage_path") or "",
                                  backend=doc.get("storage_backend") or "")
    return out


@router.patch("/media/{media_id}")
async def update_media(media_id: str, body: dict = Body(default={}), user=Depends(MEDIA)):
    """Ubah teks alternatif, nama tampilan, dan/atau folder aset."""
    db = get_db()
    try:
        doc = await ml.asset_or_404(db, media_id)
        patch = {}
        if "alt" in body:
            patch["alt"] = ml.sanitize_text(body.get("alt"), 200)
        if "original_filename" in body:
            name = ml.safe_display_name(body.get("original_filename"), "")
            if not name:
                raise ml.MediaLibError("Nama berkas tidak boleh kosong")
            patch["original_filename"] = name
        if "folder_id" in body:
            # `str(...)` bukan hiasan: klien pernah mengirim `folder_id: 5` (angka) sehingga
            # `.strip()` melempar AttributeError → HTTP 500. Input bertipe salah WAJIB berakhir
            # sebagai 4xx berALASAN, bukan crash server.
            fid = str(body.get("folder_id") or "").strip()
            if fid:
                await ml.folder_or_404(db, fid)
            patch["folder_id"] = fid
        if not patch:
            raise ml.MediaLibError("Tidak ada perubahan yang dikirim")
        patch["updated_at"] = ml.now_iso()
        await db[ml.MEDIA].update_one({"id": media_id}, {"$set": patch})
    except ml.MediaLibError as exc:
        raise _bad(exc) from None
    await record(db, actor=user, action="update", entity_type="media_asset", entity_id=media_id,
                 after=patch, summary=f"Ubah aset media '{doc.get('original_filename')}'")
    return safe_doc(ml.public_doc({**doc, **patch}))


@router.delete("/media/{media_id}")
async def delete_media(media_id: str, user=Depends(MEDIA)):
    db = get_db()
    try:
        out = await ml.soft_delete_assets(db, [media_id])
    except ml.MediaLibError as exc:
        raise _bad(exc) from None
    await record(db, actor=user, action="delete", entity_type="media_asset", entity_id=media_id,
                 summary=f"Hapus aset media '{(out.get('names') or [media_id])[0]}'")
    return {"deleted": True, "id": media_id, "used_by_pages": out["used_by"]}


@router.get("/media/{media_id}/usage")
async def media_usage(media_id: str, user=Depends(MEDIA)):
    """Halaman iklan & konten website yang memakai aset ini — ditampilkan SEBELUM hapus."""
    db = get_db()
    try:
        doc = await ml.asset_or_404(db, media_id, include_deleted=True)
    except ml.MediaLibError as exc:
        raise _bad(exc) from None
    return await ml.usage(db, media_id, legacy_url=doc.get("legacy_url") or "")


@router.get("/media/{media_id}/download")
async def download_media(media_id: str, user=Depends(MEDIA)):
    """Unduh berkas asli. Ber-auth (tidak seperti pembacaan publik) + nama berkas disanitasi."""
    db = get_db()
    try:
        doc = await ml.asset_or_404(db, media_id)
        data, ctype = ms.fetch(doc.get("storage_path") or "",
                               backend=doc.get("storage_backend") or "")
    except ml.MediaLibError as exc:
        raise _bad(exc) from None
    except ms.MediaError as exc:
        raise HTTPException(status_code=404, detail=f"Berkas tidak tersedia: {exc}") from None
    ext = "." + (doc.get("storage_path") or "").rsplit(".", 1)[-1] if "." in (doc.get("storage_path") or "") else ""
    name = ml.safe_display_name(doc.get("original_filename") or media_id, media_id)
    if ext and not name.lower().endswith(ext.lower()):
        name = f"{name}{ext}"
    quoted = urllib.parse.quote(name)
    return Response(content=data, media_type=ctype or doc.get("content_type") or "application/octet-stream",
                    headers={"Content-Disposition": f"attachment; filename=\"{quoted}\"; "
                                                    f"filename*=UTF-8''{quoted}",
                             "Cache-Control": "private, no-store",
                             "Content-Length": str(len(data))})


@router.post("/media/{media_id}/replace")
async def replace_media(media_id: str, file: UploadFile = File(...), user=Depends(MEDIA)):
    """Ganti berkas aset. `id` & URL tetap sama → semua halaman/konten yang memakainya ikut berubah."""
    db = get_db()
    data = await file.read()
    try:
        doc = await ml.replace_file(db, media_id, data,
                                    ms.resolve_content_type(file.content_type, file.filename or ""),
                                    file.filename or "", user)
    except ml.MediaLibError as exc:
        raise _bad(exc) from None
    except ms.MediaError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    await record(db, actor=user, action="update", entity_type="media_asset", entity_id=media_id,
                 summary=f"Ganti berkas aset media '{doc.get('original_filename')}' "
                         f"(versi {doc.get('version')})")
    return safe_doc(ml.public_doc(doc))


@router.post("/media/{media_id}/crop")
async def crop_media(media_id: str, body: dict = Body(default={}), user=Depends(MEDIA)):
    """Potong/ubah ukuran foto. `mode='replace'` menimpa aset, `mode='new'` membuat aset baru."""
    db = get_db()
    mode = str(body.get("mode") or "new").strip().lower()
    if mode not in ("new", "replace"):
        raise HTTPException(status_code=400, detail="mode harus 'new' atau 'replace'")
    rect = {k: body.get(k) for k in ("x", "y", "width", "height")}
    target = {"width": body.get("target_width"), "height": body.get("target_height")}
    try:
        doc = await ml.crop_asset(db, media_id, rect, mode, user, target=target)
    except ml.MediaLibError as exc:
        raise _bad(exc) from None
    except ms.MediaError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    await record(db, actor=user, action="update" if mode == "replace" else "create",
                 entity_type="media_asset", entity_id=doc["id"],
                 summary=f"Potong foto '{doc.get('original_filename')}' "
                         f"({'ganti aset' if mode == 'replace' else 'aset baru'})")
    return safe_doc(ml.public_doc(doc))
