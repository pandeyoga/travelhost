"""routers/site_pages.py — PAGE BUILDER halaman situs (home/about/contact) + Pengaturan Situs.

Model data: `site_pages` (pge_) menyimpan URUTAN section per halaman + override teks/gambar.
Field kosong = frontend memakai teks bawaan dua-bahasa; terisi = override tampil di semua
bahasa. Section bisa diurutkan, dimatikan, ditambah (duplikat tipe diizinkan utk tipe teks).
Pengaturan Situs = merge ke settings.company_info (SATU sumber dgn header/footer publik).
Dikelola dari menu CMS (section `cms`), publik membaca lewat /api/public/pages/{slug}.
"""
import os

from fastapi import APIRouter, Depends, HTTPException

from core_utils import new_id, now_iso, safe_doc
from db import get_db
from dependencies import require_section
from schemas_site import SitePageUpdate, SiteSettingsIn
from services.audit import record

router = APIRouter(prefix="/api", tags=["site-pages"])
CMS = require_section("cms")

# Registry tipe section per halaman: kunci = tipe, nilai = field data yang DIIZINKAN.
# Menambah tipe baru wajib lewat sini (whitelist — payload liar dibuang diam-diam).
SECTION_FIELDS = {
    "hero": ["eyebrow", "title", "subtitle", "image", "chips",
             "primary_label", "primary_href", "secondary_label", "secondary_href"],
    "booking_steps": [],
    "value_props": ["eyebrow", "title", "subtitle", "items"],
    "stats_band": ["eyebrow", "title"],
    "fleet_featured": ["title", "subtitle"],
    "destinations_featured": ["title", "subtitle"],
    "testimonials": ["title", "subtitle"],
    "gallery": ["eyebrow", "title", "subtitle", "items"],
    "trust": ["items"],
    "faq": ["title", "items"],
    "cta_band": ["title", "text", "primary_label", "primary_href",
                 "secondary_label", "secondary_href"],
    "page_hero": ["eyebrow", "title", "subtitle", "image"],
    "stat_cards": ["items"],
    "about_story": ["eyebrow", "title", "body", "cta_label", "cta_href", "items"],
    "contact_channels": ["eyebrow", "title", "subtitle"],
    "contact_cta": ["title", "note"],
}

PAGE_DEFS = {
    "home": {"title": "Beranda", "types": [
        "hero", "booking_steps", "value_props", "stats_band", "fleet_featured",
        "destinations_featured", "testimonials", "gallery", "trust", "faq", "cta_band"]},
    "about": {"title": "Tentang Kami", "types": ["page_hero", "stat_cards", "about_story"]},
    "contact": {"title": "Kontak", "types": ["page_hero", "contact_channels", "contact_cta"]},
    # Halaman daftar: hero-nya bisa di-override; isi (unit/destinasi/paket/promo/artikel)
    # dikelola dari tab CMS masing-masing.
    "fleet": {"title": "Armada", "types": ["page_hero"]},
    "destinations": {"title": "Destinasi", "types": ["page_hero"]},
    "packages": {"title": "Paket Wisata", "types": ["page_hero"]},
    "promo": {"title": "Promo", "types": ["page_hero"]},
    "blog": {"title": "Blog / Artikel", "types": ["page_hero"]},
    "trip-calculator": {"title": "Kalkulator Trip", "types": ["page_hero"]},
}


def default_sections(slug: str):
    return [{"id": new_id("sec"), "type": t, "enabled": True, "data": {}}
            for t in PAGE_DEFS[slug]["types"]]


def _clean_str(v, cap=4000):
    return str(v)[:cap] if isinstance(v, (str, int, float)) else ""


def _clean_data(sec_type: str, data):
    allowed = SECTION_FIELDS.get(sec_type, [])
    out = {}
    for key in allowed:
        val = (data or {}).get(key)
        if val in (None, "", []):
            continue
        if key == "chips" and isinstance(val, list):
            out[key] = [_clean_str(x, 120) for x in val[:12] if _clean_str(x, 120)]
        elif key == "items" and isinstance(val, list):
            items = []
            for it in val[:30]:
                if isinstance(it, dict):
                    items.append({k: _clean_str(v, 1000) for k, v in it.items()
                                  if isinstance(k, str) and k[:40] and _clean_str(v, 1000)})
            out[key] = items
        else:
            out[key] = _clean_str(val)
    return out


