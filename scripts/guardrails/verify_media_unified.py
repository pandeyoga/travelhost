#!/usr/bin/env python3
"""INV-MEDIA-03 — Media Library TETAP SATU (anti kembalinya "dua dunia media" & aset hilang).

Kelas bug yang ditutup penjaga ini (semuanya NYATA, ditemukan saat menyatukan media di ronde ini):

  1. **Dua dunia media.** `POST /api/uploads/cms` dulu menulis berkas sendiri ke `uploads/cms/`
     TANPA mencatat apa pun di Mongo. Akibatnya aset website tidak bisa dicari, tidak punya teks
     alternatif, tidak bisa dipakai ulang, dan tidak pernah muncul di Media Library — sementara
     halaman iklan punya library lengkap. Satu bisnis, dua cara kerja, dan ratusan berkas "tak
     terlihat" di disk. Kalau endpoint baru (atau yang lama) kembali menulis berkas langsung,
     pemisahan itu kembali tanpa ada yang sadar.
  2. **Pemilih media liar di frontend.** Selama masih ada komponen yang membuat kotak unggah
     sendiri (POST langsung ke endpoint unggah), penyatuan picker akan terkikis satu komponen per
     ronde sampai kembali seperti semula.
  3. **Hapus folder = kehilangan aset.** Folder di sistem ini hanya LABEL. Bila suatu saat
     `delete_folder` diubah menjadi ikut menghapus aset, satu klik bisa memusnahkan ratusan foto
     yang sedang tayang — kerusakan yang tak bisa dibatalkan.
  4. **Folder jadi pulau terputus (siklus).** Memindahkan folder ke dalam anak/cucunya sendiri
     membuat folder + seluruh isinya hilang dari daftar padahal datanya masih ada.
  5. **Cache membeku setelah "Ganti berkas".** Endpoint publik dulu selalu `max-age=86400`; foto
     yang sudah diganti tetap tampil versi lama sampai sehari penuh ("sudah saya ganti kok tidak
     berubah?"). Karena itu versi + ETag/revalidasi WAJIB dipertahankan.
  6. **Kebocoran jalur penyimpanan internal** ke klien (memudahkan penebakan/penyalahgunaan).

Metode: analisis STATIK + EKSEKUSI NYATA fungsi `services/media_lib.py` memakai stub database
in-memory (tanpa Mongo, tanpa jaringan) — jadi aturan folder benar-benar DIUJI perilakunya,
bukan sekadar dicari kata kuncinya di kode.
"""
import ast
import asyncio
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from _common import BACKEND, FRONTEND, Guard  # noqa: E402

sys.path.insert(0, str(BACKEND))

CONTENT = BACKEND / "routers" / "content.py"
MEDIA_ROUTER = BACKEND / "routers" / "media.py"
PUBLIC = BACKEND / "routers" / "public.py"
LIB = BACKEND / "services" / "media_lib.py"
STORE = BACKEND / "services" / "media_store.py"

# Router yang MEMANG menulis berkas sendiri untuk domain lain (bukti pengiriman/POD sopir):
# berkas itu bukan aset publikasi, tidak masuk Media Library, dan aturannya berbeda.
# Daftar ini sengaja EKSPLISIT supaya penambahan baru harus disengaja & dijelaskan.
WRITE_ALLOWLIST = {"dispatch.py", "driver.py"}

# Komponen frontend yang BOLEH memuat kotak unggah sendiri = inti Media Library itu sendiri.
FE_UPLOAD_ALLOWLIST = {"components/media/MediaBrowser.jsx", "components/media/mediaApi.js",
                       "components/media/MediaDetailPanel.jsx"}

SHARED_PICKER = "components/media/MediaPickerDialog"


def read(path):
    return path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""


def code_only(text: str) -> str:
    """Buang docstring & komentar Python. Penjaga TIDAK boleh bisa dipuaskan oleh PROSA.

    Lubang NYATA yang ditemukan self-test mutasi (M07): cek `"ETag" not in public_media` selalu
    lolos karena kata "ETag" ada di DOCSTRING fungsi — header aslinya sudah boleh diganti nama
    (`X-Media-Tag`) tanpa gate menyadarinya. Penjaga yang puas dengan komentar = tidak ada penjaga,
    dan justru terasa paling aman karena selalu hijau.
    """
    no_doc = re.sub(r'("""|\'\'\')(?:.|\n)*?\1', '""', text)
    return re.sub(r"(?m)#.*$", "", no_doc)


