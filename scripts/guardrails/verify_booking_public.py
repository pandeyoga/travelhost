#!/usr/bin/env python3
"""INV-BOOK-02 — Pemesanan online: harga dihitung ulang server, ketersediaan & mutex ditegakkan.

Kelas bug yang dicegah
----------------------
1. **Formulir publik menulis booking tanpa memeriksa apa pun.** Versi lama membuat dokumen
   `vehicle_id=None, total_amount=0, status='pending'` — tamu "berhasil memesan" tanggal yang
   armadanya penuh, lalu ditolak manual lewat WhatsApp berjam-jam kemudian.
2. **Klien mengirim total.** Selama skema permintaan punya field harga, siapa pun bisa memesan
   Rp 1 dengan curl. Karena itu `schemas_booking.PublicBookingSubmit` DILARANG punya field
   harga sama sekali (bukan sekadar "diabaikan di kode").
3. **Cek ketersediaan di luar mutex** → dua pemesan paralel sama-sama lolos cek lalu sama-sama
   menahan unit yang sama (satu unit, dua pelanggan yang sudah bayar DP).
4. **Unit yang tidak dijual online tetap bisa dipesan** dengan menebak `vehicle_id` (unit mitra,
   unit yang sengaja disembunyikan, atau artefak skrip uji).

STATIK  : skema tanpa field harga; `create_booking` memanggil `build_quote` + `assert_free`
          + `vehicle_lock` + `publishable_vehicles`; `assert_free` memeriksa booking aktif DAN
          jendela perawatan; router publik ber-rate-limit dan tak membaca harga dari body.
RUNTIME : pesan unit yang sama dua kali → penolakan berALASAN; 8 permintaan PARALEL pada unit &
          jendela yang sama → TEPAT 1 sukses, 0 5xx; unit tak-tayang → ditolak; harga tersimpan
          = harga hasil hitung server (bukan angka kiriman klien).
"""
import ast
import json
import os
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(__file__))
from _common import BACKEND, Guard, G, X, purge_guard_bookings  # noqa: E402

BASE = os.environ.get("GUARD_BASE_URL", "http://127.0.0.1:8001") + "/api"
PRICE_FIELDS = ("total", "total_amount", "base_price", "dp_amount", "dp_percent",
                "subtotal", "discount", "price", "grand_total")


def req(method, path, token=None, body=None, timeout=40):
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


def jreq(method, path, token=None, body=None):
    st, txt = req(method, path, token, body)
    try:
        return st, json.loads(txt)
    except Exception:  # noqa: BLE001
        return st, {}


def login(email="owner@demo.local"):
    st, data = jreq("POST", "/auth/login", body={"email": email, "password": "demo12345"})
    return data.get("token") if st == 200 else None


# ----------------------------------------------------------------------- STATIK
def _public_schema_names(router_src: str) -> set:
    """Nama kelas skema yang BENAR-BENAR dipakai router publik (dibaca dari import-nya).

    Kenapa diturunkan dari import, bukan daftar manual: daftar manual selalu tertinggal dari
    pertumbuhan kode. Endpoint publik BARU (mis. `POST /public/booking/promos` yang lahir saat
    fitur daftar promo) otomatis ikut terjaga tanpa seseorang harus ingat menambahkannya —
    pelajaran dari kelas bug "daftar-larangan manual" di repo ini.
    """
    names = set()
    for node in ast.walk(ast.parse(router_src)):
        if isinstance(node, ast.ImportFrom) and (node.module or "").endswith("schemas_booking"):
            for alias in node.names:
                names.add(alias.name)
    return names


