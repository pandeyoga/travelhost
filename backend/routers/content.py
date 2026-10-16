"""routers/content.py — Light CMS (Phase 9 / B3 + G1-G10 enhancement).

CRUD admin generik untuk entitas konten website:
destinations, packages, articles, testimonials, promos.
Section RBAC 'cms' (owner & ops_admin). Pembacaan publik tetap via /api/public/*.

Pendekatan generik + whitelist field per-resource agar ringkas namun aman
(hanya field terdaftar yang ditulis; ko-ersi tipe int/num/bool sesuai konfigurasi).
Setiap mutasi tercatat di Audit Log (A1).

Enhancement G1-G10 (2026-07-03):
- G1: Validasi unik slug per resource (409 saat duplikat).
- G3: POST /uploads/cms — upload gambar (jpg/png/webp <=6MB) ke uploads/cms/.
- G4: Destinations tambah field intro/route_points/faqs (sudah ada di whitelist, dieskpos ke FE).
- G6: SEO metadata (meta_title/meta_description/og_image) untuk destinations/packages/articles/promos.
- G8: POST /content/{resource}/{id}/duplicate — clone item dgn slug/kode auto-suffix.
- G9: testimonials +field `approved` (moderasi manual sebelum tampil di publik).
- G10: sort/reorder manual via field `position` (int). ContentManager mengurutkan naik jika ada.
- Search: `q` param di list — filter case-insensitive pada judul/nama/kode.
"""
import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Body, Depends, File, HTTPException, Query, Request, Response, UploadFile

from core_utils import new_id, now_iso, safe_doc
from db import get_db
from dependencies import require_section
from services import content_publish as cp
from services import content_redirects as credir
from services import content_stats as cstats
from services import content_trash as ctrash
from services import content_versions as cver
from services import i18n
from services import media_lib as ml
from services import media_store as ms
from services import ratelimit
from services import richtext
from services import translate_ai
from services.audit import record

router = APIRouter(prefix="/api", tags=["content"])
CMS = require_section("cms")

# SEO fields tersedia utk 4 resource public (kecuali testimonials).
# CMS-02: +canonical URL (opsional, override URL kanonik utk SEO)
_SEO = ["meta_title", "meta_description", "og_image", "canonical"]
# CMS-05: siklus terbit (draft/scheduled/published) untuk konten yang punya halaman publik.
_PUBLISH = ["status", "publish_at"]
# CMS-06: kantong terjemahan (`translations.en`) — divalidasi services/i18n.clean_translations.
_I18N = ["translations"]

RESOURCES = {
    "destinations": {"prefix": "dst", "sort": ("position", 1), "sort_fallback": ("name", 1),
        "slug_field": "slug", "search_fields": ["name", "slug", "region"],
        "fields": ["slug", "name", "region", "description", "intro", "hero_image", "gallery",
                   "hotel_recommendations", "highlights", "itinerary", "route_points",
                   "faqs", "best_time", "lat", "lng", "tour_scenes", "popular",
                   "position", *_SEO, *_PUBLISH, *_I18N],
        "int": ["position"], "num": ["lat", "lng"], "bool": ["popular"]},
    "packages": {"prefix": "pkg", "sort": ("position", 1), "sort_fallback": ("name", 1),
        "slug_field": "slug", "search_fields": ["name", "slug", "destination"],
        "fields": ["slug", "name", "description", "destination", "destination_id", "vehicle_type",
                   "pax_min", "pax_max", "days", "price_from",
                   "includes", "image_url", "active", "position", *_SEO, *_PUBLISH, *_I18N],
        "int": ["days", "price_from", "pax_min", "pax_max", "position"], "bool": ["active"]},
    "articles": {"prefix": "art", "sort": ("position", 1), "sort_fallback": ("published_at", -1),
        "slug_field": "slug", "search_fields": ["title", "slug", "category", "author"],
        "fields": ["slug", "title", "excerpt", "cover_image", "body", "author", "tags",
                   "category", "featured", "read_minutes", "published", "published_at",
                   "position", *_SEO, *_PUBLISH, *_I18N],
        "int": ["read_minutes", "position"], "bool": ["published", "featured"],
        "html": ["body"]},
    "testimonials": {"prefix": "tst", "sort": ("position", 1), "sort_fallback": ("created_at", -1),
        "search_fields": ["name", "role", "quote", "booking_code"],
        "fields": ["name", "role", "quote", "rating", "avatar", "approved", "position"],
        "int": ["rating", "position"], "bool": ["approved"]},
    "promos": {"prefix": "pro", "sort": ("position", 1), "sort_fallback": ("created_at", -1),
        "slug_field": "code", "search_fields": ["code", "title", "description"],
        # Syarat promo WAJIB berupa data agar bisa ditegakkan server saat checkout
        # (dulu hanya tertulis di deskripsi → diskon bocor di luar niat pemilik).
        "fields": ["code", "title", "description", "discount_type", "discount_value",
                   "valid_from", "valid_until", "min_days", "min_amount", "vehicle_types",
                   "services", "weekend_only", "max_uses", "active", "position",
                   *_SEO, *_I18N],
        "num": ["discount_value", "min_amount"],
        "int": ["position", "min_days", "max_uses"],
        "bool": ["active", "weekend_only"]},
}