def jsx_code_only(text: str) -> str:
    """Buang baris komentar JS/JSX (`//`, `/* ... */`, `*`) TANPA merusak string.

    Sengaja per-baris (bukan regex `//.*`): URL seperti `https://…` di dalam string akan terpotong
    dan menghasilkan temuan palsu. Tujuannya menutup trik "import di-komentari tapi gate tetap
    hijau" — persis kelas kegagalan yang sama dengan lubang docstring di atas.
    """
    out = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("//") or s.startswith("/*") or s.startswith("*"):
            continue
        out.append(line)
    return "\n".join(out)


def fn_body(text: str, name: str) -> str:
    """Ambil badan satu fungsi async berdasarkan indentasi (bukan regex serakah)."""
    marker = f"async def {name}("
    start = text.find(marker)
    if start < 0:
        return ""
    lines = text[start:].splitlines()
    out = [lines[0]]
    for line in lines[1:]:
        if line and not line[0].isspace() and not line.startswith(")"):
            break
        out.append(line)
    return "\n".join(out)


def router_endpoints(text: str, prefix: str) -> list:
    """Ambil (metode, path, nama, node AST) tiap endpoint `@router.<m>("<prefix>...")`.

    Dipakai AST, BUKAN regex. Alasannya konkret: regex dekorator satu-baris berhenti mencocokkan
    begitu seseorang menulis `@router.get(\n    "/media/x",\n    response_model=dict,\n)` atau
    menambah `dependencies=[Depends(...)]`. Rute itu lalu TIDAK ikut terpindai — penjaga tetap
    HIJAU sambil rute barunya tanpa RBAC. Itu hijau-palsu, kelas kegagalan yang paling berbahaya
    untuk penjaga: diam, meyakinkan, dan salah.
    """
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
            continue
        for dec in node.decorator_list:
            if not isinstance(dec, ast.Call):
                continue
            fn = dec.func
            if not (isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name)
                    and fn.value.id == "router" and fn.attr in ("get", "post", "patch", "put", "delete")):
                continue
            path = ""
            if dec.args and isinstance(dec.args[0], ast.Constant) and isinstance(dec.args[0].value, str):
                path = dec.args[0].value
            if path == prefix or path.startswith(prefix + "/") or path.startswith(prefix + "?"):
                found.append((fn.attr.upper(), path, node.name, node))
    return found


def guarded_by(node, dep: str) -> bool:
    """True bila endpoint benar-benar memakai `Depends(<dep>)` (parameter ATAU `dependencies=[...]`)."""
    defaults = list(node.args.defaults) + [d for d in node.args.kw_defaults if d is not None]
    for value in defaults:
        if (isinstance(value, ast.Call) and isinstance(value.func, ast.Name)
                and value.func.id == "Depends" and value.args
                and isinstance(value.args[0], ast.Name) and value.args[0].id == dep):
            return True
    for dec in node.decorator_list:  # bentuk sah kedua: dependencies=[Depends(MEDIA)]
        if isinstance(dec, ast.Call):
            for kw in dec.keywords or []:
                if kw.arg == "dependencies" and f"id='{dep}'" in ast.dump(kw.value):
                    return True
    return False


# --------------------------------------------------------------------------- stub DB in-memory
class _Coll:
    def __init__(self):
        self.docs = []

    async def find_one(self, q, proj=None):
        for d in self.docs:
            if all(d.get(k) == v for k, v in q.items() if not isinstance(v, dict)):
                return dict(d)
        return None

    def find(self, q=None, proj=None):
        rows = [dict(d) for d in self.docs]
        return _Cursor(rows)

    async def insert_one(self, doc):
        self.docs.append(dict(doc))

    async def update_one(self, q, upd):
        for d in self.docs:
            if all(d.get(k) == v for k, v in q.items() if not isinstance(v, dict)):
                d.update(upd.get("$set") or {})
                return _Res(1)
        return _Res(0)

    async def update_many(self, q, upd):
        n = 0
        for d in self.docs:
            if all(d.get(k) == v for k, v in q.items() if not isinstance(v, dict)):
                d.update(upd.get("$set") or {})
                n += 1
        return _Res(n)

    async def delete_one(self, q):
        before = len(self.docs)
        self.docs = [d for d in self.docs
                     if not all(d.get(k) == v for k, v in q.items() if not isinstance(v, dict))]
        return _Res(before - len(self.docs))

    async def count_documents(self, q=None):
        return len(self.docs)

    async def create_index(self, *a, **k):
        return "ok"

    def aggregate(self, pipeline):
        return _Cursor([])


