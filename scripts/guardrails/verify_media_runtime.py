#!/usr/bin/env python3
"""INV-MEDIA-04 — PERILAKU Media Library diverifikasi RUNTIME (bukan hanya konfigurasi).

Kenapa perlu gate runtime padahal INV-MEDIA-03 (statik) sudah hijau?
--------------------------------------------------------------------
Penjaga statik membuktikan KODE-nya benar bentuknya: RBAC terpasang, `version` dinaikkan, ETag
dikirim, aturan folder ada. Itu tidak sama dengan PERILAKU yang benar. Kelas kegagalan yang lolos
dari analisis statik dan sudah pernah nyata di repo ini:

  * urutan route menelan literal (`/media/{media_id}` mendahului `/media/health` → "health"
    diperlakukan sebagai id aset). Statik tak bisa melihat urutan pencocokan Starlette.
  * `Depends` yang benar tapi matriks section-nya salah → driver tetap dapat HTTP 200.
  * input adversarial (id raksasa, JSON aneh, folder_id NUL) → **HTTP 500** walau semua pagar
    "terlihat ada" di kode.
  * impor legacy yang idempoten di kode tapi tidak di database (indeks unik tak pernah dibuat pada
    pod baru) → dua klik = aset ganda.
  * hapus folder yang "seharusnya" menaikkan aset, tetapi endpoint memanggil fungsi lain.

Yang diverifikasi (login `owner`/`ops`/`driver` demo):
  A. Pintu modul  : driver → 403 di SEMUA rute `/api/media/*` yang terdaftar (dibaca dari OpenAPI,
                    jadi rute BARU otomatis ikut diuji — tidak perlu diingat manusia).
  B. Anti-5xx     : 12 permintaan adversarial ke jalur media → wajib 2xx/4xx, dilarang 5xx.
  C. Folder       : hapus folder berisi aset → aset NAIK ke induk & tetap terbaca (tidak musnah).
  D. Cache        : setelah "Ganti berkas" → versi naik, ETag berubah, `If-None-Match` → 304,
                    URL tanpa versi wajib `must-revalidate` (foto baru langsung terlihat).
  E. Legacy       : `import-legacy` dijalankan dua kali → tidak ada duplikasi (idempoten NYATA).
  F. Kebersihan   : aset uji dihapus kembali; `public_doc` tidak membocorkan `storage_path`.

Aset yang dibuat penjaga ini diberi prefiks `guard-media-` dan dibersihkan di akhir (bahkan bila
ada kegagalan), supaya gate boleh dijalankan berulang tanpa menyampahi Media Library nyata.
"""
import io
import json
import os
import struct
import sys
import urllib.error
import urllib.request
import uuid
import zlib

sys.path.insert(0, os.path.dirname(__file__))
from _common import BACKEND, G, Guard, R, X, Y, purge_guard_artifacts  # noqa: E402

BASE = os.environ.get("GUARD_BASE_URL", "http://127.0.0.1:8001") + "/api"
TAG = f"guard-media-{uuid.uuid4().hex[:8]}"


# --------------------------------------------------------------------------- HTTP tanpa dependensi
def req(method, path, token=None, body=None, timeout=30, headers=None, raw=False):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method)
    if body is not None:
        r.add_header("Content-Type", "application/json")
    if token:
        r.add_header("Authorization", f"Bearer {token}")
    for k, v in (headers or {}).items():
        r.add_header(k, v)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            payload = resp.read()
            return resp.status, (payload if raw else payload.decode("utf-8", "replace")), _ci(resp.headers)
    except urllib.error.HTTPError as e:
        payload = e.read()
        return e.code, (payload if raw else payload.decode("utf-8", "replace")), _ci(e.headers or {})
    except Exception as e:  # noqa: BLE001
        return -1, str(e), _ci({})


class _ci(dict):
    """Header HTTP TIDAK case-sensitive. uvicorn mengirim `etag`/`cache-control` huruf kecil.

    Penjaga versi pertama memakai `dict(resp.headers)` lalu mencari `"ETag"` → selalu None →
    melaporkan "ETag hilang" pada aplikasi yang sebenarnya SEHAT. Temuan palsu seperti ini
    sama merusaknya dengan lubang: sesi berikutnya belajar mengabaikan gate.
    """

    def __init__(self, src):
        super().__init__({str(k).lower(): v for k, v in dict(src).items()})

    def get(self, key, default=None):  # noqa: D102
        return super().get(str(key).lower(), default)