def static_checks(g: Guard):
    schemas = (BACKEND / "schemas_booking.py")
    tree = ast.parse(schemas.read_text(encoding="utf-8", errors="ignore"))
    router_src = (BACKEND / "routers" / "booking_public.py").read_text(
        encoding="utf-8", errors="ignore")
    public_schemas = _public_schema_names(router_src)
    classes = {node.name: node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)}
    submit = classes.get("PublicBookingSubmit")
    g.bump()
    if submit is None:
        g.add("schemas_booking.py: kelas `PublicBookingSubmit` hilang — kontrak pemesanan "
              "publik tak bisa diperiksa.")

    # SEMUA skema yang dipakai router publik wajib bebas field harga (bukan hanya submit):
    # promo/quote/search juga bisa dipakai untuk menyelipkan angka pilihan penyerang
    # (mis. `subtotal` besar agar promo bersyarat "min. Rp 3 juta" ikut lolos).
    g.bump()
    if not public_schemas:
        g.add("routers/booking_public.py: tidak satu pun skema diimpor dari `schemas_booking` — "
              "penjaga kontrak harga kehilangan sasaran (import diubah?).")
    for name in sorted(public_schemas):
        node = classes.get(name)
        if node is None:
            continue
        for st in node.body:
            if isinstance(st, ast.AnnAssign) and isinstance(st.target, ast.Name):
                g.bump()
                if st.target.id in PRICE_FIELDS:
                    g.add(f"{name}.{st.target.id}: skema publik TIDAK boleh menerima harga dari "
                          f"klien (harga & kelayakan promo selalu dihitung server).")

    bp = (BACKEND / "services" / "booking_public.py").read_text(
        encoding="utf-8", errors="ignore")
    for needle, why in (
        ("build_quote", "harga tidak dihitung ulang di server"),
        ("assert_free", "ketersediaan tidak diperiksa saat pesanan dibuat"),
        ("vehicle_lock", "penulisan booking tidak dilindungi mutex per armada"),
        ("publishable_vehicles", "unit tak-tayang/mitra bisa dipesan dari web"),
    ):
        g.bump()
        if needle not in bp:
            g.add(f"services/booking_public.py: `{needle}` tidak dipakai → {why}.")

    # `assert_free` wajib memeriksa DUA sumber bentrok.
    g.bump()
    body = bp.split("async def assert_free", 1)[-1].split("\nasync def ", 1)[0]
    if "find_conflicts" not in body or "find_maintenance_conflicts" not in body:
        g.add("services/booking_public.assert_free: harus memeriksa booking aktif DAN jendela "
              "perawatan (unit di bengkel pernah tetap terjual).")

    # Mutex harus MEMBUNGKUS penulisan, bukan hanya disebut.
    g.bump()
    create = bp.split("async def create_booking", 1)[-1].split("\nasync def ", 1)[0]
    lock_at = create.find("vehicle_lock")
    insert_at = create.find("insert_one", lock_at if lock_at >= 0 else 0)
    if lock_at < 0 or insert_at < 0:
        g.add("services/booking_public.create_booking: `vehicle_lock` tidak membungkus "
              "`insert_one` → jendela balapan reservasi terbuka lagi.")

    router = (BACKEND / "routers" / "booking_public.py").read_text(
        encoding="utf-8", errors="ignore")
    g.bump()
    if "_guard(" not in router:
        g.add("routers/booking_public.py: endpoint publik tanpa rate-limit `_guard(` "
              "→ terbuka untuk banjir permintaan bot.")
    for field in PRICE_FIELDS:
        g.bump()
        if f"body.{field}" in router:
            g.add(f"routers/booking_public.py: membaca `body.{field}` dari klien "
                  f"→ harga/DP tidak boleh datang dari luar.")


# ---------------------------------------------------------------------- RUNTIME
def _window(days_ahead=35, days=2):
    start = (datetime.now(timezone.utc) + timedelta(days=days_ahead)).replace(
        hour=8, minute=0, second=0, microsecond=0)
    return start.isoformat(), (start + timedelta(days=days)).isoformat()