class _Res:
    def __init__(self, n):
        self.modified_count = n
        self.deleted_count = n


class _Cursor:
    def __init__(self, rows):
        self.rows = rows

    def sort(self, *a, **k):
        return self

    def skip(self, *a):
        return self

    def limit(self, *a):
        return self

    async def to_list(self, n=None):
        return self.rows

    def __aiter__(self):
        async def gen():
            for r in self.rows:
                yield r
        return gen()


class _DB:
    def __init__(self):
        self.colls = {}

    def __getitem__(self, name):
        return self.colls.setdefault(name, _Coll())

    def __getattr__(self, name):
        return self[name]


async def _exercise_folder_rules(g, ml):
    """Uji PERILAKU aturan folder (bukan kata kunci): siklus ditolak & hapus folder tidak menghapus aset."""
    db = _DB()
    user = {"email": "guard@local"}
    parent = await ml.create_folder(db, "Induk", "", user)
    child = await ml.create_folder(db, "Anak", parent["id"], user)
    grand = await ml.create_folder(db, "Cucu", child["id"], user)

    g.bump()
    try:
        await ml.update_folder(db, parent["id"], parent_id=grand["id"])
        g.add("media_lib.update_folder MENERIMA pemindahan folder ke dalam cucunya sendiri → folder "
              "beserta seluruh isinya akan hilang dari daftar (pulau terputus dari akar).")
    except ml.MediaLibError:
        pass

    g.bump()
    try:
        await ml.update_folder(db, parent["id"], parent_id=parent["id"])
        g.add("media_lib.update_folder MENERIMA folder menjadi induk dirinya sendiri (siklus).")
    except ml.MediaLibError:
        pass

    g.bump()
    try:
        await ml.create_folder(db, "Induk", "", user)
        g.add("media_lib.create_folder MENERIMA dua folder bernama sama di lokasi sama → pengguna "
              "tidak bisa membedakan tujuan saat memindahkan aset.")
    except ml.MediaLibError:
        pass

    # hapus folder yang berisi aset → aset WAJIB pindah ke induk, bukan terhapus
    db[ml.MEDIA].docs.append({"id": "med_x", "folder_id": child["id"], "deleted": False})
    out = await ml.delete_folder(db, child["id"])
    asset = await db[ml.MEDIA].find_one({"id": "med_x"})
    g.bump()
    if not asset or asset.get("deleted"):
        g.add("media_lib.delete_folder MENGHAPUS aset di dalam folder → satu klik bisa memusnahkan "
              "ratusan foto yang sedang tayang (tak bisa dibatalkan).")
    g.bump()
    if not asset or asset.get("folder_id") != parent["id"]:
        g.add(f"aset di folder yang dihapus TIDAK dinaikkan ke induk (folder_id="
              f"{(asset or {}).get('folder_id')!r}) → aset jadi tak terjangkau lewat navigasi folder.")
    g.bump()
    if out.get("moved_assets", 0) < 1:
        g.add("delete_folder tidak melaporkan jumlah aset yang dipindahkan → UI tak bisa menjelaskan "
              "apa yang terjadi pada isinya.")


