#!/usr/bin/env python3
"""INV-REF-01 — Referensi (FK) & pilihan (enum) dari luar WAJIB divalidasi server.

Kelas bug yang dicegah (ditemukan lewat audit permintaan user, 2026-08-12)
-------------------------------------------------------------------------
Formulir ERP sudah memakai dropdown yang isinya diambil dari koleksi. Tetapi API-nya sama
sekali tidak memeriksa: 13 endpoint menerima referensi HANTU dan pilihan di luar daftar,
lalu MENYIMPANNYA (HTTP 200). Contoh nyata yang terbukti:

  * `POST /api/vehicles` & `PATCH /api/vehicles` menerima `type="ngawur"` → mesin harga tak
    menemukan tarif tipe itu (unit tanpa harga), label UI menampilkan "Ngawur";
    `status="ngawur"` membocorkan penyaring Tersedia/Perawatan; `ownership="ngawur"` membuat
    unit HILANG dari katalog publik tanpa satu pun pesan galat (publishable_filter menuntut
    `owned`) — "bug hantu" yang tidak mungkin dilacak ops.
  * `POST /api/maintenance` menerima `workshop_id` hantu, `PATCH /api/drivers/{id}` menerima
    `current_vehicle_id` hantu, `POST /api/conversations` menerima `customer_id`/`lead_id`
    hantu, `POST /api/crm/campaigns` menerima `segment_id` hantu → dokumen YATIM; tabel &
    laporan menampilkan "-" abadi dan ops mengira datanya hilang. Kampanye ke segmen hantu
    "sukses" terkirim ke NOL penerima.
  * `POST /api/transfer-routes` menerima `rates={"ngawur": 500000}` padahal docstring-nya
    MENJANJIKAN "hanya tipe armada yang dikenal" → rute tampak bertarif, tak pernah bisa dijual.

RUNTIME (satu-satunya cara jujur menguji ini): tembak endpoint dengan referensi hantu &
pilihan di luar daftar; server WAJIB menolak 4xx berALASAN (atau MENORMALKAN nilainya).
Dokumen apa pun yang lolos langsung dihapus agar tabel ops tetap bersih — dan dilaporkan
sebagai pelanggaran.

Anti hijau-palsu: setiap probe memastikan payload-nya SAH selain field yang diracuni. Bila
sebuah probe ditolak karena alasan LAIN (mis. 422 field wajib kurang), itu dihitung sebagai
pelanggaran "probe tidak sah" — bukan lolos. SKIP != PASS.
"""
import json
import os
import random
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from _common import Guard, G, X, purge_guard_artifacts  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / "backend" / ".env")
except Exception:  # noqa: BLE001
    pass
from pymongo import MongoClient  # noqa: E402

BASE = os.environ.get("GUARD_BASE_URL", "http://127.0.0.1:8001") + "/api"
DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[
    os.environ.get("DB_NAME", "test_database")]
RND = random.randint(100000, 999999)
GHOST = {
    "customers": "cus_ghost000000000", "vehicles": "veh_ghost000000000",
    "drivers": "drv_ghost000000000", "bookings": "bk_ghost0000000000",
    "trips": "trp_ghost000000000", "workshops": "wrk_ghost000000000",
    "partners": "prt_ghost000000000", "segments": "seg_ghost000000000",
    "leads": "led_ghost000000000", "transfer_routes": "trt_ghost000000000",
}


def req(method, path, token=None, body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method)
    r.add_header("Content-Type", "application/json")
    if token:
        r.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(r, timeout=40) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except Exception:  # noqa: BLE001
            return e.code, {}
    except Exception as e:  # noqa: BLE001
        return -1, {"error": str(e)}


def login():
    st, d = req("POST", "/auth/login", body={"email": "owner@demo.local",
                                            "password": "demo12345"})
    return d.get("token") if st == 200 else None


