#!/usr/bin/env python3
"""scripts/test_core_cms_cw3.py — POC INTI fase CMS-CW3 (4 gap CMS yang belum pernah ditutup).

Diuji LEWAT API SUNGGUHAN (bukan mock), sebelum UI dibangun:

  A. CMS-10  Riwayat versi + pemulihan (rollback) — isi lama bisa dikembalikan, rollback
             tidak destruktif, status terbit TIDAK ikut berubah, riwayat dibatasi.
  B. CMS-11  Tempat Sampah — hapus bisa dibatalkan, pulih SELALU sebagai draft, bentrok
             slug ditolak jujur (409) atau diganti nama atas permintaan, buang permanen.
  C. CMS-12  Pengalihan URL 301 — slug berubah → URL lama TIDAK mati; rantai diratakan;
             lingkaran mustahil; pengalihan manual + penghitung kunjungan.
  D. CMS-13  Aksi massal — tayangkan/sembunyikan/hapus banyak sekaligus, kegagalan per-item
             dilaporkan apa adanya (bukan digagalkan semua / disembunyikan).
  E. RBAC    Semua endpoint baru tertutup untuk peran non-CMS (driver → 403).

KEBERSIHAN DATA (INV-CLEAN-01): seluruh dokumen uji memakai penanda `Penjaga INV-` lalu
dibersihkan `purge_guard_artifacts()` di blok `finally` — termasuk riwayat versi, baris
tempat sampah, dan pengalihan yang lahir dari dokumen uji.
"""
import os
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

from guardrails._common import purge_guard_artifacts  # noqa: E402

BASE = os.environ.get("POC_BASE_URL", "http://localhost:8001")
API = f"{BASE}/api"
OWNER = {"email": "owner@demo.local", "password": "demo12345"}
DRIVER = {"email": "driver@demo.local", "password": "demo12345"}

MARK = "Penjaga INV-CMS3"
SLUG_A = "penjaga-inv-cms3-a"
SLUG_B = "penjaga-inv-cms3-b"
SLUG_C = "penjaga-inv-cms3-c"
SLUG_TRASH = "penjaga-inv-cms3-sampah"
BULK_SLUGS = ("penjaga-inv-cms3-massal-1", "penjaga-inv-cms3-massal-2",
              "penjaga-inv-cms3-massal-3")
MANUAL_FROM = "/blog/penjaga-inv-cms3-kampanye-lama"
MANUAL_TO = "/blog/penjaga-inv-cms3-a"

G, R, Y, C, X = "\033[92m", "\033[91m", "\033[93m", "\033[96m", "\033[0m"
PASS, FAIL = [], []
CREATED_IDS = []
MANUAL_REDIRECTS = []


def check(name, cond, detail=""):
    if cond:
        PASS.append(name)
        print(f"  {G}✓{X} {name}")
    else:
        FAIL.append(f"{name} — {detail}")
        print(f"  {R}✗{X} {name} {Y}{detail}{X}")
    return bool(cond)


def section(title):
    print(f"\n{C}▶ {title}{X}")


class Api:
    def __init__(self, creds):
        self.s = requests.Session()
        self.creds = creds
        self.token = ""

    def login(self):
        r = self.s.post(f"{API}/auth/login", json=self.creds, timeout=20)
        r.raise_for_status()
        self.token = r.json()["token"]
        self.s.headers["Authorization"] = f"Bearer {self.token}"
        return self

    def get(self, path, **kw):
        return self.s.get(f"{API}{path}", timeout=60, **kw)

    def post(self, path, **kw):
        return self.s.post(f"{API}{path}", timeout=60, **kw)

    def put(self, path, **kw):
        return self.s.put(f"{API}{path}", timeout=60, **kw)

    def delete(self, path, **kw):
        return self.s.delete(f"{API}{path}", timeout=60, **kw)


def public_get(path, **kw):
    return requests.get(f"{API}{path}", timeout=30, **kw)


def make_article(api, slug, title_suffix="", status="draft", body=None):
    payload = {"title": f"{MARK} {title_suffix or slug}", "slug": slug,
               "excerpt": "Ringkasan uji penjaga CW3",
               "body": body or "<p>Isi asli penjaga CW3.</p>",
               "category": "Tips", "author": "Penjaga", "status": status}
    r = api.post("/content/articles", json=payload)
    if r.status_code not in (200, 201):
        return None, r
    doc = r.json()
    CREATED_IDS.append(doc["id"])
    return doc, r


