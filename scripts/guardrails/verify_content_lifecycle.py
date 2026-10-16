#!/usr/bin/env python3
"""INV-CMS-01 — Siklus hidup konten CMS wajib AMAN & PULIH (versi · tempat sampah · pengalihan).

Kelas bug yang dicegah (semuanya pernah TERBUKA di produk ini sebelum fase CMS-CW3):

  1. **Hapus permanen tanpa jalan pulang.** `DELETE /content/{resource}/{id}` dulu memanggil
     `delete_one` langsung: satu klik dan destinasi/paket/artikel hilang selamanya beserta
     galeri, tur 360°, dan metadata SEO-nya. Sekarang WAJIB lewat Tempat Sampah.
  2. **Isi tertimpa tanpa riwayat.** Tidak ada snapshot sebelum/sesudah penyuntingan, jadi
     salah tempel = kerusakan konten permanen. Sekarang setiap mutasi menulis versi.
  3. **Slug diubah → URL lama mati 404.** Ini kerugian SEO paling mahal: peringkat pencarian
     dan tautan pihak lain ikut mati. Sekarang perubahan slug WAJIB mencatat pengalihan, dan
     halaman detail publik WAJIB mencoba pengalihan sebelum menyerah.
  4. **Pemulihan yang diam-diam menayangkan.** Konten yang pernah dibuang tidak boleh kembali
     tayang tanpa diperiksa manusia → pemulihan SELALU draft.
  5. **Artefak uji bocor ke Tempat Sampah/riwayat editor** (kelas BUG-0127/0128): koleksi baru
     WAJIB terdaftar di mesin bersih-bersih.

STATIK (selalu): titik-tulis di router & service masih terpasang, koleksi baru terdaftar di
seluruh SSOT (kontrak/skema/compliance/purge), penjadwal pembuang retensi ter-wire, dan UI
benar-benar memakai ketiga fitur (bukan berkas komponen yatim).

RUNTIME (bila backend hidup): buat konten uji → ubah slug → URL lama dialihkan → hapus →
masuk Tempat Sampah → pulih sebagai DRAFT → buang permanen. Artefak dibersihkan sendiri.
"""
import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(__file__))
from _common import BACKEND, FRONTEND, Guard, G, R, X, mongo_db, purge_guard_artifacts  # noqa: E402

BASE = os.environ.get("GUARD_BASE_URL", "http://127.0.0.1:8001") + "/api"

MARK = "Penjaga INV-CMS-01"
SLUG_1 = "penjaga-inv-cms01-satu"
SLUG_2 = "penjaga-inv-cms01-dua"
CREATED = []


def req(method, path, token=None, body=None, timeout=25):
    url = BASE + path
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, method=method)
    r.add_header("Content-Type", "application/json")
    if token:
        r.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001
        return -1, str(e)


def login(email="owner@demo.local", password="demo12345"):
    st, txt = req("POST", "/auth/login", body={"email": email, "password": password})
    if st != 200:
        return None
    try:
        return json.loads(txt)["token"]
    except Exception:  # noqa: BLE001
        return None


