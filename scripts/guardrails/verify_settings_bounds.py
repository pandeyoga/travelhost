#!/usr/bin/env python3
"""INV-SET-01 — Tarif pricing/settings WAJIB tervalidasi (tolak negatif/absurd/non-numerik → 4xx).

Kelas bug dicegah: SET-1 — nilai tarif di `settings.pricing_rules`/`pricing_defaults` dipakai
langsung dalam perkalian harga (services/pricing.py) tanpa validasi → nilai NEGATIF menghasilkan
harga negatif, `dp_percent`>100 → DP melebihi total, non-numerik → 0 senyap. Pertahanan: validasi
di titik-tulis `PATCH /settings` → 400 dgn pesan jelas.

STATIK (selalu): pastikan `_validate_pricing` masih terpasang di `routers/settings.py`.
RUNTIME (bila backend hidup): PATCH /settings dgn tarif buruk → 400 (bukan 200 senyap / 5xx);
tarif valid → 200 (jalur normal tak rusak).
"""
import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(__file__))
from _common import Guard, G, R, X, BACKEND  # noqa: E402

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
    s = (BACKEND / "routers" / "settings.py").read_text(encoding="utf-8", errors="ignore")
    g.bump()
    if "_validate_pricing" not in s:
        g.add("routers/settings.py: `_validate_pricing` hilang → tarif tak divalidasi (SET-1 terbuka lagi).")


def runtime_probe(g: Guard, tok: str):
    st, txt = req("GET", "/settings", tok)
    current = {}
    try:
        current = json.loads(txt).get("pricing_rules") or {}
    except Exception:
        pass

    # (label, payload, expect) — expect: '4xx' harus ditolak, '2xx' harus lolos.
    cases = [
        ("day_rate negatif", {"pricing_rules": {"default_day_rate": -1000}}, "4xx"),
        ("driver_fee negatif", {"pricing_rules": {"driver_fee_per_day": -1}}, "4xx"),
        ("dp_percent > 100", {"pricing_rules": {"dp_percent": 150}}, "4xx"),
        ("dp_percent negatif", {"pricing_defaults": {"dp_percent": -5}}, "4xx"),
        ("fuel_per_km non-numerik", {"pricing_rules": {"fuel_per_km": "gratis"}}, "4xx"),
        ("min_rental_hours negatif", {"pricing_defaults": {"min_rental_hours": -3}}, "4xx"),
        # jalur normal: kirim balik pricing_rules valid saat ini → tak boleh rusak.
        ("pricing_rules valid (no-op)", {"pricing_rules": current or {"dp_percent": 30}}, "2xx"),
    ]
    for label, payload, expect in cases:
        st, txt = req("PATCH", "/settings", tok, payload)
        g.bump()
        if st >= 500:
            g.add(f"SET-1: '{label}' → HTTP {st} (5xx!). Validasi harus 4xx, bukan crash. Resp: {txt[:140]}")
            mark = R + "5XX" + X
        elif expect == "4xx" and not (400 <= st < 500):
            g.add(f"SET-1: '{label}' → HTTP {st} (harusnya 4xx ditolak; tarif buruk tersimpan senyap).")
            mark = R + "BAD" + X
        elif expect == "2xx" and not (200 <= st < 300):
            g.add(f"SET-1: '{label}' → HTTP {st} (jalur normal tarif valid gagal — regresi).")
            mark = R + "BAD" + X
        else:
            mark = G + "ok" + X
        print(f"    [{mark}] {label}: HTTP {st}")


def main() -> int:
    g = Guard("INV-SET-01", "Tarif pricing/settings tervalidasi (tolak negatif/absurd/non-numerik)")
    static_checks(g)
    tok = login()
    if tok:
        runtime_probe(g, tok)
    else:
        print(f"    {G}(backend/login tak tersedia — probe RUNTIME dilewati; cek STATIK tetap berlaku){X}")
    return g.finish()


if __name__ == "__main__":
    sys.exit(main())
