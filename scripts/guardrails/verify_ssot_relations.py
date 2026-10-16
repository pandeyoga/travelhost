#!/usr/bin/env python3
"""INV-REF-02 — Relasi SSOT: destinasi booking ERP WAJIB dari master `destinations`.

Kelas bug yang ditutup (RC-E, keluhan user 2026-08-29, BUG-0135): field yang seharusnya
RELASI antar-collection diisi lewat input teks bebas. Untuk `bookings.destination` akibatnya
nyata: "Bromo" vs "Gunung Bromo" vs "bromo " dihitung sebagai 3 destinasi berbeda di laporan,
dan paket/penawaran (yang sudah relasional via `destination_id`) tidak pernah bisa dicocokkan
dengan booking.

Yang dikunci:
  STATIK : (1) `services/refs.py` punya `destination_or_400` (validator satu pintu),
           (2) `routers/bookings.py` memanggilnya di jalur BUAT, ROMBONGAN, dan UBAH,
           (3) endpoint pilihan `GET /bookings/destination-options` tersedia utk FE.
  RUNTIME: POST /bookings dgn destinasi di luar master → WAJIB 400 dengan alasan destinasi
           (bukan alasan lain = hijau-palsu). Bila server malah MENERIMA (2xx), dokumen uji
           dibersihkan via purge_guard_bookings() dan dilaporkan sebagai pelanggaran.
"""
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(__file__))
from _common import BACKEND, Guard, mongo_db, purge_guard_bookings  # noqa: E402

BASE = "http://localhost:8001/api"
REFS = BACKEND / "services" / "refs.py"
BOOKINGS = BACKEND / "routers" / "bookings.py"
LEADS = BACKEND / "routers" / "leads.py"
PICKUPS = BACKEND / "routers" / "pickup_points.py"
QUOTATIONS = BACKEND / "routers" / "quotations.py"
PUBLIC = BACKEND / "routers" / "public.py"


def req(method, path, token=None, body=None, timeout=30):
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


def login():
    st, data = jreq("POST", "/auth/login",
                    body={"email": "owner@demo.local", "password": "demo12345"})
    return data.get("token") if st == 200 else None


def read(p):
    return p.read_text(encoding="utf-8", errors="ignore") if p.exists() else ""


