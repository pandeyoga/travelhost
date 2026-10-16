#!/usr/bin/env python3
"""
Round 6 — Comprehensive multi-role endpoint sweep + coverage matrix.
- Enumerates ALL routes (every method) from server.app.
- Logs in as owner / ops / driver.
- GET every GET route as owner, ops, driver, and UNAUTH.
- Records a status matrix -> /app/scripts/audit_r6/sweep_matrix.json
- Flags 5xx (real bugs) and RBAC anomalies for later review.
This drives request execution so coverage.py can measure reachable code.
"""
import asyncio, json, os, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
try:
    from dotenv import load_dotenv; load_dotenv(ROOT / "backend" / ".env")
except Exception: pass
sys.path.insert(0, str(ROOT / "backend"))
import httpx

API = os.environ.get("API_BASE", "http://localhost:8001").rstrip("/")
CREDS = {
    "owner": {"email": "owner@demo.local", "password": "demo12345"},
    "ops": {"email": "ops@demo.local", "password": "demo12345"},
    "driver": {"email": "driver@demo.local", "password": "demo12345"},
}
SAMPLES = {}
OUT = Path(__file__).resolve().parent


def get_routes():
    from server import app
    out = []
    for r in app.routes:
        methods = getattr(r, "methods", set()) or set()
        path = getattr(r, "path", "")
        if not path.startswith("/api"):
            continue
        for m in methods:
            if m in ("HEAD", "OPTIONS"):
                continue
            out.append((m, path))
    # unique
    seen = set(); uniq = []
    for m, p in out:
        if (m, p) in seen: continue
        seen.add((m, p)); uniq.append((m, p))
    return sorted(uniq, key=lambda x: (x[1], x[0]))


def fill_path(path):
    params = re.findall(r"\{([^}]+)\}", path)
    if not params:
        return path
    filled = path
    for p in params:
        key = p.lower()
        val = SAMPLES.get(key) or (SAMPLES.get("id") if key.endswith("id") else None)
        if val is None:
            return None
        filled = filled.replace("{" + p + "}", str(val))
    return filled


async def first_id(client, h, path, field="id"):
    try:
        r = await client.get(API + path, headers=h, timeout=20)
        if r.status_code != 200: return None
        d = r.json(); items = d if isinstance(d, list) else d.get("items", [])
        if isinstance(items, list) and items:
            return items[0].get(field)
    except Exception:
        return None
    return None


async def resolve_samples(client, h):
    for key, path in [
        ("vehicle_id", "/api/vehicles"), ("driver_id", "/api/drivers"),
        ("customer_id", "/api/customers"), ("booking_id", "/api/bookings"),
        ("lead_id", "/api/leads"), ("trip_id", "/api/trips"),
        ("id", "/api/vehicles"), ("user_id", "/api/users"),
        ("quotation_id", "/api/quotations"), ("invoice_id", "/api/invoices"),
        ("payment_id", "/api/payments"), ("maintenance_id", "/api/maintenance"),
        ("workshop_id", "/api/workshops"), ("campaign_id", "/api/campaigns"),
        ("segment_id", "/api/growth/segments"), ("partner_id", "/api/partners"),
        ("subcharter_id", "/api/subcharters"), ("conversation_id", "/api/inbox/conversations"),
        ("service_type_id", "/api/service-types"), ("location_id", "/api/locations"),
    ]:
        SAMPLES[key] = await first_id(client, h, path)


async def login(client, creds):
    try:
        r = await client.post(API + "/api/auth/login", json=creds, timeout=20)
        return r.json().get("token")
    except Exception:
        return None


async def main():
    routes = get_routes()
    async with httpx.AsyncClient(follow_redirects=False) as client:
        tokens = {}
        for role, creds in CREDS.items():
            tokens[role] = await login(client, creds)
        owner_h = {"Authorization": f"Bearer {tokens['owner']}"}
        await resolve_samples(client, owner_h)

        get_routes_only = [(m, p) for (m, p) in routes if m == "GET"]
        matrix = []
        five_xx = []
        for m, path in get_routes_only:
            filled = fill_path(path)
            row = {"method": m, "path": path, "filled": bool(filled)}
            if filled is None:
                row["status"] = {r: "SKIP(no-sample)" for r in ["owner", "ops", "driver", "unauth"]}
                matrix.append(row); continue
            statuses = {}
            for role in ["owner", "ops", "driver"]:
                h = {"Authorization": f"Bearer {tokens[role]}"}
                try:
                    resp = await client.get(API + filled, headers=h, timeout=30)
                    statuses[role] = resp.status_code
                    if resp.status_code >= 500:
                        five_xx.append((role, m, path, resp.status_code, resp.text[:160]))
                except Exception as e:
                    statuses[role] = "EXC"; five_xx.append((role, m, path, "EXC", str(e)[:160]))
            # unauth
            try:
                resp = await client.get(API + filled, timeout=30)
                statuses["unauth"] = resp.status_code
                if resp.status_code >= 500:
                    five_xx.append(("unauth", m, path, resp.status_code, resp.text[:160]))
            except Exception as e:
                statuses["unauth"] = "EXC"
            row["status"] = statuses
            matrix.append(row)
            await asyncio.sleep(0.01)

    (OUT / "sweep_matrix.json").write_text(json.dumps({
        "api": API, "total_routes": len(routes),
        "get_routes": len(get_routes_only), "matrix": matrix,
        "five_xx": five_xx, "samples": SAMPLES,
    }, indent=2, default=str))

    # summary
    print(f"TOTAL routes(all methods)={len(routes)} | GET routes={len(get_routes_only)}")
    print(f"5xx/EXC found: {len(five_xx)}")
    for role, m, path, sc, msg in five_xx:
        print(f"  [{role}] {m} {path} -> {sc}  {msg}")
    # RBAC quick view: GET endpoints returning 200 for driver
    driver_200 = [r["path"] for r in matrix if isinstance(r.get("status"), dict) and r["status"].get("driver") == 200]
    unauth_200 = [r["path"] for r in matrix if isinstance(r.get("status"), dict) and r["status"].get("unauth") == 200]
    print(f"\nGET returning 200 for DRIVER: {len(driver_200)}")
    print(f"GET returning 200 for UNAUTH (potential leak): {len(unauth_200)}")
    for p in unauth_200:
        print(f"  UNAUTH-200: {p}")
    return 0

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
