#!/usr/bin/env python3
"""INV-IDENT-01 — Pembuatan identity (customer) harus AMAN-BALAPAN (no duplicate, no 5xx).

Kelas bug dicegah: ID-RACE — dua+ request paralel dgn kontak sama lolos pengecekan
find-then-insert (TOCTOU) → customer GANDA (atau 500 saat index unik dilanggar tanpa handler).
Pertahanan: index UNIK-PARSIAL pada `customers.phone_normalized` (non-kosong) sebagai SSOT +
tangani `DuplicateKeyError` (dedupe/409) di semua jalur tulis.

STATIK (selalu): pastikan index unik dideklarasikan + DuplicateKeyError ditangani di
`routers/customers.py` & `services/identity.py` (cegah fix DIHAPUS diam-diam antar-sesi).
RUNTIME (bila backend hidup): N POST /customers paralel kontak sama → TEPAT 1 dibuat,
sisanya 409, tak ada 5xx, dan hanya 1 customer bernomor itu di DB.
"""
import concurrent.futures
import json
import os
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(__file__))
from _common import Guard, G, R, X, BACKEND, purge_guard_artifacts  # noqa: E402

BASE = os.environ.get("GUARD_BASE_URL", "http://127.0.0.1:8001") + "/api"


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


def login():
    st, txt = req("POST", "/auth/login", body={"email": "owner@demo.local", "password": "demo12345"})
    if st != 200:
        return None
    try:
        return json.loads(txt)["token"]
    except Exception:
        return None


def static_checks(g: Guard):
    server = (BACKEND / "server.py").read_text(encoding="utf-8", errors="ignore")
    g.bump()
    has_idx = ("customers.create_index(" in server and "phone_normalized" in server
               and "unique=True" in server)
    if not has_idx:
        g.add("server.py: index UNIK `customers.phone_normalized` tak ditemukan — ID-RACE tak terjaga di level DB.")
    g.bump()
    if "partialFilterExpression" not in server:
        g.add("server.py: `partialFilterExpression` hilang — nilai phone_normalized kosong akan saling bentrok.")

    cust = (BACKEND / "routers" / "customers.py").read_text(encoding="utf-8", errors="ignore")
    g.bump()
    if "DuplicateKeyError" not in cust:
        g.add("routers/customers.py: `DuplicateKeyError` tak ditangani → create/update customer bisa 500 saat balapan.")

    ident = (BACKEND / "services" / "identity.py").read_text(encoding="utf-8", errors="ignore")
    g.bump()
    if "DuplicateKeyError" not in ident:
        g.add("services/identity.py: `ensure_customer` tak menangani `DuplicateKeyError` → bisa 500/duplikat saat balapan.")


def runtime_probe(g: Guard, tok: str):
    phone = "08" + str(int(time.time() * 1000))[-10:]  # unik per-run
    body = {"name": "Penjaga INV-IDENT " + phone, "phone": phone}
    N = 8

    def fire(_):
        return req("POST", "/customers", tok, body)

    with concurrent.futures.ThreadPoolExecutor(max_workers=N) as ex:
        results = list(ex.map(fire, range(N)))
    statuses = [s for s, _ in results]
    created = sum(1 for s in statuses if s in (200, 201))
    conflict = sum(1 for s in statuses if s == 409)
    server_err = sum(1 for s in statuses if s >= 500)
    print(f"    N={N} POST /customers paralel (kontak sama): 2xx={created} 409={conflict} 5xx={server_err} | {statuses}")

    g.bump()
    if server_err:
        g.add(f"ID-RACE: {server_err}/{N} request → 5xx saat buat customer paralel (harus 409, bukan crash).")
    g.bump()
    if created != 1:
        g.add(f"ID-RACE: {created} customer dibuat utk kontak sama (harus TEPAT 1) — dedupe balapan bocor.")

    # Verifikasi hanya 1 customer bernomor itu di DB + cleanup.
    st, txt = req("GET", "/customers?limit=500", tok)
    g.bump()
    try:
        items = json.loads(txt)
        norm = "+62" + phone[1:]  # 08.. -> +628..
        match = [c for c in items if isinstance(c, dict)
                 and (c.get("phone_normalized") == norm or c.get("phone") == phone)]
        if len(match) != 1:
            g.add(f"ID-RACE: {len(match)} customer bernomor {phone} di DB (harus 1).")
        for c in match:  # cleanup probe
            req("DELETE", f"/customers/{c.get('id')}", tok)
    except Exception as e:  # noqa: BLE001
        g.add(f"ID-RACE: gagal verifikasi jumlah customer ({e}).")


def main() -> int:
    g = Guard("INV-IDENT-01", "Pembuatan identity aman-balapan (no duplicate, no 5xx)")
    static_checks(g)
    tok = login()
    if tok:
        try:
            runtime_probe(g, tok)
        finally:
            purge_guard_artifacts(verbose=True)  # INV-CLEAN-01
    else:
        print(f"    {G}(backend/login tak tersedia — probe RUNTIME dilewati; cek STATIK tetap berlaku){X}")
    return g.finish()


if __name__ == "__main__":
    sys.exit(main())
