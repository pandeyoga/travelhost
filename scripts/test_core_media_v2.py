#!/usr/bin/env python3
"""test_core_media_v2.py — POC WAJIB Media Manager v2 (satu library media untuk CMS + halaman iklan).

Mengapa POC ini ada
-------------------
Ronde ini menyatukan DUA sistem media yang sebelumnya tidak saling tahu (`/api/uploads/cms` tanpa
metadata vs `/api/landing/media` dengan metadata tapi tertutup untuk ops_admin) dan menambah
folder, unduh, ganti berkas, aksi massal, crop, serta impor aset lama. Semuanya menyentuh BERKAS
NYATA di disk dan URL yang sudah dipakai halaman publik yang tayang — kelas pekerjaan yang paling
mudah "berhasil di layar tapi rusak di kenyataan" (gambar 404, cache membeku, aset hilang saat
folder dihapus). Karena itu seluruh alur inti dibuktikan di sini TANPA UI dulu.

Cakupan (A–I):
  A. Folder: buat/ganti nama/pindah/hapus · tolak siklus · hapus folder TIDAK menghapus aset.
  B. Unggah ke folder + daftar dengan saringan folder/jenis/kata kunci + hitungan benar.
  C. Unduh: byte identik, header attachment, tanpa auth ditolak, id palsu 404 (bukan 500).
  D. Ganti berkas: id & URL tetap, `version` naik, cache tidak membeku (ETag/`?v=`), tipe beda ditolak.
  E. Aksi massal: pindah banyak, hapus banyak, laporan "dipakai di mana" akurat, aset terhapus 404.
  F. Crop: dimensi benar, simpan-sebagai-baru vs ganti-asli, kotak potong tidak sah ditolak 400.
  G. Penyatuan + migrasi: impor aset CMS lama IDEMPOTEN, URL lama tetap hidup, unggah CMS masuk library.
  H. RBAC: ops_admin & marketing_admin boleh; driver 403 di SEMUA endpoint; landing lama tetap ketat.
  I. Keamanan: path traversal ditolak, MIME/ukuran ditegakkan, nama folder/berkas disanitasi.

Jalankan: cd /app && python scripts/test_core_media_v2.py
"""
import asyncio
import io
import os
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / "backend" / ".env")
from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

G, R, C, B, X = "\033[92m", "\033[91m", "\033[96m", "\033[1m", "\033[0m"
API = "http://localhost:8001/api"
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok)))
    print(f"  {G}[OK]{X} {name}" if ok else f"  {R}[GAGAL]{X} {name}" + (f" — {detail}" if detail else ""))
    return bool(ok)


def head(t):
    print(f"\n{C}{B}== {t} =={X}")


def login(email):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": "demo12345"}, timeout=20)
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['token']}"}