# ── STATIK ───────────────────────────────────────────────────────────────────
def static_checks(g: Guard):
    router = (BACKEND / "routers" / "content.py").read_text(encoding="utf-8", errors="ignore")
    pub = (BACKEND / "routers" / "public.py").read_text(encoding="utf-8", errors="ignore")
    server = (BACKEND / "server.py").read_text(encoding="utf-8", errors="ignore")
    versions = (BACKEND / "services" / "content_versions.py").read_text(encoding="utf-8", errors="ignore")
    trash = (BACKEND / "services" / "content_trash.py").read_text(encoding="utf-8", errors="ignore")
    redir = (BACKEND / "services" / "content_redirects.py").read_text(encoding="utf-8", errors="ignore")
    publish = (BACKEND / "services" / "content_publish.py").read_text(encoding="utf-8", errors="ignore")

    # (1) hapus WAJIB lewat tempat sampah, bukan delete_one permanen.
    g.bump()
    if "ctrash.move_to_trash" not in router:
        g.add("routers/content.py: hapus konten tidak lagi memakai `ctrash.move_to_trash` → "
              "konten bisa hilang permanen dari satu klik (tidak ada jalan pulang).")
    g.bump()
    delete_block = router.split("async def delete_content", 1)[-1].split("@router.", 1)[0]
    # Dicocokkan pada POLA PEMANGGILAN nyata (`db[resource].delete_one`), bukan kata "delete_one"
    # di dalam docstring — kalau tidak, penjaga memerahkan dokumentasinya sendiri.
    if "db[resource].delete_one" in delete_block:
        g.add("routers/content.py::delete_content memanggil `db[resource].delete_one` langsung → "
              "penghapusan permanen kembali (Tempat Sampah dilewati).")

    # (2) riwayat versi ditulis di titik-tulis create & update.
    for fn in ("create_content", "update_content"):
        g.bump()
        block = router.split(f"async def {fn}", 1)[-1].split("@router.", 1)[0]
        if "cver.snapshot" not in block:
            g.add(f"routers/content.py::{fn} tidak menulis `cver.snapshot` → penyuntingan tanpa "
                  f"jejak versi (isi lama mustahil dipulihkan).")
    g.bump()
    if "MAX_VERSIONS" not in versions or "async def prune" not in versions:
        g.add("services/content_versions.py: batas simpan (`MAX_VERSIONS`) atau pemangkas "
              "(`prune`) hilang → riwayat tumbuh tanpa batas.")
    g.bump()
    if "cver.restorable" not in router:
        g.add("routers/content.py: pemulihan versi tidak menyaring field lewat "
              "`cver.restorable` → snapshot lama bisa menyuntikkan field asing "
              "(mass-assignment lewat pintu riwayat).")

    # (3) perubahan slug WAJIB mencatat pengalihan; rantai diratakan; lingkaran dibuang.
    g.bump()
    update_block = router.split("async def update_content", 1)[-1].split("@router.", 1)[0]
    if "credir.record_slug_change" not in update_block:
        g.add("routers/content.py::update_content tidak mencatat pengalihan saat slug berubah → "
              "URL lama mati 404 (kerugian SEO paling mahal di CMS ini).")
    g.bump()
    if 'update_many(\n        {"to_path": old_path}' not in redir and '{"to_path": old_path}' not in redir:
        g.add("services/content_redirects.py: perataan rantai pengalihan hilang → lahir rantai "
              "A→B→C yang lambat & mudah putus.")
    g.bump()
    if 'delete_many({"from_path": new_path})' not in redir:
        g.add("services/content_redirects.py: pembuangan pengalihan yang BERASAL dari slug baru "
              "hilang → lingkaran pengalihan mungkin terjadi.")
    g.bump()
    if "/redirect" not in pub:
        g.add("routers/public.py: endpoint publik `GET /public/redirect` hilang → pengunjung dari "
              "tautan lama tidak punya jalan ke URL baru.")
    g.bump()
    if "PUBLIC_PATHS" not in publish:
        g.add("services/content_publish.py: `preview_url` tidak lagi memakai SSOT "
              "`content_redirects.PUBLIC_PATHS` → tautan pratinjau & pengalihan bisa berbeda "
              "bentuk URL (salah satunya akan 404).")

    # (4) pemulihan SELALU draft + retensi + penjadwal pembuang.
    g.bump()
    if 'doc["status"] = "draft"' not in trash:
        g.add("services/content_trash.py: pemulihan tidak memaksa status draft → konten yang "
              "pernah dibuang bisa diam-diam tayang kembali tanpa diperiksa manusia.")
    g.bump()
    if "RETENTION_DAYS" not in trash or "expires_at" not in trash:
        g.add("services/content_trash.py: retensi tempat sampah (`RETENTION_DAYS`/`expires_at`) "
              "hilang → konten terhapus tersimpan selamanya.")
    g.bump()
    if "purge_expired" not in server:
        g.add("server.py: penjadwal tidak memanggil `content_trash.purge_expired` → tempat "
              "sampah tak pernah dikosongkan otomatis.")

    # (5) aksi massal berpagar (RBAC + batas jumlah).
    g.bump()
    bulk_block = router.split("async def bulk_content", 1)[-1].split("@router.", 1)[0] if "bulk_content" in router else ""
    if not bulk_block:
        g.add("routers/content.py: endpoint aksi massal hilang.")
    else:
        if "BULK_MAX" not in bulk_block:
            g.add("routers/content.py::bulk_content tidak membatasi jumlah item (`BULK_MAX`) → "
                  "satu permintaan bisa menyapu seluruh koleksi.")
        g.bump()
        if "Depends(CMS)" not in bulk_block:
            g.add("routers/content.py::bulk_content tanpa `Depends(CMS)` → aksi massal terbuka "
                  "untuk peran yang tidak berhak.")

    # (6) koleksi baru terdaftar di SELURUH SSOT.
    ssot = {
        "scripts/verify_contract.py": (BACKEND.parent / "scripts" / "verify_contract.py"),
        "scripts/validate_compliance.py": (BACKEND.parent / "scripts" / "validate_compliance.py"),
        "scripts/verify_schema.py": (BACKEND.parent / "scripts" / "verify_schema.py"),
        "scripts/seed_data.py": (BACKEND.parent / "scripts" / "seed_data.py"),
    }
    for label, path in ssot.items():
        text = path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""
        for coll in ("content_versions", "content_trash", "content_redirects"):
            g.bump()
            if coll not in text:
                g.add(f"{label}: koleksi `{coll}` tidak terdaftar → gate koleksi/skema/seed tidak "
                      f"mengawalnya (koleksi liar = kelas bug 'tak terdaftar' terbuka lagi).")
    # Mesin bersih-bersih: DAFTAR koleksi & CASCADE diperiksa TERPISAH — keduanya wajib menyebut
    # ketiga koleksi. Kalau hanya salah satunya, artefak uji tetap bocor ke CMS pengguna.
    common = (BACKEND.parent / "scripts" / "guardrails" / "_common.py").read_text(encoding="utf-8", errors="ignore")
    # Blok tuple dipotong pada `\n)` — BUKAN pada `)` pertama: komentar di dalam tuple memuat
    # tanda kurung tutup ("(panel \"Bukti Bayar\" ops)") sehingga pemotongan naif memotong
    # daftarnya di tengah dan penjaga menuduh pelanggaran yang tidak ada.
    purge_block = common.split("PURGE_COLLECTIONS = (", 1)[-1].split("\n)", 1)[0]
    for coll in ("content_versions", "content_trash", "content_redirects"):
        g.bump()
        if f'"{coll}"' not in purge_block:
            g.add(f"scripts/guardrails/_common.py: `{coll}` tidak ada di `PURGE_COLLECTIONS` → "
                  f"artefak data uji tertinggal & TERLIHAT editor di CMS (kelas BUG-0127).")
        g.bump()
        if f'("{coll}", {{"item_id"' not in common:
            g.add(f"scripts/guardrails/_common.py: cascade bersih-bersih tidak menghapus "
                  f"`{coll}` milik dokumen uji → editor melihat riwayat/tempat sampah berisi "
                  f"konten hantu (kelas BUG-0128).")

    # (7) UI benar-benar memakai ketiga fitur (bukan komponen yatim).
    cm = (FRONTEND / "src" / "features" / "app" / "ContentManager.jsx").read_text(encoding="utf-8", errors="ignore")
    for needle, why in (
        ("VersionHistoryDialog", "riwayat versi tidak bisa dibuka dari CMS"),
        ("TrashDialog", "Tempat Sampah tidak bisa dibuka dari CMS"),
        ("RedirectManagerPanel", "panel pengalihan URL hilang dari CMS"),
        ('data-testid="content-bulk-bar"', "bar aksi massal hilang"),
        ('data-testid="content-select-all"', "pilih-semua aksi massal hilang"),
        ('data-testid="content-trash-open"', "tombol Tempat Sampah hilang"),
        ("content-history-", "tombol riwayat versi per baris hilang"),
        ('content-tab-${k}', "tab CMS tidak lagi ber-testid"),
    ):
        g.bump()
        if needle not in cm:
            g.add(f"ContentManager.jsx: `{needle}` tidak ditemukan → {why} "
                  f"(backend punya fiturnya, pengguna tidak bisa memakainya).")
    for page in ("BlogDetail.jsx", "DestinationDetail.jsx", "PackageDetail.jsx"):
        g.bump()
        src = (FRONTEND / "src" / "features" / "public" / page)
        text = src.read_text(encoding="utf-8", errors="ignore") if src.exists() else ""
        # Diperiksa PEMANGGILANNYA (bukan sekadar baris import): import yang tersisa tanpa
        # pemanggilan adalah bentuk kegagalan senyap yang paling mudah lolos review.
        if "useSlugRedirect(" not in text:
            g.add(f"{page}: tidak MEMANGGIL `useSlugRedirect(...)` → URL lama halaman ini tetap "
                  f"jalan buntu meski pengalihan sudah tercatat di server.")