def runtime_checks(g: Guard, tok: str):
    created = []
    try:
        start_iso, end_iso = _window()
        st, res = jreq("POST", "/public/booking/search",
                       body={"service": "daily_rental", "start_datetime": start_iso,
                             "end_datetime": end_iso, "pax": 2})
        g.bump()
        if st != 200 or not (res.get("options") or []):
            g.add(f"pencarian jendela uji gagal (HTTP {st}, {len(res.get('options') or [])} "
                  f"unit) — perilaku pemesanan tak bisa dibuktikan.")
            return
        option = res["options"][0]
        vid = option["vehicle"]["id"]
        quoted = int((option.get("quote") or {}).get("total") or 0)

        def submit(idem, extra=None):
            body = {"service": "daily_rental", "vehicle_id": vid,
                    "start_datetime": start_iso, "end_datetime": end_iso, "pax": 2,
                    "name": "Penjaga INV-BOOK-02", "phone": "0800000202",
                    "idempotency_key": idem, "marketing_consent": False}
            body.update(extra or {})
            return jreq("POST", "/public/booking/submit", body=body)

        # R1 — 8 permintaan PARALEL pada unit & jendela yang sama → TEPAT 1 sukses.
        stamp = datetime.now(timezone.utc).strftime("%H%M%S%f")
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda i: submit(f"guard-book-{stamp}-{i}"), range(8)))
        ok = [d for s, d in results if s == 200 and d.get("code")]
        server_err = [s for s, _ in results if s >= 500]
        for d in ok:
            created.append((d["code"], d.get("token") or ""))
        g.bump(2)
        if len(ok) != 1:
            g.add(f"8 pemesanan paralel unit+jendela SAMA menghasilkan {len(ok)} sukses "
                  f"(harus TEPAT 1) → satu unit bisa dijual dua kali.")
        else:
            print(f"    [{G}ok{X}] 8 permintaan paralel → 1 sukses ({ok[0]['code']}), "
                  f"7 ditolak berALASAN")
        if server_err:
            g.add(f"pemesanan paralel menghasilkan {len(server_err)} respons 5xx "
                  f"(balapan bocor sebagai error server).")

        # R2 — harga tersimpan = hasil hitung server, walau klien mengirim angka palsu.
        if ok:
            g.bump()
            stored = int(ok[0].get("total_amount") or 0)
            if stored != quoted:
                g.add(f"harga tersimpan {stored} != harga hasil hitung server {quoted}.")

        # R3 — pesan LAGI unit yang sama → ditolak dengan alasan (bukan 5xx, bukan sukses).
        st, again = jreq("POST", "/public/booking/submit",
                         body={"service": "daily_rental", "vehicle_id": vid,
                               "start_datetime": start_iso, "end_datetime": end_iso,
                               "pax": 2, "name": "Penjaga Bentrok", "phone": "0800000203",
                               "marketing_consent": False})
        g.bump()
        if st == 200 and again.get("code"):
            created.append((again["code"], again.get("token") or ""))
            g.add("unit yang sudah ditahan MASIH bisa dipesan ulang untuk jendela sama "
                  "→ ketersediaan tidak ditegakkan saat pembuatan.")
        elif st >= 500 or st < 0:
            g.add(f"pemesanan bentrok menghasilkan HTTP {st} (harus 4xx berALASAN).")
        else:
            print(f"    [{G}ok{X}] pemesanan bentrok ditolak HTTP {st}: "
                  f"{str(again.get('detail'))[:70]}")

        # R4 — unit yang TIDAK dijual online tidak bisa dipesan walau id-nya ditebak.
        st, allv = jreq("GET", "/vehicles", tok)
        rows = allv if isinstance(allv, list) else (allv.get("items") or [])
        hidden = [v for v in rows if v.get("publish_to_web") is False
                  or v.get("ownership") == "partner"]
        g.bump()
        if not hidden:
            g.add("tidak ada armada tak-tayang di data → penjaga tak bisa membuktikan "
                  "penyaringan katalog (seed harus punya minimal 1 unit tak-tayang).")
        else:
            st, out = jreq("POST", "/public/booking/submit",
                           body={"service": "daily_rental", "vehicle_id": hidden[0]["id"],
                                 "start_datetime": start_iso, "end_datetime": end_iso,
                                 "pax": 2, "name": "Penjaga Unit Tersembunyi",
                                 "phone": "0800000204", "marketing_consent": False})
            if st == 200 and out.get("code"):
                created.append((out["code"], out.get("token") or ""))
                g.add(f"unit tak-tayang {hidden[0].get('code')} bisa dipesan dari web "
                      f"(publish_to_web/ownership diabaikan).")
            elif st >= 500:
                g.add(f"pemesanan unit tak-tayang → HTTP {st} (harus 4xx berALASAN).")
            else:
                print(f"    [{G}ok{X}] unit tak-tayang {hidden[0].get('code')} ditolak "
                      f"HTTP {st}")
    finally:
        for code, token in created:
            jreq("POST", f"/public/booking/{code}/cancel",
                 body={"token": token, "reason": "bersih-bersih guardrail INV-BOOK-02"})
        purged = purge_guard_bookings("08000002")
        if created:
            print(f"    [{G}ok{X}] bersih-bersih: {len(created)} pesanan uji dibatalkan, "
                  f"{purged} dokumen uji dihapus (tabel ops tetap bersih)")


def main() -> int:
    g = Guard("INV-BOOK-02",
              "Pemesanan online: hitung ulang server + ketersediaan + mutex, tanpa total klien")
    static_checks(g)
    tok = login()
    if not tok:
        g.add("tidak bisa login owner@demo.local — gate runtime WAJIB jalan (SKIP != PASS).")
        return g.finish()
    runtime_checks(g, tok)
    return g.finish()


if __name__ == "__main__":
    sys.exit(main())
