#!/usr/bin/env python3
"""audit_rbac_sections.py — CEK SILANG matriks RBAC vs perilaku NYATA (report-only).

Latar: testing agent menemukan `GET /api/bookings` menjawab **200** untuk `marketing_admin`
padahal SSOT `backend/permissions_config.SECTION_ACCESS["bookings"] = {owner, ops_admin, driver}`.
Kelas kegagalan ini sama dengan BUG-0107: penulis endpoint memakai `Depends(get_current_user)`
saja, sehingga "pintu modul" tak pernah ditegakkan. Skrip ini menembak satu endpoint GET
perwakilan per section dengan SEMUA peran dan melaporkan setiap penyimpangan.
"""
import json
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8001/api"
ROLES = {"owner": "owner@demo.local", "ops_admin": "ops@demo.local",
         "marketing_admin": "marketing@demo.local", "driver": "driver@demo.local"}
# section -> (metode, path perwakilan)
PROBES = {
    "bookings": ("GET", "/bookings?limit=1"),
    "bookings#detail": ("GET", "/bookings/availability?vehicle_id=x&start_datetime=2026-09-01T00:00:00&end_datetime=2026-09-02T00:00:00"),
    "vehicles": ("GET", "/vehicles"),
    "drivers": ("GET", "/drivers"),
    "customers": ("GET", "/customers"),
    "crm": ("GET", "/leads"),
    "finance": ("GET", "/payments"),
    "reports": ("GET", "/reports/summary"),
    "maintenance": ("GET", "/maintenance"),
    "gps": ("GET", "/gps/live"),
    "media": ("GET", "/media"),
    "landing": ("GET", "/landing/pages"),
    "ads": ("GET", "/ads/overview"),
    "tracking": ("GET", "/tracking/health"),
    "integrations": ("GET", "/integrations"),
    "calendar": ("GET", "/bookings/calendar?month=2026-09"),
    "dispatch": ("GET", "/dispatch/today"),
    "partners": ("GET", "/partners"),
    "quotations": ("GET", "/quotations"),
    "inbox": ("GET", "/conversations"),
    "automation": ("GET", "/automation/rules"),
    "analytics": ("GET", "/analytics/cockpit"),
    "users": ("GET", "/users"),
    "settings": ("GET", "/settings"),
    "audit": ("GET", "/audit-logs"),
}


def req(method, path, token=None):
    r = urllib.request.Request(BASE + path, method=method)
    if token:
        r.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(r, timeout=20) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:  # noqa: BLE001
        return -1


def login(email):
    data = json.dumps({"email": email, "password": "demo12345"}).encode()
    r = urllib.request.Request(BASE + "/auth/login", data=data, method="POST")
    r.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(r, timeout=20) as resp:
        return json.loads(resp.read())["token"]


def main():
    sys.path.insert(0, "/app/backend")
    from permissions_config import SECTION_ACCESS
    tokens = {role: login(email) for role, email in ROLES.items()}
    problems = []
    print(f"{'SECTION':22} {'ENDPOINT':46} " + " ".join(f"{r[:9]:>9}" for r in ROLES))
    for section, (method, path) in PROBES.items():
        base_section = section.split("#")[0]
        allowed = SECTION_ACCESS.get(base_section, set())
        row = []
        for role in ROLES:
            code = req(method, path, tokens[role])
            row.append(code)
            should_allow = role in allowed
            if should_allow and code == 403:
                problems.append(f"OVER-BLOCK {role} → {method} {path} = 403 (section "
                                f"'{base_section}' seharusnya mengizinkan)")
            if not should_allow and code not in (403, 404, -1):
                problems.append(f"BOCOR      {role} → {method} {path} = {code} (section "
                                f"'{base_section}' hanya untuk {sorted(allowed)})")
        print(f"{section:22} {path[:46]:46} " + " ".join(f"{c:>9}" for c in row))
    print()
    if problems:
        print(f"[{len(problems)} PENYIMPANGAN]")
        for p in problems:
            print("  -", p)
        return 1
    print("[OK] Perilaku sesuai matriks SECTION_ACCESS.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