async def _get_page(db, slug: str):
    doc = await db.site_pages.find_one({"slug": slug}, {"_id": 0})
    if not doc:
        doc = {"id": new_id("pge"), "slug": slug, "title": PAGE_DEFS[slug]["title"],
               "sections": default_sections(slug), "updated_at": now_iso()}
        await db.site_pages.insert_one(dict(doc))
    return doc


@router.get("/public/pages/{slug}")
async def public_page(slug: str):
    """Halaman publik: hanya section AKTIF, dalam urutan builder."""
    if slug not in PAGE_DEFS:
        raise HTTPException(status_code=404, detail="Halaman tidak ditemukan")
    doc = await _get_page(get_db(), slug)
    return {"slug": slug, "title": doc.get("title"),
            "sections": [safe_doc(s) for s in doc.get("sections") or [] if s.get("enabled")]}


@router.get("/site/pages")
async def list_site_pages(user=Depends(CMS)):
    db = get_db()
    out = []
    for slug, meta in PAGE_DEFS.items():
        doc = await _get_page(db, slug)
        out.append({"slug": slug, "title": meta["title"],
                    "section_count": len(doc.get("sections") or []),
                    "updated_at": doc.get("updated_at")})
    return out


@router.get("/site/pages/{slug}")
async def get_site_page(slug: str, user=Depends(CMS)):
    if slug not in PAGE_DEFS:
        raise HTTPException(status_code=404, detail="Halaman tidak ditemukan")
    doc = await _get_page(get_db(), slug)
    return {**safe_doc(doc), "allowed_types": PAGE_DEFS[slug]["types"]}


@router.put("/site/pages/{slug}")
async def update_site_page(slug: str, body: SitePageUpdate, user=Depends(CMS)):
    """Simpan builder: urutan array = urutan tampil; tipe di luar registry halaman DITOLAK."""
    if slug not in PAGE_DEFS:
        raise HTTPException(status_code=404, detail="Halaman tidak ditemukan")
    db = get_db()
    allowed_types = set(PAGE_DEFS[slug]["types"])
    sections = []
    for s in body.sections:
        if s.type not in allowed_types:
            raise HTTPException(status_code=400,
                                detail=f"Tipe section '{s.type}' tidak dikenal utk halaman ini")
        sections.append({"id": s.id or new_id("sec"), "type": s.type,
                         "enabled": bool(s.enabled), "data": _clean_data(s.type, s.data)})
    if not any(x["enabled"] for x in sections):
        raise HTTPException(status_code=400, detail="Minimal satu section harus aktif")
    await _get_page(db, slug)
    await db.site_pages.update_one(
        {"slug": slug}, {"$set": {"sections": sections, "updated_at": now_iso()}})
    await record(db, actor=user, action="update", entity_type="site_page", entity_id=slug,
                 summary=f"Page builder: halaman '{slug}' — {len(sections)} section disimpan")
    return {"slug": slug, "sections": sections}


# ---------- PENGATURAN SITUS (merge ke settings.company_info — satu sumber) ----------
@router.get("/site/settings")
async def get_site_settings(user=Depends(CMS)):
    s = await get_db().settings.find_one({"key": "company_info"}, {"_id": 0})
    val = dict((s or {}).get("value") or {})
    # URL situs publik: dipakai pratinjau Page Builder saat ERP berjalan di domain terpisah.
    if not (val.get("site_url") or "").strip():
        val["site_url"] = (os.environ.get("PUBLIC_SITE_URL") or "").strip().rstrip("/")
    return safe_doc(val)


@router.put("/site/settings")
async def update_site_settings(body: SiteSettingsIn, user=Depends(CMS)):
    db = get_db()
    updates = {k: v.strip() if isinstance(v, str) else v
               for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    current = await db.settings.find_one({"key": "company_info"}, {"_id": 0})
    merged = dict((current or {}).get("value") or {})
    merged.update(updates)
    await db.settings.update_one({"key": "company_info"},
                                 {"$set": {"value": merged}}, upsert=True)
    await record(db, actor=user, action="update", entity_type="settings",
                 entity_id="company_info",
                 summary=f"Pengaturan Situs: {', '.join(sorted(updates)) or '-'}")
    return merged