def admin_article(api, slug):
    rows = api.get("/content/articles", params={"q": slug, "limit": 50}).json()
    if not isinstance(rows, list):
        return None
    return next((r for r in rows if r.get("slug") == slug), None)


# ── A. CMS-10 — riwayat versi & rollback ─────────────────────────────────────
def test_versions(api):
    section("A. CMS-10 — riwayat versi & pemulihan (rollback)")
    art, r = make_article(api, SLUG_A, "Versi", status="published")
    if not check("Buat artikel uji (tayang)", bool(art), f"HTTP {r.status_code} {r.text[:160]}"):
        return None
    item_id = art["id"]

    v = api.get(f"/content/articles/{item_id}/versions")
    if not check("Riwayat versi dapat diakses", v.status_code == 200, f"HTTP {v.status_code}"):
        return art
    rows = v.json().get("rows") or []
    check("Versi pertama tercatat otomatis saat konten dibuat", len(rows) == 1, f"{len(rows)} versi")
    check("Versi pertama bertanda aksi `create`",
          rows and rows[0].get("action") == "create", str(rows[:1])[:160])
    check("Daftar versi TIDAK mengirim snapshot penuh (hemat & aman)",
          rows and "snapshot" not in rows[0], "snapshot ikut terkirim")

    upd = api.put(f"/content/articles/{item_id}",
                  json={"body": "<p>Isi DIUBAH penjaga CW3.</p>", "excerpt": "Ringkasan diubah"})
    check("Ubah isi artikel (200)", upd.status_code == 200, f"HTTP {upd.status_code}")
    rows = (api.get(f"/content/articles/{item_id}/versions").json() or {}).get("rows") or []
    check("Versi kedua tercatat setelah penyuntingan", len(rows) == 2, f"{len(rows)} versi")
    check("Versi kedua mencatat field yang berubah",
          rows and "body" in (rows[0].get("changed_fields") or []),
          str(rows[0].get("changed_fields"))[:160] if rows else "kosong")

    # Menyimpan tanpa perubahan TIDAK boleh melahirkan versi baru (riwayat harus bermakna).
    api.put(f"/content/articles/{item_id}", json={"body": "<p>Isi DIUBAH penjaga CW3.</p>"})
    rows_same = (api.get(f"/content/articles/{item_id}/versions").json() or {}).get("rows") or []
    check("Simpan tanpa perubahan tidak menambah versi kosong", len(rows_same) == 2,
          f"{len(rows_same)} versi")

    first = next((x for x in rows if x.get("version") == 1), None)
    detail = api.get(f"/content/articles/{item_id}/versions/{first['id']}") if first else None
    if check("Satu versi bisa dibuka lengkap", bool(detail) and detail.status_code == 200,
             f"HTTP {getattr(detail, 'status_code', '-')}"):
        snap = (detail.json().get("version") or {}).get("snapshot") or {}
        check("Snapshot versi lama memuat isi ASLI",
              "Isi asli penjaga CW3" in str(snap.get("body")), str(snap.get("body"))[:120])
        check("Perbandingan dengan isi sekarang tersedia",
              "body" in (detail.json().get("changed_vs_current") or []),
              str(detail.json().get("changed_vs_current"))[:160])

    res = api.post(f"/content/articles/{item_id}/versions/{first['id']}/restore") if first else None
    if check("Pulihkan ke versi 1 (200)", bool(res) and res.status_code == 200,
             f"HTTP {getattr(res, 'status_code', '-')} {getattr(res, 'text', '')[:160]}"):
        after = admin_article(api, SLUG_A) or {}
        check("Isi artikel kembali ke versi lama",
              "Isi asli penjaga CW3" in str(after.get("body")), str(after.get("body"))[:120])
        check("Status terbit TIDAK berubah karena rollback isi",
              (after.get("effective_status") or after.get("status")) == "published",
              f"status={after.get('effective_status') or after.get('status')}")
        rows2 = (api.get(f"/content/articles/{item_id}/versions").json() or {}).get("rows") or []
        check("Rollback dicatat sebagai versi BARU (rollback bisa di-rollback)",
              len(rows2) == 3 and rows2[0].get("action") == "restore",
              f"{len(rows2)} versi, aksi terbaru={rows2[0].get('action') if rows2 else '-'}")

    # Batas simpan riwayat: 20 versi terakhir per dokumen.
    meta = api.get(f"/content/articles/{item_id}/versions").json()
    cap = int(meta.get("max_versions") or 0)
    check("Batas riwayat diumumkan API", cap > 0, str(meta)[:120])
    for i in range(cap + 3):
        api.put(f"/content/articles/{item_id}", json={"excerpt": f"Ringkasan versi {i}"})
    rows3 = (api.get(f"/content/articles/{item_id}/versions",
                     params={"limit": 100}).json() or {}).get("rows") or []
    check(f"Riwayat dibatasi {cap} versi terakhir (database tidak tumbuh tanpa batas)",
          len(rows3) == cap, f"{len(rows3)} versi")
    check("Versi terbaru tetap tersedia setelah pemangkasan",
          rows3 and rows3[0].get("version") == max(r.get("version", 0) for r in rows3),
          str(rows3[:1])[:120])

    miss = api.get("/content/articles/art_tidak_ada/versions")
    check("Riwayat konten yang tak ada → 404", miss.status_code == 404, f"HTTP {miss.status_code}")
    bad = api.post(f"/content/articles/{item_id}/versions/cvr_palsu/restore")
    check("Pulihkan versi palsu → 404", bad.status_code == 404, f"HTTP {bad.status_code}")
    return art


