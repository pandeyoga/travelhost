#!/usr/bin/env python3
"""INV-RBAC-06 — Penegakan RBAC diverifikasi secara RUNTIME (bukan hanya konfigurasi).

Kelas bug dicegah: RBAC-CAL-01 + RBAC-SCOPE (sesi E28).

Kenapa perlu gate RUNTIME padahal sudah ada INV-RBAC-01..05 (statik)?
  Penjaga statik memastikan *konfigurasi* benar (allowlist FE, matriks BE, ada pemanggilan
  penyaring). Tetapi konfigurasi benar TIDAK menjamin *perilaku* benar: satu `Depends`
  tertukar, urutan route salah (`/bookings/{id}` menelan `/bookings/calendar`), atau filter
  row-level dilewati pada cabang tertentu → tetap bocor sementara gate statik hijau.
  Kelas bug aslinya justru lolos begitu: RoleGuard SUDAH terpasang, tapi API mengembalikan 200.

Yang diverifikasi (login driver@demo.local & owner@demo.local):
  A. Pintu modul  : driver -> 403 pada 3 endpoint kalender; owner -> 200 (jalur normal aman).
  B. Cakupan data : driver GET /bookings hanya trip miliknya; GET /drivers hanya profilnya;
                    detail booking/driver milik orang lain -> 403 (bukan 200/404 senyap).
  C. Workspace    : /driver/{my-trips,tasks,summary} tetap 200 (fix tidak boleh over-block).
  D. MATRIKS PENUH: untuk SETIAP section di `permissions_config.SECTION_ACCESS`, satu endpoint
                    perwakilan ditembak dengan SEMUA peran; peran di luar matriks WAJIB 403 dan
                    peran di dalam matriks WAJIB bukan-403. Ditambahkan setelah testing agent
                    menemukan `marketing_admin` mendapat **HTTP 200** pada `GET /api/bookings`
                    (lalu audit menemukan 8 endpoint bocor: bookings, availability, vehicles,
                    drivers, maintenance, gps, quotations, driver-workspace). Akar masalahnya
                    lapis A/B/C hanya pernah menguji peran **driver**: peran BARU
                    (`marketing_admin`, lahir di FASE F) tak pernah diuji terhadap endpoint BACA
                    LAMA yang memakai `Depends(get_current_user)` saja. Karena itu lapis D
                    digerakkan MATRIKS, bukan daftar kasus — dan `SECTION_PROBES` wajib memuat
                    SEMUA section (section baru tanpa probe → gate MERAH, bukan lolos diam-diam).
"""
import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(__file__))
from _common import Guard, G, R, X, ROOT  # noqa: E402

sys.path.insert(0, str(ROOT / "backend"))

BASE = os.environ.get("GUARD_BASE_URL", "http://127.0.0.1:8001") + "/api"
CAL_ENDPOINTS = [
    "/departures/attention?month=2026-08",
    "/bookings/calendar?month=2026-08",
    "/bookings/calendar/export?month=2026-08&format=excel",
]

DEMO_ACCOUNTS = {
    "owner": "owner@demo.local",
    "ops_admin": "ops@demo.local",
    "marketing_admin": "marketing@demo.local",
    "driver": "driver@demo.local",
}

# Satu endpoint GET perwakilan per section. WAJIB lengkap: kunci di sini harus SAMA dengan
# kunci `SECTION_ACCESS` (dicek di bawah), supaya section baru tidak bisa lahir tanpa bukti
# perilaku. Nilai None = section yang MEMANG tidak punya endpoint sendiri + alasannya.
SECTION_PROBES = {
    "ads": "/ads/overview",
    "analytics": "/analytics/summary",
    "audit": "/audit-logs",
    "automation": "/automation/rules",
    "bookings": "/bookings?limit=1",
    "calendar": "/bookings/calendar?month=2026-08",
    "cms": "/content/destinations",
    "crm": "/leads",
    "customers": "/customers",
    "dashboard": "/dashboard",
    "dispatch": "/dispatch/today",
    "driver-workspace": "/driver/my-trips",
    "drivers": "/drivers",
    "finance": "/payments",
    "gps": "/gps/live",
    "inbox": "/conversations",
    "integrations": "/integrations/config",
    "landing": "/landing/pages",
    "maintenance": "/maintenance",
    "masterdata": "/master/destinations",
    "media": "/media",
    "partners": "/partners",
    "quotations": "/quotations",
    "reports": "/reports/summary",
    "sales": None,  # section khusus FE (grup menu penjualan); tak ada endpoint ber-section 'sales'
    "settings": "/settings",
    "tracking": "/tracking/health",
    "users": "/users",
    "vehicles": "/vehicles",
}


