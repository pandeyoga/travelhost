"""services/content_redirects.py — CMS-12: pengalihan URL (301) saat slug konten berubah.

Masalah yang diperbaiki (risiko SEO paling mahal di CMS ini)
-----------------------------------------------------------
Slug adalah URL. Begitu editor merapikan slug artikel yang sudah diindeks Google
(`/blog/tips-liburan-bali` → `/blog/tips-liburan-bali-2026`), URL lama LANGSUNG mati 404:
peringkat pencarian yang dibangun berbulan-bulan hilang, tautan dari blog/medsos lain
menjadi rusak, dan pengunjung dari iklan mendarat di halaman kosong. Tidak ada satu pun
koleksi/endpoint pengalihan sebelum ini.

Solusi
------
Setiap perubahan slug otomatis mencatat pengalihan `dari → ke` di `content_redirects`.
Pengunjung yang membuka URL lama diarahkan ke URL baru (`replace`, bukan push, sehingga
tombol Kembali tidak terjebak), dan editor bisa menambah/menghapus pengalihan manual
(mis. memindahkan tautan kampanye lama ke halaman baru).

Kejujuran teknis
----------------
Situs ini SPA: HTTP 301 sesungguhnya hanya bisa dikirim server yang menyajikan HTML.
Yang dilakukan di sini adalah pengalihan sisi-klien berbasis data + endpoint publik
`GET /api/public/redirect?path=…` yang menjawab `status: 301` beserta tujuannya — mesin
pencari modern mengikuti pengalihan sisi-klien ini, dan URL lama tidak lagi menjadi jalan
buntu. Bila kelak dipasang server render/edge, tabel yang sama bisa langsung dipakai untuk
mengirim 301 sungguhan tanpa mengubah data.

Rantai & lingkaran
------------------
Slug boleh berubah berkali-kali. Agar tidak lahir rantai `A→B→C` (dua lompatan = lambat,
mudah putus), pencatatan baru MERATAKAN pengalihan lama yang menunjuk `B` menjadi menunjuk
`C`, dan pengalihan yang berasal dari `C` dibuang supaya tidak ada lingkaran `C→C`.
"""
from core_utils import new_id, now_iso

COLLECTION = "content_redirects"

# Peta resource → prefiks URL publik yang BENAR-BENAR ada di frontend (`App.js`).
# SSOT: dipakai juga oleh `content_publish.preview_url` supaya tautan pratinjau, sitemap,
# dan pengalihan mustahil berbeda pendapat soal bentuk URL.
PUBLIC_PATHS = {"articles": "/blog", "destinations": "/destinations", "packages": "/packages"}

MAX_PATH_LEN = 300
MAX_HOPS = 5


class RedirectError(Exception):
    """Masukan pengalihan tidak sah (dipetakan ke HTTP 400 oleh router)."""


def normalize_path(value) -> str:
    """`/Blog/slug?lang=en#bagian` → `/blog/slug`? TIDAK: huruf besar/kecil slug dipertahankan.

    Yang dinormalkan: buang query & fragment, pastikan berawal `/`, buang garis miring akhir,
    rapatkan garis miring ganda, dan batasi panjang. Slug bersifat case-sensitive di MongoDB,
    jadi mengubah huruf akan membuat pengalihan tidak pernah cocok.
    """
    raw = str(value or "").strip()
    if not raw:
        return ""
    raw = raw.split("#", 1)[0].split("?", 1)[0].strip()
    if raw.startswith("http://") or raw.startswith("https://"):
        # Terima URL absolut milik situs sendiri → ambil path-nya saja.
        rest = raw.split("://", 1)[1]
        raw = "/" + rest.partition("/")[2]
    if not raw.startswith("/"):
        raw = "/" + raw
    while "//" in raw:
        raw = raw.replace("//", "/")
    if len(raw) > 1 and raw.endswith("/"):
        raw = raw[:-1]
    return raw[:MAX_PATH_LEN]


def path_for(resource: str, slug) -> str:
    """URL publik satu konten (kosong bila resource tidak punya halaman publik)."""
    prefix = PUBLIC_PATHS.get(resource)
    slug = str(slug or "").strip()
    if not prefix or not slug:
        return ""
    return normalize_path(f"{prefix}/{slug}")