# ── B. CMS-11 — Tempat Sampah ────────────────────────────────────────────────
def test_trash(api):
    section("B. CMS-11 — Tempat Sampah (hapus bisa dibatalkan)")
    art, r = make_article(api, SLUG_TRASH, "Sampah", status="published")
    if not check("Buat artikel uji tayang", bool(art), f"HTTP {r.status_code} {r.text[:160]}"):
        return
    item_id = art["id"]
    live = public_get(f"/public/articles/{SLUG_TRASH}")
    check("Artikel tayang bisa dibuka publik", live.status_code == 200, f"HTTP {live.status_code}")

    d = api.delete(f"/content/articles/{item_id}")
    if not check("Hapus artikel (200)", d.status_code == 200, f"HTTP {d.status_code} {d.text[:160]}"):
        return
    body = d.json()
    check("Hapus = PINDAH ke tempat sampah (bukan musnah)", body.get("trashed") is True, str(body)[:160])
    check("Retensi tempat sampah diumumkan (30 hari)",
          int(body.get("retention_days") or 0) == 30, str(body.get("retention_days")))
    trash_id = body.get("trash_id") or ""

    check("Artikel hilang dari daftar admin", admin_article(api, SLUG_TRASH) is None, "masih ada")
    gone = public_get(f"/public/articles/{SLUG_TRASH}")
    check("Artikel hilang dari publik (404)", gone.status_code == 404, f"HTTP {gone.status_code}")

    t = api.get("/content/trash", params={"resource": "articles"})
    if check("Daftar tempat sampah dapat diakses", t.status_code == 200, f"HTTP {t.status_code}"):
        rows = t.json().get("rows") or []
        row = next((x for x in rows if x.get("item_id") == item_id), None)
        if check("Item terhapus muncul di tempat sampah", bool(row), f"{len(rows)} baris"):
            check("Baris tempat sampah menyimpan label & tenggat",
                  bool(row.get("label")) and bool(row.get("expires_at")), str(row)[:160])
        check("Statistik retensi tersedia",
              int((t.json().get("stats") or {}).get("retention_days") or 0) == 30,
              str(t.json().get("stats")))

    rest = api.post(f"/content/trash/{trash_id}/restore")
    if check("Pulihkan dari tempat sampah (200)", rest.status_code == 200,
             f"HTTP {rest.status_code} {rest.text[:160]}"):
        back = admin_article(api, SLUG_TRASH)
        check("Artikel kembali ada di admin", bool(back), "tidak kembali")
        check("Pulihan SELALU draft (tidak diam-diam tayang lagi)",
              (back or {}).get("effective_status") == "draft",
              f"status={(back or {}).get('effective_status')}")
        still_hidden = public_get(f"/public/articles/{SLUG_TRASH}")
        check("Pulihan belum tayang di publik", still_hidden.status_code == 404,
              f"HTTP {still_hidden.status_code}")
        check("Id konten dipertahankan (tautan & atribusi tidak putus)",
              (back or {}).get("id") == item_id, f"{(back or {}).get('id')} vs {item_id}")
    twice = api.post(f"/content/trash/{trash_id}/restore")
    check("Pulihkan dua kali ditolak (409)", twice.status_code == 409, f"HTTP {twice.status_code}")

    # Bentrok slug: konten lain memakai slug yang sama selagi aslinya di tempat sampah.
    d2 = api.delete(f"/content/articles/{item_id}")
    trash_id2 = (d2.json() or {}).get("trash_id") or ""
    clash, _ = make_article(api, SLUG_TRASH, "Sampah Pengganti", status="draft")
    conflict = api.post(f"/content/trash/{trash_id2}/restore")
    check("Bentrok slug ditolak JUJUR (409, bukan menimpa konten hidup)",
          conflict.status_code == 409, f"HTTP {conflict.status_code} {conflict.text[:160]}")
    renamed = api.post(f"/content/trash/{trash_id2}/restore", params={"rename": "true"})
    if check("Pulihkan dengan ganti nama otomatis (200)", renamed.status_code == 200,
             f"HTTP {renamed.status_code} {renamed.text[:160]}"):
        item = (renamed.json() or {}).get("item") or {}
        check("Slug pulihan diberi akhiran unik `-restored`",
              str(item.get("slug", "")).startswith(f"{SLUG_TRASH}-restored"), str(item.get("slug")))
        check("Alasan penggantian nama dijelaskan ke editor",
              bool((renamed.json() or {}).get("notes")), str(renamed.json())[:160])

    # Buang permanen.
    if clash:
        d3 = api.delete(f"/content/articles/{clash['id']}")
        tid3 = (d3.json() or {}).get("trash_id") or ""
        purge = api.delete(f"/content/trash/{tid3}")
        check("Buang permanen dari tempat sampah (200)", purge.status_code == 200,
              f"HTTP {purge.status_code} {purge.text[:160]}")
        again = api.post(f"/content/trash/{tid3}/restore")
        check("Item yang dibuang permanen tidak bisa dipulihkan (404)", again.status_code == 404,
              f"HTTP {again.status_code}")
    missing = api.delete("/content/trash/ctr_palsu")
    check("Buang item tempat sampah palsu → 404", missing.status_code == 404,
          f"HTTP {missing.status_code}")