def static_checks(g: Guard):
    refs = read(REFS)
    g.bump()
    if "async def destination_or_400" not in refs:
        g.add("services/refs.py: validator `destination_or_400` HILANG — destinasi kembali teks bebas.")
    src = read(BOOKINGS)
    g.bump()
    if src.count("destination_or_400(") < 3:
        g.add("routers/bookings.py: `destination_or_400` harus dipanggil di 3 jalur "
              "(create, group, update) — ada jalur tulis destinasi yang lolos validasi master.")
    g.bump()
    if "/bookings/destination-options" not in src:
        g.add("routers/bookings.py: endpoint `GET /bookings/destination-options` hilang — "
              "FE tak punya sumber pilihan, ops akan kembali mengetik bebas.")
    # --- batch 2: titik jemput (bookings.origin) + destinasi lead ---
    g.bump()
    if "async def origin_or_400" not in refs:
        g.add("services/refs.py: validator `origin_or_400` HILANG — titik jemput kembali teks bebas.")
    g.bump()
    if src.count("origin_or_400(") < 3:
        g.add("routers/bookings.py: `origin_or_400` harus dipanggil di 3 jalur (create, group, "
              "update) — ada jalur tulis titik jemput yang lolos validasi master.")
    leads_src = read(LEADS)
    g.bump()
    if leads_src.count("destination_or_400(") < 2:
        g.add("routers/leads.py: `destination_or_400` harus dipanggil di jalur create & update "
              "lead — destinasi lead ERP kembali teks bebas.")
    pk = read(PICKUPS)
    g.bump()
    if "/pickup-points" not in pk or "PickupPointCreate" not in pk:
        g.add("routers/pickup_points.py: master titik jemput (GET/POST /pickup-points) hilang — "
              "FE tak punya sumber pilihan/quick-add satu pintu.")
    # --- batch 3: penawaran + form publik + halaman kelola master (rename cascade) ---
    quo = read(QUOTATIONS)
    g.bump()
    if quo.count("destination_or_400(") < 2:
        g.add("routers/quotations.py: `destination_or_400` harus dipanggil di create & update — "
              "destinasi penawaran ERP kembali teks bebas.")
    pub = read(PUBLIC)
    g.bump()
    if "/destination-options" not in pub:
        g.add("routers/public.py: endpoint publik `/destination-options` hilang — form penawaran "
              "web kembali ketik-bebas tanpa pilihan master.")
    g.bump()
    if "/master/pickup-points" not in pk or "/master/destinations" not in pk or "update_many" not in pk:
        g.add("routers/pickup_points.py: halaman kelola master (rename CASCADE via update_many + "
              "toggle aktif) hilang — rename master tidak lagi menyeret dokumen pemakai → nama bercabang.")
    # --- batch 4: normalisasi LUNAK seluruh jalur tulis publik/inbound + preview cascade ---
    g.bump()
    if "async def origin_normalize" not in refs:
        g.add("services/refs.py: `origin_normalize` HILANG — titik jemput inbound publik "
              "tidak dikanonikkan lagi.")
    bp_src = read(BACKEND / "services" / "booking_public.py")
    g.bump()
    if "destination_normalize(" not in bp_src or "origin_normalize(" not in bp_src:
        g.add("services/booking_public.py: pemesanan online tidak menormalkan origin/destination "
              "— booking publik menulis teks bebas ke koleksi yang SAMA dgn ERP (nama bercabang lagi).")
    g.bump()
    if "origin_normalize(" not in pub:
        g.add("routers/public.py: lead landing menyimpan origin teks bebas tanpa `origin_normalize`.")
    ads_src = read(BACKEND / "services" / "ads.py")
    g.bump()
    if "destination_normalize(" not in ads_src:
        g.add("services/ads.py: lead ads menyimpan destination teks bebas tanpa "
              "`destination_normalize` — laporan per-destinasi bercabang dari inbound iklan.")
    g.bump()
    if "used_by_quotations" not in pk:
        g.add("routers/pickup_points.py: master destinasi tidak melaporkan `used_by_quotations` — "
              "preview cascade di Master Data buta terhadap penawaran.")
    # --- batch 5: master KOTA (customers/partners), tipe armada landing, merge & ekspor ---
    g.bump()
    if "async def city_or_400" not in refs or "def vehicle_type_normalize" not in refs:
        g.add("services/refs.py: `city_or_400` / `vehicle_type_normalize` HILANG — kota & tipe "
              "armada kembali teks bebas.")
    cust_src = read(BACKEND / "routers" / "customers.py")
    g.bump()
    if cust_src.count("city_or_400(") < 2:
        g.add("routers/customers.py: `city_or_400` harus dipanggil di create & update — kota "
              "pelanggan kembali teks bebas.")
    ptn_src = read(BACKEND / "routers" / "partners.py")
    g.bump()
    if ptn_src.count("city_or_400(") < 2:
        g.add("routers/partners.py: `city_or_400` harus dipanggil di create & update — kota "
              "mitra kembali teks bebas.")
    g.bump()
    if "vehicle_type_normalize(" not in pub:
        g.add("routers/public.py: lead landing menyimpan vehicle_type teks bebas tanpa "
              "`vehicle_type_normalize` — filter/label tipe armada bercabang dari inbound.")
    g.bump()
    if "/master/cities" not in pk or "/merge" not in pk or "/master/export" not in pk:
        g.add("routers/pickup_points.py: endpoint master kota / gabung destinasi / ekspor Excel "
              "hilang — kelola master tidak lagi satu pintu.")
    # --- batch 6/7: undo gabungan (destinasi & titik jemput) + kota bengkel ---
    g.bump()
    if pk.count("/merge") < 2 or pk.count("/unmerge") < 2 or "merged_moved" not in pk:
        g.add("routers/pickup_points.py: endpoint merge/unmerge (destinasi DAN titik jemput) "
              "atau catatan `merged_moved` hilang — gabungan tidak bisa dibatalkan tanpa DB.")
    wsh_src = read(BACKEND / "routers" / "workshops.py")
    g.bump()
    if wsh_src.count("city_or_400(") < 2:
        g.add("routers/workshops.py: `city_or_400` harus dipanggil di create & update — kota "
              "bengkel kembali teks bebas.")
    g.bump()
    if '"workshops"' not in pk or "used_by_workshops" not in pk:
        g.add("routers/pickup_points.py: cascade rename kota / pemakaian tidak mencakup workshops "
              "— rename kota meninggalkan bengkel bernama lama.")


