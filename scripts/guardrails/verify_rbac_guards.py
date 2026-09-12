#!/usr/bin/env python3
"""INV-RBAC-01/02/03/04 \u2014 Penegakan RBAC berlapis (route FE + endpoint BE + sinkron matrix 2-arah).

Kelas bug yang dicegah: O-1 RBAC leakage (Putaran 11: driver bisa buka modul owner/ops via URL)
dan RBAC-CAL-01 (E28: 'calendar' ada di allowlist driver + section-nya TIDAK dideklarasikan di
SSOT backend, sehingga endpoint kalender hanya ber-auth tanpa RBAC \u2192 driver 200 OK).

  INV-RBAC-01 (FE route guard): tiap <Route> modul ERP di frontend/src/App.js WAJIB dibungkus
     <RoleGuard> (kecuali 'dashboard' yang boleh semua peran). Route baru tanpa guard => MERAH.
  INV-RBAC-02 (BE enforcement): router sensitif (owner/ops-only) WAJIB memakai
     require_section / require_role. Anchor anti-regresi bila guard dihapus.
  INV-RBAC-03 (matrix sync): ROLE_MENU_ALLOWLIST (FE) tidak boleh mengekspos modul terlarang
     ke driver/ops (drift SSOT \u2192 kebocoran seperti O-1).
  INV-RBAC-04 (sinkron 2-arah FE\u2194BE): setiap section di FE (`ROLE_MENU_ALLOWLIST`/`PAGE_META`)
     WAJIB dideklarasikan di `backend/permissions_config.SECTION_ACCESS`, dan himpunan peran-nya
     WAJIB IDENTIK di kedua sisi. Menutup akar RBAC-CAL-01: daftar `FORBIDDEN` yang di-hardcode
     tak pernah menyebut modul BARU, sehingga modul baru bocor diam-diam. Kini SSOT-nya matriks
     backend (yang juga dipakai `require_section`), bukan ingatan penulis guardrail.
  INV-RBAC-05 (cakupan data row-level): endpoint daftar/detail milik-sendiri WAJIB memakai
     penyaring `services/rbac_scope.py`. Menutup RBAC-SCOPE: `require_section` membuka pintu
     modul, tapi query tanpa filter tetap mengembalikan SELURUH baris (driver melihat semua
     booking + nama pelanggan + nominal, padahal SSOT '\U0001f441\ufe0f trip miliknya').
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from _common import BACKEND, FRONTEND, Guard  # noqa: E402

sys.path.insert(0, str(BACKEND))
from permissions_config import ROLES, SECTION_ACCESS, canonical_section  # noqa: E402

EXEMPT_ROUTES = {"dashboard"}  # boleh diakses semua peran \u2192 guard opsional

# Router owner/ops-only yang WAJIB menegakkan require_section/require_role.
SENSITIVE_ROUTERS = [
    "settings", "users", "audit_logs", "automation", "dispatch", "finance", "quotations",
    "customers", "content", "reports", "partners", "inbox", "subcharters", "growth",
    "leads", "campaigns", "broadcasts", "analytics", "payroll", "invoices", "expenses", "payments",
]

# Modul yang TERLARANG per peran (turunan docs/05_NAVIGATION_MAP.md \u2014 SSOT).
FORBIDDEN = {
    "ops_admin": ["users", "settings", "auditlog", "landing", "tracking", "integrations"],
    "marketing_admin": ["finance", "reports", "users", "settings", "auditlog", "bookings",
                        "calendar", "dispatch", "vehicles", "drivers", "gps", "maintenance",
                        "partners", "quotations", "driver-workspace", "automation"],
    "driver": ["dispatch", "calendar", "partners", "customers", "crm", "quotations", "inbox",
               "automation", "finance", "reports", "cms", "users", "settings", "auditlog",
               "ads", "landing", "tracking", "integrations"],
}

# Section FE yang sengaja TIDAK punya padanan di SECTION_ACCESS (harus eksplisit + beralasan).
# Kosong = semua modul FE wajib dideklarasikan di SSOT backend.
ALLOW_FE_ONLY_SECTIONS = set()

# Endpoint "milik-sendiri" yang WAJIB disaring row-level (INV-RBAC-05).
SCOPE_REQUIREMENTS = {
    "bookings.py": ["scope_bookings_query", "can_view_booking"],
    "drivers.py": ["scope_drivers_query", "can_view_driver"],
}


def parse_allowlist(js: str, role: str):
    m = re.search(r"^\s*" + role + r"\s*:\s*\[([^\]]*)\]", js, re.MULTILINE)
    if not m:
        return None
    return set(re.findall(r'"([^"]+)"', m.group(1)))


def parse_page_meta(js: str):
    m = re.search(r"PAGE_META\s*=\s*\{(.*?)\n\};", js, re.DOTALL)
    if not m:
        return set()
    return set(re.findall(r'^\s*"?([a-z0-9_-]+)"?\s*:\s*\{', m.group(1), re.MULTILINE))


def main() -> int:
    g = Guard("INV-RBAC-01/02/03/04/05", "RBAC berlapis: route FE + endpoint BE + sinkron matrix 2-arah + cakupan data")

    # ---- INV-RBAC-01: FE route guard ----
    app = (FRONTEND / "src" / "App.js").read_text()
    nav = (FRONTEND / "src" / "config" / "navigationConfig.js").read_text()
    owner_allow = parse_allowlist(nav, "owner") or set()
    routes = re.findall(r'<Route\s+path="([^"]+)"\s+element=\{(.*?)\}\s*/>', app, re.DOTALL)
    for path, element in routes:
        if path not in owner_allow:
            continue  # hanya modul ERP ber-SSOT yang dijaga
        if path in EXEMPT_ROUTES:
            continue
        g.bump()
        if "RoleGuard" not in element:
            g.add(f"FE route '/app/{path}' TIDAK dibungkus <RoleGuard> di App.js \u2192 bisa diakses via URL oleh peran mana pun. "
                  f"Bungkus: element={{<RoleGuard section=\"{path}\">...</RoleGuard>}}.")

    # Anchor E28: kedua penjaga FE (AppShell terpusat + RoleGuard per-route) WAJIB memakai SSOT
    # perilaku penolakan `@/lib/accessControl`. Sebelumnya logikanya diduplikasi dan AppShell
    # dieksekusi lebih dulu, sehingga perbaikan UX di RoleGuard tak pernah terlihat.
    for fname in ("AppShell.jsx", "RoleGuard.jsx"):
        fp = FRONTEND / "src" / "components" / "app" / fname
        g.bump()
        if not fp.exists():
            g.add(f"FE '{fname}' tidak ditemukan — penjaga RBAC frontend hilang.")
            continue
        if "lib/accessControl" not in fp.read_text():
            g.add(f"FE '{fname}' tidak memakai SSOT `@/lib/accessControl` (isDenied/roleHome/useDeniedNotice) "
                  f"\u2192 perilaku penolakan RBAC berpotensi berbeda antar-penjaga (pesan/tujuan pengalihan "
                  f"tak konsisten, seperti bug drift E28).")

    # ---- INV-RBAC-02: BE enforcement ----
    for r in SENSITIVE_ROUTERS:
        fp = BACKEND / "routers" / f"{r}.py"
        if not fp.exists():
            continue
        g.bump()
        src = fp.read_text()
        if not re.search(r"require_section|require_role", src):
            g.add(f"BE router '{r}.py' (sensitif) TIDAK memakai require_section/require_role \u2192 RBAC backend bocor.")

    # ---- INV-RBAC-03: matrix sync (FE tak boleh ekspos modul terlarang) ----
    for role, forbidden in FORBIDDEN.items():
        allow = parse_allowlist(nav, role)
        g.bump()
        if allow is None:
            g.add(f"ROLE_MENU_ALLOWLIST tak punya entri peran '{role}' \u2014 tak bisa verifikasi drift.")
            continue
        leaked = sorted(set(forbidden) & allow)
        if leaked:
            g.add(f"DRIFT SSOT: peran '{role}' diberi akses modul TERLARANG {leaked} di ROLE_MENU_ALLOWLIST (navigationConfig.js). "
                  f"Hapus dari allowlist (rujuk docs/05_NAVIGATION_MAP.md).")

    # ---- INV-RBAC-04: sinkron 2-arah FE (ROLE_MENU_ALLOWLIST) <-> BE (SECTION_ACCESS) ----
    # Akar RBAC-CAL-01: modul BARU ('calendar') tak pernah masuk daftar FORBIDDEN dan tak
    # dideklarasikan di SECTION_ACCESS -> lolos INV-RBAC-03 sekaligus bebas RBAC di backend.
    # Penjaga ini memaksa: setiap section FE ADA di SSOT backend & himpunan peran-nya IDENTIK.
    fe_sections = set(parse_page_meta(nav))
    fe_allow = {}
    for role in ROLES:
        a = parse_allowlist(nav, role)
        fe_allow[role] = a if a is not None else set()
        fe_sections |= fe_allow[role]
    fe_sections -= ALLOW_FE_ONLY_SECTIONS

    for section in sorted(fe_sections):
        canon = canonical_section(section)
        g.bump()
        if canon not in SECTION_ACCESS:
            g.add(f"SSOT TIDAK LENGKAP: modul FE '{section}' tidak dideklarasikan di "
                  f"backend/permissions_config.SECTION_ACCESS \u2192 require_section('{section}') akan selalu 403 "
                  f"dan endpoint modul itu rawan hanya ber-auth tanpa RBAC (kelas bug RBAC-CAL-01). "
                  f"Tambahkan section '{canon}' beserta himpunan peran-nya.")
            continue
        be_roles = set(SECTION_ACCESS[canon])
        for role in ROLES:
            g.bump()
            fe_ok = section in fe_allow.get(role, set())
            be_ok = role in be_roles
            if fe_ok and not be_ok:
                g.add(f"DRIFT FE\u2192BE: peran '{role}' melihat menu '{section}' di FE, tapi backend MELARANG "
                      f"(SECTION_ACCESS['{canon}']={sorted(be_roles)}). Menu tampil lalu API 403 = UX rusak / RBAC ambigu. "
                      f"Selaraskan navigationConfig.js atau permissions_config.py.")
            elif be_ok and not fe_ok:
                g.add(f"DRIFT BE\u2192FE: backend MENGIZINKAN peran '{role}' pada section '{canon}', tapi FE tidak "
                      f"menampilkannya di ROLE_MENU_ALLOWLIST['{role}'] \u2192 hak akses tersembunyi / matriks tak konsisten. "
                      f"Selaraskan kedua sisi (SSOT: docs/05_NAVIGATION_MAP.md \u00a73).")

    # ---- INV-RBAC-05: cakupan data row-level (anchor anti-regresi) ----
    # Kelas RBAC-SCOPE: modul boleh dibuka driver, TAPI barisnya wajib disaring ke miliknya.
    scope_mod = BACKEND / "services" / "rbac_scope.py"
    g.bump()
    if not scope_mod.exists():
        g.add("services/rbac_scope.py HILANG \u2192 penyaring cakupan data (row-level) driver tak ada. "
              "Tanpa itu driver melihat seluruh booking/driver armada (kelas bug RBAC-SCOPE).")
    else:
        for fname, needles in SCOPE_REQUIREMENTS.items():
            fp = BACKEND / "routers" / fname
            if not fp.exists():
                continue
            src = fp.read_text()
            for needle in needles:
                g.bump()
                # Cek PEMANGGILAN nyata (`await needle(`), bukan sekadar baris import —
                # anchor lemah "needle in src" pernah lolos saat call-nya dihapus.
                if not re.search(r"await\s+" + needle + r"\s*\(", src):
                    g.add(f"BE router '{fname}' tidak MEMANGGIL `await {needle}(...)` dari services/rbac_scope.py \u2192 "
                          f"endpoint daftar/detail berpotensi mengembalikan baris milik peran lain "
                          f"(SSOT docs/05_NAVIGATION_MAP.md \u00a73: driver = trip/profil miliknya).")

    return g.finish()


if __name__ == "__main__":
    sys.exit(main())
