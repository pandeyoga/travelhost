"""services/content_publish.py — CMS-05: siklus hidup konten (draft → terjadwal → tayang).

Masalah yang diperbaiki
-----------------------
Sebelumnya "terbit" hanyalah SATU boolean (`articles.published`, `packages.active`).
Akibatnya editor tidak bisa: (a) menyiapkan konten musiman lebih awal, (b) meminta
review sebelum tayang, (c) melihat hasil akhir sebelum publik melihatnya. Dan ada bug
nyata: `GET /api/public/articles/{slug}` MENGABAIKAN `published` → artikel draft bocor
ke publik & bisa terindeks mesin pencari.

Solusi (kompatibel data lama)
-----------------------------
- Field baru `status` ∈ {draft, scheduled, published} + `publish_at` (ISO UTC).
- Boolean lama TETAP DISINKRONKAN (`published`/`active`) supaya kode & laporan lama
  (sitemap, LivePreviewPanel, seed) tidak rusak.
- Dokumen TANPA `status` (data lama) dinilai memakai boolean lama → tidak ada konten
  yang "hilang" setelah upgrade.
- Visibilitas publik dihitung dengan SATU predikat bersama `visibility_filter()`, jadi
  daftar, detail, dan sitemap mustahil berbeda pendapat.
- Konten `scheduled` yang waktunya sudah lewat LANGSUNG dianggap tayang (tak menunggu
  scheduler) — `publish_due()` hanya merapikan status di database agar admin konsisten.

Pratinjau aman
--------------
`mint_preview_token()` membuat token acak berumur pendek yang disimpan di
`content_previews`. Publik yang membawa `?preview=<token>` boleh melihat SATU dokumen
spesifik meski masih draft — tanpa membuka seluruh koleksi.
"""
import os
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException

from core_utils import new_id, now_iso

STATUSES = ("draft", "scheduled", "published")

# Resource yang punya siklus terbit + boolean lama yang harus tetap sinkron.
LEGACY_FLAG = {"articles": "published", "packages": "active", "destinations": None}
PUBLISHABLE = tuple(LEGACY_FLAG.keys())

PREVIEW_TTL_MINUTES = 60 * 24  # 24 jam — cukup untuk siklus review, tak abadi.
PREVIEW_COLLECTION = "content_previews"


