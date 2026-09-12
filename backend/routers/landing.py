"""routers/landing.py — Landing Page Builder untuk iklan (segmen ARMADA & DESTINASI).

RBAC: `require_section("landing")` = owner + marketing_admin (dibatasi karena halaman ini adalah
tujuan uang iklan; ops_admin & driver tidak perlu menyentuhnya).

Alur: pilih template per segmen → edit blok/copy/warna/tombol → unggah media → **Pratinjau** →
**Terbitkan** (dicek aturan layak-terbit INV-LP-01: slug, judul, SEO, dan minimal satu blok
konversi). Halaman publik dirender `GET /api/public/landing/{slug}` (di `routers/public.py`).

Semua validasi blok & sanitasi HTML/warna dilakukan `services/landing_blocks.py` (tidak pernah
melempar → editor tak bisa 5xx). Statistik & pemenang uji A/B di `services/landing_stats.py`.
Penyimpanan media di `services/media_store.py` (default: disk lokal server).
"""
import re

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Query, UploadFile

from core_utils import new_id, now_iso, safe_doc
from db import get_db
from dependencies import require_section
from services import landing_ads as la
from services import landing_blocks as lb
from services import landing_stats as ls
from services import landing_templates as lt
from services import media_lib as ml
from services import media_store as ms
from services.audit import record

router = APIRouter(prefix="/api", tags=["landing"])
LANDING = require_section("landing")
COLL = "landing_pages"
MEDIA = "media_assets"
_SLUG = re.compile(r"[^a-z0-9-]+")


def slugify(value: str) -> str:
    s = _SLUG.sub("-", str(value or "").strip().lower()).strip("-")[:60]
    return s or f"halaman-{new_id('lp')[-6:]}"


async def _unique_slug(db, slug: str, exclude_id: str = "") -> str:
    base, n = slug, 1
    while True:
        q = {"slug": slug}
        if exclude_id:
            q["id"] = {"$ne": exclude_id}
        if not await db[COLL].find_one(q, {"_id": 1}):
            return slug
        n += 1
        slug = f"{base}-{n}"


def media_url(media_id: str, version: int = 1) -> str:
    """URL baca aset. WAJIB lewat router publik `/api/public/media/...` supaya halaman iklan
    memuat gambar tanpa login. BUG-0112: dulu ditulis `/api/media/...` (rute tak ada) → 404.

    SSOT bentuk URL sekarang di `services/media_lib.media_url()` (dipakai juga oleh Media Manager
    v2). Literal kontrak di bawah DIPERTAHANKAN dengan sengaja: selain menjadi jangkar guardrail
    INV-MEDIA-02, ia bekerja sebagai self-check anti-drift — bila suatu saat SSOT mengubah prefix,
    kegagalan langsung terlihat di sini alih-alih muncul sebagai "semua gambar halaman iklan 404".
    """
    url = ml.media_url(media_id, version)
    contract = f"/api/public/media/{media_id}"
    if not url.startswith(contract):
        raise RuntimeError(f"URL media melenceng dari kontrak publik: {url} (harap {contract})")
    return url


def media_public(doc: dict) -> dict:
    """Bentuk aset untuk UI: URL asli + URL thumbnail (grid Media Library tetap ringan)."""
    out = ml.public_doc(doc)
    # Panggil media_url() agar self-check kontrak di atas benar-benar dieksekusi setiap request.
    out["url"] = media_url(out.get("id"), out.get("version") or 1)
    return out


async def _media_map(db, ids):
    ids = [i for i in ids if i]
    if not ids:
        return {}
    rows = await db[MEDIA].find({"id": {"$in": ids}}, {"_id": 0}).to_list(len(ids))
    return {r["id"]: media_public(r) for r in rows}