def main() -> int:  # noqa: C901 — satu penjaga, banyak aturan; dipisah = mudah lupa mendaftarkan
    g = Guard("INV-MEDIA-03", "Media Library tetap SATU (unified) + folder & cache tidak merusak aset")
    media_src = read(MEDIA_ROUTER)  # sumber UTUH — parser AST butuh Python yang sah
    content_txt, media_txt, public_txt = (code_only(read(CONTENT)), code_only(media_src),
                                          code_only(read(PUBLIC)))
    lib_txt, store_txt = code_only(read(LIB)), code_only(read(STORE))

    g.bump()
    if not lib_txt or not media_txt:
        g.add("services/media_lib.py atau routers/media.py TIDAK ADA — penyatuan media hilang total.")
        return g.finish()

    # ---------------------------------------------------------------- (1) satu jalur tulis berkas
    upload_body = fn_body(content_txt, "upload_cms_image")
    g.bump()
    if not upload_body:
        g.add("routers/content.py tidak lagi punya endpoint unggah CMS — pemanggil lama akan rusak "
              "(kompatibilitas mundur wajib dijaga).")
    else:
        g.bump()
        if ".write_bytes(" in upload_body or 'open(' in upload_body:
            g.add("routers/content.py::upload_cms_image menulis berkas SENDIRI (write_bytes/open) → "
                  "aset tidak tercatat di `media_assets` dan kembali 'tak terlihat' di Media Library "
                  "(dua dunia media kembali).")
        g.bump()
        if "register_asset" not in upload_body:
            g.add("routers/content.py::upload_cms_image tidak memanggil media_lib.register_asset → "
                  "gambar CMS baru tidak akan pernah muncul di Media Library.")
        g.bump()
        if "upload_bytes" not in upload_body:
            g.add("routers/content.py::upload_cms_image tidak memakai media_store.upload_bytes → "
                  "validasi MIME/ukuran & pagar path traversal dilewati.")

    for path in sorted((BACKEND / "routers").glob("*.py")):
        if path.name in WRITE_ALLOWLIST or path.name == "media.py":
            continue
        text = read(path)
        if "UploadFile" not in text:
            continue
        g.bump()
        if ".write_bytes(" in text:
            g.add(f"routers/{path.name} menangani unggahan TETAPI menulis berkas langsung "
                  f"(.write_bytes) — semua penulisan aset media WAJIB lewat services/media_store "
                  f"(satu tempat validasi MIME, batas ukuran, dan anti path-traversal).")

    # ---------------------------------------------------------------- (2) RBAC endpoint media baru
    g.bump()
    if 'require_section("media")' not in media_txt:
        g.add("routers/media.py tidak memakai require_section(\"media\") → pintu modul media tidak "
              "ditegakkan di backend (RBAC 3 lapis pecah).")
    routes = router_endpoints(media_src, "/media")
    g.bump()
    if len(routes) < 10:
        g.add(f"routers/media.py hanya punya {len(routes)} rute terdeteksi — Media Manager v2 "
              f"kehilangan endpoint (folder/unduh/ganti/potong/massal/impor).")
    for _method, path, name, node in routes:
        g.bump()
        if not guarded_by(node, "MEDIA"):
            g.add(f"routers/media.py::{name} ({path}) TIDAK memakai Depends(MEDIA) → aset media bisa "
                  f"diubah/diunduh peran yang tidak berhak.")

    dl = fn_body(media_txt, "download_media")
    g.bump()
    if "attachment" not in dl:
        g.add("endpoint unduh tidak mengirim Content-Disposition: attachment → berkas dibuka di tab "
              "alih-alih diunduh, dan nama berkas asli hilang.")
    g.bump()
    if "safe_display_name" not in dl:
        g.add("endpoint unduh memakai nama berkas mentah dari database pada header HTTP → celah "
              "header injection (nama berkas berasal dari input pengguna).")
    g.bump()
    if 'storage_path' not in dl:
        g.add("endpoint unduh tidak membaca jalur dari dokumen aset (storage_path) → berisiko jalur "
              "dari input klien.")

    # ---------------------------------------------------------------- (3) cache sadar-versi
    pm = fn_body(public_txt, "public_media")
    g.bump()
    etag_hits = pm.count('"ETag"')
    if etag_hits < 2:
        # DUA jalur respons harus mengirim ETag: balasan 304 DAN balasan 200. Kalau hanya jalur 304
        # yang punya, browser tak pernah menerima validator sejak awal → 304 mustahil terjadi dan
        # foto pengganti tetap tak terlihat. Self-test M23 membuktikan cek "ada kata ETag" saja
        # meloloskan regresi separuh ini.
        g.add(f"routers/public.py::public_media tidak mengirim ETag di SEMUA jalur respons "
              f"(ditemukan {etag_hits}, butuh 2: balasan 304 & balasan 200) → browser tak punya "
              f"validator, jadi setelah 'Ganti berkas' foto lama tetap tampil sampai cache "
              f"kedaluwarsa (keluhan 'sudah diganti kok tidak berubah').")
    g.bump()
    if "if-none-match" not in pm.lower() or "304" not in pm:
        g.add("routers/public.py::public_media tidak menangani permintaan bersyarat "
              "(`If-None-Match` → 304) → setiap tampilan grid Media Library menarik ulang seluruh "
              "berkas; revalidasi jadi mahal sehingga cache pendek terasa lambat.")
    g.bump()
    if "must-revalidate" not in pm and "no-cache" not in pm:
        g.add("routers/public.py::public_media tidak memvalidasi ulang URL tanpa versi → gambar yang "
              "sudah diganti membeku di cache browser.")
    g.bump()
    if 'version' not in pm:
        g.add("routers/public.py::public_media tidak memakai `version` aset untuk cache → penanda "
              "versi jadi hiasan tanpa efek.")
    g.bump()
    if "def media_url" not in lib_txt or "?v=" not in lib_txt:
        g.add("services/media_lib.media_url tidak lagi menyertakan penanda versi (`?v=`) → URL baru "
              "tidak bisa melewati cache lama.")
    g.bump()
    replace_body = lib_txt[lib_txt.find("async def replace_file"):]
    replace_body = replace_body[:replace_body.find("async def crop_asset")] or replace_body
    if '"version"' not in replace_body or "+ 1" not in replace_body:
        g.add("services/media_lib.replace_file tidak menaikkan `version` saat berkas diganti → "
              "cache tidak pernah dibatalkan.")
    g.bump()
    if "ms.remove(" not in replace_body:
        g.add("replace_file tidak membuang berkas lama → setiap penggantian menumpuk sampah di disk "
              "sampai penyimpanan penuh (penuh = SEMUA unggah gagal).")

    # ---------------------------------------------------------------- (4) tidak membocorkan jalur
    g.bump()
    if 'storage_path' not in lib_txt.split("def public_doc")[1].split("def ")[0]:
        g.add("media_lib.public_doc tidak lagi membuang `storage_path` → jalur penyimpanan internal "
              "bocor ke klien.")

    # ---------------------------------------------------------------- (5) picker frontend tunggal
    src = FRONTEND / "src"
    g.bump()
    if not src.exists():
        # Tanpa cek ini, satu perubahan struktur folder membuat SELURUH bagian frontend penjaga
        # ini dilewati diam-diam — gate tetap hijau sambil separuh invariant tak dijaga.
        g.add("frontend/src tidak ditemukan — SEMUA cek frontend pada penjaga ini akan dilewati "
              "diam-diam (hijau-palsu). Perbarui path bila struktur proyek berubah.")
    if src.exists():
        for path in sorted(list(src.rglob("*.jsx")) + list(src.rglob("*.js"))):
            rel = str(path.relative_to(src)).replace("\\", "/")
            if rel.startswith("components/ui/") or rel in FE_UPLOAD_ALLOWLIST:
                continue
            text = jsx_code_only(read(path))
            posts_upload = bool(re.search(r'post\(\s*[`"\']/?(uploads/cms|media|landing/media)', text))
            if not posts_upload:
                continue
            g.bump()
            if SHARED_PICKER not in text and "components/media/MediaBrowser" not in text:
                g.add(f"frontend/src/{rel} mengunggah media sendiri tanpa memakai pemilih bersama "
                      f"({SHARED_PICKER}) → penyatuan picker terkikis dan pengguna kembali menghadapi "
                      f"dua cara kerja untuk satu pekerjaan.")

        # Konsumen media WAJIB memakai picker bersama (bukan hanya kolom URL manual).
        for rel in ("components/cms/GalleryManager.jsx", "components/cms/TourSceneBuilder.jsx",
                    "components/app/ContentFormDialog.jsx",
                    "components/app/landing/MediaLibrary.jsx"):
            g.bump()
            text = jsx_code_only(read(src / rel))
            if not text:
                g.add(f"frontend/src/{rel} tidak ada — konsumen media hilang (regresi refactor?).")
            elif not re.search(r'from\s+["\'][^"\']*' + re.escape(SHARED_PICKER) + r'["\']', text):
                g.add(f"frontend/src/{rel} tidak mengimpor {SHARED_PICKER} → di tempat itu pengguna "
                      f"kembali harus menempel URL manual / memakai pemilih terpisah.")

        g.bump()
        nav = jsx_code_only(read(src / "config" / "navigationConfig.js"))
        if '"/app/media"' not in nav:
            g.add("navigationConfig.js tidak punya butir menu ber-path \"/app/media\" → halaman Media "
                  "Library tak terjangkau lewat navigasi (fitur mati walau backend hidup).")
        g.bump()
        if not re.search(r'ops_admin:\s*\[[^\]]*"media"', nav):
            g.add("ROLE_MENU_ALLOWLIST.ops_admin TIDAK memuat \"media\" → pemegang CMS kembali tak bisa "
                  "membuka Media Library; itu justru pemisahan (\"dua dunia media\") yang dihapus ronde ini.")
        g.bump()
        app_js = jsx_code_only(read(src / "App.js"))
        if not re.search(r'path="media"', app_js):
            g.add("App.js tidak lagi punya route `media` → menu ada tapi klik menghasilkan halaman "
                  "kosong/404 di dalam aplikasi.")

    # ---------------------------------------------------------------- (6) perilaku folder (dieksekusi)
    try:
        from services import media_lib as ml
        asyncio.run(_exercise_folder_rules(g, ml))
    except Exception as exc:  # noqa: BLE001
        g.bump()
        g.add(f"gagal menguji aturan folder secara langsung: {type(exc).__name__}: {exc}")

    # ---------------------------------------------------------------- (7) crop & impor aman
    g.bump()
    if "def crop_bytes" not in store_txt:
        g.add("services/media_store.crop_bytes tidak ada → potong gambar tidak mungkin dilakukan "
              "di server (kualitas turun bila dipaksa lewat canvas browser).")
    else:
        for needle, why in (
            ("MediaError(f\"Nilai", "kotak potong non-numerik tidak ditolak berALASAN (berisiko 5xx)"),
            ("melebihi ukuran gambar", "kotak potong di luar batas gambar tidak ditolak (berisiko 5xx)"),
            ("> MAX_CROP_SIDE", "tidak ada batas sisi hasil potong yang DITEGAKKAN (server bisa "
                                "kehabisan memori saat diminta 60000px)"),
        ):
            g.bump()
            if needle not in store_txt:
                g.add(f"services/media_store.crop_bytes: {why}.")
    g.bump()
    if not re.search(r'"legacy_key",\s*unique=True', lib_txt):
        g.add("impor aset CMS lama tidak dijaga indeks unik (`legacy_key`) → dua klik menghasilkan "
              "aset ganda untuk satu berkas.")
    g.bump()
    if 'f"/api/uploads/cms/' not in lib_txt:
        g.add("impor aset lama tidak menyimpan URL lama (`legacy_url`) → pemakaian aset di konten "
              "yang sudah tayang tidak bisa dilacak sebelum dihapus.")

    # ---------------------------------------------------------------- (8) koersi tipe input klien
    # Kelas bug NYATA yang ditemukan gate RUNTIME di ronde ini: klien mengirim `folder_id: 5`
    # (angka, bukan string) → `(body.get("folder_id") or "").strip()` melempar AttributeError →
    # **HTTP 500**. Tidak ada satu pun pagar statik yang melihatnya karena kodenya "terlihat benar".
    # Aturan: di modul media, `.strip()` pada nilai yang bisa datang dari klien WAJIB lewat `str(...)`.
    for label, path in (("routers/media.py", MEDIA_ROUTER), ("services/media_lib.py", LIB)):
        g.bump()
        risky = []
        for num, line in enumerate(read(path).splitlines(), 1):
            body = line.strip()
            if body.startswith("#") or ").strip()" not in line or "str(" in line:
                continue
            if re.search(r'\bor\s+(?:["\']|ROOT\b)', line):
                risky.append(f"{num}: {body[:90]}")
        if risky:
            g.add(f"{label} memanggil `.strip()` pada nilai yang bisa BUKAN string di "
                  f"{len(risky)} tempat ({'; '.join(risky[:3])}) → satu field bertipe salah dari "
                  f"klien (mis. `folder_id: 5`) menghasilkan HTTP 500 alih-alih 4xx berALASAN. "
                  f"Bungkus dengan `str(...)`.")

    return g.finish()


if __name__ == "__main__":
    sys.exit(main())
