#!/usr/bin/env python3
"""INV-STR-01 — Field teks dari luar WAJIB berbatas panjang (`max_length`).

Kelas bug yang dicegah (NYATA, ditemukan sesi ini — BUG-0114)
-------------------------------------------------------------
Penjaga adversarial `verify_adversarial_5xx.py` mengirim `"A" * 60000` ke endpoint tulis dan
hanya memeriksa satu hal: **tidak 5xx**. Semua endpoint memang menjawab 2xx/4xx — jadi gate
HIJAU — tetapi nilainya **TERSIMPAN**: `customers.name` benar-benar berisi 60.000 karakter.
Akibatnya di ERP: satu baris pada tabel Booking melebar sampai kolom lain terdorong keluar
layar; nama itu juga akan masuk PDF invoice/slip gaji dan payload WhatsApp (yang punya batas
4096 karakter) — semuanya rusak TANPA satu pun error di log.

Pelajaran yang dikunci di sini: "tidak 5xx" BUKAN sama dengan "input tervalidasi". Uang sudah
dijaga INV-NUM-01 (`ge=`); teks butuh penjaga sepadan (`max_length=`).

STATIK  : setiap field bertipe `str` dengan NAMA sensitif (identitas/label/teks pendek) di
          `backend/schemas*.py` wajib punya `max_length=` — atau terdaftar di ALLOW_UNBOUNDED
          dengan alasan tertulis. Field baru yang lupa dibatasi → gate MERAH otomatis.
RUNTIME : kirim 60.000 karakter ke 3 permukaan tulis (ERP internal + publik) → WAJIB 4xx
          (bukan 2xx senyap, bukan 5xx); nilai normal tetap 2xx (penjaga tidak over-block).
"""
import ast
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(__file__))
from _common import BACKEND, Guard, G, X, purge_guard_artifacts  # noqa: E402

BASE = os.environ.get("GUARD_BASE_URL", "http://127.0.0.1:8001") + "/api"

# Nama field yang WAJIB berbatas. Semua ini berakhir di tabel, PDF, atau pesan WhatsApp.
SENSITIVE = ("name", "phone", "email", "code", "plate_number", "label", "title", "city",
             "address", "reason", "sender_name", "bank", "origin", "destination",
             "note", "notes", "message", "password", "role", "status", "type",
             "slug", "subject")
# Pengecualian WAJIB beralasan (kosong = tidak ada pengecualian).
ALLOW_UNBOUNDED: dict = {}
BIG = "A" * 60000


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


def login():
    st, data = jreq("POST", "/auth/login",
                    body={"email": "owner@demo.local", "password": "demo12345"})
    return data.get("token") if st == 200 else None


def static_checks(g: Guard):
    files = sorted(BACKEND.glob("schemas*.py"))
    g.bump()
    if not files:
        g.add("tidak ada `backend/schemas*.py` (regresi struktur kontrak?).")
        return
    for path in files:
        src = path.read_text(encoding="utf-8", errors="ignore")
        for node in ast.walk(ast.parse(src)):
            if not isinstance(node, ast.ClassDef):
                continue
            for st in node.body:
                if not (isinstance(st, ast.AnnAssign) and isinstance(st.target, ast.Name)):
                    continue
                ann = ast.unparse(st.annotation)
                if not re.search(r"\bstr\b", ann) or "ict" in ann:
                    continue
                field = st.target.id
                if field not in SENSITIVE:
                    continue
                key = f"{node.name}.{field}"
                g.bump()
                if "max_length" in ast.unparse(st) or key in ALLOW_UNBOUNDED:
                    continue
                g.add(f"{path.name}:{key} bertipe teks TANPA `max_length=` → nilai raksasa "
                      f"tersimpan diam-diam (rusak tabel/PDF/WhatsApp). Tambah "
                      f"`Field(max_length=N)` atau daftarkan di ALLOW_UNBOUNDED + alasan.")


def runtime_checks(g: Guard, tok: str):
    start = (datetime.now(timezone.utc) + timedelta(days=40)).replace(
        hour=7, minute=0, second=0, microsecond=0)
    probes = [
        ("POST", "/customers", tok,
         {"name": BIG, "phone": "0800000301", "type": "individual"},
         "nama customer 60k karakter"),
        ("POST", "/public/quotation",
         None, {"name": BIG, "phone": "0800000302", "destination": "Bali",
                "days": 2, "pax": 4},
         "nama pada permintaan penawaran publik"),
        ("POST", "/public/booking/submit", None,
         {"service": "daily_rental", "vehicle_id": "veh-tidak-ada",
          "start_datetime": start.isoformat(),
          "end_datetime": (start + timedelta(days=1)).isoformat(),
          "pax": 2, "name": BIG, "phone": "0800000303"},
         "nama pada pemesanan online"),
    ]
    for method, path, token, body, what in probes:
        st, data = jreq(method, path, token, body)
        g.bump()
        if 200 <= st < 300:
            g.add(f"{method} {path}: {what} DITERIMA (HTTP {st}) → teks raksasa tersimpan "
                  f"tanpa batas.")
            # Wajib langsung dibuang: kalau tidak, dokumen 60.000 karakter itu MENETAP di
            # ERP pengguna (BUG-0127 — inilah asal customer "AAAA…" yang dikeluhkan user).
            # Terjadi setiap kali `selftest_booking_guards.py` melumpuhkan `max_length`.
            if isinstance(data, dict) and data.get("id") and path == "/customers":
                jreq("DELETE", f"/customers/{data['id']}", tok)
        elif st >= 500 or st < 0:
            g.add(f"{method} {path}: {what} → HTTP {st} (harus 4xx berALASAN, bukan error "
                  f"server).")
        else:
            print(f"    [{G}ok{X}] {what}: ditolak HTTP {st}")

    # Tidak over-block: nilai normal tetap diterima, lalu dibersihkan.
    st, made = jreq("POST", "/customers", tok,
                    {"name": "Penjaga INV-STR-01", "phone": "0800000399",
                     "type": "individual", "city": "Bandung"})
    g.bump()
    if not (200 <= st < 300 and made.get("id")):
        g.add(f"nilai normal ditolak (HTTP {st}) → batas panjang terlalu ketat "
              f"(over-block: pengguna sah tak bisa menyimpan data).")
    else:
        print(f"    [{G}ok{X}] nilai normal tetap diterima (HTTP {st})")
        jreq("DELETE", f"/customers/{made['id']}", tok)


def main() -> int:
    g = Guard("INV-STR-01", "Field teks dari luar wajib berbatas panjang (max_length)")
    static_checks(g)
    tok = login()
    if not tok:
        g.add("tidak bisa login owner@demo.local — gate runtime WAJIB jalan (SKIP != PASS).")
        return g.finish()
    try:
        runtime_checks(g, tok)
    finally:
        # INV-CLEAN-01: apa pun hasilnya, artefak uji + side-effect-nya WAJIB hilang.
        purge_guard_artifacts(verbose=True)
    return g.finish()


if __name__ == "__main__":
    sys.exit(main())