# ── RUNTIME ──────────────────────────────────────────────────────────────────
def runtime_probe(g: Guard, tok: str):
    payload = {"title": f"{MARK} Artikel", "slug": SLUG_1, "excerpt": "uji penjaga",
               "body": "<p>uji penjaga</p>", "category": "Tips", "status": "published"}
    st, txt = req("POST", "/content/articles", tok, payload)
    g.bump()
    if st not in (200, 201):
        g.add(f"INV-CMS-01: gagal membuat konten uji (HTTP {st}) — probe runtime tidak bisa jalan.")
        return
    item = json.loads(txt)
    item_id = item.get("id") or ""
    CREATED.append(item_id)

    # riwayat versi lahir otomatis
    st, txt = req("GET", f"/content/articles/{item_id}/versions", tok)
    rows = (json.loads(txt).get("rows") if st == 200 else []) or []
    g.bump()
    if st != 200 or not rows:
        g.add(f"INV-CMS-01: riwayat versi tidak terbentuk saat konten dibuat (HTTP {st}, "
              f"{len(rows)} versi).")
    print(f"    [{G if rows else R}{'ok' if rows else 'BAD'}{X}] versi awal tercatat: {len(rows)}")

    # slug berubah → pengalihan publik hidup
    st, txt = req("PUT", f"/content/articles/{item_id}", tok, {"slug": SLUG_2})
    g.bump()
    if st != 200:
        g.add(f"INV-CMS-01: gagal mengubah slug (HTTP {st}).")
    st_r, txt_r = req("GET", f"/public/redirect?path=/blog/{SLUG_1}")
    g.bump()
    if st_r != 200 or f"/blog/{SLUG_2}" not in txt_r:
        g.add(f"INV-CMS-01: URL lama TIDAK dialihkan setelah slug berubah (HTTP {st_r}: "
              f"{txt_r[:120]}) → tautan lama & peringkat pencarian mati.")
    print(f"    [{G if st_r == 200 else R}{'ok' if st_r == 200 else 'BAD'}{X}] pengalihan URL lama: HTTP {st_r}")

    # hapus → tempat sampah (bukan musnah)
    st, txt = req("DELETE", f"/content/articles/{item_id}", tok)
    trash_id = (json.loads(txt).get("trash_id") if st == 200 else "") or ""
    g.bump()
    if st != 200 or not trash_id:
        g.add(f"INV-CMS-01: hapus konten tidak menghasilkan baris Tempat Sampah (HTTP {st}: "
              f"{txt[:120]}) → penghapusan permanen tanpa jalan pulang.")
    st_l, txt_l = req("GET", "/content/trash?resource=articles", tok)
    g.bump()
    if st_l != 200 or item_id not in txt_l:
        g.add(f"INV-CMS-01: konten terhapus tidak muncul di Tempat Sampah (HTTP {st_l}).")

    # pulih → WAJIB draft
    if trash_id:
        st_re, txt_re = req("POST", f"/content/trash/{trash_id}/restore", tok)
        g.bump()
        if st_re != 200:
            g.add(f"INV-CMS-01: pemulihan dari Tempat Sampah gagal (HTTP {st_re}: {txt_re[:120]}).")
        else:
            restored = (json.loads(txt_re).get("item") or {})
            g.bump()
            if restored.get("status") != "draft" or restored.get("published") is True:
                g.add("INV-CMS-01: konten pulih TIDAK sebagai draft → halaman yang pernah dibuang "
                      f"diam-diam tayang lagi (status={restored.get('status')}).")
            print(f"    [{G}ok{X}] pulih sebagai: {restored.get('status')}")

    # aksi massal + RBAC
    st_b, txt_b = req("POST", "/content/articles/bulk", tok,
                      {"action": "publish", "ids": [item_id]})
    bulk_done = 0
    try:
        bulk_done = int(json.loads(txt_b).get("done") or 0)
    except Exception:  # noqa: BLE001
        bulk_done = 0
    g.bump()
    if st_b != 200 or bulk_done != 1:
        g.add(f"INV-CMS-01: aksi massal gagal untuk item yang sah (HTTP {st_b}: {txt_b[:120]}).")
    drv = login("driver@demo.local")
    if drv:
        for path in ("/content/trash", "/content/redirects"):
            st_d, _ = req("GET", path, drv)
            g.bump()
            if st_d != 403:
                g.add(f"INV-CMS-01: peran driver TIDAK diblokir di {path} (HTTP {st_d}) → "
                      f"permukaan CMS baru bocor lintas peran.")

    # buang permanen (kembalikan keadaan)
    st_l, txt_l = req("GET", "/content/trash?limit=200", tok)
    if st_l == 200:
        for row in (json.loads(txt_l).get("rows") or []):
            if MARK in str(row.get("label") or "") or row.get("item_id") in CREATED:
                req("DELETE", f"/content/trash/{row['id']}", tok)