def req(method, path, token=None, body=None, timeout=25):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method)
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


def login(email):
    st, txt = req("POST", "/auth/login", body={"email": email, "password": "demo12345"})
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


def main() -> int:
    g = Guard("INV-RBAC-06", "RBAC runtime: pintu modul + cakupan data per peran")

    drv_tok = login("driver@demo.local")
    own_tok = login("owner@demo.local")
    if not drv_tok or not own_tok:
        g.add("Tidak bisa login akun demo (driver/owner) — gate runtime RBAC tak dapat dijalankan. "
              "Jalankan `python scripts/seed_data.py` lalu ulangi (SKIP dilarang: itu hijau-palsu).")
        return g.finish()

    # ---- A. Pintu modul kalender ----
    for ep in CAL_ENDPOINTS:
        g.bump()
        st, _ = req("GET", ep, token=drv_tok)
        if st != 403:
            g.add(f"BOCOR: peran driver mendapat HTTP {st} pada GET {ep} — seharusnya 403. "
                  f"Kalender Keberangkatan = section 'calendar' (owner/ops_admin). "
                  f"Pastikan endpoint memakai Depends(require_section(\"calendar\")).")
        else:
            print(f"    [{G}ok{X}] driver 403 pada {ep}")
        g.bump()
        st_o, _ = req("GET", ep, token=own_tok)
        if st_o != 200:
            g.add(f"REGRESI: owner mendapat HTTP {st_o} pada GET {ep} — seharusnya 200 "
                  f"(perbaikan RBAC tidak boleh memblokir peran yang berhak).")

    # ---- B. Cakupan data row-level ----
    st, txt = req("GET", "/drivers", token=drv_tok)
    own_drivers = as_json(txt, []) or []
    g.bump()
    if st != 200 or len(own_drivers) != 1:
        g.add(f"BOCOR/ANEH: GET /drivers sebagai driver → HTTP {st}, {len(own_drivers)} baris. "
              f"Seharusnya 200 dgn TEPAT 1 baris (profil sendiri) — SSOT docs/05_NAVIGATION_MAP.md §3.")
    own_id = (own_drivers[0].get("id") if own_drivers else None)

    st, txt = req("GET", "/bookings", token=drv_tok)
    drv_bookings = as_json(txt, []) or []
    st_o, txt_o = req("GET", "/bookings", token=own_tok)
    all_bookings = as_json(txt_o, []) or []
    g.bump()
    asing = [b.get("code") for b in drv_bookings if b.get("driver_id") != own_id]
    if asing:
        g.add(f"BOCOR DATA: driver melihat {len(asing)} booking milik sopir lain ({asing[:5]}) pada "
              f"GET /bookings. Wajib disaring lewat services/rbac_scope.scope_bookings_query.")
    g.bump()
    if all_bookings and len(drv_bookings) >= len(all_bookings) and len(all_bookings) > 1:
        g.add(f"BOCOR DATA: driver melihat {len(drv_bookings)} booking, owner {len(all_bookings)} — "
              f"cakupan driver tidak menyempit sama sekali (filter kepemilikan tidak jalan).")
    else:
        print(f"    [{G}ok{X}] cakupan booking: driver {len(drv_bookings)} vs owner {len(all_bookings)}")

    foreign = next((b for b in all_bookings if b.get("driver_id") != own_id), None)
    if foreign:
        g.bump()
        st, _ = req("GET", f"/bookings/{foreign.get('id')}", token=drv_tok)
        if st != 403:
            g.add(f"BOCOR: driver membuka detail booking {foreign.get('code')} milik sopir lain → "
                  f"HTTP {st} (seharusnya 403).")
    st, txt = req("GET", "/drivers", token=own_tok)
    other = next((d for d in (as_json(txt, []) or []) if d.get("id") != own_id), None)
    if other:
        for path in (f"/drivers/{other.get('id')}", f"/drivers/{other.get('id')}/performance"):
            g.bump()
            st, _ = req("GET", path, token=drv_tok)
            if st != 403:
                g.add(f"BOCOR: driver mengakses {path} (profil/kinerja sopir lain) → HTTP {st} "
                      f"(seharusnya 403).")

    # ---- C. Workspace driver tidak boleh ikut terblokir ----
    for path in ("/driver/my-trips", "/driver/tasks", "/driver/summary"):
        g.bump()
        st, _ = req("GET", path, token=drv_tok)
        if st != 200:
            g.add(f"OVER-BLOCK: driver mendapat HTTP {st} pada GET {path} — Ruang Kerja Driver "
                  f"WAJIB tetap dapat diakses peran driver.")

    # ---- D. MATRIKS PENUH: setiap section × setiap peran ----
    section_matrix(g)

    if not g.violations:
        print(f"    {G}Pintu modul + cakupan data + workspace driver + matriks penuh: "
              f"sesuai SSOT.{X}")
    else:
        print(f"    {R}Ada pelanggaran RBAC runtime — lihat daftar di bawah.{X}")
    return g.finish()