def upload(token, blob, filename, content_type="image/png", folder_id=None):
    """Unggah multipart tanpa `requests` (guardrail harus jalan dengan pustaka standar saja)."""
    boundary = "----guard" + uuid.uuid4().hex
    buf = io.BytesIO()

    def part(header, payload):
        buf.write(f"--{boundary}\r\n{header}\r\n\r\n".encode())
        buf.write(payload)
        buf.write(b"\r\n")

    part(f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
         f"Content-Type: {content_type}", blob)
    if folder_id is not None:
        part('Content-Disposition: form-data; name="folder_id"', folder_id.encode())
    buf.write(f"--{boundary}--\r\n".encode())
    r = urllib.request.Request(BASE + "/media", data=buf.getvalue(), method="POST")
    r.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    r.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(r, timeout=90) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        return e.code, {"detail": e.read().decode("utf-8", "replace")[:200]}
    except Exception as e:  # noqa: BLE001
        return -1, {"detail": str(e)}


def png_bytes(w, h, rgb):
    """PNG valid tanpa Pillow (penjaga tidak boleh bergantung pustaka opsional)."""
    def chunk(tag, payload):
        return (struct.pack(">I", len(payload)) + tag + payload
                + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF))
    raw = b"".join(b"\x00" + bytes(rgb) * w for _ in range(h))
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


def login(email):
    st, txt, _ = req("POST", "/auth/login", body={"email": email, "password": "demo12345"})
    if st != 200:
        return None
    try:
        return json.loads(txt).get("token")
    except Exception:  # noqa: BLE001
        return None


def as_json(txt, default=None):
    try:
        return json.loads(txt)
    except Exception:  # noqa: BLE001
        return default


def media_paths_from_openapi():
    """Ambil semua rute `/api/media*` dari skema OpenAPI yang HIDUP.

    Sengaja dibaca dari aplikasi yang berjalan, bukan dari daftar tetap di skrip: rute media BARU
    otomatis ikut diuji RBAC-nya. Daftar manual pasti tertinggal — dan rute yang tertinggal itulah
    yang bocor. (Skema disajikan di root `/openapi.json`, di LUAR prefiks `/api`.)
    """
    url = BASE[: -len("/api")] + "/openapi.json"
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            spec = json.loads(resp.read().decode("utf-8", "replace"))
    except Exception:  # noqa: BLE001
        return []
    out = []
    for path, ops in (spec.get("paths") or {}).items():
        if not path.startswith("/api/media"):
            continue
        for method in ops:
            if method.lower() in ("get", "post", "patch", "put", "delete"):
                out.append((method.upper(), path[len("/api"):]))
    return sorted(set(out))