@router.get("/landing/templates")
async def landing_templates(user=Depends(LANDING)):
    """Template siap pakai per segmen iklan (armada & destinasi)."""
    return {"templates": lt.list_templates(),
            "block_types": sorted(lb.BLOCK_TYPES.keys()),
            "theme_presets": lb.THEME_PRESETS,
            "conversion_blocks": list(lb.CONVERSION_BLOCKS),
            "ab_override_fields": list(lb.AB_OVERRIDE_FIELDS)}


@router.get("/landing/pages")
async def list_pages(segment: str = Query(default=None), status: str = Query(default=None),
                     q: str = Query(default=None), limit: int = Query(default=100, le=200),
                     user=Depends(LANDING)):
    db = get_db()
    query = {}
    if segment in ("armada", "destinasi"):
        query["segment"] = segment
    if status in ("draft", "published"):
        query["status"] = status
    if (q or "").strip():
        rx = re.escape(q.strip())
        query["$or"] = [{"title": {"$regex": rx, "$options": "i"}},
                        {"slug": {"$regex": rx, "$options": "i"}}]
    rows = await db[COLL].find(query, {"_id": 0, "blocks": 0}).sort("updated_at", -1).to_list(limit)
    # ringkasan performa per halaman supaya daftar langsung berguna (bukan sekadar nama)
    for r in rows:
        agg = await ls.totals(db, r.get("id"))
        r["stats"] = {"views": sum(v["views"] for v in agg.values()),
                      "leads": sum(v["leads"] for v in agg.values()),
                      "cta_clicks": sum(v["cta_clicks"] for v in agg.values())}
        r["ab_enabled"] = bool((r.get("ab") or {}).get("enabled"))
    return {"pages": safe_doc(rows), "total": len(rows)}


@router.post("/landing/pages")
async def create_page(body: dict = Body(default={}), user=Depends(LANDING)):
    db = get_db()
    payload = body or {}
    blocks, theme, segment = lt.build(str(payload.get("template") or "armada-konversi"))
    title = str(payload.get("title") or "").strip()[:120] or "Halaman Iklan Baru"
    slug = await _unique_slug(db, slugify(payload.get("slug") or title))
    clean, _ = lb.validate_blocks(blocks)
    doc = {"id": new_id("lp"), "title": title, "slug": slug,
           "segment": payload.get("segment") if payload.get("segment") in ("armada", "destinasi") else segment,
           "template": str(payload.get("template") or "armada-konversi")[:40],
           "status": "draft", "blocks": clean, "theme": lb.sanitize_theme(theme),
           "seo": {"title": title, "description": "", "og_image": ""},
           "tracking": {"utm_default": "", "conversion_label": ""},
           "ab": lb.default_ab(),
           "published_at": None, "created_by": user.get("email"),
           "created_at": now_iso(), "updated_at": now_iso()}
    await db[COLL].insert_one(dict(doc))
    await record(db, actor=user, action="create", entity_type="landing_page", entity_id=doc["id"],
                 summary=f"Buat landing page '{title}' (template {doc['template']})")
    return safe_doc(doc)