def _cfg(resource: str):
    cfg = RESOURCES.get(resource)
    if not cfg:
        raise HTTPException(status_code=404, detail="Jenis konten tidak dikenal")
    return cfg


def _clean(cfg, data: dict) -> dict:
    out = {}
    for f in cfg["fields"]:
        if f not in data:
            continue
        v = data[f]
        # R6-5 fix: field angka diisi non-numerik (mis. "abc") dulu bikin int()/float() melempar
        # → HTTP 500. Tangkap & ubah jadi 400 yang jelas menyebut field yang salah.
        try:
            if f in cfg.get("int", []):
                v = int(v or 0)
            elif f in cfg.get("num", []):
                v = float(v or 0)
            elif f in cfg.get("bool", []):
                v = bool(v)
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail=f"Field '{f}' harus berupa angka")
        # CMS-09: isi kaya (HTML) DIBERSIHKAN di server — allowlist tag/atribut/protokol.
        # Tanpa ini `<script>` lewat curl akan tayang di halaman blog publik (XSS tersimpan).
        if f in cfg.get("html", []) and isinstance(v, str):
            v = richtext.sanitize(v)
        out[f] = v
    # CMS-06: kantong terjemahan divalidasi ketat (bahasa & field terdaftar saja).
    if "translations" in out:
        out["translations"] = i18n.clean_translations(_resource_of(cfg), out["translations"])
    return out


def _resource_of(cfg: dict) -> str:
    for name, conf in RESOURCES.items():
        if conf is cfg:
            return name
    return ""


def _label(doc: dict) -> str:
    return doc.get("name") or doc.get("title") or doc.get("code") or doc.get("id") or "konten"


async def _ensure_unique_slug(db, resource: str, cfg: dict, data: dict, exclude_id: Optional[str] = None):
    """G1: pastikan slug (atau kode utk promo) unik dlm koleksi resource."""
    sf = cfg.get("slug_field")
    if not sf:
        return
    slug = (data.get(sf) or "").strip()
    if not slug:
        return
    q = {sf: slug}
    if exclude_id:
        q["id"] = {"$ne": exclude_id}
    dup = await db[resource].find_one(q, {"_id": 0, "id": 1, sf: 1})
    if dup:
        raise HTTPException(status_code=409, detail=f"{sf.capitalize()} '{slug}' sudah dipakai — gunakan yang lain")


# ── CMS-11: Tempat Sampah konten (hapus bisa dibatalkan) ─────────────────────
# CATATAN URUTAN ROUTE (penting): endpoint di bawah HARUS dideklarasikan SEBELUM
# `/content/{resource}` — kalau tidak, FastAPI akan menganggap "trash"/"redirects" sebagai
# nama resource dan menjawab 404 "Jenis konten tidak dikenal".
@router.get("/content/trash")
async def list_trash(resource: str = Query(default=""),
                     limit: int = Query(default=100, ge=1, le=500), user=Depends(CMS)):
    """Isi Tempat Sampah + ringkasan retensi (default 30 hari)."""
    if resource:
        _cfg(resource)
    db = get_db()
    return {"rows": await ctrash.list_trash(db, resource=resource, limit=limit),
            "stats": await ctrash.stats(db)}


@router.post("/content/trash/{trash_id}/restore")
async def restore_trash(trash_id: str, rename: bool = Query(default=False), user=Depends(CMS)):
    """Pulihkan konten dari Tempat Sampah — SELALU kembali sebagai draft.

    `rename=true` dipakai bila slug/kode-nya sudah dipakai konten lain: sistem menambahkan
    akhiran `-restored` yang dijamin unik alih-alih menimpa konten yang hidup.
    """
    db = get_db()
    row = await ctrash.get(db, trash_id)
    if not row:
        raise HTTPException(status_code=404, detail="Item tempat sampah tidak ditemukan")
    cfg = _cfg(row.get("resource") or "")
    try:
        out = await ctrash.restore(db, trash_id, actor=user, rename=rename,
                                   slug_field=cfg.get("slug_field"))
    except ctrash.TrashConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    item = out["item"]
    await cver.snapshot(db, out["resource"], item.get("id") or "", item, actor=user,
                        action="restore")
    await record(db, actor=user, action="restore", entity_type=out["resource"],
                 entity_id=item.get("id") or "", after=item,
                 summary=f"Pulihkan {out['resource']} dari tempat sampah: {_label(item)}")
    return {"ok": True, "resource": out["resource"], "item": safe_doc(item),
            "notes": out["notes"]}


