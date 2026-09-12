#!/usr/bin/env python3
"""
audit_endpoint_sweep.py — GET-endpoint sweep
============================================
Hit SETIAP GET route /api sebagai admin, resolve path param dari data nyata,
catat status + emptiness + error 5xx. Usage: cd /app && python scripts/audit_endpoint_sweep.py
Exit 1 bila ada 5xx.
"""
import asyncio, os, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
try:
    from dotenv import load_dotenv; load_dotenv(ROOT / "backend" / ".env")
except Exception: pass
sys.path.insert(0, str(ROOT / "backend"))
try:
    import httpx
except ImportError:
    os.system("pip install httpx -q"); import httpx

API = os.environ.get("API_BASE", "http://localhost:8001").rstrip("/")
ADMIN = {"email": os.environ.get("ADMIN_EMAIL", "owner@demo.local"),
         "password": os.environ.get("ADMIN_PASS", "demo12345")}
G, Y, R, B, X = "\033[92m", "\033[93m", "\033[91m", "\033[1m", "\033[0m"
SAMPLES = {}


def get_routes():
    try:
        from server import app
    except Exception as e:
        print(f"{Y}server.app belum bisa di-import ({e}) — skip sweep (Phase 0).{X}"); return None
    out = []
    for r in app.routes:
        methods = getattr(r, "methods", set()) or set()
        path = getattr(r, "path", "")
        if "GET" in methods and path.startswith("/api"): out.append(path)
    return sorted(set(out))


def fill_path(path):
    params = re.findall(r"\{([^}]+)\}", path)
    if not params: return path
    filled = path
    for p in params:
        key = p.lower()
        val = SAMPLES.get(key) or (SAMPLES.get("id") if key.endswith("id") else None)
        if val is None: return None
        filled = filled.replace("{" + p + "}", str(val))
    return filled


async def first_id(client, h, path, field="id"):
    try:
        r = await client.get(API + path, headers=h, timeout=20)
        if r.status_code != 200: return None
        d = r.json(); items = d if isinstance(d, list) else d.get("items", [])
        if isinstance(items, list) and items: return items[0].get(field)
    except Exception: return None
    return None


async def resolve_samples(client, h):
    for key, path in [("vehicle_id", "/api/vehicles"), ("driver_id", "/api/drivers"),
                      ("customer_id", "/api/customers"), ("booking_id", "/api/bookings"),
                      ("lead_id", "/api/leads"), ("trip_id", "/api/trips"),
                      ("id", "/api/vehicles"), ("user_id", "/api/users")]:
        SAMPLES[key] = await first_id(client, h, path)


def count_of(d):
    if isinstance(d, list): return len(d)
    if isinstance(d, dict):
        for k in ("items", "rows", "results"):
            if isinstance(d.get(k), list): return len(d[k])
        return "obj"
    return "?"


async def main():
    routes = get_routes()
    if routes is None: return 0
    async with httpx.AsyncClient(follow_redirects=False) as client:
        try:
            r = await client.post(API + "/api/auth/login", json=ADMIN, timeout=20)
            token = r.json().get("token")
        except Exception as e:
            print(f"{R}Login gagal: {e}{X}"); return 1
        if not token: print(f"{R}Tidak dapat token.{X}"); return 1
        h = {"Authorization": f"Bearer {token}"}
        await resolve_samples(client, h)
        res = {"ok": [], "empty": [], "err5xx": [], "err4xx": [], "skipped": []}
        for path in routes:
            filled = fill_path(path)
            if filled is None: res["skipped"].append(path); continue
            try:
                resp = await client.get(API + filled, headers=h, timeout=30)
                sc = resp.status_code
                if sc >= 500: res["err5xx"].append((path, sc, resp.text[:120]))
                elif sc in (400, 401, 403, 404, 405, 422): res["err4xx"].append((path, sc))
                else:
                    try: c = count_of(resp.json())
                    except Exception: c = "non-json"
                    (res["empty"] if c == 0 else res["ok"]).append((path, c))
            except Exception as e:
                res["err5xx"].append((path, "EXC", str(e)[:120]))
            await asyncio.sleep(0.02)
    print(f"\n{B}ENDPOINT SWEEP — {len(routes)} GET routes{X}")
    print(f"  OK: {len(res['ok'])}  EMPTY: {len(res['empty'])}  5xx: {len(res['err5xx'])}  4xx: {len(res['err4xx'])}  SKIP: {len(res['skipped'])}")
    print(f"\n{R}{B}=== 5xx / EXCEPTIONS (BUG NYATA) ==={X}")
    for p, sc, msg in res["err5xx"]: print(f"  {R}[{sc}] {p}{X}\n        {msg}")
    if not res["err5xx"]: print(f"  {G}none{X}")
    print(f"\n{Y}=== 4xx (review) ==={X}")
    for p, sc in res["err4xx"]: print(f"  [{sc}] {p}")
    return 1 if res["err5xx"] else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