# ── C. CMS-12 — pengalihan URL (301) ─────────────────────────────────────────
def test_redirects(api):
    section("C. CMS-12 — pengalihan URL 301 saat slug berubah")
    art = admin_article(api, SLUG_A)
    if not check("Artikel uji dari bagian A tersedia", bool(art), "tidak ditemukan"):
        return
    item_id = art["id"]
    api.put(f"/content/articles/{item_id}", json={"status": "published"})
    check("Artikel tayang di URL awal",
          public_get(f"/public/articles/{SLUG_A}").status_code == 200, "tidak tayang")

    upd = api.put(f"/content/articles/{item_id}", json={"slug": SLUG_B})
    if check("Ubah slug (200)", upd.status_code == 200, f"HTTP {upd.status_code} {upd.text[:160]}"):
        created = (upd.json() or {}).get("redirect_created") or {}
        check("Pengalihan dibuat OTOMATIS saat slug berubah",
              created.get("from_path") == f"/blog/{SLUG_A}" and created.get("to_path") == f"/blog/{SLUG_B}",
              str(created))
    check("URL baru hidup", public_get(f"/public/articles/{SLUG_B}").status_code == 200, "mati")
    check("URL lama tidak lagi menyajikan konten (404 di API konten)",
          public_get(f"/public/articles/{SLUG_A}").status_code == 404, "masih 200")

    rd = public_get("/public/redirect", params={"path": f"/blog/{SLUG_A}"})
    if check("URL lama punya pengalihan publik (200)", rd.status_code == 200, f"HTTP {rd.status_code}"):
        data = rd.json()
        check("Pengalihan menunjuk URL baru", data.get("to_path") == f"/blog/{SLUG_B}", str(data))
        check("Niat semantik 301 dinyatakan", int(data.get("status") or 0) == 301, str(data))
    check("Pengalihan tetap cocok walau ada query string",
          public_get("/public/redirect",
                     params={"path": f"/blog/{SLUG_A}?lang=en"}).status_code == 200, "tidak cocok")
    check("Pengalihan tetap cocok walau ada garis miring akhir",
          public_get("/public/redirect",
                     params={"path": f"/blog/{SLUG_A}/"}).status_code == 200, "tidak cocok")

    # Rantai: ubah slug sekali lagi → pengalihan lama harus DIRATAKAN (1 lompatan).
    api.put(f"/content/articles/{item_id}", json={"slug": SLUG_C})
    hop1 = public_get("/public/redirect", params={"path": f"/blog/{SLUG_A}"})
    check("Rantai pengalihan diratakan (A → C langsung, bukan A → B → C)",
          hop1.status_code == 200 and (hop1.json() or {}).get("to_path") == f"/blog/{SLUG_C}",
          f"HTTP {hop1.status_code} {hop1.text[:120]}")
    hop2 = public_get("/public/redirect", params={"path": f"/blog/{SLUG_B}"})
    check("URL antara juga ikut menunjuk tujuan akhir",
          hop2.status_code == 200 and (hop2.json() or {}).get("to_path") == f"/blog/{SLUG_C}",
          f"HTTP {hop2.status_code} {hop2.text[:120]}")

    # Balik ke slug awal → pengalihan dari slug awal WAJIB hilang (kalau tidak: lingkaran).
    api.put(f"/content/articles/{item_id}", json={"slug": SLUG_A})
    loop = public_get("/public/redirect", params={"path": f"/blog/{SLUG_A}"})
    check("Lingkaran mustahil: pengalihan dari slug yang kembali dipakai dibuang",
          loop.status_code == 404, f"HTTP {loop.status_code} {loop.text[:120]}")
    back = public_get("/public/redirect", params={"path": f"/blog/{SLUG_C}"})
    check("Slug lama terakhir menunjuk slug yang sekarang hidup",
          back.status_code == 200 and (back.json() or {}).get("to_path") == f"/blog/{SLUG_A}",
          f"HTTP {back.status_code} {back.text[:120]}")

    # Pengalihan manual + validasi.
    man = api.post("/content/redirects", json={"from_path": MANUAL_FROM, "to_path": MANUAL_TO})
    if check("Tambah pengalihan manual (200)", man.status_code == 200,
             f"HTTP {man.status_code} {man.text[:160]}"):
        MANUAL_REDIRECTS.append((man.json() or {}).get("id"))
        rr = public_get("/public/redirect", params={"path": MANUAL_FROM})
        check("Pengalihan manual bekerja untuk pengunjung",
              rr.status_code == 200 and (rr.json() or {}).get("to_path") == MANUAL_TO,
              f"HTTP {rr.status_code} {rr.text[:120]}")
    dup = api.post("/content/redirects", json={"from_path": MANUAL_FROM, "to_path": "/promo"})
    check("Menambah asal yang sama = MEMPERBARUI tujuan (tanpa duplikat)",
          dup.status_code == 200 and (dup.json() or {}).get("to_path") == "/promo",
          f"HTTP {dup.status_code} {dup.text[:160]}")
    same = api.post("/content/redirects", json={"from_path": "/blog/x", "to_path": "/blog/x"})
    check("Pengalihan ke dirinya sendiri ditolak (400)", same.status_code == 400,
          f"HTTP {same.status_code}")
    home = api.post("/content/redirects", json={"from_path": "/", "to_path": "/promo"})
    check("Beranda tidak boleh dialihkan (400)", home.status_code == 400, f"HTTP {home.status_code}")
    empty = api.post("/content/redirects", json={"from_path": "", "to_path": "/promo"})
    check("Asal kosong ditolak (400)", empty.status_code == 400, f"HTTP {empty.status_code}")

    lst = api.get("/content/redirects")
    if check("Daftar pengalihan admin dapat diakses", lst.status_code == 200, f"HTTP {lst.status_code}"):
        rows = lst.json().get("rows") or []
        auto = next((x for x in rows if x.get("from_path") == f"/blog/{SLUG_C}"), None)
        if check("Pengalihan otomatis tercatat di panel admin", bool(auto), f"{len(rows)} baris"):
            check("Jumlah kunjungan terselamatkan dihitung", int(auto.get("hits") or 0) >= 1,
                  f"hits={auto.get('hits')}")
            check("Sumber pengalihan ditandai (auto vs manual)", auto.get("kind") == "auto",
                  str(auto.get("kind")))
        check("Statistik pengalihan tersedia",
              "total" in (lst.json().get("stats") or {}), str(lst.json().get("stats"))[:120])

    if MANUAL_REDIRECTS and MANUAL_REDIRECTS[0]:
        dele = api.delete(f"/content/redirects/{MANUAL_REDIRECTS[0]}")
        check("Hapus pengalihan manual (200)", dele.status_code == 200, f"HTTP {dele.status_code}")
        check("Setelah dihapus, pengalihan tidak berlaku lagi (404)",
              public_get("/public/redirect", params={"path": MANUAL_FROM}).status_code == 404,
              "masih berlaku")
        MANUAL_REDIRECTS.pop(0)
    check("Hapus pengalihan palsu → 404",
          api.delete("/content/redirects/crd_palsu").status_code == 404, "bukan 404")
    check("URL tanpa pengalihan → 404 (bukan 500)",
          public_get("/public/redirect", params={"path": "/blog/tidak-pernah-ada"}).status_code == 404,
          "bukan 404")