@router.delete("/content/trash/{trash_id}")
async def purge_trash(trash_id: str, user=Depends(CMS)):
    """Buang permanen satu item (beserta riwayat versinya). Setelah ini tidak bisa dipulihkan."""
    db = get_db()
    row = await ctrash.purge(db, trash_id)
    if not row:
        raise HTTPException(status_code=404, detail="Item tempat sampah tidak ditemukan")
    await record(db, actor=user, action="purge", entity_type=row.get("resource") or "content",
                 entity_id=row.get("item_id") or "",
                 summary=f"Buang permanen {row.get('resource')}: {row.get('label')}")
    return {"ok": True}


# ── CMS-12: Pengalihan URL (301) ─────────────────────────────────────────────
@router.get("/content/redirects")
async def list_redirects(resource: str = Query(default=""),
                         limit: int = Query(default=200, ge=1, le=500), user=Depends(CMS)):
    """Daftar pengalihan URL + jumlah kunjungan yang terselamatkan."""
    db = get_db()
    return {"rows": await credir.list_redirects(db, resource=resource, limit=limit),
            "stats": await credir.stats(db),
            "prefixes": credir.PUBLIC_PATHS}


@router.post("/content/redirects")
async def create_redirect(body: dict = Body(...), user=Depends(CMS)):
    """Tambah pengalihan manual (URL lama/kampanye → halaman yang masih hidup)."""
    db = get_db()
    try:
        row = await credir.create_manual(db, body.get("from_path"), body.get("to_path"), user)
    except credir.RedirectError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    await record(db, actor=user, action="create", entity_type="content_redirect",
                 entity_id=row["id"], after=row,
                 summary=f"Pengalihan URL {row['from_path']} → {row['to_path']}")
    return safe_doc(row)


@router.delete("/content/redirects/{redirect_id}")
async def delete_redirect(redirect_id: str, user=Depends(CMS)):
    db = get_db()
    row = await credir.delete_redirect(db, redirect_id)
    if not row:
        raise HTTPException(status_code=404, detail="Pengalihan tidak ditemukan")
    await record(db, actor=user, action="delete", entity_type="content_redirect",
                 entity_id=row["id"], before=row,
                 summary=f"Hapus pengalihan {row.get('from_path')} → {row.get('to_path')}")
    return {"ok": True}


@router.get("/content/{resource}")
async def list_content(
    resource: str,
    response: Response,
    q: Optional[str] = Query(default=None, description="Cari (case-insensitive) di judul/nama/kode"),
    status: Optional[str] = Query(default=None, description="Filter status terbit (draft|scheduled|published)"),
    translated: Optional[str] = Query(default=None,
                                      description="Filter terjemahan: en (punya EN) | missing (belum ada EN)"),
    limit: int = Query(default=100, ge=1, le=500, description="Batas item per halaman (1..500)"),
    offset: int = Query(default=0, ge=0, description="Offset paginasi (0-based)"),
    user=Depends(CMS),
):
    cfg = _cfg(resource)
    # G10: sort utama pd `position` (asc); fallback ke sort default resource.
    primary = cfg["sort"]
    fallback = cfg.get("sort_fallback") or primary
    db = get_db()
    query = {}
    # Search (case-insensitive) di search_fields.
    if q and q.strip():
        import re
        pattern = re.escape(q.strip())
        query["$or"] = [{f: {"$regex": pattern, "$options": "i"}} for f in cfg.get("search_fields", [])]
    # CMS-05: filter status terbit (hanya utk resource yang punya siklus terbit).
    want_status = cp.normalize_status(status) if status and str(status).lower() != "all" else ""
    if want_status and resource in cp.PUBLISHABLE:
        flag = cp.LEGACY_FLAG.get(resource)
        if want_status == "published":
            clauses = [{"status": "published"}]
            if flag:
                clauses += [{"status": {"$exists": False}, flag: True},
                            {"status": {"$in": [None, ""]}, flag: True}]
            else:
                clauses += [{"status": {"$exists": False}}, {"status": {"$in": [None, ""]}}]
        elif want_status == "draft":
            clauses = [{"status": "draft"}]
            if flag:
                clauses += [{"status": {"$exists": False}, flag: {"$ne": True}},
                            {"status": {"$in": [None, ""]}, flag: {"$ne": True}}]
        else:
            clauses = [{"status": "scheduled"}]
        status_q = {"$or": clauses}
        query = {"$and": [query, status_q]} if query else status_q
    # CMS-06 (Fase 3): filter terjemahan — "mana yang BELUM punya versi English" adalah
    # pertanyaan kerja harian editor; tanpa filter ini ia harus membuka satu per satu.
    want_tr = str(translated or "").strip().lower()
    if want_tr in ("en", "missing") and i18n.translatable_fields(resource):
        if want_tr == "en":
            tr_q = {"translations.en": {"$exists": True, "$nin": [None, {}, ""]}}
        else:
            tr_q = {"$or": [{"translations.en": {"$exists": False}},
                            {"translations.en": {"$in": [None, {}, ""]}}]}
        query = {"$and": [query, tr_q]} if query else tr_q
    # CMS-D3: paginasi (limit + offset) + total count via header agar FE bisa "Muat Lebih Banyak".
    total = await db[resource].count_documents(query)
    docs = await (
        db[resource]
        .find(query, {"_id": 0})
        .sort([primary, fallback])
        .skip(offset)
        .limit(limit)
        .to_list(limit)
    )
    rows = safe_doc(docs)
    if resource in cp.PUBLISHABLE:
        for row in rows:
            row["status"] = cp.derive_status(resource, row)
            row["effective_status"] = cp.public_status(resource, row)
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Limit"] = str(limit)
    response.headers["X-Offset"] = str(offset)
    return rows