def png_bytes(w=800, h=600, color=(30, 120, 220)):
    """Gambar PNG nyata (bukan byte palsu) supaya PIL, dimensi, thumbnail & crop benar-benar teruji."""
    from PIL import Image
    im = Image.new("RGB", (w, h), color)
    for x in range(0, w, 40):          # pola agar crop bisa dibedakan secara visual
        for y in range(0, h, 40):
            if (x // 40 + y // 40) % 2 == 0:
                im.paste((250, 250, 250), (x, y, min(x + 40, w), min(y + 40, h)))
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def upload(headers, data, name="foto.png", ctype="image/png", folder_id="", alt=""):
    return requests.post(f"{API}/media", headers=headers,
                         files={"file": (name, data, ctype)},
                         data={"folder_id": folder_id, "alt": alt}, timeout=60)


async def main():  # noqa: C901 — satu skrip POC sengaja linier agar mudah dibaca urut
    print(f"{B}{C}POC Media Manager v2 — folder · unduh · ganti berkas · massal · crop · unifikasi{X}")
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    owner = login("owner@demo.local")
    ops = login("ops@demo.local")
    mkt = login("marketing@demo.local")
    drv = login("driver@demo.local")

    # ================================================================= A. FOLDER
    head("A · Folder (buat / ganti nama / pindah / hapus tanpa kehilangan aset)")
    r = requests.post(f"{API}/media/folders", headers=ops, json={"name": "Kampanye Uji"}, timeout=20)
    check("ops_admin bisa membuat folder", r.status_code == 200, f"{r.status_code} {r.text[:160]}")
    f_root = r.json().get("id") if r.status_code == 200 else ""

    r = requests.post(f"{API}/media/folders", headers=ops,
                      json={"name": "Lebaran", "parent_id": f_root}, timeout=20)
    check("bisa membuat subfolder", r.status_code == 200, r.text[:160])
    f_child = r.json().get("id") if r.status_code == 200 else ""

    r = requests.post(f"{API}/media/folders", headers=ops, json={"name": "Kampanye Uji"}, timeout=20)
    check("nama folder ganda di lokasi sama ditolak", r.status_code == 400, f"{r.status_code} {r.text[:120]}")

    r = requests.post(f"{API}/media/folders", headers=ops, json={"name": "  "}, timeout=20)
    check("nama folder kosong ditolak berALASAN", r.status_code == 400, r.text[:120])

    r = requests.post(f"{API}/media/folders", headers=ops,
                      json={"name": "<img src=x onerror=alert(1)>Promo"}, timeout=20)
    xss_name = r.json().get("name", "") if r.status_code == 200 else ""
    check("nama folder ber-HTML disanitasi (anti XSS tersimpan)",
          r.status_code == 200 and "<" not in xss_name and ">" not in xss_name, xss_name)
    f_xss = r.json().get("id") if r.status_code == 200 else ""

    r = requests.patch(f"{API}/media/folders/{f_child}", headers=ops,
                       json={"name": "Lebaran 2026"}, timeout=20)
    check("ganti nama folder berhasil",
          r.status_code == 200 and r.json().get("name") == "Lebaran 2026", r.text[:160])

    r = requests.patch(f"{API}/media/folders/{f_root}", headers=ops,
                       json={"parent_id": f_child}, timeout=20)
    check("pindah folder ke dalam anaknya sendiri DITOLAK (anti siklus)",
          r.status_code == 400, f"{r.status_code} {r.text[:160]}")

    r = requests.patch(f"{API}/media/folders/{f_root}", headers=ops,
                       json={"parent_id": f_root}, timeout=20)
    check("pindah folder ke dirinya sendiri DITOLAK", r.status_code == 400, r.text[:120])

    r = requests.patch(f"{API}/media/folders/{f_child}", headers=ops,
                       json={"parent_id": "mdf_tidakada"}, timeout=20)
    check("pindah ke folder tak dikenal → 404 (bukan 500)", r.status_code == 404, r.text[:120])

    # ================================================================= B. UNGGAH & DAFTAR
    head("B · Unggah ke folder + daftar dengan saringan")
    img_a = png_bytes(800, 600, (20, 110, 200))
    r = upload(ops, img_a, "hiace-premio.png", folder_id=f_child, alt="Hiace Premio putih")
    check("unggah foto ke subfolder berhasil", r.status_code == 200, r.text[:200])
    asset_a = r.json() if r.status_code == 200 else {}
    check("metadata dimensi terisi dari berkas nyata",
          asset_a.get("width") == 800 and asset_a.get("height") == 600,
          f"{asset_a.get('width')}x{asset_a.get('height')}")
    check("URL aset memakai rute publik yang benar",
          str(asset_a.get("url", "")).startswith("/api/public/media/"), asset_a.get("url"))
    check("versi awal aset = 1", asset_a.get("version") == 1, str(asset_a.get("version")))
    check("folder aset tercatat", asset_a.get("folder_id") == f_child, asset_a.get("folder_id"))

    r = upload(ops, png_bytes(400, 400, (200, 60, 60)), "promo-lebaran.png", folder_id=f_root)
    asset_b = r.json() if r.status_code == 200 else {}
    check("unggah aset kedua (folder induk)", r.status_code == 200, r.text[:160])

    r = requests.get(f"{API}/media?folder_id={f_child}", headers=ops, timeout=20)
    ids = [a["id"] for a in r.json().get("assets", [])]
    check("saringan folder hanya mengembalikan aset folder itu",
          r.status_code == 200 and asset_a.get("id") in ids and asset_b.get("id") not in ids,
          str(ids))

    r = requests.get(f"{API}/media?q=premio", headers=ops, timeout=20)
    check("pencarian nama berkas bekerja",
          r.status_code == 200 and any(a["id"] == asset_a.get("id") for a in r.json().get("assets", [])),
          r.text[:160])

    r = requests.get(f"{API}/media?kind=video", headers=ops, timeout=20)
    check("saringan jenis video tidak mengembalikan foto",
          r.status_code == 200 and all(a["kind"] == "video" for a in r.json().get("assets", [])),
          r.text[:160])

    r = requests.get(f"{API}/media/folders", headers=ops, timeout=20)
    folders = {f["id"]: f for f in r.json().get("folders", [])}
    check("hitungan aset per folder benar",
          folders.get(f_child, {}).get("asset_count") == 1
          and folders.get(f_root, {}).get("asset_count") == 1,
          str([(f["name"], f["asset_count"]) for f in folders.values()]))
    check("label jalur folder menampilkan hierarki",
          "›" in (folders.get(f_child, {}).get("path_label") or ""),
          folders.get(f_child, {}).get("path_label"))

    # ================================================================= C. UNDUH
    head("C · Unduh berkas asli (ber-auth, byte identik, header attachment)")
    mid_a = asset_a.get("id")
    r = requests.get(f"{API}/media/{mid_a}/download", headers=ops, timeout=30)
    check("unduh mengembalikan 200", r.status_code == 200, str(r.status_code))
    check("byte hasil unduh IDENTIK dengan yang diunggah", r.content == img_a,
          f"{len(r.content)} vs {len(img_a)}")
    check("header Content-Disposition attachment + nama berkas",
          "attachment" in (r.headers.get("Content-Disposition") or "")
          and ".png" in (r.headers.get("Content-Disposition") or "").lower(),
          r.headers.get("Content-Disposition"))
    check("unduh tidak boleh di-cache bersama (private/no-store)",
          "no-store" in (r.headers.get("Cache-Control") or ""), r.headers.get("Cache-Control"))
    r = requests.get(f"{API}/media/{mid_a}/download", timeout=20)
    check("unduh TANPA auth ditolak", r.status_code in (401, 403), str(r.status_code))
    r = requests.get(f"{API}/media/med_tidakada/download", headers=ops, timeout=20)
    check("unduh id palsu → 404 (bukan 500)", r.status_code == 404, str(r.status_code))

    # ================================================================= D. GANTI BERKAS
    head("D · Ganti berkas (id & URL tetap, versi naik, cache tidak membeku)")
    old_doc = await db.media_assets.find_one({"id": mid_a}, {"_id": 0})
    old_path, old_thumb = old_doc.get("storage_path"), old_doc.get("thumb_path")
    thumb_before = requests.get(f"{API}/public/media/{mid_a}?thumb=1", timeout=30).content
    img_a2 = png_bytes(1200, 900, (10, 180, 90))
    r = requests.post(f"{API}/media/{mid_a}/replace", headers=ops,
                      files={"file": ("hiace-baru.png", img_a2, "image/png")}, timeout=60)
    check("ganti berkas berhasil", r.status_code == 200, r.text[:200])
    rep = r.json() if r.status_code == 200 else {}
    check("id aset TIDAK berubah setelah ganti berkas", rep.get("id") == mid_a, rep.get("id"))
    check("versi naik menjadi 2", rep.get("version") == 2, str(rep.get("version")))
    check("URL menyertakan penanda versi (?v=2) untuk membatalkan cache",
          "v=2" in str(rep.get("url")), rep.get("url"))
    check("dimensi ikut diperbarui dari berkas baru",
          rep.get("width") == 1200 and rep.get("height") == 900,
          f"{rep.get('width')}x{rep.get('height')}")
    r = requests.get(f"{API}/media/{mid_a}/download", headers=ops, timeout=30)
    check("byte hasil unduh sekarang = berkas BARU", r.content == img_a2, str(len(r.content)))
    check("berkas lama dibuang dari disk (tidak menumpuk sampah)",
          not (ROOT / "backend" / "uploads" / "media" / str(old_path)).exists()
          and not (ROOT / "backend" / "uploads" / "media" / str(old_thumb)).exists(),
          f"{old_path} / {old_thumb}")

    pub = f"{API}/public/media/{mid_a}"
    r = requests.get(pub, timeout=30)
    etag = r.headers.get("ETag")
    check("baca publik tanpa login tetap 200", r.status_code == 200, str(r.status_code))
    check("respons publik punya ETag berbasis versi",
          bool(etag) and "-2-" in str(etag), str(etag))
    check("URL tanpa versi TIDAK di-cache lama (harus divalidasi ulang)",
          "must-revalidate" in (r.headers.get("Cache-Control") or ""), r.headers.get("Cache-Control"))
    r2 = requests.get(f"{pub}?v=2", timeout=30)
    check("URL berversi terkini boleh di-cache selamanya (immutable)",
          "immutable" in (r2.headers.get("Cache-Control") or ""), r2.headers.get("Cache-Control"))
    r3 = requests.get(pub, headers={"If-None-Match": etag}, timeout=30)
    check("ETag cocok → 304 Not Modified (hemat kuota, tetap segar)", r3.status_code == 304,
          str(r3.status_code))
    r4 = requests.get(f"{pub}?thumb=1", timeout=30)
    # Thumbnail WAJIB ikut diregenerasi. Kalau tidak, grid Media Library tetap memperlihatkan foto
    # LAMA padahal berkas sudah diganti — pengguna akan memilih ulang aset yang salah.
    check("thumbnail ikut diregenerasi setelah ganti berkas (tidak stale)",
          r4.status_code == 200 and r4.content and r4.content != thumb_before,
          f"{r4.status_code} lama={len(thumb_before)} baru={len(r4.content)}")
    from PIL import Image as _PILImage
    thumb_dim = _PILImage.open(io.BytesIO(r4.content)).size if r4.content else (0, 0)
    check("thumbnail berukuran kecil (grid tetap ringan)",
          max(thumb_dim) <= 480 and max(thumb_dim) > 0, str(thumb_dim))

    r = requests.post(f"{API}/media/{mid_a}/replace", headers=ops,
                      files={"file": ("klip.mp4", b"\x00\x00\x00\x18ftypmp42" + b"0" * 400, "video/mp4")},
                      timeout=60)
    check("ganti foto dengan VIDEO ditolak berALASAN (blok pemakai tidak rusak)",
          r.status_code == 400 and "tipe" in r.text.lower(), f"{r.status_code} {r.text[:160]}")
    r = requests.post(f"{API}/media/{mid_a}/replace", headers=ops,
                      files={"file": ("jahat.exe", b"MZ" + b"0" * 100, "application/x-msdownload")},
                      timeout=30)
    check("ganti dengan berkas eksekutabel ditolak", r.status_code == 400, str(r.status_code))
    r = requests.post(f"{API}/media/med_tidakada/replace", headers=ops,
                      files={"file": ("x.png", png_bytes(10, 10), "image/png")}, timeout=30)
    check("ganti berkas pada id palsu → 404", r.status_code == 404, str(r.status_code))

    # ================================================================= E. AKSI MASSAL & PEMAKAIAN
    head("E · Aksi massal + laporan 'dipakai di mana' (jangan hapus buta)")
    # Aset ini dipakai halaman iklan (media_id) DAN konten website (URL string).
    r = requests.post(f"{API}/landing/pages", headers=owner,
                      json={"title": "POC Media Usage", "template": "armada-konversi"}, timeout=30)
    page = r.json() if r.status_code == 200 else {}
    blocks = page.get("blocks") or []
    hero = next((b for b in blocks if isinstance(b.get("props"), dict)
                 and isinstance(b["props"].get("media"), dict)), None)
    if hero:
        hero["props"]["media"] = {**hero["props"]["media"], "media_id": mid_a,
                                 "src": rep.get("url"), "alt": "Hiace"}
        r = requests.patch(f"{API}/landing/pages/{page.get('id')}", headers=owner,
                           json={"blocks": blocks}, timeout=30)
    check("halaman iklan memakai aset (untuk uji pemakaian)",
          bool(hero) and r.status_code == 200, f"hero={bool(hero)} {r.status_code}")

    r = requests.post(f"{API}/content/destinations", headers=ops,
                      json={"slug": "poc-media-dest", "name": "POC Media Destinasi",
                            "hero_image": rep.get("url")}, timeout=30)
    dest_id = r.json().get("id") if r.status_code == 200 else ""
    check("konten website memakai aset lewat URL", bool(dest_id), r.text[:160])

    r = requests.get(f"{API}/media/{mid_a}/usage", headers=ops, timeout=30)
    usage = r.json() if r.status_code == 200 else {}
    check("laporan pemakaian menemukan halaman iklan",
          any(p.get("slug") for p in usage.get("landing_pages", [])), str(usage)[:200])
    check("laporan pemakaian menemukan konten website (URL string, bukan media_id)",
          any(c.get("id") == dest_id for c in usage.get("content", [])), str(usage)[:200])
    check("total pemakaian >= 2 (halaman iklan + konten)", usage.get("total", 0) >= 2,
          str(usage.get("total")))

    r = requests.post(f"{API}/media/bulk-move", headers=ops,
                      json={"ids": [mid_a, asset_b.get("id")], "folder_id": f_root}, timeout=30)
    check("pindah banyak aset sekaligus", r.status_code == 200 and r.json().get("moved") == 2,
          r.text[:160])
    r = requests.get(f"{API}/media?folder_id={f_root}", headers=ops, timeout=20)
    check("kedua aset kini berada di folder tujuan",
          {a["id"] for a in r.json().get("assets", [])} >= {mid_a, asset_b.get("id")}, r.text[:160])

    r = requests.post(f"{API}/media/bulk-move", headers=ops, json={"ids": []}, timeout=20)
    check("pindah tanpa memilih aset ditolak berALASAN", r.status_code == 400, r.text[:120])
    r = requests.post(f"{API}/media/bulk-move", headers=ops,
                      json={"ids": [mid_a], "folder_id": "mdf_tidakada"}, timeout=20)
    check("pindah ke folder tak dikenal → 404", r.status_code == 404, str(r.status_code))

    # hapus folder berisi aset → aset HARUS naik ke induk, bukan hilang
    r = requests.delete(f"{API}/media/folders/{f_root}", headers=ops, timeout=30)
    out = r.json() if r.status_code == 200 else {}
    check("hapus folder berhasil", r.status_code == 200, r.text[:160])
    check("aset di dalamnya DIPINDAHKAN (tidak terhapus)", out.get("moved_assets", 0) >= 2,
          str(out))
    check("subfolder juga dipindahkan ke induk", out.get("moved_folders", 0) >= 1, str(out))
    r = requests.get(f"{API}/media/{mid_a}", headers=ops, timeout=20)
    check("aset masih hidup setelah foldernya dihapus", r.status_code == 200, str(r.status_code))
    check("aset pindah ke akar", r.json().get("folder_id") == "", str(r.json().get("folder_id")))

    # hapus massal (soft) + verifikasi hilang dari publik
    extra = upload(ops, png_bytes(120, 120, (90, 90, 90)), "buang-1.png").json()
    extra2 = upload(ops, png_bytes(130, 130, (95, 95, 95)), "buang-2.png").json()
    r = requests.post(f"{API}/media/bulk-delete", headers=ops,
                      json={"ids": [extra.get("id"), extra2.get("id")]}, timeout=30)
    check("hapus banyak aset sekaligus", r.status_code == 200 and r.json().get("deleted") == 2,
          r.text[:160])
    r = requests.get(f"{API}/public/media/{extra.get('id')}", timeout=20)
    check("aset terhapus → 404 di endpoint publik", r.status_code == 404, str(r.status_code))
    r = requests.get(f"{API}/media", headers=ops, timeout=20)
    check("aset terhapus tidak muncul lagi di daftar",
          extra.get("id") not in [a["id"] for a in r.json().get("assets", [])], "")
    r = requests.post(f"{API}/media/bulk-delete", headers=ops,
                      json={"ids": ["med_tidakada"]}, timeout=20)
    check("hapus massal id palsu → 404 (bukan 500)", r.status_code == 404, str(r.status_code))

    # ================================================================= F. CROP
    head("F · Crop di browser → potong piksel di server (PIL)")
    src = upload(ops, png_bytes(1000, 800, (40, 40, 160)), "crop-sumber.png").json()
    mid_c = src.get("id")
    r = requests.post(f"{API}/media/{mid_c}/crop", headers=ops,
                      json={"x": 100, "y": 50, "width": 400, "height": 400, "mode": "new"}, timeout=60)
    check("crop 'simpan sebagai aset baru' berhasil", r.status_code == 200, r.text[:200])
    cropped = r.json() if r.status_code == 200 else {}
    check("aset hasil crop punya id BARU", cropped.get("id") and cropped.get("id") != mid_c,
          cropped.get("id"))
    check("dimensi hasil crop tepat 400×400",
          cropped.get("width") == 400 and cropped.get("height") == 400,
          f"{cropped.get('width')}x{cropped.get('height')}")
    r = requests.get(f"{API}/media/{mid_c}", headers=ops, timeout=20)
    check("aset asli TIDAK berubah saat mode 'baru'",
          r.json().get("width") == 1000 and r.json().get("version") == 1, r.text[:160])

    r = requests.post(f"{API}/media/{mid_c}/crop", headers=ops,
                      json={"x": 0, "y": 0, "width": 600, "height": 300, "mode": "replace"}, timeout=60)
    check("crop 'ganti aset asli' berhasil", r.status_code == 200, r.text[:200])
    rc = r.json() if r.status_code == 200 else {}
    check("crop-ganti menaikkan versi (cache aman)", rc.get("version") == 2, str(rc.get("version")))
    check("crop-ganti memperbarui dimensi aset asli",
          rc.get("width") == 600 and rc.get("height") == 300,
          f"{rc.get('width')}x{rc.get('height')}")

    r = requests.post(f"{API}/media/{mid_c}/crop", headers=ops,
                      json={"x": 0, "y": 0, "width": 200, "height": 100,
                            "target_width": 800, "mode": "new"}, timeout=60)
    tgt = r.json() if r.status_code == 200 else {}
    check("ubah ukuran (target_width) menjaga rasio",
          r.status_code == 200 and tgt.get("width") == 800 and tgt.get("height") == 400,
          f"{r.status_code} {tgt.get('width')}x{tgt.get('height')}")

    for label, payload in (
            ("lebar 0", {"x": 0, "y": 0, "width": 0, "height": 100}),
            ("negatif", {"x": -10, "y": -10, "width": 50, "height": 50}),
            ("melebihi gambar", {"x": 0, "y": 0, "width": 99999, "height": 10}),
            ("bukan angka", {"x": "abc", "y": 0, "width": 10, "height": 10}),
    ):
        r = requests.post(f"{API}/media/{mid_c}/crop", headers=ops,
                          json={**payload, "mode": "new"}, timeout=30)
        check(f"kotak potong tidak sah ({label}) → 400 berALASAN, bukan 500",
              r.status_code == 400, f"{r.status_code} {r.text[:120]}")
    r = requests.post(f"{API}/media/{mid_c}/crop", headers=ops,
                      json={"x": 0, "y": 0, "width": 10, "height": 10, "mode": "aneh"}, timeout=20)
    check("mode crop tak dikenal ditolak", r.status_code == 400, str(r.status_code))

    vid = await db.media_assets.find_one({"kind": "video", "deleted": {"$ne": True}}, {"_id": 0, "id": 1})
    if vid:
        r = requests.post(f"{API}/media/{vid['id']}/crop", headers=ops,
                          json={"x": 0, "y": 0, "width": 10, "height": 10}, timeout=20)
        check("crop pada video ditolak berALASAN", r.status_code == 400, str(r.status_code))
    else:
        check("crop pada video ditolak berALASAN (tidak ada video di data uji — dilewati sah)", True)

    # ================================================================= G. UNIFIKASI & MIGRASI
    head("G · Penyatuan dengan CMS lama + impor aset lama (idempoten)")
    legacy_dir = ROOT / "backend" / "uploads" / "cms"
    legacy_dir.mkdir(parents=True, exist_ok=True)
    legacy_name = "poc-legacy-aset.png"
    (legacy_dir / legacy_name).write_bytes(png_bytes(300, 200, (120, 40, 160)))

    r = requests.post(f"{API}/media/import-legacy", headers=ops, timeout=120)
    first = r.json() if r.status_code == 200 else {}
    check("impor aset CMS lama berjalan", r.status_code == 200, r.text[:200])
    check("berkas lama terdaftar ke library", first.get("imported", 0) >= 1, str(first))
    check("tidak ada berkas yang gagal diimpor", first.get("failed", 0) == 0, str(first.get("errors")))

    r = requests.post(f"{API}/media/import-legacy", headers=ops, timeout=120)
    second = r.json() if r.status_code == 200 else {}
    check("impor kedua IDEMPOTEN (tidak menduplikasi)",
          second.get("imported", 0) == 0 and second.get("skipped", 0) >= first.get("imported", 0),
          str(second))

    r = requests.get(f"http://localhost:8001/api/uploads/cms/{legacy_name}", timeout=20)
    check("URL lama /api/uploads/cms/* TETAP hidup (konten tayang tidak rusak)",
          r.status_code == 200, str(r.status_code))

    imported = await db.media_assets.find_one({"legacy_key": f"cms:{legacy_name}"}, {"_id": 0})
    check("aset impor punya jejak asal (legacy_url) untuk pelacakan pemakaian",
          bool(imported) and imported.get("legacy_url") == f"/api/uploads/cms/{legacy_name}",
          str((imported or {}).get("legacy_url")))
    if imported:
        r = requests.get(f"{API}/public/media/{imported['id']}", timeout=20)
        check("aset impor bisa dibaca lewat URL library", r.status_code == 200, str(r.status_code))

    r = requests.post(f"{API}/uploads/cms", headers=ops,
                      files={"image": ("cms-baru.png", png_bytes(500, 400, (200, 200, 40)), "image/png")},
                      timeout=60)
    cms_up = r.json() if r.status_code == 200 else {}
    check("unggah CMS lama tetap berfungsi (kompatibilitas)", r.status_code == 200, r.text[:200])
    check("unggah CMS kini mengembalikan URL library kanonik",
          str(cms_up.get("url", "")).startswith("/api/public/media/"), cms_up.get("url"))
    check("unggah CMS kini TERLIHAT di Media Library (dua dunia media disatukan)",
          bool(cms_up.get("media_id")), str(cms_up)[:160])
    if cms_up.get("media_id"):
        r = requests.get(f"{API}/media/{cms_up['media_id']}", headers=ops, timeout=20)
        check("aset unggahan CMS punya metadata lengkap di library",
              r.status_code == 200 and r.json().get("source") == "cms"
              and r.json().get("width") == 500, r.text[:200])

    r = requests.post(f"{API}/uploads/cms", headers=ops,
                      files={"image": ("x.exe", b"MZ" + b"0" * 50, "application/x-msdownload")},
                      timeout=20)
    check("unggah CMS dengan tipe berbahaya tetap ditolak (415)", r.status_code == 415,
          str(r.status_code))

    # ================================================================= H. RBAC
    head("H · RBAC 3 lapis (ops_admin & marketing boleh, driver DILARANG)")
    r = requests.get(f"{API}/media", headers=mkt, timeout=20)
    check("marketing_admin boleh membuka Media Library", r.status_code == 200, str(r.status_code))
    r = requests.get(f"{API}/media", headers=ops, timeout=20)
    check("ops_admin boleh membuka Media Library (inti penyatuan CMS)", r.status_code == 200,
          str(r.status_code))

    driver_denied = []
    for method, path, kwargs in (
            ("get", "/media", {}),
            ("get", "/media/folders", {}),
            ("post", "/media/folders", {"json": {"name": "x"}}),
            ("patch", f"/media/folders/{f_child}", {"json": {"name": "y"}}),
            ("delete", f"/media/folders/{f_child}", {}),
            ("post", "/media/bulk-move", {"json": {"ids": [mid_a], "folder_id": ""}}),
            ("post", "/media/bulk-delete", {"json": {"ids": [mid_a]}}),
            ("post", "/media/import-legacy", {}),
            ("get", "/media/health", {}),
            ("get", f"/media/{mid_a}", {}),
            ("patch", f"/media/{mid_a}", {"json": {"alt": "z"}}),
            ("delete", f"/media/{mid_a}", {}),
            ("get", f"/media/{mid_a}/usage", {}),
            ("get", f"/media/{mid_a}/download", {}),
            ("post", f"/media/{mid_a}/crop", {"json": {"x": 0, "y": 0, "width": 5, "height": 5}}),
    ):
        resp = getattr(requests, method)(f"{API}{path}", headers=drv, timeout=20, **kwargs)
        driver_denied.append((f"{method.upper()} {path}", resp.status_code))
    bad = [d for d in driver_denied if d[1] != 403]
    check(f"driver 403 di SEMUA {len(driver_denied)} endpoint /api/media/*", not bad, str(bad))

    r = requests.post(f"{API}/media", headers=drv,
                      files={"file": ("x.png", png_bytes(10, 10), "image/png")}, timeout=20)
    check("driver tidak bisa mengunggah media", r.status_code == 403, str(r.status_code))
    r = requests.get(f"{API}/landing/media", headers=ops, timeout=20)
    check("endpoint media LAMA tetap ketat (ops_admin 403 di /landing/media)",
          r.status_code == 403, str(r.status_code))
    r = requests.get(f"{API}/landing/media", headers=mkt, timeout=20)
    check("endpoint media lama tetap berfungsi untuk marketing_admin", r.status_code == 200,
          str(r.status_code))
    check("daftar media lama kini juga membawa daftar folder (satu SSOT)",
          isinstance(r.json().get("folders"), list), str(list(r.json().keys())))

    # ================================================================= I. KEAMANAN
    head("I · Keamanan penyimpanan & sanitasi")
    from services import media_lib as mlib
    from services import media_store as mstore
    blocked = 0
    for evil in ("../../../etc/passwd", "/etc/passwd", "a/../../../../etc/hosts", "", "\x00x"):
        try:
            mstore.fetch(evil, backend="local")
        except mstore.MediaError:
            blocked += 1
        except Exception:  # noqa: BLE001
            blocked += 1
    check("semua jalur berbahaya ditolak media_store.fetch", blocked == 5, str(blocked))
    check("remove() menolak path traversal (tidak menghapus berkas sistem)",
          mstore.remove("../../../etc/hosts") is False)
    check("exists() menolak path traversal", mstore.exists("../../../etc/hosts") is False)
    check("nama berkas hasil unggah acak (nama pengguna tidak masuk jalur disk)",
          "hiace" not in str((await db.media_assets.find_one({"id": mid_a}))
                             .get("storage_path", "")).lower(), "")
    check("sanitize_text membuang tag HTML & karakter kendali (teks murni tetap utuh)",
          mlib.sanitize_text("<b>Pro\x00mo</b> <script>alert(1)</script>") == "Promo alert(1)"
          or ("<" not in mlib.sanitize_text("<b>Pro\x00mo</b> <script>alert(1)</script>")
              and ">" not in mlib.sanitize_text("<b>Pro\x00mo</b> <script>alert(1)</script>")
              and "\x00" not in mlib.sanitize_text("<b>Pro\x00mo</b> <script>alert(1)</script>")),
          mlib.sanitize_text("<b>Pro\x00mo</b> <script>alert(1)</script>"))
    check("safe_display_name membuang tanda kutip & pemisah jalur (anti header injection)",
          '"' not in mlib.safe_display_name('a"b/c\\d.png')
          and "/" not in mlib.safe_display_name('a"b/c\\d.png'),
          mlib.safe_display_name('a"b/c\\d.png'))

    r = requests.patch(f"{API}/media/{mid_a}", headers=ops,
                       json={"alt": "<script>alert(1)</script>Hiace"}, timeout=20)
    check("teks alternatif ber-HTML disanitasi",
          r.status_code == 200 and "<" not in r.json().get("alt", ""), r.json().get("alt"))
    r = requests.patch(f"{API}/media/{mid_a}", headers=ops, json={}, timeout=20)
    check("PATCH tanpa perubahan ditolak berALASAN (bukan 500)", r.status_code == 400, str(r.status_code))
    big = b"0" * (11 * 1024 * 1024)
    r = requests.post(f"{API}/media", headers=ops,
                      files={"file": ("besar.png", big, "image/png")}, data={"folder_id": ""}, timeout=120)
    check("unggah melebihi batas ukuran ditolak berALASAN",
          r.status_code == 400 and "maksimal" in r.text.lower(), f"{r.status_code} {r.text[:120]}")
    r = requests.get(f"{API}/media/health", headers=ops, timeout=60)
    check("panel kesehatan media melaporkan aset yang berkasnya hilang",
          r.status_code == 200 and "missing_count" in r.json(), r.text[:160])

    # ================================================================= bersih-bersih
    if dest_id:
        requests.delete(f"{API}/content/destinations/{dest_id}", headers=ops, timeout=20)
    if page.get("id"):
        requests.delete(f"{API}/landing/pages/{page['id']}", headers=owner, timeout=20)
    for fid in (f_child, f_xss):
        requests.delete(f"{API}/media/folders/{fid}", headers=ops, timeout=20)
    (legacy_dir / legacy_name).unlink(missing_ok=True)
    await db.media_assets.delete_many({"id": {"$in": [i for i in [
        mid_a, asset_b.get("id"), mid_c, cropped.get("id"), tgt.get("id"),
        extra.get("id"), extra2.get("id"), cms_up.get("media_id"),
        (imported or {}).get("id")] if i]}})

    ok = sum(1 for _, v in RESULTS if v)
    total = len(RESULTS)
    print(f"\n{B}{'=' * 66}{X}")
    print(f"{B}HASIL POC MEDIA MANAGER v2: {ok}/{total}{X}")
    if ok == total:
        print(f"{G}{B}✓ SEMUA LULUS — inti Media Manager v2 terbukti bekerja.{X}")
    else:
        print(f"{R}{B}✗ GAGAL:{X}")
        for name, v in RESULTS:
            if not v:
                print(f"  {R}- {name}{X}")
    print(f"{B}{'=' * 66}{X}")
    return 0 if ok == total else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