class Prober:
    def __init__(self, guard: Guard, token: str):
        self.g = guard
        self.t = token
        self.cleaned = 0

    def _cleanup(self, collection, doc_id):
        if collection and doc_id:
            self.cleaned += DB[collection].delete_many({"id": doc_id}).deleted_count

    def poison(self, label, method, path, payload, *, collection=None, field=None,
               allowed=None, expect_reject_words=()):
        """Kirim payload beracun. WAJIB ditolak 4xx (atau nilainya dinormalkan)."""
        self.g.bump()
        st, res = req(method, path, self.t, payload)
        if st == -1:
            self.g.add(f"{label}: backend tidak merespons ({res.get('error')})")
            return
        if st >= 500:
            self.g.add(f"{label}: HTTP {st} (5xx) — harus 4xx berALASAN")
            return
        if st in (200, 201):
            doc_id = res.get("id") if isinstance(res, dict) else None
            stored = None
            if field:
                doc = DB[collection].find_one({"id": doc_id}) if (collection and doc_id) else None
                stored = (doc or {}).get(field)
                if allowed is not None and stored in allowed:
                    self._cleanup(collection, doc_id)
                    print(f"    [{G}ok{X}] {label} → dinormalkan menjadi '{stored}'")
                    return
            self._cleanup(collection, doc_id)
            what = f"tersimpan '{stored}'" if field else f"dokumen {doc_id} dibuat"
            self.g.add(f"{label}: HTTP {st} — {what}; referensi/pilihan ngawur DITERIMA "
                       f"(harus 4xx berALASAN)")
            return
        # 4xx — pastikan alasannya memang tentang field yang diracuni (anti hijau-palsu)
        detail = json.dumps(res.get("detail") or res, ensure_ascii=False).lower()
        if expect_reject_words and not any(w.lower() in detail for w in expect_reject_words):
            self.g.add(f"{label}: ditolak HTTP {st} tetapi ALASANNYA lain "
                       f"({detail[:90]}) → probe tidak sah, kelayakan field tak terbukti")
            return
        print(f"    [{G}ok{X}] {label} → HTTP {st} · {detail[:72]}")