@router.get("/landing/pages/{page_id}")
async def get_page(page_id: str, user=Depends(LANDING)):
    db = get_db()
    doc = await db[COLL].find_one({"id": page_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Landing page tidak ditemukan")
    out = safe_doc(doc)
    out["media"] = safe_doc(list((await _media_map(db, lb.media_ids(doc.get("blocks")))).values()))
    out["publish_errors"] = lb.publish_errors(doc)
    out["ab"] = lb.sanitize_ab(doc.get("ab") or lb.default_ab())
    out["public_url"] = f"/lp/{doc.get('slug')}"
    return out


@router.patch("/landing/pages/{page_id}")
async def update_page(page_id: str, body: dict = Body(default={}), user=Depends(LANDING)):
    db = get_db()
    doc = await db[COLL].find_one({"id": page_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Landing page tidak ditemukan")
    payload = body or {}
    upd, warnings = {}, []
    if "title" in payload:
        upd["title"] = str(payload["title"] or "").strip()[:120] or doc.get("title")
    if "slug" in payload:
        upd["slug"] = await _unique_slug(db, slugify(payload["slug"]), exclude_id=page_id)
    if payload.get("segment") in ("armada", "destinasi"):
        upd["segment"] = payload["segment"]
    if "theme" in payload:
        upd["theme"] = lb.sanitize_theme(payload["theme"])
    if "seo" in payload and isinstance(payload["seo"], dict):
        seo = payload["seo"]
        upd["seo"] = {"title": lb.plain(seo.get("title"), 120),
                      "description": lb.plain(seo.get("description"), 300),
                      "og_image": str(seo.get("og_image") or "")[:600],
                      "noindex": bool(seo.get("noindex", True))}
    if "tracking" in payload and isinstance(payload["tracking"], dict):
        tr = payload["tracking"]
        upd["tracking"] = {"utm_default": lb.plain(tr.get("utm_default"), 200),
                           "conversion_label": lb.plain(tr.get("conversion_label"), 80)}
    if "ab" in payload:
        upd["ab"] = lb.sanitize_ab(payload["ab"])
        if payload.get("ab") and (payload["ab"] or {}).get("enabled") and not upd["ab"]["enabled"]:
            warnings.append("Uji A/B butuh minimal 2 versi halaman — masih dinonaktifkan.")
    if "blocks" in payload:
        clean, warnings_blocks = lb.validate_blocks(payload["blocks"])
        upd["blocks"] = clean
        warnings.extend(warnings_blocks)
    if upd:
        upd["updated_at"] = now_iso()
        await db[COLL].update_one({"id": page_id}, {"$set": upd})
    fresh = await db[COLL].find_one({"id": page_id}, {"_id": 0})
    out = safe_doc(fresh)
    out["media"] = safe_doc(list((await _media_map(db, lb.media_ids(fresh.get("blocks")))).values()))
    return {"page": out, "warnings": warnings, "publish_errors": lb.publish_errors(fresh)}


@router.post("/landing/pages/{page_id}/publish")
async def publish_page(page_id: str, body: dict = Body(default={}), user=Depends(LANDING)):
    """Terbitkan / batalkan terbit. Menolak dengan alasan JELAS bila belum layak (INV-LP-01)."""
    db = get_db()
    doc = await db[COLL].find_one({"id": page_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Landing page tidak ditemukan")
    unpublish = bool((body or {}).get("unpublish"))
    if unpublish:
        await db[COLL].update_one({"id": page_id}, {"$set": {"status": "draft", "updated_at": now_iso()}})
        await record(db, actor=user, action="update", entity_type="landing_page", entity_id=page_id,
                     summary=f"Tarik dari publikasi landing page '{doc.get('title')}'")
        return {"status": "draft", "errors": []}
    errors = lb.publish_errors(doc)
    if errors:
        raise HTTPException(status_code=400, detail="Belum layak terbit: " + " · ".join(errors))
    await db[COLL].update_one({"id": page_id}, {"$set": {
        "status": "published", "published_at": now_iso(), "updated_at": now_iso()}})
    await record(db, actor=user, action="update", entity_type="landing_page", entity_id=page_id,
                 summary=f"Terbitkan landing page '{doc.get('title')}' (/lp/{doc.get('slug')})")
    return {"status": "published", "errors": [], "url": f"/lp/{doc.get('slug')}"}


@router.post("/landing/pages/{page_id}/duplicate")
async def duplicate_page(page_id: str, body: dict = Body(default={}), user=Depends(LANDING)):
    """Duplikat halaman sebagai DRAF baru. Dipakai untuk iterasi cepat kampanye (mis. satu
    halaman per kota/kata kunci) tanpa menyusun ulang blok dari nol. Statistik TIDAK dibawa —
    halaman baru harus punya angka sendiri agar keputusan iklan tidak tercampur."""
    db = get_db()
    src = await db[COLL].find_one({"id": page_id}, {"_id": 0})
    if not src:
        raise HTTPException(status_code=404, detail="Landing page tidak ditemukan")
    title = str((body or {}).get("title") or f"{src.get('title')} (kopi)").strip()[:120]
    slug = await _unique_slug(db, slugify((body or {}).get("slug") or f"{src.get('slug')}-kopi"))
    blocks, _ = lb.validate_blocks(src.get("blocks"))
    doc = {**src, "id": new_id("lp"), "title": title, "slug": slug, "status": "draft",
           "blocks": blocks, "published_at": None,
           "seo": {**(src.get("seo") or {}), "title": (src.get("seo") or {}).get("title") or title},
           "ab": lb.sanitize_ab(src.get("ab") or lb.default_ab()),
           "duplicated_from": src.get("id"), "created_by": user.get("email"),
           "created_at": now_iso(), "updated_at": now_iso()}
    await db[COLL].insert_one(dict(doc))
    await record(db, actor=user, action="create", entity_type="landing_page", entity_id=doc["id"],
                 summary=f"Duplikat landing page '{src.get('title')}' → '{title}' (/lp/{slug})")
    return safe_doc(doc)


@router.get("/landing/pages/{page_id}/ab")
async def ab_report(page_id: str, since: str = Query(default=""), user=Depends(LANDING)):
    """Laporan uji A/B: tampilan, klik CTA, lead, dan pemenang (dengan syarat sampel minimum)."""
    db = get_db()
    doc = await db[COLL].find_one({"id": page_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Landing page tidak ditemukan")
    doc["ab"] = lb.sanitize_ab(doc.get("ab") or lb.default_ab())
    return await ls.report(db, doc, since=since or "")


@router.get("/landing/pages/{page_id}/leads")
async def page_leads(page_id: str, limit: int = Query(default=50, le=200), user=Depends(LANDING)):
    """Lead yang benar-benar masuk dari halaman ini — bukti bahwa iklan menghasilkan, bukan
    hanya tampilan. Field dibatasi (tanpa catatan internal) sesuai kebutuhan marketing."""
    db = get_db()
    doc = await db[COLL].find_one({"id": page_id}, {"_id": 0, "slug": 1, "id": 1})
    if not doc:
        raise HTTPException(status_code=404, detail="Landing page tidak ditemukan")
    rows = await db.leads.find(
        {"landing_page_id": page_id},
        {"_id": 0, "id": 1, "customer_name": 1, "phone": 1, "destination": 1, "pax": 1,
         "stage": 1, "channel": 1, "utm_source": 1, "utm_campaign": 1, "landing_variant": 1,
         "marketing_consent": 1, "created_at": 1}).sort("created_at", -1).to_list(limit)
    return {"leads": safe_doc(rows), "total": len(rows)}


@router.delete("/landing/pages/{page_id}")
async def delete_page(page_id: str, user=Depends(LANDING)):
    db = get_db()
    doc = await db[COLL].find_one({"id": page_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Landing page tidak ditemukan")
    await db[COLL].delete_one({"id": page_id})
    try:
        await db[ls.COLL].delete_many({"page_id": page_id})
    except Exception:  # noqa: BLE001 — statistik yatim tidak boleh menggagalkan penghapusan
        pass
    await record(db, actor=user, action="delete", entity_type="landing_page", entity_id=page_id,
                 summary=f"Hapus landing page '{doc.get('title')}'")
    return {"deleted": True, "id": page_id}


# --------------------------------------------------------------------------- Media Library
@router.get("/landing/media")
async def list_media(q: str = Query(default=None), kind: str = Query(default=None),
                     folder_id: str = Query(default=None),
                     limit: int = Query(default=60, le=200), user=Depends(LANDING)):
    """Daftar aset untuk pemilih media di editor halaman iklan.

    Logika daftar sekarang SATU PINTU di `services/media_lib.list_assets` (dipakai juga oleh Media
    Manager v2) sehingga folder, versi, dan URL selalu identik di kedua permukaan. Bentuk respons
    lama dipertahankan agar UI & skrip POC F8 tidak perlu diubah."""
    db = get_db()
    out = await ml.list_assets(db, q=q, kind=kind, folder_id=folder_id, limit=limit)
    info = ms.storage_info()
    return {"assets": safe_doc([media_public(r) for r in out["assets"]]),
            "counts": out["counts"], "total": out["total"],
            "folders": await ml.list_folders(db),
            "storage": info,
            # kompatibilitas bentuk lama yang dipakai UI & skrip POC F1
            "storage_ready": info["ready"], "max_image_mb": info["max_image_mb"],
            "max_video_mb": info["max_video_mb"]}


@router.post("/landing/media")
async def upload_media(file: UploadFile = File(...), alt: str = "", folder_id: str = Form(default=""),
                       user=Depends(LANDING)):
    """Unggah foto/video untuk halaman iklan. Batas & tipe divalidasi `services/media_store.py`."""
    db = get_db()
    info = ms.storage_info()
    if not info["ready"]:
        raise HTTPException(status_code=400,
                            detail=f"Penyimpanan media belum siap: {info['reason'] or 'tidak diketahui'}")
    data = await file.read()
    try:
        meta = ms.upload_bytes(data, ms.resolve_content_type(file.content_type, file.filename or ""),
                               filename=file.filename or "media", folder="landing")
    except ms.MediaError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    try:
        doc = await ml.register_asset(db, meta, user, folder_id=folder_id,
                                      alt=lb.plain(alt, 160), source="landing")
    except ml.MediaLibError as exc:
        ms.remove(meta.get("storage_path") or "")
        ms.remove(meta.get("thumb_path") or "")
        raise HTTPException(status_code=400, detail=str(exc)) from None
    await record(db, actor=user, action="create", entity_type="media_asset", entity_id=doc["id"],
                 summary=f"Unggah {meta['kind']} '{meta['original_filename']}' "
                         f"({max(1, meta['size'] // 1024)} KB) untuk landing page")
    return safe_doc(media_public(doc))


@router.patch("/landing/media/{media_id}")
async def update_media(media_id: str, body: dict = Body(default={}), user=Depends(LANDING)):
    """Ubah teks alternatif (alt). Penting untuk SEO halaman iklan & aksesibilitas."""
    db = get_db()
    doc = await db[MEDIA].find_one({"id": media_id, "deleted": {"$ne": True}}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Aset media tidak ditemukan")
    alt = lb.plain((body or {}).get("alt"), 160)
    await db[MEDIA].update_one({"id": media_id}, {"$set": {"alt": alt, "updated_at": now_iso()}})
    doc["alt"] = alt
    return safe_doc(media_public(doc))


@router.delete("/landing/media/{media_id}")
async def delete_media(media_id: str, user=Depends(LANDING)):
    """Soft-delete: aset hilang dari Media Library DAN dari halaman publik (URL 404), tetapi
    berkas fisik dibiarkan agar salah-hapus masih bisa dipulihkan lewat database."""
    db = get_db()
    doc = await db[MEDIA].find_one({"id": media_id}, {"_id": 0, "original_filename": 1,
                                                     "kind": 1, "legacy_url": 1})
    if not doc:
        raise HTTPException(status_code=404, detail="Aset media tidak ditemukan")
    await db[MEDIA].update_one({"id": media_id}, {"$set": {"deleted": True, "deleted_at": now_iso()}})
    # Pemakaian dihitung lewat SSOT: dulu hanya blok `props.media.media_id` yang dihitung, sehingga
    # foto galeri/poster video yang masih tayang dilaporkan "tidak dipakai" — pengguna menghapus
    # buta. Sekarang halaman iklan DAN konten website ikut terhitung.
    info = await ml.usage(db, media_id, legacy_url=doc.get("legacy_url") or "")
    await record(db, actor=user, action="delete", entity_type="media_asset", entity_id=media_id,
                 summary=f"Hapus aset media '{doc.get('original_filename')}'")
    return {"deleted": True, "id": media_id, "used_by_pages": info["total"],
            "usage": info}

# ------------------------------------------------------- Kesiapan iklan & kesehatan media (F8b)
async def _media_missing(db, page) -> list:
    """Aset yang dipakai halaman tetapi berkas/dokumennya sudah tidak ada.

    Penyimpanan lokal berarti berkas bisa hilang (pod dibuat ulang dari repo bersih, berkas
    di-gitignore) sementara dokumen `media_assets` tetap ada. Tanpa pemeriksaan ini, halaman iklan
    tetap tayang dengan gambar rusak dan tidak ada yang tahu sampai ada yang membukanya.
    """
    ids = lb.media_ids(page.get("blocks"))
    if not ids:
        return []
    rows = await db[MEDIA].find({"id": {"$in": ids}}, {"_id": 0}).to_list(len(ids))
    by_id = {r["id"]: r for r in rows}
    missing = []
    for mid in ids:
        row = by_id.get(mid)
        if not row:
            missing.append({"media_id": mid, "filename": "(dokumen tidak ada)",
                            "reason": "Aset sudah dihapus dari Media Library."})
            continue
        if row.get("deleted"):
            missing.append({"media_id": mid, "filename": row.get("original_filename") or mid,
                            "reason": "Aset ada di tempat sampah (sudah dihapus)."})
            continue
        try:
            ms.fetch(row.get("storage_path") or "", backend=row.get("storage_backend") or "")
        except Exception:  # noqa: BLE001
            missing.append({"media_id": mid, "filename": row.get("original_filename") or mid,
                            "reason": "Berkas tidak ditemukan di penyimpanan server."})
    return missing


@router.get("/landing/pages/{page_id}/readiness")
async def page_readiness(page_id: str, user=Depends(LANDING)):
    """Skor kesiapan iklan + daftar perbaikan + URL iklan siap pakai per platform."""
    db = get_db()
    doc = await db[COLL].find_one({"id": page_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Landing page tidak ditemukan")
    missing = await _media_missing(db, doc)
    out = la.readiness(doc, media_ok=not missing)
    out["missing_media"] = missing
    out["publish_errors"] = lb.publish_errors(doc)
    out["slug"] = doc.get("slug")
    out["ad_urls"] = {
        prov: la.ad_url("", doc.get("slug"), **la.preset_utm(prov, doc.get("slug") or ""))
        for prov in ("meta", "google", "tiktok")
    }
    return out


@router.get("/landing/ad-targets")
async def ad_targets(user=Depends(LANDING)):
    """Daftar halaman untuk dipilih sebagai TUJUAN IKLAN di pembuat kampanye.

    Halaman draf tetap dikirim tetapi ditandai `publishable=false` + alasan, supaya pembuat
    kampanye bisa MEMPERINGATKAN alih-alih membiarkan iklan mengarah ke halaman 404.
    """
    db = get_db()
    rows = await db[COLL].find({}, {"_id": 0}).sort("updated_at", -1).to_list(100)
    out = []
    for r in rows:
        score = la.readiness(r, media_ok=True)
        out.append({"id": r.get("id"), "title": r.get("title"), "slug": r.get("slug"),
                    "segment": r.get("segment"), "status": r.get("status"),
                    "path": f"/lp/{r.get('slug')}", "ready": score["level"] == "siap",
                    "score": score["score"], "level": score["level"],
                    "blockers": score["blockers"],
                    "published": r.get("status") == "published"})
    return {"targets": out, "total": len(out),
            "utm_presets": {p: la.preset_utm(p) for p in ("meta", "google", "tiktok")}}
