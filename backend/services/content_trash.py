"""services/content_trash.py — CMS-11: Tempat Sampah konten (hapus bisa dibatalkan).

Masalah yang diperbaiki
-----------------------
Tombol hapus di CMS dulu memanggil `delete_one` — SATU klik dan destinasi/paket/artikel hilang
selamanya beserta galeri, tur 360°, dan metadata SEO-nya. Dialog konfirmasinya bahkan berbunyi
"Tindakan ini tidak dapat dibatalkan", dan itu memang benar: satu-satunya sisa adalah snapshot
JSON di Audit Log yang tak punya tombol pulihkan. Untuk pemilik usaha, artinya kerja berhari-hari
bisa lenyap karena satu salah klik.

Solusi
------
Hapus = PINDAH ke koleksi `content_trash` (retensi 30 hari), bukan musnah. Pemilihan sengaja
"pindah koleksi" — bukan `deleted_at` di dokumen aslinya — supaya SELURUH kueri publik & admin
yang sudah ada (daftar, detail, sitemap, statistik) mustahil lupa menyaring dokumen terhapus.
Itu kelas bug yang mahal: satu kueri lupa filter → konten "terhapus" tetap tayang.

Pemulihan mengembalikan dokumen dengan **id yang sama** (tautan internal & atribusi analitik
tetap nyambung) tetapi SELALU sebagai draft: konten yang pernah dibuang tidak boleh diam-diam
tayang kembali sebelum diperiksa manusia.
"""
from datetime import datetime, timedelta, timezone

from core_utils import new_id, now_iso
from services import content_publish as cp

COLLECTION = "content_trash"

# Retensi 30 hari: cukup panjang untuk menyadari kesalahan (siklus laporan bulanan), cukup
# pendek agar konten sensitif tidak menumpuk selamanya.
RETENTION_DAYS = 30


class TrashConflict(Exception):
    """Slug/kode dokumen yang akan dipulihkan sudah dipakai dokumen lain."""

    def __init__(self, message: str, slug: str = ""):
        super().__init__(message)
        self.slug = slug


def label_of(doc: dict) -> str:
    doc = doc or {}
    return str(doc.get("name") or doc.get("title") or doc.get("code") or doc.get("id") or "konten")


def _expiry(days: int = RETENTION_DAYS) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).replace(microsecond=0).isoformat()


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


async def move_to_trash(db, resource: str, doc: dict, actor: dict | None = None,
                       slug_field: str | None = None) -> dict:
    """Pindahkan dokumen konten ke Tempat Sampah. Return baris tempat sampah."""
    snap = {k: v for k, v in (doc or {}).items() if k != "_id"}
    row = {
        "id": new_id("ctr"),
        "resource": resource,
        "item_id": str(snap.get("id") or ""),
        "label": label_of(snap),
        "slug": str(snap.get(slug_field) if slug_field else (snap.get("slug") or "")) or "",
        "slug_field": slug_field or "",
        "snapshot": snap,
        "deleted_by": str((actor or {}).get("id") or ""),
        "deleted_by_name": str((actor or {}).get("name") or (actor or {}).get("email") or "sistem"),
        "deleted_at": now_iso(),
        "expires_at": _expiry(),
        "restored": False,
    }
    await db[COLLECTION].insert_one(dict(row))
    await db[resource].delete_one({"id": row["item_id"]})
    return {k: v for k, v in row.items() if k != "snapshot"}


async def list_trash(db, resource: str = "", limit: int = 100) -> list:
    query: dict = {"restored": {"$ne": True}}
    if resource:
        query["resource"] = resource
    rows = await db[COLLECTION].find(query, {"_id": 0, "snapshot": 0}).sort(
        [("deleted_at", -1)]).to_list(limit)
    now = _now()
    for r in rows:
        exp = str(r.get("expires_at") or "")
        r["expired"] = bool(exp and exp <= now)
    return rows


async def get(db, trash_id: str) -> dict | None:
    return await db[COLLECTION].find_one({"id": str(trash_id or "")}, {"_id": 0})