# ── D. CMS-13 — aksi massal ──────────────────────────────────────────────────
def test_bulk(api):
    section("D. CMS-13 — aksi massal (tayangkan / sembunyikan / hapus)")
    ids = []
    for slug in BULK_SLUGS:
        doc, r = make_article(api, slug, "Massal", status="draft")
        if doc:
            ids.append(doc["id"])
    if not check("Siapkan 3 artikel draft", len(ids) == 3, f"{len(ids)} dibuat"):
        return

    pub = api.post("/content/articles/bulk", json={"action": "publish", "ids": ids})
    if check("Tayangkan massal (200)", pub.status_code == 200,
             f"HTTP {pub.status_code} {pub.text[:160]}"):
        check("Semua item dilaporkan berhasil", (pub.json() or {}).get("done") == 3,
              str(pub.json())[:160])
    live = public_get("/public/articles", params={"limit": 100}).json()
    live_slugs = {a.get("slug") for a in live if isinstance(a, dict)}
    check("Ketiga artikel benar-benar tayang di publik",
          all(s in live_slugs for s in BULK_SLUGS), str(sorted(live_slugs))[:200])

    unpub = api.post("/content/articles/bulk", json={"action": "unpublish", "ids": ids})
    check("Sembunyikan massal (200)", unpub.status_code == 200, f"HTTP {unpub.status_code}")
    live2 = public_get("/public/articles", params={"limit": 100}).json()
    live_slugs2 = {a.get("slug") for a in live2 if isinstance(a, dict)}
    check("Ketiganya hilang dari publik setelah disembunyikan",
          not any(s in live_slugs2 for s in BULK_SLUGS), str(sorted(live_slugs2))[:200])

    mixed = api.post("/content/articles/bulk",
                     json={"action": "publish", "ids": ids[:1] + ["art_tidak_ada"]})
    if check("Sebagian gagal tetap 200 dengan laporan jujur", mixed.status_code == 200,
             f"HTTP {mixed.status_code}"):
        data = mixed.json()
        check("Item yang berhasil dihitung", data.get("done") == 1, str(data)[:160])
        check("Item yang gagal disebutkan beserta alasannya",
              len(data.get("failed") or []) == 1 and data["failed"][0]["id"] == "art_tidak_ada",
              str(data.get("failed"))[:160])
        check("`ok` menjadi false bila ada yang gagal", data.get("ok") is False, str(data)[:120])

    check("Aksi tak dikenal ditolak (400)",
          api.post("/content/articles/bulk",
                   json={"action": "hapus-semua", "ids": ids}).status_code == 400, "lolos")
    check("Tanpa pilihan item ditolak (400)",
          api.post("/content/articles/bulk", json={"action": "publish", "ids": []}).status_code == 400,
          "lolos")
    check("Batas jumlah per aksi ditegakkan (400)",
          api.post("/content/articles/bulk",
                   json={"action": "publish", "ids": [f"art_{i}" for i in range(201)]}
                   ).status_code == 400, "lolos")
    check("Jenis konten tak dikenal ditolak (404)",
          api.post("/content/entahapa/bulk",
                   json={"action": "publish", "ids": ids}).status_code == 404, "lolos")

    dele = api.post("/content/articles/bulk", json={"action": "delete", "ids": ids})
    if check("Hapus massal (200)", dele.status_code == 200, f"HTTP {dele.status_code}"):
        check("Ketiganya dilaporkan terhapus", (dele.json() or {}).get("done") == 3,
              str(dele.json())[:160])
    trash_rows = (api.get("/content/trash", params={"resource": "articles", "limit": 200})
                  .json() or {}).get("rows") or []
    trashed_ids = {x.get("item_id") for x in trash_rows}
    check("Hapus massal juga masuk tempat sampah (bisa dibatalkan)",
          all(i in trashed_ids for i in ids), f"{len(trash_rows)} baris tempat sampah")
    check("Ketiganya hilang dari daftar admin",
          all(admin_article(api, s) is None for s in BULK_SLUGS), "masih ada")


