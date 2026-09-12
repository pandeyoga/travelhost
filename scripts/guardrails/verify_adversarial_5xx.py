#!/usr/bin/env python3
"""INV-5XX-01 \u2014 Endpoint TIDAK boleh 5xx pada input adversarial (harus 2xx/4xx).

Kelas bug yang dicegah: crash 500 pada input tak wajar (Putaran 11: EXPORT-1 PDF markup,
R6-4 kriteria segmen invalid, R6-5 field angka non-numerik) + generalisasi (string super panjang,
unicode/null, tipe salah). Runtime: login owner, tembak payload adversarial, assert status < 500.
Input buruk = tanggung jawab client (4xx), BUKAN server error (5xx).
"""
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(__file__))
from _common import Guard, G, R, X, purge_guard_artifacts  # noqa: E402

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
            return resp.status, resp.read(2000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read(2000).decode("utf-8", "replace")
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


def main() -> int:
    g = Guard("INV-5XX-01", "Tidak ada 5xx pada input adversarial (harus 2xx/4xx)")
    tok = login()
    if not tok:
        g.add("Tidak bisa login owner@demo.local \u2014 seed DB dulu (python scripts/seed_data.py).")
        return g.finish()

    BIG = "A" * 60000
    WEIRD = "x <b>&</b> <script> \u0000 \ud83d\ude00 \u202e rtl"

    # (label, method, path, body, followups)
    cases = []

    # R6-5: field angka CMS diisi non-numerik
    cases.append(("CMS destinations lat non-numerik", "POST", "/content/destinations",
                  {"name": "Penjaga INV-5XX Destinasi", "slug": "penjaga-inv5xx-1", "lat": "abc", "lng": "xyz"}))
    cases.append(("CMS packages price_from non-numerik", "POST", "/content/packages",
                  {"name": "Penjaga INV-5XX Paket", "slug": "penjaga-inv5xx-2", "price_from": "gratis", "days": "banyak"}))

    # negative-value \u2192 harus 422 (bukan 5xx)
    cases.append(("expense amount negatif", "POST", "/expenses",
                  {"category": "bbm", "amount": -99999}))
    cases.append(("booking base_price negatif", "POST", "/bookings",
                  {"customer_id": "x", "vehicle_id": "y",
                   "start_datetime": "2030-01-01T10:00:00Z", "end_datetime": "2030-01-02T10:00:00Z",
                   "base_price": -5000}))

    # string super panjang + unicode/null
    cases.append(("customer nama super panjang", "POST", "/customers",
                  {"name": BIG, "phone": "0800000501"}))
    cases.append(("lead pesan unicode/null", "POST", "/leads",
                  {"customer_name": "Penjaga INV-5XX " + WEIRD, "message": WEIRD, "pax": 1}))

    for c in cases:
        label, method, path, body = c
        st, txt = req(method, path, tok, body)
        g.bump()
        mark = G + "ok" + X if 0 <= st < 500 else R + "5XX" + X
        print(f"    [{mark}] {label}: HTTP {st}")
        if st >= 500:
            g.add(f"{label} \u2192 HTTP {st} (5xx!). Endpoint harus menolak input buruk dgn 4xx, bukan crash. Resp: {txt[:160]}")

    # EXPORT-1: buat quotation berisi markup lalu render PDF
    st, txt = req("POST", "/quotations", tok,
                  {"customer_name": "Penjaga INV-5XX " + WEIRD, "destination": "Bali <&>", "notes": "a & b < c > d",
                   "items": [{"label": "Sewa <&> unit", "amount": 100000}]})
    g.bump()
    if 0 <= st < 500:
        try:
            qid = json.loads(txt).get("id")
        except Exception:
            qid = None
        if qid:
            pst, ptxt = req("GET", f"/quotations/{qid}/pdf", tok)
            print(f"    [{G + 'ok' + X if 0 <= pst < 500 else R + '5XX' + X}] EXPORT-1 quotation PDF markup: HTTP {pst}")
            if pst >= 500:
                g.add(f"EXPORT-1: PDF penawaran dgn markup \u2192 HTTP {pst} (5xx!). Escape teks user sebelum Paragraph reportlab.")
    else:
        print(f"    [{G + 'ok' + X}] quotation create markup: HTTP {st} (ditolak berjenjang, bukan 5xx)")

    # R6-4: segmen kriteria malformed \u2192 preview
    st, txt = req("POST", "/crm/segments", tok,
                  {"name": "Penjaga INV-5XX Segmen", "audience": "customer",
                   "criteria": {"and": "bukan-list", "$weird": {"op": "??", "value": [1, 2]}}})
    g.bump()
    if 0 <= st < 500:
        try:
            sid = json.loads(txt).get("id")
        except Exception:
            sid = None
        if sid:
            pst, ptxt = req("GET", f"/crm/segments/{sid}/preview", tok)
            print(f"    [{G + 'ok' + X if 0 <= pst < 500 else R + '5XX' + X}] R6-4 segment preview malformed: HTTP {pst}")
            if pst >= 500:
                g.add(f"R6-4: preview segmen kriteria invalid \u2192 HTTP {pst} (5xx!). Bungkus resolve_segment \u2192 400.")
    else:
        print(f"    [{G + 'ok' + X}] segment create malformed: HTTP {st} (ditolak berjenjang, bukan 5xx)")

    # INV-CLEAN-01 — penjaga ini SENGAJA membuat dokumen bernilai aneh (itu intinya), jadi
    # dokumen + side-effect-nya WAJIB dihapus. Tanpa ini, lead/penawaran berisi karakter NUL
    # dan segmen "Penjaga INV-5XX" menetap di CRM pengguna (bagian dari BUG-0127).
    purge_guard_artifacts(verbose=True)

    return g.finish()


if __name__ == "__main__":
    sys.exit(main())