def _now_str() -> str:
    """Waktu sekarang UTC tanpa mikrodetik — format kanonik agar bisa dibandingkan string."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_dt(value) -> str:
    """Terima ISO/`datetime-local` → ISO UTC kanonik `YYYY-MM-DDTHH:MM:SS+00:00`.

    Format kanonik penting: perbandingan `$lte` di MongoDB dilakukan sebagai STRING,
    jadi panjang & offset harus selalu sama (kalau tidak, jadwal terbit bisa salah urut).
    """
    raw = str(value or "").strip()
    if not raw:
        return ""
    txt = raw.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(txt)
    except ValueError:
        # `datetime-local` tanpa detik (2026-08-18T14:30) sudah tertangani fromisoformat;
        # sisanya (tanggal saja) diperlakukan tengah malam UTC.
        try:
            dt = datetime.fromisoformat(f"{txt}T00:00:00")
        except ValueError:
            raise HTTPException(status_code=400,
                                detail="Format tanggal terbit tidak dikenal (gunakan tanggal & jam)") from None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def normalize_status(value) -> str:
    s = str(value or "").strip().lower()
    if s in STATUSES:
        return s
    aliases = {"terbit": "published", "publish": "published", "live": "published",
               "terjadwal": "scheduled", "schedule": "scheduled"}
    return aliases.get(s, "draft")


def derive_status(resource: str, doc: dict) -> str:
    """Status efektif satu dokumen (dokumen lama tanpa `status` dinilai dari boolean lama)."""
    doc = doc or {}
    raw = str(doc.get("status") or "").strip().lower()
    if raw in STATUSES:
        return raw
    flag = LEGACY_FLAG.get(resource)
    if flag is None:
        return "published"          # destinasi lama: selalu tayang
    return "published" if doc.get(flag) else "draft"


def apply_status(resource: str, updates: dict, existing: dict | None = None) -> dict:
    """Selaraskan `status`, `publish_at`, dan boolean lama dalam SATU tempat.

    Aturan:
    - `status` (bila dikirim) menang atas boolean lama.
    - `scheduled` WAJIB punya `publish_at` (kalau tidak → 400, bukan diam-diam draft).
    - `published` tanpa `published_at` diberi cap waktu sekarang (untuk urutan blog).
    """
    if resource not in PUBLISHABLE:
        return updates
    flag = LEGACY_FLAG.get(resource)
    existing = existing or {}
    out = dict(updates)

    if "publish_at" in out:
        out["publish_at"] = normalize_dt(out.get("publish_at"))

    if "status" in out:
        status = normalize_status(out.get("status"))
    elif flag and flag in out:
        status = "published" if out.get(flag) else "draft"
    else:
        return out                  # tak ada perubahan status pada request ini

    if status == "scheduled":
        # Bila editor MENGIRIM `publish_at` kosong secara eksplisit → itu penghapusan jadwal,
        # bukan izin memakai jadwal lama. Kalau field tak dikirim sama sekali, jadwal yang
        # sudah tersimpan tetap dipakai.
        if "publish_at" in out:
            pa = out.get("publish_at") or ""
        else:
            pa = normalize_dt(existing.get("publish_at"))
        if not pa:
            raise HTTPException(status_code=400,
                                detail="Status 'Terjadwal' wajib diisi tanggal & jam terbit")
        out["publish_at"] = pa
    if status == "draft":
        out.setdefault("publish_at", "")

    out["status"] = status
    if flag:
        out[flag] = status == "published"
    if status == "published" and not (out.get("published_at") or existing.get("published_at")):
        out["published_at"] = now_iso()
    return out


def visibility_filter(resource: str, now: str | None = None) -> dict:
    """Predikat MongoDB "boleh dilihat publik" — SSOT untuk daftar, detail, & sitemap."""
    now = now or _now_str()
    flag = LEGACY_FLAG.get(resource, None)
    clauses = [
        {"status": "published"},
        {"status": "scheduled", "publish_at": {"$lte": now}},
    ]
    legacy_true = {flag: True} if flag else {}
    clauses.append({"status": {"$exists": False}, **legacy_true})
    clauses.append({"status": {"$in": [None, ""]}, **legacy_true})
    return {"$or": clauses}


def is_visible(resource: str, doc: dict, now: str | None = None) -> bool:
    """Versi in-memory dari `visibility_filter` (dipakai endpoint detail & pratinjau)."""
    now = now or _now_str()
    status = derive_status(resource, doc)
    if status == "published":
        return True
    if status == "scheduled":
        return bool(doc.get("publish_at")) and str(doc["publish_at"]) <= now
    return False


def public_status(resource: str, doc: dict) -> str:
    """Status yang ditampilkan di admin (scheduled yang sudah lewat = published)."""
    status = derive_status(resource, doc)
    if status == "scheduled" and is_visible(resource, doc):
        return "published"
    return status


async def publish_due(db, now: str | None = None) -> int:
    """Promosikan konten `scheduled` yang waktunya lewat → `published` (dipanggil scheduler).

    Idempotent: dokumen yang sudah published tak tersentuh.
    """
    now = now or _now_str()
    total = 0
    for resource in PUBLISHABLE:
        flag = LEGACY_FLAG.get(resource)
        cursor = db[resource].find(
            {"status": "scheduled", "publish_at": {"$lte": now, "$ne": ""}},
            {"_id": 0, "id": 1, "published_at": 1})
        rows = await cursor.to_list(500)
        for row in rows:
            sets = {"status": "published", "updated_at": now_iso()}
            if flag:
                sets[flag] = True
            if not row.get("published_at"):
                sets["published_at"] = now_iso()
            await db[resource].update_one({"id": row["id"]}, {"$set": sets})
            total += 1
    return total


async def ensure_indexes(db):
    try:
        await db[PREVIEW_COLLECTION].create_index("token", unique=True)
        await db[PREVIEW_COLLECTION].create_index("expires_at")
        for resource in PUBLISHABLE:
            await db[resource].create_index([("status", 1), ("publish_at", 1)])
    except Exception:  # noqa: BLE001 — index opsional, jangan gagalkan boot
        pass


def preview_url(resource: str, doc: dict, token: str) -> str:
    """URL pratinjau siap-klik untuk editor (base dari env PUBLIC_SITE_URL)."""
    from services.content_redirects import PUBLIC_PATHS

    base = (os.environ.get("PUBLIC_SITE_URL") or "").strip().rstrip("/")
    # SSOT bentuk URL publik ada di `content_redirects.PUBLIC_PATHS` — tautan pratinjau,
    # sitemap, dan tabel pengalihan tidak boleh berbeda pendapat soal path.
    paths = PUBLIC_PATHS
    slug = (doc or {}).get("slug") or ""
    path = f"{paths.get(resource, '/')}/{slug}"
    return f"{base}{path}?preview={token}" if base else f"{path}?preview={token}"


async def mint_preview_token(db, resource: str, doc: dict, actor: dict | None = None,
                             ttl_minutes: int = PREVIEW_TTL_MINUTES) -> dict:
    """Buat token pratinjau sekali-pakai-panjang (boleh dibuka berkali-kali sampai kedaluwarsa)."""
    token = secrets.token_urlsafe(24)
    expires = (datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)).replace(
        microsecond=0).isoformat()
    row = {
        "id": new_id("cpv"), "token": token, "resource": resource,
        "item_id": (doc or {}).get("id") or "", "slug": (doc or {}).get("slug") or "",
        "created_by": (actor or {}).get("id") or "", "created_at": now_iso(),
        "expires_at": expires,
    }
    await db[PREVIEW_COLLECTION].insert_one(row)
    return {"token": token, "expires_at": expires,
            "url": preview_url(resource, doc, token),
            "path": preview_url(resource, doc, token).split("://")[-1].split("/", 1)[-1]}


async def resolve_preview(db, token: str, resource: str | None = None,
                          item_id: str | None = None, slug: str | None = None) -> bool:
    """True bila token pratinjau sah untuk dokumen yang diminta."""
    tok = str(token or "").strip()
    if not tok:
        return False
    row = await db[PREVIEW_COLLECTION].find_one({"token": tok}, {"_id": 0})
    if not row:
        return False
    if str(row.get("expires_at") or "") <= _now_str():
        return False
    if resource and row.get("resource") != resource:
        return False
    if item_id and row.get("item_id") and row.get("item_id") != item_id:
        return False
    if slug and row.get("slug") and row.get("slug") != slug:
        return False
    return True