# ── E. RBAC ──────────────────────────────────────────────────────────────────
def test_rbac():
    section("E. RBAC — endpoint baru tertutup untuk peran non-CMS")
    try:
        drv = Api(DRIVER).login()
    except Exception as exc:  # noqa: BLE001
        check("Login driver untuk uji RBAC", False, str(exc))
        return
    probes = [
        ("GET /content/trash", drv.get("/content/trash")),
        ("GET /content/redirects", drv.get("/content/redirects")),
        ("POST /content/redirects", drv.post("/content/redirects",
                                             json={"from_path": "/a", "to_path": "/b"})),
        ("GET /content/articles/{id}/versions", drv.get("/content/articles/art_x/versions")),
        ("POST /content/articles/bulk", drv.post("/content/articles/bulk",
                                                 json={"action": "publish", "ids": ["art_x"]})),
        ("POST /content/trash/{id}/restore", drv.post("/content/trash/ctr_x/restore")),
        ("DELETE /content/trash/{id}", drv.delete("/content/trash/ctr_x")),
    ]
    for label, resp in probes:
        check(f"Driver diblokir di {label} (403)", resp.status_code == 403,
              f"HTTP {resp.status_code}")


# ─────────────────────────────────────────────────────────────────────────────
def cleanup(api):
    section("Bersih-bersih (INV-CLEAN-01)")
    # 1) hapus konten uji (masuk tempat sampah) lalu buang permanen tempat sampahnya.
    for resource in ("articles", "destinations", "packages", "promos"):
        try:
            rows = api.get(f"/content/{resource}", params={"q": MARK, "limit": 200}).json()
            for row in rows if isinstance(rows, list) else []:
                api.delete(f"/content/{resource}/{row['id']}")
        except Exception:  # noqa: BLE001
            pass
    try:
        rows = (api.get("/content/trash", params={"limit": 500}).json() or {}).get("rows") or []
        for row in rows:
            if MARK in str(row.get("label") or "") or row.get("item_id") in CREATED_IDS:
                api.delete(f"/content/trash/{row['id']}")
    except Exception:  # noqa: BLE001
        pass
    # 2) pengalihan manual uji (tak punya item_id → tidak tercakup cascade).
    try:
        rows = (api.get("/content/redirects", params={"limit": 500}).json() or {}).get("rows") or []
        for row in rows:
            paths = f"{row.get('from_path')} {row.get('to_path')}"
            if "penjaga-inv-cms3" in paths or row.get("item_id") in CREATED_IDS:
                api.delete(f"/content/redirects/{row['id']}")
    except Exception:  # noqa: BLE001
        pass
    removed = purge_guard_artifacts(verbose=True, extra_ids=tuple(i for i in CREATED_IDS if i))
    print(f"    dokumen artefak dibersihkan: {removed}")


def main():
    print(f"{C}=== POC CMS CW3 (riwayat versi · tempat sampah · pengalihan 301 · aksi massal) ==={X}")
    api = Api(OWNER)
    try:
        api.login()
    except Exception as exc:  # noqa: BLE001
        print(f"{R}Login gagal: {exc}{X}")
        sys.exit(1)
    try:
        test_versions(api)
        test_trash(api)
        test_redirects(api)
        test_bulk(api)
        test_rbac()
    finally:
        cleanup(api)

    total = len(PASS) + len(FAIL)
    print(f"\n{C}{'=' * 70}{X}")
    if FAIL:
        print(f"{R}GAGAL {len(FAIL)}/{total}{X}")
        for f in FAIL:
            print(f"  {R}·{X} {f}")
        sys.exit(1)
    print(f"{G}SEMUA LOLOS {len(PASS)}/{total}{X}")


if __name__ == "__main__":
    main()