async def restore(db, trash_id: str, actor: dict | None = None, rename: bool = False,
                  slug_field: str | None = None) -> dict:
    """Pulihkan dokumen dari Tempat Sampah sebagai DRAFT.

    `slug_field` diberikan pemanggil (router) supaya SSOT whitelist resource tetap satu tempat.
    Bila slug sudah dipakai dokumen lain: `rename=False` → `TrashConflict` (editor memutuskan),
    `rename=True` → slug diberi akhiran `-restored` yang dijamin unik.
    """
    row = await get(db, trash_id)
    if not row:
        raise TrashConflict("Item tempat sampah tidak ditemukan")
    if row.get("restored"):
        raise TrashConflict("Item ini sudah dipulihkan")
    resource = row["resource"]
    doc = dict(row.get("snapshot") or {})
    doc.pop("_id", None)
    if not doc.get("id"):
        doc["id"] = row.get("item_id") or new_id("res")
    sf = slug_field or row.get("slug_field") or ""
    notes = []

    # Dokumen dengan id sama mungkin sudah dibuat ulang manual selagi berada di tempat sampah.
    if await db[resource].find_one({"id": doc["id"]}, {"_id": 0, "id": 1}):
        raise TrashConflict("Konten dengan id ini sudah ada kembali — tidak dipulihkan agar "
                            "tidak menimpa data baru")

    if sf and doc.get(sf):
        base = str(doc[sf])
        taken = await db[resource].find_one({sf: base}, {"_id": 0, "id": 1})
        if taken:
            if not rename:
                raise TrashConflict(
                    f"{sf.capitalize()} '{base}' kini dipakai konten lain. Pulihkan dengan "
                    f"penggantian nama otomatis, atau ubah dulu konten yang memakainya.", base)
            candidate = f"{base}-restored"
            i = 2
            while await db[resource].find_one({sf: candidate}, {"_id": 0, "id": 1}):
                candidate = f"{base}-restored-{i}"
                i += 1
            doc[sf] = candidate
            notes.append(f"{sf} diubah menjadi '{candidate}' karena '{base}' sudah dipakai")

    # Konten yang pernah dibuang TIDAK boleh langsung tayang tanpa diperiksa manusia.
    if resource in cp.PUBLISHABLE:
        doc["status"] = "draft"
        doc["publish_at"] = ""
        flag = cp.LEGACY_FLAG.get(resource)
        if flag:
            doc[flag] = False
    elif resource == "testimonials":
        doc["approved"] = False
    elif "active" in doc:
        doc["active"] = False
    doc["restored_at"] = now_iso()
    doc["updated_at"] = now_iso()

    await db[resource].insert_one(dict(doc))
    await db[COLLECTION].update_one(
        {"id": row["id"]},
        {"$set": {"restored": True, "restored_at": now_iso(),
                  "restored_by": str((actor or {}).get("id") or "")}})
    doc.pop("_id", None)
    return {"resource": resource, "item": doc, "notes": notes}


async def purge(db, trash_id: str) -> dict | None:
    """Buang permanen satu item tempat sampah (beserta riwayat versinya)."""
    row = await get(db, trash_id)
    if not row:
        return None
    from services import content_versions as cv
    await cv.drop_for(db, row.get("resource") or "", row.get("item_id") or "")
    await db[COLLECTION].delete_one({"id": row["id"]})
    return row


async def purge_expired(db, now: str | None = None) -> int:
    """Buang item yang melewati retensi (dipanggil scheduler). Idempotent."""
    now = now or _now()
    rows = await db[COLLECTION].find(
        {"restored": {"$ne": True}, "expires_at": {"$lte": now, "$ne": ""}},
        {"_id": 0, "id": 1}).to_list(500)
    total = 0
    for r in rows:
        if await purge(db, r["id"]):
            total += 1
    # Baris yang sudah dipulihkan tidak perlu disimpan selamanya (jejaknya ada di Audit Log).
    await db[COLLECTION].delete_many({"restored": True, "expires_at": {"$lte": now, "$ne": ""}})
    return total


async def stats(db) -> dict:
    now = _now()
    total = await db[COLLECTION].count_documents({"restored": {"$ne": True}})
    expiring = await db[COLLECTION].count_documents(
        {"restored": {"$ne": True}, "expires_at": {"$lte": now, "$ne": ""}})
    return {"total": int(total), "expired": int(expiring), "retention_days": RETENTION_DAYS}


async def ensure_indexes(db):
    try:
        await db[COLLECTION].create_index("id", unique=True)
        await db[COLLECTION].create_index([("resource", 1), ("deleted_at", -1)])
        await db[COLLECTION].create_index([("expires_at", 1)])
    except Exception:  # noqa: BLE001 — index opsional, jangan gagalkan boot
        pass
