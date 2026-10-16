"""services/content_stats.py — CMS-08: analitik konten + atribusi konten→lead→pesanan.

Mengapa
-------
Situs publik adalah mesin akuisisi, tetapi tidak ada satu angka pun yang menunjukkan
KONTEN MANA yang menghasilkan uang. Keputusan konten jadi menebak: artikel ditulis
tanpa tahu apakah ada yang membacanya, apalagi apakah ada yang memesan karenanya.

Apa yang dihitung
-----------------
- `views` per konten (artikel/destinasi/paket) — dicatat dari halaman publik.
  Anti-inflasi: satu IP hanya dihitung sekali per 30 menit per konten (memakai
  rate limiter yang sama dengan endpoint publik lain), dan TIDAK menyimpan IP
  (hanya dipakai sebagai kunci hitung di memori).
- `leads` & `bookings` + nilai pesanan yang atribusinya menunjuk konten itu
  (`content_ref.slug`, diisi dari jejak kunjungan terakhir di browser).

Semua agregasi dilakukan saat diminta (bukan disimpan ganda) supaya tidak ada dua
versi kebenaran.
"""
from core_utils import money, now_iso

COLLECTION = "content_stats"
KINDS = ("article", "destination", "package")
KIND_LABELS = {"article": "Artikel", "destination": "Destinasi", "package": "Paket"}
KIND_PATHS = {"article": "/blog/", "destination": "/destinations/", "package": "/packages/"}
KIND_COLLECTIONS = {"article": "articles", "destination": "destinations", "package": "packages"}
VIEW_DEDUPE_SECONDS = 1800


def normalize_kind(value) -> str:
    kind = str(value or "").strip().lower().rstrip("s")
    aliases = {"artikel": "article", "destinasi": "destination", "paket": "package",
               "blog": "article"}
    kind = aliases.get(kind, kind)
    return kind if kind in KINDS else ""


async def ensure_indexes(db):
    try:
        await db[COLLECTION].create_index([("kind", 1), ("slug", 1)], unique=True)
        await db[COLLECTION].create_index([("views", -1)])
        await db.leads.create_index("content_ref.slug", sparse=True)
        await db.bookings.create_index("content_ref.slug", sparse=True)
    except Exception:  # noqa: BLE001
        pass


async def record_view(db, kind: str, slug: str, *, title: str = "", dedupe_key: str = "") -> dict:
    """Catat satu tampilan konten. Return {counted: bool, views: int}."""
    k = normalize_kind(kind)
    s = str(slug or "").strip()[:200]
    if not k or not s:
        return {"counted": False, "views": 0, "reason": "konten tidak dikenal"}

    counted = True
    if dedupe_key:
        from services.ratelimit import allow
        counted = allow(f"cview:{k}:{s}:{dedupe_key}", 1, VIEW_DEDUPE_SECONDS)

    update = {"$setOnInsert": {"kind": k, "slug": s, "created_at": now_iso()},
              "$set": {"last_view_at": now_iso()}}
    if title:
        update["$set"]["title"] = str(title)[:200]
    if counted:
        update["$inc"] = {"views": 1}
    await db[COLLECTION].update_one({"kind": k, "slug": s}, update, upsert=True)
    row = await db[COLLECTION].find_one({"kind": k, "slug": s}, {"_id": 0})
    return {"counted": counted, "views": int((row or {}).get("views") or 0), "kind": k, "slug": s}


async def _title_for(db, kind: str, slug: str, fallback: str = "") -> str:
    col = KIND_COLLECTIONS.get(kind)
    if not col:
        return fallback or slug
    doc = await db[col].find_one({"slug": slug}, {"_id": 0, "name": 1, "title": 1})
    if not doc:
        return fallback or slug
    return doc.get("title") or doc.get("name") or fallback or slug


async def top_content(db, limit: int = 20) -> list:
    """Peringkat konten: views + lead + pesanan + omzet yang bisa diatribusikan."""
    rows = await db[COLLECTION].find({}, {"_id": 0}).sort("views", -1).to_list(200)
    stats = {(r.get("kind"), r.get("slug")): dict(r) for r in rows}

    # Lead & pesanan yang menyimpan jejak konten.
    leads = await db.leads.find({"content_ref.slug": {"$exists": True, "$ne": ""}},
                                {"_id": 0, "content_ref": 1, "status": 1}).to_list(2000)
    bookings = await db.bookings.find({"content_ref.slug": {"$exists": True, "$ne": ""}},
                                      {"_id": 0, "content_ref": 1, "total_amount": 1,
                                       "status": 1}).to_list(2000)
    for lead in leads:
        ref = lead.get("content_ref") or {}
        key = (normalize_kind(ref.get("kind")), str(ref.get("slug") or ""))
        if not key[0] or not key[1]:
            continue
        bucket = stats.setdefault(key, {"kind": key[0], "slug": key[1], "views": 0,
                                        "title": ref.get("title") or ""})
        bucket["leads"] = int(bucket.get("leads") or 0) + 1
    for bk in bookings:
        ref = bk.get("content_ref") or {}
        key = (normalize_kind(ref.get("kind")), str(ref.get("slug") or ""))
        if not key[0] or not key[1]:
            continue
        bucket = stats.setdefault(key, {"kind": key[0], "slug": key[1], "views": 0,
                                       "title": ref.get("title") or ""})
        bucket["bookings"] = int(bucket.get("bookings") or 0) + 1
        if str(bk.get("status")) not in ("cancelled", "expired"):
            bucket["revenue"] = money(bucket.get("revenue")) + money(bk.get("total_amount"))

    out = []
    for (kind, slug), bucket in stats.items():
        views = int(bucket.get("views") or 0)
        leads_n = int(bucket.get("leads") or 0)
        title = bucket.get("title") or await _title_for(db, kind, slug)
        out.append({
            "kind": kind, "kind_label": KIND_LABELS.get(kind, kind), "slug": slug,
            "title": title, "path": f"{KIND_PATHS.get(kind, '/')}{slug}",
            "views": views, "leads": leads_n,
            "bookings": int(bucket.get("bookings") or 0),
            "revenue": money(bucket.get("revenue")),
            "lead_rate": round((leads_n / views) * 100, 1) if views else 0.0,
            "last_view_at": bucket.get("last_view_at") or "",
        })
    out.sort(key=lambda r: (r["revenue"], r["leads"], r["views"]), reverse=True)
    return out[:max(1, min(limit, 100))]


async def overview(db) -> dict:
    """Ringkasan untuk kartu atas panel analitik konten."""
    rows = await top_content(db, limit=100)
    return {
        "tracked": len(rows),
        "views": sum(r["views"] for r in rows),
        "leads": sum(r["leads"] for r in rows),
        "bookings": sum(r["bookings"] for r in rows),
        "revenue": sum(r["revenue"] for r in rows),
    }