def runtime_checks(g: Guard, token: str) -> None:  # noqa: C901
    p = Prober(g, token)
    _, veh = req("GET", "/vehicles", token)
    _, cus = req("GET", "/customers", token)
    _, drv = req("GET", "/drivers", token)
    _, bks = req("GET", "/bookings", token)
    lists = [x if isinstance(x, list) else (x or {}).get("items", []) for x in (veh, cus, drv, bks)]
    vlist, clist, dlist, blist = lists
    if not (vlist and clist and dlist and blist):
        g.bump()
        g.add("data demo kurang (vehicles/customers/drivers/bookings) — jalankan "
              "`python scripts/seed_data.py`; penjaga TIDAK boleh lolos tanpa data.")
        return
    vid, cid, did = vlist[0]["id"], clist[0]["id"], dlist[0]["id"]
    payable = next((b for b in blist if b.get("status") in ("confirmed", "ongoing", "hold")
                    and float(b.get("paid_amount") or 0) < float(b.get("total_amount") or 0)),
                   None)
    start = (datetime.now(timezone.utc) + timedelta(days=210)).replace(microsecond=0)
    end = start + timedelta(days=1)
    d1, d2 = start.date().isoformat(), end.date().isoformat()

    # ---------------- A. REFERENSI HANTU ----------------
    p.poison("booking customer_id hantu", "POST", "/bookings",
             {"customer_id": GHOST["customers"], "vehicle_id": vid,
              "start_datetime": start.isoformat(), "end_datetime": end.isoformat(),
              "origin": "Bandung", "destination": "Bali", "base_price": 1000000},
             collection="bookings", expect_reject_words=("customer", "pelanggan"))
    p.poison("booking vehicle_id hantu", "POST", "/bookings",
             {"customer_id": cid, "vehicle_id": GHOST["vehicles"],
              "start_datetime": start.isoformat(), "end_datetime": end.isoformat(),
              "origin": "Bandung", "destination": "Bali", "base_price": 1000000},
             collection="bookings", expect_reject_words=("armada", "vehicle"))
    p.poison("booking driver_id hantu", "POST", "/bookings",
             {"customer_id": cid, "vehicle_id": vid, "driver_id": GHOST["drivers"],
              "start_datetime": start.isoformat(), "end_datetime": end.isoformat(),
              "origin": "Bandung", "destination": "Bali", "base_price": 1000000},
             collection="bookings", expect_reject_words=("driver", "sopir"))
    p.poison("payment booking_id hantu", "POST", "/payments",
             {"booking_id": GHOST["bookings"], "amount": 10000, "type": "dp"},
             collection="payments", expect_reject_words=("booking", "pesanan"))
    p.poison("expense booking_id hantu", "POST", "/expenses",
             {"booking_id": GHOST["bookings"], "amount": 10000, "category": "bbm",
              "description": "guard"}, collection="expenses",
             expect_reject_words=("booking", "pesanan"))
    p.poison("invoice booking_id hantu", "POST", "/invoices",
             {"booking_id": GHOST["bookings"]}, collection="invoices",
             expect_reject_words=("booking", "pesanan"))
    p.poison("maintenance vehicle_id hantu", "POST", "/maintenance",
             {"vehicle_id": GHOST["vehicles"], "type": "servis", "title": "guard",
              "start_date": d1, "end_date": d2}, collection="maintenance_records",
             expect_reject_words=("armada", "vehicle"))
    p.poison("maintenance workshop_id hantu", "POST", "/maintenance",
             {"vehicle_id": vid, "workshop_id": GHOST["workshops"], "type": "servis",
              "title": "guard", "start_date": d1, "end_date": d2},
             collection="maintenance_records", expect_reject_words=("bengkel", "workshop"))
    p.poison("vehicle partner_id hantu", "POST", "/vehicles",
             {"name": f"Guard Unit {RND}", "plate_number": f"GRD {RND}", "type": "hiace",
              "ownership": "partner", "partner_id": GHOST["partners"], "capacity": 12},
             collection="vehicles", expect_reject_words=("mitra", "partner"))
    p.poison("driver current_vehicle_id hantu (PATCH)", "PATCH", f"/drivers/{did}",
             {"current_vehicle_id": GHOST["vehicles"]},
             expect_reject_words=("armada", "vehicle"))
    p.poison("payout driver_id hantu", "POST", "/payroll/payouts/generate",
             {"driver_id": GHOST["drivers"], "period_start": d1, "period_end": d2},
             collection="driver_payouts", expect_reject_words=("driver", "sopir"))
    p.poison("campaign segment_id hantu", "POST", "/crm/campaigns",
             {"name": f"Guard {RND}", "channel": "wa", "segment_id": GHOST["segments"],
              "message": "guard", "audience": "customer"}, collection="campaigns",
             expect_reject_words=("segmen", "segment"))
    p.poison("share trip_id hantu", "POST", "/shares", {"trip_id": GHOST["trips"]},
             collection="trip_shares", expect_reject_words=("trip",))
    p.poison("conversation customer_id hantu", "POST", "/conversations",
             {"subject": "guard", "channel": "internal", "customer_id": GHOST["customers"]},
             collection="conversations", expect_reject_words=("pelanggan", "customer"))
    p.poison("conversation lead_id hantu", "POST", "/conversations",
             {"subject": "guard", "channel": "internal", "lead_id": GHOST["leads"]},
             collection="conversations", expect_reject_words=("lead",))
    p.poison("public booking route_id hantu", "POST", "/public/booking/submit",
             {"service": "airport_transfer", "vehicle_id": vid,
              "route_id": GHOST["transfer_routes"], "start_datetime": start.isoformat(),
              "name": "Guard Ref", "phone": "081200000009"},
             expect_reject_words=("rute", "route"))

    # ---------------- B. PILIHAN DI LUAR DAFTAR ----------------
    p.poison("user role='dewa' (RBAC)", "POST", "/users",
             {"name": "Guard Role", "email": f"guard.role{RND}@demo.local",
              "password": "demo12345", "role": "dewa"}, collection="users", field="role",
             allowed={"owner", "ops_admin", "marketing_admin", "driver"},
             expect_reject_words=("peran", "role"))
    for field, value, words in (("type", "ngawur", ("tipe", "type")),
                                ("status", "ngawur", ("status",)),
                                ("ownership", "ngawur", ("kepemilikan", "ownership"))):
        p.poison(f"vehicle {field}='ngawur' (POST)", "POST", "/vehicles",
                 {"name": f"Guard {field} {RND}", "plate_number": f"GRD{RND}{field[:2]}",
                  "type": "hiace", "capacity": 10, field: value},
                 collection="vehicles", field=field, allowed=None, expect_reject_words=words)
        p.poison(f"vehicle {field}='ngawur' (PATCH)", "PATCH", f"/vehicles/{vid}",
                 {field: value}, collection=None, expect_reject_words=words)
    p.poison("driver status='ngawur'", "POST", "/drivers",
             {"name": f"Guard Drv {RND}", "phone": f"0814{RND}0", "status": "ngawur"},
             collection="drivers", field="status", expect_reject_words=("status",))
    p.poison("customer type='ngawur'", "POST", "/customers",
             {"name": f"Guard Cust {RND}", "phone": f"0812{RND}1", "type": "ngawur"},
             collection="customers", field="type", expect_reject_words=("jenis", "type"))
    if payable:
        p.poison("payment type='ngawur'", "POST", "/payments",
                 {"booking_id": payable["id"], "amount": 1000, "type": "ngawur"},
                 collection="payments", field="type", expect_reject_words=("jenis", "type"))
        p.poison("payment method='ngawur'", "POST", "/payments",
                 {"booking_id": payable["id"], "amount": 1000, "type": "settlement",
                  "method": "ngawur"}, collection="payments", field="method",
                 expect_reject_words=("metode", "method"))
    else:
        g.bump(2)
        g.add("tidak ada booking yang bisa dibayar pada data demo → probe enum pembayaran "
              "tidak bisa dibuktikan (SKIP != PASS). Jalankan seed_data.py.")
    p.poison("expense category='ngawur'", "POST", "/expenses",
             {"amount": 1000, "category": "ngawur", "description": "guard"},
             collection="expenses", field="category",
             allowed={"bbm", "tol", "uang_jalan", "gaji_driver", "other"},
             expect_reject_words=("kategori", "category"))
    p.poison("lead stage='ngawur'", "POST", "/leads",
             {"customer_name": f"Guard Lead {RND}", "phone": f"0813{RND}2", "stage": "ngawur"},
             collection="leads", field="stage",
             allowed={"new", "contacted", "qualified", "proposal", "won", "lost"},
             expect_reject_words=("stage", "tahap"))
    p.poison("maintenance status='ngawur'", "POST", "/maintenance",
             {"vehicle_id": vid, "type": "servis", "title": "guard", "status": "ngawur",
              "start_date": d1, "end_date": d2}, collection="maintenance_records",
             field="status", allowed={"scheduled", "in_progress", "done", "cancelled"},
             expect_reject_words=("status",))
    p.poison("transfer route rates{'ngawur'}", "POST", "/transfer-routes",
             {"name": f"Guard Route {RND}", "from_label": "Kota Uji",
              "to_label": "Bandara Uji", "code": f"GRD-{RND}",
              "rates": {"ngawur": 500000}}, collection="transfer_routes",
             expect_reject_words=("tipe", "type"))

    if p.cleaned:
        print(f"    [{G}ok{X}] bersih-bersih: {p.cleaned} dokumen uji dihapus "
              f"(tabel ops tetap bersih)")


def main():
    g = Guard("INV-REF-01", "Referensi (FK) & pilihan (enum) dari luar wajib divalidasi server")
    token = login()
    if not token:
        g.bump()
        g.add("login owner@demo.local gagal — penjaga runtime TIDAK boleh dianggap lolos.")
        return g.finish()
    try:
        runtime_checks(g, token)
    finally:
        # INV-CLEAN-01: dokumen utama sudah dihapus `p.cleanup`, tetapi SIDE-EFFECT-nya
        # (percakapan WA mock "Guard Lead …", notifikasi, event, entri audit) tidak — itulah
        # BUG-0127. Mesin bersih-bersih bersama menuntaskan sisanya.
        purge_guard_artifacts(verbose=True)
    return g.finish()


if __name__ == "__main__":
    sys.exit(main())