async def record_slug_change(db, resource: str, item_id: str, old_slug, new_slug,
                            actor: dict | None = None) -> dict | None:
    """Catat pengalihan otomatis setelah slug berubah. Return baris pengalihan (atau None)."""
    old_path = path_for(resource, old_slug)
    new_path = path_for(resource, new_slug)
    if not old_path or not new_path or old_path == new_path:
        return None
    now = now_iso()
    # (1) Ratakan rantai: pengalihan lama yang menunjuk URL lama kini menunjuk URL baru.
    await db[COLLECTION].update_many(
        {"to_path": old_path}, {"$set": {"to_path": new_path, "updated_at": now}})
    # (2) Buang pengalihan yang BERASAL dari URL baru (kalau dibiarkan → lingkaran).
    await db[COLLECTION].delete_many({"from_path": new_path})
    # (3) Catat / perbarui pengalihan URL lama → URL baru.
    row = {
        "id": new_id("crd"),
        "from_path": old_path,
        "to_path": new_path,
        "resource": resource,
        "item_id": item_id,
        "kind": "auto",
        "hits": 0,
        "last_hit_at": "",
        "created_by": str((actor or {}).get("id") or ""),
        "created_at": now,
        "updated_at": now,
    }
    existing = await db[COLLECTION].find_one({"from_path": old_path}, {"_id": 0, "id": 1})
    if existing:
        await db[COLLECTION].update_one(
            {"id": existing["id"]},
            {"$set": {"to_path": new_path, "resource": resource, "item_id": item_id,
                      "kind": "auto", "updated_at": now}})
        return {**row, "id": existing["id"]}
    await db[COLLECTION].insert_one(dict(row))
    return row


async def resolve(db, path, count_hit: bool = True) -> dict | None:
    """Cari tujuan pengalihan untuk satu path. Mengikuti rantai maksimum `MAX_HOPS`."""
    start = normalize_path(path)
    if not start:
        return None
    seen = {start}
    current = start
    final = None
    for _ in range(MAX_HOPS):
        row = await db[COLLECTION].find_one({"from_path": current}, {"_id": 0})
        if not row:
            break
        final = row
        nxt = normalize_path(row.get("to_path"))
        if not nxt or nxt in seen:
            break                 # lingkaran / tujuan kosong → hentikan di sini
        seen.add(nxt)
        current = nxt
    if not final or current == start:
        return None
    if count_hit:
        await db[COLLECTION].update_one(
            {"from_path": start},
            {"$inc": {"hits": 1}, "$set": {"last_hit_at": now_iso()}})
    return {"from_path": start, "to_path": current, "status": 301,
            "resource": final.get("resource") or "", "kind": final.get("kind") or "auto"}


async def list_redirects(db, resource: str = "", limit: int = 200) -> list:
    query: dict = {}
    if resource:
        query["resource"] = resource
    return await db[COLLECTION].find(query, {"_id": 0}).sort(
        [("updated_at", -1)]).to_list(limit)


def _validate_manual(from_path: str, to_path: str):
    if not from_path or not to_path:
        raise RedirectError("URL asal & tujuan wajib diisi")
    if from_path == to_path:
        raise RedirectError("URL asal dan tujuan tidak boleh sama (lingkaran)")
    if from_path == "/":
        raise RedirectError("Beranda tidak boleh dialihkan")


async def create_manual(db, from_path, to_path, actor: dict | None = None) -> dict:
    """Tambah/ubah pengalihan manual (mis. URL kampanye lama → halaman promo baru)."""
    src = normalize_path(from_path)
    dst = normalize_path(to_path)
    _validate_manual(src, dst)
    # Cegah lingkaran: kalau tujuan (dst) sendiri sudah dialihkan kembali ke src.
    hop = await resolve(db, dst, count_hit=False)
    if hop and hop["to_path"] == src:
        raise RedirectError("Pengalihan ini membentuk lingkaran dengan pengalihan yang sudah ada")
    now = now_iso()
    existing = await db[COLLECTION].find_one({"from_path": src}, {"_id": 0, "id": 1})
    if existing:
        await db[COLLECTION].update_one(
            {"id": existing["id"]},
            {"$set": {"to_path": dst, "kind": "manual", "updated_at": now}})
        return await db[COLLECTION].find_one({"id": existing["id"]}, {"_id": 0})
    row = {
        "id": new_id("crd"), "from_path": src, "to_path": dst, "resource": "", "item_id": "",
        "kind": "manual", "hits": 0, "last_hit_at": "",
        "created_by": str((actor or {}).get("id") or ""), "created_at": now, "updated_at": now,
    }
    await db[COLLECTION].insert_one(dict(row))
    return row


async def delete_redirect(db, redirect_id: str) -> dict | None:
    row = await db[COLLECTION].find_one({"id": str(redirect_id or "")}, {"_id": 0})
    if not row:
        return None
    await db[COLLECTION].delete_one({"id": row["id"]})
    return row


async def drop_for_item(db, resource: str, item_id: str) -> int:
    res = await db[COLLECTION].delete_many({"resource": resource, "item_id": item_id})
    return int(res.deleted_count or 0)


async def stats(db) -> dict:
    total = await db[COLLECTION].count_documents({})
    rows = await db[COLLECTION].find({}, {"_id": 0, "hits": 1}).to_list(1000)
    return {"total": int(total), "hits": int(sum(int(r.get("hits") or 0) for r in rows))}


async def ensure_indexes(db):
    try:
        await db[COLLECTION].create_index("from_path", unique=True)
        await db[COLLECTION].create_index([("resource", 1), ("item_id", 1)])
    except Exception:  # noqa: BLE001 — index opsional, jangan gagalkan boot
        pass