def section_matrix(g: Guard):
    """Tembak satu endpoint perwakilan per section dengan SEMUA peran demo."""
    try:
        from permissions_config import SECTION_ACCESS
    except Exception as exc:  # noqa: BLE001
        g.bump()
        g.add(f"tidak bisa membaca SSOT `permissions_config.SECTION_ACCESS` ({exc}) — matriks "
              f"RBAC tak dapat diverifikasi.")
        return
    # D0 — daftar probe WAJIB selengkap matriks (cegah "section baru lolos tanpa bukti").
    g.bump()
    missing = sorted(set(SECTION_ACCESS) - set(SECTION_PROBES))
    extra = sorted(set(SECTION_PROBES) - set(SECTION_ACCESS))
    if missing:
        g.add(f"section tanpa probe perilaku: {missing} → tambahkan endpoint perwakilan di "
              f"SECTION_PROBES (tanpa itu section baru bisa bocor tanpa terdeteksi).")
    if extra:
        g.add(f"probe untuk section yang tidak ada di SECTION_ACCESS: {extra} → daftar usang.")

    tokens = {}
    for role, email in DEMO_ACCOUNTS.items():
        tokens[role] = login(email)
        g.bump()
        if not tokens[role]:
            g.add(f"tidak bisa login akun demo peran {role} ({email}) — matriks tak lengkap "
                  f"(SKIP dilarang).")
    leaks, blocked = [], []
    for section, path in SECTION_PROBES.items():
        if not path:
            continue
        allowed = SECTION_ACCESS.get(section, set())
        codes = {}
        for role, token in tokens.items():
            if not token:
                continue
            st, _ = req("GET", path, token=token)
            codes[role] = st
            g.bump()
            if role in allowed:
                if st == 403:
                    blocked.append(f"{role} → GET {path} = 403 (section '{section}' "
                                   f"seharusnya MENGIZINKAN peran ini)")
            elif st != 403:
                leaks.append(f"{role} → GET {path} = {st} (section '{section}' hanya untuk "
                             f"{sorted(allowed)})")
        # Probe yang 404/-1 untuk SEMUA peran = jalur salah → penjaga jadi hampa.
        g.bump()
        if codes and all(c in (404, -1) for c in codes.values()):
            g.add(f"probe section '{section}' ({path}) menjawab 404/gagal untuk SEMUA peran → "
                  f"jalur usang; perbaiki SECTION_PROBES agar penjaga tidak hampa.")
    for msg in leaks:
        g.add(f"BOCOR MATRIKS: {msg} — endpoint BACA wajib memakai "
              f"Depends(require_section(\"<section>\")), bukan get_current_user saja.")
    for msg in blocked:
        g.add(f"OVER-BLOCK MATRIKS: {msg}")
    if not leaks and not blocked:
        n = sum(1 for p in SECTION_PROBES.values() if p)
        print(f"    [{G}ok{X}] matriks penuh: {n} section × {len(tokens)} peran sesuai "
              f"SECTION_ACCESS (0 bocor, 0 over-block)")


if __name__ == "__main__":
    sys.exit(main())