@router.post("/content/{resource}")
async def create_content(resource: str, body: dict = Body(...), user=Depends(CMS)):
    cfg = _cfg(resource)
    db = get_db()
    doc = _clean(cfg, body)
    await _ensure_unique_slug(db, resource, cfg, doc)  # G1
    # CMS-05: satu tempat penentu status terbit (draft/scheduled/published) + sinkron boolean lama.
    doc = cp.apply_status(resource, doc, {})
    doc["id"] = new_id(cfg["prefix"])
    doc["created_at"] = now_iso()
    if resource == "articles" and not doc.get("published_at"):
        doc["published_at"] = now_iso()
    await db[resource].insert_one(doc)
    # CMS-10: versi pertama dicatat supaya "kembali ke isi awal" selalu mungkin.
    await cver.snapshot(db, resource, doc["id"], doc, actor=user, action="create")
    await record(db, actor=user, action="create", entity_type=resource, entity_id=doc["id"],
                 after=doc, summary=f"Buat {resource}: {_label(doc)}")
    return safe_doc(doc)


@router.put("/content/{resource}/{item_id}")
async def update_content(resource: str, item_id: str, body: dict = Body(...), user=Depends(CMS)):
    cfg = _cfg(resource)
    db = get_db()
    existing = await db[resource].find_one({"id": item_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Konten tidak ditemukan")
    updates = _clean(cfg, body)
    # G1: cek unik slug kalau slug/code ikut ter-update.
    if cfg.get("slug_field") in updates:
        await _ensure_unique_slug(db, resource, cfg, updates, exclude_id=item_id)
    updates = cp.apply_status(resource, updates, existing)
    sf = cfg.get("slug_field")
    old_slug = str(existing.get(sf) or "") if sf else ""
    if updates:
        updates["updated_at"] = now_iso()
        await db[resource].update_one({"id": item_id}, {"$set": updates})
    after = await db[resource].find_one({"id": item_id}, {"_id": 0})
    # CMS-12: slug = URL. Bila slug berubah, URL lama WAJIB dialihkan — kalau tidak, halaman
    # yang sudah diindeks mesin pencari & ditaut pihak lain langsung mati 404.
    new_slug = str((after or {}).get(sf) or "") if sf else ""
    redirect_row = None
    if sf and old_slug and new_slug and old_slug != new_slug:
        redirect_row = await credir.record_slug_change(db, resource, item_id, old_slug,
                                                      new_slug, user)
    # CMS-10: satu versi per penyimpanan (hanya bila memang ada perubahan isi).
    changed = cver.diff_fields(existing, after)
    if changed:
        await cver.snapshot(db, resource, item_id, after, actor=user, action="update",
                            before=existing)
    await record(db, actor=user, action="update", entity_type=resource, entity_id=item_id,
                 before=existing, after=after, summary=f"Ubah {resource}: {_label(after)}")
    out = safe_doc(after)
    if redirect_row:
        out["redirect_created"] = {"from_path": redirect_row["from_path"],
                                   "to_path": redirect_row["to_path"]}
    return out


@router.delete("/content/{resource}/{item_id}")
async def delete_content(resource: str, item_id: str, user=Depends(CMS)):
    """CMS-11: hapus = PINDAH ke Tempat Sampah (retensi 30 hari), bukan musnah.

    Dulu satu klik memanggil `delete_one` dan konten hilang selamanya beserta galeri, tur 360°,
    dan metadata SEO-nya. Sekarang editor punya jalan pulang; pembuangan permanen adalah
    tindakan terpisah yang sadar (`DELETE /content/trash/{id}`).
    """
    cfg = _cfg(resource)
    db = get_db()
    existing = await db[resource].find_one({"id": item_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Konten tidak ditemukan")
    row = await ctrash.move_to_trash(db, resource, existing, actor=user,
                                     slug_field=cfg.get("slug_field"))
    await record(db, actor=user, action="delete", entity_type=resource, entity_id=item_id,
                 before=existing,
                 summary=f"Hapus {resource} ke tempat sampah: {_label(existing)}")
    return {"ok": True, "trashed": True, "trash_id": row["id"],
            "expires_at": row.get("expires_at", ""),
            "retention_days": ctrash.RETENTION_DAYS}


@router.post("/content/{resource}/{item_id}/duplicate")
async def duplicate_content(resource: str, item_id: str, user=Depends(CMS)):
    """G8: clone konten. Slug/code diberi suffix `-copy` (dan `-copy-2`, dst) supaya unik."""
    cfg = _cfg(resource)
    db = get_db()
    src = await db[resource].find_one({"id": item_id}, {"_id": 0})
    if not src:
        raise HTTPException(status_code=404, detail="Konten sumber tidak ditemukan")
    new_doc = {k: v for k, v in src.items() if k not in {"id", "created_at", "updated_at"}}
    # Auto-suffix slug/code utk hindari konflik.
    sf = cfg.get("slug_field")
    if sf and new_doc.get(sf):
        base = str(new_doc[sf])
        candidate = f"{base}-copy"
        i = 2
        while await db[resource].find_one({sf: candidate}, {"_id": 0, "id": 1}):
            candidate = f"{base}-copy-{i}"; i += 1
        new_doc[sf] = candidate
    # Nama/judul juga diberi tanda salinan (opsional).
    for name_key in ("name", "title"):
        if new_doc.get(name_key):
            new_doc[name_key] = f"{new_doc[name_key]} (Salinan)"
            break
    # Testimonials: reset moderation state; Articles/Packages/Promos: nonaktifkan default.
    if resource == "testimonials":
        new_doc["approved"] = False
    elif "published" in new_doc:
        new_doc["published"] = False
    elif "active" in new_doc:
        new_doc["active"] = False
    # CMS-05: salinan SELALU mulai sebagai draft (tak boleh diam-diam tayang).
    if resource in cp.PUBLISHABLE:
        new_doc["status"] = "draft"
        new_doc["publish_at"] = ""
    new_doc["id"] = new_id(cfg["prefix"])
    new_doc["created_at"] = now_iso()
    await db[resource].insert_one(new_doc)
    await cver.snapshot(db, resource, new_doc["id"], new_doc, actor=user, action="create")
    await record(db, actor=user, action="duplicate", entity_type=resource, entity_id=new_doc["id"],
                 after=new_doc, summary=f"Duplikat {resource}: {_label(new_doc)}")
    return safe_doc(new_doc)


# ── G3: CMS Image Upload ─────────────────────────────────────────────────────
_UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", str(Path(__file__).resolve().parent.parent / "uploads")))
_CMS_DIR = _UPLOAD_DIR / "cms"
_CMS_DIR.mkdir(parents=True, exist_ok=True)
_ALLOWED_IMG = {"image/jpeg": ".jpg", "image/jpg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif"}
# Batas ukuran & jenis kini SATU PINTU di services/media_store (dulu 6 MB khusus CMS, berbeda dari
# Media Library 10 MB — pengguna yang sama dengan dua aturan berbeda hanya membuat bingung).


@router.post("/uploads/cms")
async def upload_cms_image(image: UploadFile = File(...), user=Depends(CMS)):
    """Unggah gambar CMS — kini DISATUKAN ke Media Library v2.

    Dulu endpoint ini menulis berkas ke `uploads/cms/` tanpa satu pun catatan di database:
    gambar tidak bisa dicari, tidak punya teks alternatif, tidak bisa dipakai ulang, dan tidak
    pernah muncul di Media Library — sementara halaman iklan punya library lengkap. Dua dunia
    media untuk satu bisnis yang sama.

    Sekarang berkas ditulis lewat `services/media_store` (pagar MIME/ukuran/path yang sama dengan
    Media Library) dan didaftarkan sebagai `media_assets`, sehingga langsung terlihat & bisa dipakai
    ulang di seluruh aplikasi. Bentuk respons LAMA dipertahankan (`url`, `size_bytes`,
    `content_type`, `filename`) agar pemanggil lama tidak rusak; URL lama `/api/uploads/cms/*`
    yang sudah tersimpan di konten tayang tetap disajikan seperti biasa.
    """
    if not image or not image.filename:
        raise HTTPException(status_code=400, detail="File gambar wajib diunggah")
    ctype = (image.content_type or "").lower().split(";")[0].strip()
    if ctype not in _ALLOWED_IMG:
        raise HTTPException(status_code=415, detail="Format tidak didukung — gunakan JPG/PNG/WEBP/GIF")
    blob = await image.read()
    if len(blob) == 0:
        raise HTTPException(status_code=400, detail="File kosong")
    if len(blob) > ms.MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413,
                            detail=f"Ukuran melebihi {ms.MAX_IMAGE_BYTES // (1024 * 1024)}MB")
    info = ms.storage_info()
    if not info["ready"]:
        raise HTTPException(status_code=400,
                            detail=f"Penyimpanan media belum siap: {info['reason'] or 'tidak diketahui'}")
    try:
        meta = ms.upload_bytes(blob, ctype, filename=image.filename, folder="cms")
    except ms.MediaError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    db = get_db()
    doc = await ml.register_asset(db, meta, user, folder_id="", alt="", source="cms")
    public = ml.public_doc(doc)
    await record(db, actor=user, action="upload", entity_type="cms_image", entity_id=doc["id"],
                 summary=f"Upload gambar CMS: {doc['original_filename']} ({len(blob) // 1024}KB)")
    return {"url": public["url"], "size_bytes": len(blob), "content_type": ctype,
            "filename": doc["original_filename"], "id": doc["id"], "media_id": doc["id"],
            "thumb_url": public["thumb_url"], "width": meta.get("width") or 0,
            "height": meta.get("height") or 0}


# ── CMS-05: Pratinjau konten yang BELUM tayang ───────────────────────────────
@router.post("/content/{resource}/{item_id}/preview-token")
async def create_preview_token(resource: str, item_id: str, user=Depends(CMS)):
    """Buat tautan pratinjau berumur 24 jam untuk konten draft/terjadwal.

    Tanpa ini editor harus MENAYANGKAN dulu untuk melihat hasil akhir — artinya pengunjung
    (dan mesin pencari) melihat konten setengah jadi. Token hanya membuka SATU dokumen.
    """
    _cfg(resource)
    if resource not in cp.PUBLISHABLE:
        raise HTTPException(status_code=400, detail="Jenis konten ini tidak punya halaman publik")
    db = get_db()
    doc = await db[resource].find_one({"id": item_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Konten tidak ditemukan")
    if not (doc.get("slug") or "").strip():
        raise HTTPException(status_code=400, detail="Konten belum punya slug — simpan dulu")
    out = await cp.mint_preview_token(db, resource, doc, user)
    await record(db, actor=user, action="preview", entity_type=resource, entity_id=item_id,
                 summary=f"Buat tautan pratinjau {resource}: {_label(doc)}")
    return {**out, "status": cp.derive_status(resource, doc)}


# ── CMS-06: Bantuan terjemahan ID→EN (opsional, hasil bisa diedit) ───────────
@router.post("/content/{resource}/translate")
async def translate_content(resource: str, request: Request, body: dict = Body(...), user=Depends(CMS)):
    """Sarankan terjemahan English untuk field terpilih. TIDAK menyimpan apa pun.

    Editor tetap pemilik keputusan: hasil dikembalikan ke form untuk ditinjau & disunting
    sebelum disimpan. Bila kunci LLM belum diisi → 503 dengan pesan jelas (isi manual tetap bisa).

    Rate-limit (Fase 3): panggilan model berbiaya nyata dan lambat. Batas 12 permintaan / 5 menit
    per pengguna mencegah tombol yang ditekan berulang menghabiskan kuota kunci LLM.
    """
    _cfg(resource)
    actor = str((user or {}).get("id") or (request.client.host if request and request.client else "anon"))
    if not ratelimit.allow(f"cms-translate:{actor}", 12, 300):
        raise HTTPException(status_code=429,
                            detail="Terlalu banyak permintaan terjemahan — coba lagi beberapa menit.")
    target = i18n.normalize_lang(body.get("target") or "en")
    if target == i18n.DEFAULT_LANG:
        raise HTTPException(status_code=400, detail="Bahasa tujuan harus selain Indonesia")
    # Ketersediaan mesin terjemahan diperiksa LEBIH DULU daripada isi payload: bila fitur ini
    # memang dimatikan pemilik (kunci LLM tidak dipasang), jawabannya harus SELALU 503 berpesan
    # "isi manual" — bukan 400 yang membuat pemanggil menyangka payload-nya yang salah.
    if not translate_ai.available():
        raise HTTPException(status_code=503,
                            detail="Terjemahan otomatis belum tersedia (EMERGENT_LLM_KEY belum "
                                   "diisi). Anda tetap bisa mengisi terjemahan manual.")
    allowed = set(i18n.translatable_fields(resource))
    fields = {k: v for k, v in (body.get("fields") or {}).items() if k in allowed}
    if not fields:
        raise HTTPException(status_code=400,
                            detail="Tidak ada field yang bisa diterjemahkan untuk jenis konten ini")
    try:
        out = await translate_ai.translate_fields(fields, target=target,
                                                 context=body.get("context") or "")
    except translate_ai.TranslateError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None
    db = get_db()
    await record(db, actor=user, action="translate", entity_type=resource,
                 entity_id=str(body.get("item_id") or ""),
                 summary=f"Saran terjemahan {target.upper()} ({len(out)} field) — {resource}")
    return {"target": target, "translations": out, "fields": list(out.keys())}


@router.get("/content/meta/i18n")
async def i18n_meta(user=Depends(CMS)):
    """Metadata bahasa untuk UI CMS (bahasa tersedia + field yang bisa diterjemahkan)."""
    return {
        "langs": [{"code": c, "label": i18n.LANG_LABELS.get(c, c)} for c in i18n.LANGS],
        "default": i18n.DEFAULT_LANG,
        "translatable": i18n.TRANSLATABLE,
        "ai_available": translate_ai.available(),
        "ai_model": translate_ai.DEFAULT_MODEL,
    }


@router.get("/content/meta/promo-options")
async def promo_options(user=Depends(CMS)):
    """A2 — pilihan aturan promo (tipe armada & layanan) untuk form CMS.

    Diambil dari SSOT yang menegakkan aturannya saat checkout: `services/pricing` (tipe armada)
    dan `services/booking_flow` (layanan yang bisa dipesan online). Kalau daftar ini ditulis
    ulang di frontend, suatu hari pemilik akan memilih tipe armada yang tidak dikenal mesin
    harga — promo lolos/gagal tanpa alasan yang bisa dijelaskan.
    """
    from services import booking_flow, pricing
    return {
        "vehicle_types": [{"value": v, "label": pricing.VEHICLE_TYPE_LABELS.get(v, v)}
                          for v in pricing.VEHICLE_TYPES],
        "services": [{"value": s["value"], "label": s["label"]}
                     for s in booking_flow.SERVICES.values()],
    }


# ── CMS-08: Analitik konten (views → lead → pesanan → omzet) ─────────────────
@router.get("/content/analytics/top")
async def content_analytics(limit: int = Query(default=20, ge=1, le=100), user=Depends(CMS)):
    """Peringkat konten berdasarkan tampilan, lead, pesanan, dan omzet teratribusi."""
    db = get_db()
    rows = await cstats.top_content(db, limit=limit)
    return {"overview": await cstats.overview(db), "rows": rows,
            "kinds": [{"value": k, "label": cstats.KIND_LABELS[k]} for k in cstats.KINDS]}


# ── CMS-10: Riwayat versi & pemulihan (rollback) ──────────────────────────────
@router.get("/content/{resource}/{item_id}/versions")
async def list_versions(resource: str, item_id: str,
                        limit: int = Query(default=50, ge=1, le=100), user=Depends(CMS)):
    """Riwayat penyuntikan satu konten (terbaru dulu) — metadata + field yang berubah."""
    _cfg(resource)
    db = get_db()
    doc = await db[resource].find_one({"id": item_id}, {"_id": 0, "id": 1})
    if not doc:
        raise HTTPException(status_code=404, detail="Konten tidak ditemukan")
    rows = await cver.list_versions(db, resource, item_id, limit=limit)
    return {"rows": rows, "max_versions": cver.MAX_VERSIONS, "total": len(rows)}


@router.get("/content/{resource}/{item_id}/versions/{version_id}")
async def get_version(resource: str, item_id: str, version_id: str, user=Depends(CMS)):
    """Satu versi LENGKAP (untuk dibandingkan dengan isi sekarang sebelum dipulihkan)."""
    _cfg(resource)
    db = get_db()
    row = await cver.get_version(db, resource, item_id, version_id)
    if not row:
        raise HTTPException(status_code=404, detail="Versi tidak ditemukan")
    current = await db[resource].find_one({"id": item_id}, {"_id": 0})
    return {"version": row,
            "changed_vs_current": cver.diff_fields(current, row.get("snapshot") or {})}


@router.post("/content/{resource}/{item_id}/versions/{version_id}/restore")
async def restore_version(resource: str, item_id: str, version_id: str, user=Depends(CMS)):
    """Kembalikan konten ke isi versi tertentu.

    TIDAK destruktif: isi saat ini lebih dulu tersimpan sebagai versi baru, lalu hasil pemulihan
    dicatat sebagai versi berikutnya — jadi rollback pun bisa di-rollback. Status terbit TIDAK
    ikut dipulihkan (memulihkan isi lama tidak boleh diam-diam menayangkan/menyembunyikan
    halaman yang sedang hidup).
    """
    cfg = _cfg(resource)
    db = get_db()
    existing = await db[resource].find_one({"id": item_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Konten tidak ditemukan")
    row = await cver.get_version(db, resource, item_id, version_id)
    if not row:
        raise HTTPException(status_code=404, detail="Versi tidak ditemukan")
    snap = row.get("snapshot") or {}
    updates = cver.restorable(snap, cfg["fields"])
    # Siklus terbit dikelola panel "Terbit", bukan riwayat versi.
    for key in ("status", "publish_at"):
        updates.pop(key, None)
    if not updates:
        raise HTTPException(status_code=400, detail="Versi ini tidak memuat field yang bisa dipulihkan")
    sf = cfg.get("slug_field")
    if sf and sf in updates:
        try:
            await _ensure_unique_slug(db, resource, cfg, updates, exclude_id=item_id)
        except HTTPException:
            # Slug versi lama sudah dipakai konten lain → pulihkan isinya TANPA slug
            # (lebih baik isi kembali benar daripada gagal total karena satu field).
            updates.pop(sf, None)
    updates["updated_at"] = now_iso()
    await db[resource].update_one({"id": item_id}, {"$set": updates})
    after = await db[resource].find_one({"id": item_id}, {"_id": 0})
    old_slug = str(existing.get(sf) or "") if sf else ""
    new_slug = str((after or {}).get(sf) or "") if sf else ""
    if sf and old_slug and new_slug and old_slug != new_slug:
        await credir.record_slug_change(db, resource, item_id, old_slug, new_slug, user)
    await cver.snapshot(db, resource, item_id, after, actor=user, action="restore",
                        before=existing)
    await record(db, actor=user, action="restore", entity_type=resource, entity_id=item_id,
                 before=existing, after=after,
                 summary=f"Pulihkan {resource} ke versi {row.get('version')}: {_label(after)}")
    return {"ok": True, "restored_from": row.get("version"),
            "fields": sorted(updates.keys() - {"updated_at"}), "item": safe_doc(after)}


# ── CMS-13: Aksi massal (tayangkan / sembunyikan / hapus banyak sekaligus) ────
BULK_ACTIONS = ("publish", "unpublish", "delete")
BULK_MAX = 200


@router.post("/content/{resource}/bulk")
async def bulk_content(resource: str, body: dict = Body(...), user=Depends(CMS)):
    """Jalankan satu aksi untuk banyak konten sekaligus.

    Kegagalan per-item dilaporkan apa adanya (`failed[]`) — bukan digagalkan semua atau
    disembunyikan. Editor harus tahu PERSIS item mana yang tidak berubah dan mengapa.
    """
    cfg = _cfg(resource)
    action = str(body.get("action") or "").strip().lower()
    if action not in BULK_ACTIONS:
        raise HTTPException(status_code=400,
                            detail=f"Aksi tidak dikenal — pilih: {', '.join(BULK_ACTIONS)}")
    ids = [str(i) for i in (body.get("ids") or []) if str(i or "").strip()]
    if not ids:
        raise HTTPException(status_code=400, detail="Tidak ada konten yang dipilih")
    if len(ids) > BULK_MAX:
        raise HTTPException(status_code=400, detail=f"Maksimal {BULK_MAX} item per aksi")
    db = get_db()
    done, failed = [], []
    for item_id in ids:
        existing = await db[resource].find_one({"id": item_id}, {"_id": 0})
        if not existing:
            failed.append({"id": item_id, "reason": "tidak ditemukan"})
            continue
        try:
            if action == "delete":
                row = await ctrash.move_to_trash(db, resource, existing, actor=user,
                                                 slug_field=cfg.get("slug_field"))
                await record(db, actor=user, action="delete", entity_type=resource,
                             entity_id=item_id, before=existing,
                             summary=f"Hapus {resource} ke tempat sampah (massal): {_label(existing)}")
                done.append({"id": item_id, "trash_id": row["id"]})
                continue
            want_live = action == "publish"
            if resource in cp.PUBLISHABLE:
                updates = cp.apply_status(resource,
                                          {"status": "published" if want_live else "draft"},
                                          existing)
            elif resource == "testimonials":
                updates = {"approved": want_live}
            else:
                updates = {"active": want_live}
            updates["updated_at"] = now_iso()
            await db[resource].update_one({"id": item_id}, {"$set": updates})
            after = await db[resource].find_one({"id": item_id}, {"_id": 0})
            if cver.diff_fields(existing, after):
                await cver.snapshot(db, resource, item_id, after, actor=user, action="update",
                                    before=existing)
            await record(db, actor=user, action="update", entity_type=resource, entity_id=item_id,
                         before=existing, after=after,
                         summary=f"{'Tayangkan' if want_live else 'Sembunyikan'} {resource} "
                                 f"(massal): {_label(after)}")
            done.append({"id": item_id})
        except HTTPException as exc:
            failed.append({"id": item_id, "reason": str(exc.detail)})
        except Exception as exc:  # noqa: BLE001 — satu item gagal tak boleh menjatuhkan sisanya
            failed.append({"id": item_id, "reason": f"gagal: {exc}"})
    return {"ok": not failed, "action": action, "done": len(done), "items": done,
            "failed": failed}