def runtime_checks(g: Guard, tok: str):
    _, cust = jreq("GET", "/customers?limit=1", tok)
    _, veh = jreq("GET", "/vehicles?limit=1", tok)
    if not (isinstance(cust, list) and cust and isinstance(veh, list) and veh):
        g.bump()
        g.add("Runtime: tidak bisa mengambil customer/vehicle demo untuk probe (seed rusak?).")
        return
    start = (datetime.now(timezone.utc) + timedelta(days=400)).replace(microsecond=0)
    end = start + timedelta(days=1)
    body = {"customer_id": cust[0]["id"], "vehicle_id": veh[0]["id"],
            "origin": "Bandung", "destination": "NgawurLand Penjaga INV-REF-02",
            "start_datetime": start.isoformat(), "end_datetime": end.isoformat(),
            "base_price": 1000000}
    st, data = jreq("POST", "/bookings", tok, body)
    g.bump()
    if st == 400:
        detail = str((data or {}).get("detail") or "").lower()
        if "destinasi" not in detail and "master" not in detail:
            g.add(f"Runtime: destinasi ngawur ditolak tetapi karena alasan LAIN ('{detail[:80]}') "
                  f"— hijau-palsu; validasi master tidak terbukti bekerja.")
    elif 200 <= st < 300:
        g.add("Runtime: POST /bookings MENERIMA destinasi di luar master (INV-REF-02 dilanggar) "
              "— dokumen uji dibersihkan.")
    else:
        g.add(f"Runtime: respons tak terduga HTTP {st} untuk destinasi ngawur (harus 400).")
    g.bump()
    st2, opts = jreq("GET", "/bookings/destination-options", tok)
    if st2 != 200 or not isinstance(opts, list) or not opts:
        g.add(f"Runtime: GET /bookings/destination-options gagal (HTTP {st2}) atau kosong — "
              f"selector FE tak punya pilihan.")
    # --- batch 2: origin ngawur → 400 beralasan titik jemput; lead dest ngawur → 400 ---
    body2 = dict(body, destination="Bali", origin="NgawurPoint Penjaga INV-REF-02")
    st3, data3 = jreq("POST", "/bookings", tok, body2)
    g.bump()
    if st3 == 400:
        detail = str((data3 or {}).get("detail") or "").lower()
        if "titik jemput" not in detail and "master" not in detail:
            g.add(f"Runtime: origin ngawur ditolak karena alasan LAIN ('{detail[:80]}') — "
                  f"validasi master titik jemput tidak terbukti bekerja.")
    elif 200 <= st3 < 300:
        g.add("Runtime: POST /bookings MENERIMA titik jemput di luar master (INV-REF-02 b2).")
    else:
        g.add(f"Runtime: respons tak terduga HTTP {st3} untuk origin ngawur (harus 400).")
    st4, data4 = jreq("POST", "/leads", tok,
                      {"customer_name": "Penjaga INV-REF-02 Lead", "pax": 1,
                       "destination": "NgawurLand Penjaga INV-REF-02"})
    g.bump()
    if st4 == 400:
        detail = str((data4 or {}).get("detail") or "").lower()
        if "destinasi" not in detail and "master" not in detail:
            g.add(f"Runtime: destinasi lead ngawur ditolak karena alasan LAIN ('{detail[:80]}').")
    elif 200 <= st4 < 300:
        g.add("Runtime: POST /leads MENERIMA destinasi di luar master — dokumen uji dibersihkan.")
    else:
        g.add(f"Runtime: respons tak terduga HTTP {st4} untuk destinasi lead ngawur (harus 400).")
    st5, pkts = jreq("GET", "/pickup-points", tok)
    g.bump()
    if st5 != 200 or not isinstance(pkts, list) or not pkts:
        g.add(f"Runtime: GET /pickup-points gagal (HTTP {st5}) atau kosong — selector titik "
              f"jemput FE tak punya pilihan.")
    # --- batch 3: destinasi penawaran ngawur → 400; opsi publik tersedia ---
    st6, data6 = jreq("POST", "/quotations", tok,
                      {"customer_name": "Penjaga INV-REF-02 Quo", "pax": 1,
                       "destination": "NgawurLand Penjaga INV-REF-02",
                       "vehicle_type": "hiace_premio", "days": 1})
    g.bump()
    if st6 == 400:
        detail = str((data6 or {}).get("detail") or "").lower()
        if "destinasi" not in detail and "master" not in detail:
            g.add(f"Runtime: destinasi penawaran ngawur ditolak karena alasan LAIN ('{detail[:80]}').")
    elif 200 <= st6 < 300:
        g.add("Runtime: POST /quotations MENERIMA destinasi di luar master — dokumen uji dibersihkan.")
    else:
        g.add(f"Runtime: respons tak terduga HTTP {st6} untuk destinasi penawaran ngawur (harus 400).")
    st7, popts = jreq("GET", "/public/destination-options")
    g.bump()
    if st7 != 200 or not isinstance(popts, list) or not popts:
        g.add(f"Runtime: GET /public/destination-options gagal (HTTP {st7}) atau kosong — "
              f"form penawaran publik tak punya pilihan master.")
    # --- batch 4: normalisasi lunak jalur publik TERBUKTI di dokumen tersimpan ---
    stb, datab = jreq("POST", "/public/booking", body={
        "name": "Penjaga INV-REF-02 B4", "phone": "0800000441",
        "origin": "bandung", "destination": "bali", "pax": 2,
        "start_datetime": start.isoformat(), "end_datetime": end.isoformat(),
        "message": "Penjaga INV-REF-02 batch 4 (normalisasi publik)"})
    g.bump()
    if not (200 <= stb < 300):
        g.add(f"Runtime: POST /public/booking probe normalisasi gagal HTTP {stb} — jalur publik "
              f"menolak input warisan (harus LUNAK, bukan ditolak).")
    else:
        mdb, mclient = mongo_db()
        if mdb is None:
            g.add("Runtime: tidak bisa membaca DB utk memverifikasi normalisasi tersimpan.")
        else:
            bdoc = mdb["bookings"].find_one({"id": (datab or {}).get("id")}) or {}
            if bdoc.get("destination") != "Bali" or bdoc.get("origin") != "Bandung":
                g.add(f"Runtime: booking publik tersimpan TANPA nama kanonik "
                      f"(origin={bdoc.get('origin')!r}, destination={bdoc.get('destination')!r}) "
                      f"— seharusnya 'Bandung'/'Bali' (normalisasi lunak mati).")
            mclient.close()
    # --- batch 5: kota ngawur di ERP → 400; selector kota tersedia ---
    st8, data8 = jreq("POST", "/customers", tok,
                      {"name": "Penjaga INV-REF-02 B5", "phone": "0800000551",
                       "city": "KotaNgawur Penjaga INV-REF-02"})
    g.bump()
    if st8 == 400:
        detail = str((data8 or {}).get("detail") or "").lower()
        if "kota" not in detail and "master" not in detail:
            g.add(f"Runtime: kota ngawur ditolak karena alasan LAIN ('{detail[:80]}') — "
                  f"validasi master kota tidak terbukti bekerja.")
    elif 200 <= st8 < 300:
        g.add("Runtime: POST /customers MENERIMA kota di luar master (INV-REF-02 b5) — "
              "dokumen uji dibersihkan.")
    else:
        g.add(f"Runtime: respons tak terduga HTTP {st8} untuk kota ngawur (harus 400).")
    st9, ctys = jreq("GET", "/cities", tok)
    g.bump()
    if st9 != 200 or not isinstance(ctys, list) or not ctys:
        g.add(f"Runtime: GET /cities gagal (HTTP {st9}) atau kosong — selector kota FE "
              f"tak punya pilihan.")


def main() -> int:
    g = Guard("INV-REF-02", "Destinasi booking = relasi ke master destinations (bukan teks bebas)")
    static_checks(g)
    tok = login()
    if not tok:
        g.bump()
        g.add("Runtime: gagal login akun demo — probe runtime tidak berjalan (bukan skip senyap).")
    else:
        try:
            runtime_checks(g, tok)
        finally:
            purge_guard_bookings()
    return g.finish()


if __name__ == "__main__":
    sys.exit(main())