def main() -> int:  # noqa: C901
    g = Guard("INV-MEDIA-04", "Perilaku Media Library (RBAC, anti-5xx, folder, cache, legacy) runtime")
    own = login("owner@demo.local")
    ops = login("ops@demo.local")
    drv = login("driver@demo.local")
    if not (own and ops and drv):
        g.add("Tidak bisa login akun demo (owner/ops/driver) — jalankan `python scripts/seed_data.py` "
              "lalu ulangi. SKIP dilarang: gate runtime yang di-skip = hijau-palsu.")
        return g.finish()

    created, folders = [], []
    try:
        # ---------------------------------------------------------------- A. pintu modul (driver)
        routes = media_paths_from_openapi()
        g.bump()
        if len(routes) < 10:
            g.add(f"Hanya {len(routes)} rute /api/media* terbaca dari OpenAPI — router media tidak "
                  f"terpasang penuh di server yang berjalan (fitur mati walau kodenya ada).")
        probe = {"GET": None, "POST": {}, "PATCH": {}, "PUT": {}, "DELETE": None}
        leaks = []
        for method, path in routes:
            concrete = path.replace("{media_id}", "med_guardprobe").replace("{folder_id}", "mdf_guardprobe")
            g.bump()
            st, _txt, _h = req(method, concrete, token=drv, body=probe.get(method))
            if st != 403:
                leaks.append(f"{method} {path} → HTTP {st}")
        if leaks:
            g.add(f"BOCOR RBAC: peran driver TIDAK ditolak 403 di {len(leaks)} rute media "
                  f"({'; '.join(leaks[:6])}). Semua rute /api/media/* wajib di balik "
                  f"require_section(\"media\") = owner/ops_admin/marketing_admin.")
        else:
            print(f"    [{G}ok{X}] driver 403 di SEMUA {len(routes)} rute /api/media* (dibaca dari OpenAPI)")

        g.bump()
        st, _txt, _h = req("GET", "/media", token=ops)
        if st != 200:
            g.add(f"REGRESI: ops_admin mendapat HTTP {st} pada GET /media — pemegang CMS WAJIB bisa "
                  f"memakai Media Library (inti penyatuan 'dua dunia media').")

        # ---------------------------------------------------------------- B. anti-5xx
        st, asset = upload(ops, png_bytes(240, 160, (30, 120, 200)), f"{TAG}-a.png")
        g.bump()
        if st != 200 or not asset.get("id"):
            g.add(f"Unggah aset uji GAGAL (HTTP {st}: {str(asset)[:160]}) — jalur unggah Media "
                  f"Library rusak; sisa pemeriksaan runtime tak bisa dipercaya.")
            return g.finish()
        mid = asset["id"]
        created.append(mid)
        g.bump()
        if "storage_path" in asset:
            g.add("Respons unggah membocorkan `storage_path` (jalur penyimpanan internal) ke klien.")

        BIG = "A" * 5000
        adversarial = [
            ("id aset raksasa", "GET", f"/media/{BIG}", None),
            ("id aset unicode/kendali", "GET", "/media/%09%0amed%20x%F0%9F%98%80", None),
            ("folder_id NUL saat pindah", "POST", "/media/bulk-move",
             {"ids": [mid], "folder_id": "a\x00b"}),
            ("ids bukan list", "POST", "/media/bulk-move", {"ids": "bukan-list", "folder_id": ""}),
            ("ids kosong", "POST", "/media/bulk-delete", {"ids": []}),
            ("ids berisi objek aneh", "POST", "/media/bulk-delete", {"ids": [{"a": 1}, None, 5]}),
            ("crop kotak negatif", "POST", f"/media/{mid}/crop",
             {"x": -10, "y": -10, "width": -5, "height": 0, "mode": "new"}),
            ("crop kotak non-numerik", "POST", f"/media/{mid}/crop",
             {"x": "kiri", "y": None, "width": "lebar", "height": [], "mode": "new"}),
            ("crop melampaui gambar", "POST", f"/media/{mid}/crop",
             {"x": 5, "y": 5, "width": 999999, "height": 999999, "mode": "replace"}),
            ("crop target raksasa (OOM)", "POST", f"/media/{mid}/crop",
             {"x": 0, "y": 0, "width": 100, "height": 100, "mode": "new",
              "target_width": 90000, "target_height": 90000}),
            ("patch alt tipe salah", "PATCH", f"/media/{mid}", {"alt": {"x": [1, 2]}, "folder_id": 5}),
            ("folder induk tak dikenal", "POST", "/media/folders",
             {"name": f"{TAG}-x", "parent_id": "mdf_tidakada"}),
            ("nama folder kosong/HTML", "POST", "/media/folders", {"name": "<script>alert(1)</script>"}),
            ("halaman daftar absurd", "GET", "/media?limit=-5&offset=-99&kind=%00", None),
        ]
        for label, method, path, body in adversarial:
            g.bump()
            st, txt, _h = req(method, path, token=ops, body=body)
            if st >= 500 or st == -1:
                g.add(f"5XX: {label} → HTTP {st} pada {method} {path}. Input buruk WAJIB dijawab "
                      f"4xx berALASAN, bukan crash server. Resp: {str(txt)[:140]}")
            else:
                new_id = as_json(txt, {}) if isinstance(txt, str) else {}
                if isinstance(new_id, dict) and str(new_id.get("id", "")).startswith("mdf"):
                    folders.append(new_id["id"])
        print(f"    [{G}ok{X}] {len(adversarial)} permintaan adversarial media: tidak ada 5xx")

        # ---------------------------------------------------------------- C. folder tidak memusnahkan aset
        st, parent, _h = req("POST", "/media/folders", token=ops, body={"name": f"{TAG}-induk"})
        st2, child, _h = req("POST", "/media/folders", token=ops,
                             body={"name": f"{TAG}-anak",
                                   "parent_id": (as_json(parent, {}) or {}).get("id", "")})
        pid = (as_json(parent, {}) or {}).get("id", "")
        cid = (as_json(child, {}) or {}).get("id", "")
        folders += [x for x in (pid, cid) if x]
        g.bump()
        if st != 200 or st2 != 200 or not (pid and cid):
            g.add(f"Membuat folder GAGAL (HTTP {st}/{st2}) — navigasi folder Media Library tidak "
                  f"berfungsi di server yang berjalan.")
        else:
            req("POST", "/media/bulk-move", token=ops, body={"ids": [mid], "folder_id": cid})
            st, txt, _h = req("DELETE", f"/media/folders/{cid}", token=ops)
            out = as_json(txt, {}) or {}
            g.bump()
            if st != 200:
                g.add(f"Hapus folder → HTTP {st} (seharusnya 200). Resp: {str(txt)[:140]}")
            g.bump()
            if int(out.get("moved_assets") or 0) < 1:
                g.add(f"Hapus folder tidak melaporkan aset yang dipindahkan (moved_assets="
                      f"{out.get('moved_assets')}) → UI tak bisa menjelaskan apa yang terjadi pada isinya.")
            st, txt, _h = req("GET", f"/media/{mid}", token=ops)
            doc = as_json(txt, {}) or {}
            g.bump()
            if st != 200:
                g.add(f"ASET MUSNAH: setelah foldernya dihapus, GET /media/{mid} → HTTP {st}. Folder "
                      f"hanya LABEL; menghapusnya TIDAK BOLEH menghapus aset (kerusakan tak bisa dibatalkan).")
            g.bump()
            if doc.get("folder_id") != pid:
                g.add(f"Aset tidak dinaikkan ke folder induk (folder_id={doc.get('folder_id')!r}, "
                      f"harusnya {pid!r}) → aset jadi tak terjangkau lewat navigasi folder.")
            g.bump()
            st, txt, _h = req("PATCH", f"/media/folders/{pid}", token=ops, body={"parent_id": cid})
            if st < 400:
                g.add(f"SIKLUS FOLDER: memindahkan induk ke dalam anaknya diterima (HTTP {st}) → "
                      f"folder + seluruh isinya hilang dari daftar padahal datanya masih ada.")
            folders = [f for f in folders if f != cid]

        # ---------------------------------------------------------------- D. cache sadar-versi
        st, txt, hdr = req("GET", f"/public/media/{mid}", raw=True)
        etag1 = (hdr.get("ETag") or "").strip()
        g.bump()
        if st != 200:
            g.add(f"Aset tidak bisa dibaca publik (HTTP {st}) → gambar 404 di halaman yang tayang.")
        g.bump()
        if not etag1:
            g.add("Respons publik TANPA header ETag → browser tak punya validator, foto pengganti "
                  "tidak akan terlihat sampai cache kedaluwarsa.")
        g.bump()
        if "must-revalidate" not in (hdr.get("Cache-Control") or ""):
            g.add(f"URL tanpa versi memakai Cache-Control={hdr.get('Cache-Control')!r} tanpa "
                  f"must-revalidate → foto lama membeku di browser setelah 'Ganti berkas'.")
        g.bump()
        st, _txt, _h = req("GET", f"/public/media/{mid}", headers={"If-None-Match": etag1}, raw=True)
        if st != 304:
            g.add(f"Permintaan bersyarat If-None-Match → HTTP {st} (bukan 304) → revalidasi jadi "
                  f"transfer penuh; grid Media Library berat tanpa alasan.")

        boundary = "----guard" + uuid.uuid4().hex
        new_blob = png_bytes(260, 180, (200, 40, 60))
        body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; "
                f"filename=\"{TAG}-b.png\"\r\nContent-Type: image/png\r\n\r\n").encode() \
            + new_blob + f"\r\n--{boundary}--\r\n".encode()
        rq = urllib.request.Request(BASE + f"/media/{mid}/replace", data=body, method="POST")
        rq.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
        rq.add_header("Authorization", f"Bearer {ops}")
        try:
            with urllib.request.urlopen(rq, timeout=90) as resp:
                rep = json.loads(resp.read().decode("utf-8", "replace"))
                rep_st = resp.status
        except urllib.error.HTTPError as e:  # noqa: PERF203
            rep, rep_st = {"detail": e.read().decode("utf-8", "replace")[:160]}, e.code
        g.bump()
        if rep_st != 200:
            g.add(f"Ganti berkas → HTTP {rep_st} ({str(rep)[:140]}) — fitur inti Media Manager v2 mati.")
        else:
            g.bump()
            if rep.get("id") != mid:
                g.add(f"Ganti berkas MENGUBAH id aset ({rep.get('id')}) → semua halaman/konten yang "
                      f"memakai aset ini langsung kehilangan gambar.")
            g.bump()
            if int(rep.get("version") or 1) < 2:
                g.add(f"Ganti berkas tidak menaikkan versi (version={rep.get('version')}) → cache "
                      f"browser tak pernah dibatalkan; pengguna tetap melihat foto lama.")
            g.bump()
            st, _txt, hdr2 = req("GET", f"/public/media/{mid}", raw=True)
            if (hdr2.get("ETag") or "").strip() == etag1:
                g.add("ETag TIDAK berubah setelah berkas diganti → browser menganggap foto lama masih "
                      "sah (304) dan penggantian tidak pernah terlihat.")
            g.bump()
            ver = int(rep.get("version") or 2)
            st, _txt, hdr3 = req("GET", f"/public/media/{mid}?v={ver}", raw=True)
            if "immutable" not in (hdr3.get("Cache-Control") or ""):
                g.add(f"URL berversi terkini tidak boleh di-cache lama "
                      f"(Cache-Control={hdr3.get('Cache-Control')!r}) → setiap tampilan menarik ulang "
                      f"berkas penuh, halaman iklan jadi lambat & mahal.")

        # ---------------------------------------------------------------- E. legacy idempoten
        # Dibuat berkas legacy SUNGGUHAN dulu. Tanpa ini cek jadi hampa: bila tak ada berkas yang
        # perlu diimpor, "jalan kedua mengimpor 0" selalu benar tanpa membuktikan apa pun.
        legacy_dir = BACKEND / "uploads" / "cms"
        legacy_file = legacy_dir / f"{TAG}-legacy.png"
        try:
            legacy_dir.mkdir(parents=True, exist_ok=True)
            legacy_file.write_bytes(png_bytes(120, 90, (60, 160, 60)))
        except Exception as exc:  # noqa: BLE001
            g.bump()
            g.add(f"tidak bisa menyiapkan berkas legacy uji ({exc}) — idempotensi impor tak teruji.")
        st1, txt1, _h = req("POST", "/media/import-legacy", token=ops, timeout=180)
        st2, txt2, _h = req("POST", "/media/import-legacy", token=ops, timeout=180)
        one, two = as_json(txt1, {}) or {}, as_json(txt2, {}) or {}
        g.bump()
        if st1 != 200 or st2 != 200:
            g.add(f"Impor aset CMS lama → HTTP {st1}/{st2} (seharusnya 200 dua kali; operasi ini "
                  f"WAJIB aman dijalankan berulang).")
        else:
            g.bump()
            if int(one.get("imported") or 0) < 1:
                g.add(f"Berkas legacy baru TIDAK terimpor (imported={one.get('imported')}, "
                      f"errors={str(one.get('errors'))[:120]}) → aset CMS lama tetap 'tak terlihat' "
                      f"di Media Library (dua dunia media).")
            g.bump()
            if int(two.get("imported") or 0) != 0:
                g.add(f"Impor legacy TIDAK idempoten: jalan kedua masih mengimpor "
                      f"{two.get('imported')} berkas → aset ganda untuk satu berkas (indeks unik "
                      f"`legacy_key` tidak aktif di database ini).")
            g.bump()
            if int(two.get("failed") or 0) != 0:
                g.add(f"Impor legacy melaporkan {two.get('failed')} kegagalan: "
                      f"{str(two.get('errors'))[:160]}")
            g.bump()
            lst, ltxt, _h = req("GET", f"/media?q={TAG}-legacy", token=ops)
            rows = (as_json(ltxt, {}) or {}).get("assets") or []
            if len(rows) != 1:
                g.add(f"Pencarian aset legacy hasil impor mengembalikan {len(rows)} baris (harus 1) "
                      f"→ tanda duplikasi atau aset tak terdaftar.")
            for row in rows:
                created.append(row.get("id"))
                g.bump()
                if not str(row.get("legacy_url") or "").startswith("/api/uploads/cms/"):
                    g.add("Aset hasil impor tidak menyimpan `legacy_url` → pemakaian di konten yang "
                          "sudah tayang tak bisa dilacak sebelum aset dihapus.")
            g.bump()
            lst, _ltxt, _h = req("GET", f"/uploads/cms/{legacy_file.name}", raw=True)
            if lst != 200:
                g.add(f"URL lama /api/uploads/cms/{legacy_file.name} → HTTP {lst}; URL yang sudah "
                      f"tersimpan di konten tayang WAJIB tetap hidup setelah impor.")
            print(f"    [{G}ok{X}] import-legacy idempoten (jalan-1 imported={one.get('imported')}, "
                  f"jalan-2 imported={two.get('imported')}, skipped={two.get('skipped')})")

        # ---------------------------------------------------------------- F. peringatan pemakaian
        g.bump()
        st, txt, _h = req("GET", f"/media/{mid}/usage", token=ops)
        info = as_json(txt, {}) or {}
        if st != 200 or "total" not in info:
            g.add(f"GET /media/{{id}}/usage → HTTP {st} tanpa ringkasan pemakaian → dialog hapus tak "
                  f"bisa memperingatkan bahwa aset sedang dipakai halaman iklan/konten.")
        g.bump()
        st, txt, _h = req("POST", "/media/bulk-delete", token=ops, body={"ids": [mid]})
        out = as_json(txt, {}) or {}
        if st != 200 or "used_by" not in out:
            g.add(f"Hapus massal tidak melaporkan `used_by` (HTTP {st}) → pengguna menghapus aset "
                  f"yang sedang tayang tanpa peringatan.")
        else:
            created.remove(mid)
        g.bump()
        st, _txt, _h = req("GET", f"/public/media/{mid}", raw=True)
        if st != 404:
            g.add(f"Aset yang sudah dihapus MASIH terbaca publik (HTTP {st}) → penghapusan tidak "
                  f"berefek pada halaman yang tayang.")
    finally:
        for mid in created:
            if mid:
                req("POST", "/media/bulk-delete", token=ops, body={"ids": [mid]})
        for fid in folders:
            req("DELETE", f"/media/folders/{fid}", token=ops)
        try:  # berkas legacy uji tidak boleh menumpuk di uploads/cms tiap kali gate jalan
            f = BACKEND / "uploads" / "cms" / f"{TAG}-legacy.png"
            if f.exists():
                f.unlink()
        except Exception:  # noqa: BLE001
            print(f"    {Y}catatan: berkas legacy uji {TAG}-legacy.png gagal dibersihkan.{X}")
        # INV-CLEAN-01 — API media hanya melakukan SOFT delete (`deleted: true`), jadi dokumen
        # `guard-media-*` tetap ada di koleksi `media_assets` (dan bisa muncul di pemulih/
        # laporan Media Library). Bersihkan sampai habis.
        purge_guard_artifacts(verbose=True)

    if not g.violations:
        print(f"    {G}RBAC + anti-5xx + folder + cache + legacy: perilaku sesuai invariant.{X}")
    else:
        print(f"    {R}Ada pelanggaran perilaku media — lihat daftar di bawah.{X}")
        print(f"    {Y}Catatan: aset/folder uji berprefiks {TAG} sudah dibersihkan.{X}")
    return g.finish()


if __name__ == "__main__":
    sys.exit(main())
