"""services/content_versions.py — CMS-10: riwayat versi & pemulihan (rollback) konten.

Masalah yang diperbaiki
-----------------------
CMS-05 memberi konten siklus terbit (draft → terjadwal → tayang), tetapi TIDAK ada satu pun
jejak "isi sebelumnya". Bila editor menimpa artikel yang sudah tayang dengan teks salah — atau
menghapus separuh isinya lalu menyimpan — satu-satunya jejak tersisa hanyalah JSON mentah di
Audit Log yang tidak bisa dipulihkan lewat UI. Untuk situs yang menjadi mesin akuisisi lead,
itu berarti kerusakan konten PERMANEN yang hanya bisa diperbaiki dengan menulis ulang.

Solusi
------
Setiap mutasi konten (`create` / `update` / `restore`) menuliskan SNAPSHOT dokumen SESUDAH
perubahan ke koleksi `content_versions`. Pemulihan bersifat TIDAK destruktif: memulihkan versi
lama membuat versi BARU (jadi rollback pun bisa di-rollback, dan jejak siapa-melakukan-apa tidak
pernah hilang). Riwayat dibatasi `MAX_VERSIONS` terakhir per dokumen supaya database tidak
tumbuh tanpa batas pada artikel yang sering disunting.

Catatan desain
--------------
- Nomor versi dijaga index UNIK `(resource, item_id, version)` + retry: dua penyimpanan paralel
  tidak boleh menghasilkan dua "versi 5" yang berbeda isi (riwayat yang berbohong lebih buruk
  daripada tidak ada riwayat).
- Daftar versi TIDAK mengirim snapshot penuh (artikel bisa puluhan KB) — hanya metadata +
  ringkasan field yang berubah. Snapshot penuh diambil saat editor membuka satu versi.
"""
from core_utils import new_id, now_iso

COLLECTION = "content_versions"

# Simpan 20 versi terakhir per dokumen: cukup untuk memulihkan kesalahan sunting sehari-hari
# tanpa membuat koleksi tumbuh tanpa batas.
MAX_VERSIONS = 20

# Field yang tidak pernah masuk hitungan "berubah" (derau teknis, bukan keputusan editor).
_NOISE = {"_id", "id", "created_at", "updated_at", "published_at", "used_count"}

ACTIONS = ("create", "update", "restore")


def label_of(doc: dict) -> str:
    doc = doc or {}
    return str(doc.get("name") or doc.get("title") or doc.get("code") or doc.get("id") or "konten")


def diff_fields(before: dict | None, after: dict | None) -> list:
    """Nama field yang benar-benar berbeda antara dua dokumen (untuk ringkasan riwayat)."""
    before = before or {}
    after = after or {}
    keys = (set(before) | set(after)) - _NOISE
    return sorted(k for k in keys if before.get(k) != after.get(k))


def _clip(doc: dict) -> dict:
    """Buang `_id` Mongo (tidak bisa di-serialisasi & tidak berguna di snapshot)."""
    return {k: v for k, v in (doc or {}).items() if k != "_id"}


async def _next_version(db, resource: str, item_id: str) -> int:
    last = await db[COLLECTION].find_one(
        {"resource": resource, "item_id": item_id}, {"_id": 0, "version": 1},
        sort=[("version", -1)])
    return int((last or {}).get("version") or 0) + 1


async def snapshot(db, resource: str, item_id: str, doc: dict, actor: dict | None = None,
                   action: str = "update", before: dict | None = None) -> dict:
    """Catat satu versi (dokumen SESUDAH perubahan). Aman dipanggil tanpa `before`."""
    act = action if action in ACTIONS else "update"
    snap = _clip(doc)
    row = {
        "id": new_id("cvr"),
        "resource": resource,
        "item_id": item_id,
        "action": act,
        "snapshot": snap,
        "changed_fields": diff_fields(before, doc) if before is not None else [],
        "label": label_of(doc),
        "actor_id": str((actor or {}).get("id") or ""),
        "actor_name": str((actor or {}).get("name") or (actor or {}).get("email") or "sistem"),
        "created_at": now_iso(),
    }
    for attempt in range(4):
        row["version"] = await _next_version(db, resource, item_id)
        try:
            await db[COLLECTION].insert_one(dict(row))
            break
        except Exception:  # noqa: BLE001 — bentrok nomor versi (paralel) → hitung ulang
            if attempt == 3:
                return {}
    await prune(db, resource, item_id)
    return {k: v for k, v in row.items() if k != "snapshot"}


async def prune(db, resource: str, item_id: str, keep: int = MAX_VERSIONS) -> int:
    """Buang versi paling lama di luar batas simpan. Return jumlah terhapus."""
    rows = await db[COLLECTION].find(
        {"resource": resource, "item_id": item_id}, {"_id": 0, "id": 1, "version": 1}
    ).sort([("version", -1)]).to_list(500)
    stale = [r["id"] for r in rows[keep:]]
    if not stale:
        return 0
    res = await db[COLLECTION].delete_many({"id": {"$in": stale}})
    return int(res.deleted_count or 0)


async def list_versions(db, resource: str, item_id: str, limit: int = 50) -> list:
    """Metadata riwayat (tanpa snapshot penuh) — terbaru lebih dulu."""
    rows = await db[COLLECTION].find(
        {"resource": resource, "item_id": item_id},
        {"_id": 0, "snapshot": 0}
    ).sort([("version", -1)]).to_list(limit)
    return rows


async def get_version(db, resource: str, item_id: str, version_id: str) -> dict | None:
    """Satu versi lengkap. `version_id` boleh id (`cvr_…`) atau nomor versi."""
    vid = str(version_id or "").strip()
    if not vid:
        return None
    query = {"resource": resource, "item_id": item_id}
    if vid.isdigit():
        query["version"] = int(vid)
    else:
        query["id"] = vid
    return await db[COLLECTION].find_one(query, {"_id": 0})


def restorable(snap: dict, fields) -> dict:
    """Ambil HANYA field yang boleh ditulis resource ini (whitelist yang sama dgn CRUD).

    Tanpa penyaringan ini, memulihkan versi lama bisa menyuntikkan field asing yang pernah ada
    di dokumen (mass-assignment lewat pintu belakang riwayat).
    """
    snap = snap or {}
    return {f: snap[f] for f in fields if f in snap}


async def count(db, resource: str, item_id: str) -> int:
    return int(await db[COLLECTION].count_documents({"resource": resource, "item_id": item_id}))


async def drop_for(db, resource: str, item_id: str) -> int:
    """Hapus seluruh riwayat satu dokumen (dipakai saat konten dibuang permanen)."""
    res = await db[COLLECTION].delete_many({"resource": resource, "item_id": item_id})
    return int(res.deleted_count or 0)


async def ensure_indexes(db):
    try:
        await db[COLLECTION].create_index(
            [("resource", 1), ("item_id", 1), ("version", -1)], unique=True)
        await db[COLLECTION].create_index([("created_at", -1)])
    except Exception:  # noqa: BLE001 — index opsional, jangan gagalkan boot
        pass