def cleanup(tok):
    """Bersih-bersih TOTAL — tidak bergantung pada daftar purge (yang bisa dimutasi self-test)."""
    if tok:
        st, txt = req("GET", f"/content/articles?q={MARK.replace(' ', '%20')}&limit=100", tok)
        if st == 200:
            try:
                for row in json.loads(txt):
                    req("DELETE", f"/content/articles/{row['id']}", tok)
            except Exception:  # noqa: BLE001
                pass
        st, txt = req("GET", "/content/trash?limit=300", tok)
        if st == 200:
            try:
                for row in (json.loads(txt).get("rows") or []):
                    if MARK in str(row.get("label") or "") or row.get("item_id") in CREATED:
                        req("DELETE", f"/content/trash/{row['id']}", tok)
            except Exception:  # noqa: BLE001
                pass
    db, client = mongo_db()
    if db is not None:
        try:
            ids = [i for i in CREATED if i]
            if ids:
                db.content_versions.delete_many({"item_id": {"$in": ids}})
                db.content_trash.delete_many({"item_id": {"$in": ids}})
                db.content_redirects.delete_many({"item_id": {"$in": ids}})
                db.articles.delete_many({"id": {"$in": ids}})
            for slug in (SLUG_1, SLUG_2):
                db.content_redirects.delete_many({"from_path": f"/blog/{slug}"})
                db.content_redirects.delete_many({"to_path": f"/blog/{slug}"})
                db.articles.delete_many({"slug": slug})
        except Exception:  # noqa: BLE001
            pass
        finally:
            if client is not None:
                client.close()
    purge_guard_artifacts(extra_ids=tuple(i for i in CREATED if i))


def main() -> int:
    g = Guard("INV-CMS-01", "Siklus hidup konten CMS aman & pulih (versi · tempat sampah · pengalihan)")
    static_checks(g)
    tok = login()
    try:
        if tok:
            runtime_probe(g, tok)
        else:
            print(f"    {G}(backend/login tak tersedia — probe RUNTIME dilewati; cek STATIK tetap berlaku){X}")
    finally:
        cleanup(tok)
    return g.finish()


if __name__ == "__main__":
    sys.exit(main())
