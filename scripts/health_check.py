#!/usr/bin/env python3
"""
health_check.py — Automated Health Check
========================================
Verifikasi endpoint kritis: cek ISI (bukan hanya status 200).
Kontrak: login → {"token": "..."}; list → ARRAY langsung.
Usage: cd /app && python scripts/health_check.py
Exit 1 jika ada FAIL.
"""
import asyncio, os, sys
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent
try:
    from dotenv import load_dotenv; load_dotenv(ROOT / "backend" / ".env")
except Exception: pass
try:
    import httpx
except ImportError:
    os.system("pip install httpx -q"); import httpx

API = os.environ.get("API_BASE", "http://localhost:8001").rstrip("/")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "owner@demo.local")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "demo12345")
G, Y, R, C, X, B = "\033[92m", "\033[93m", "\033[91m", "\033[96m", "\033[0m", "\033[1m"

# (path, min_items, desc) min_items=-1 → cek status saja
CRITICAL_ENDPOINTS = [
    ("/api/", -1, "Health root"),
    ("/api/auth/me", -1, "Auth: current user"),
    ("/api/dashboard", -1, "Dashboard metrics"),
    ("/api/vehicles", 0, "Master: vehicles"),
    ("/api/drivers", 0, "Master: drivers"),
    ("/api/customers", 0, "Master: customers"),
    ("/api/bookings", 0, "Bookings"),
    ("/api/payments", 0, "Finance: payments"),
    ("/api/maintenance", 0, "Maintenance records"),
    ("/api/conversations", 0, "CRM Inbox: conversations"),
    ("/api/notifications", 0, "Notification center"),
    ("/api/leads", 0, "CRM: leads"),
    ("/api/users", 1, "Admin: users"),
]


def extract_count(data):
    if isinstance(data, list): return len(data)
    if isinstance(data, dict):
        for k in ("items", "data", "rows", "results"):
            if isinstance(data.get(k), list): return len(data[k])
        return -1
    return -1


async def get_token(client):
    try:
        r = await client.post(f"{API}/api/auth/login",
                              json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=15)
        if r.status_code == 200:
            return r.json().get("token")
        print(f"{R}  LOGIN GAGAL HTTP {r.status_code}: {r.text[:160]}{X}")
    except Exception as e:
        print(f"{R}  LOGIN ERROR: {e}{X}")
    return None


async def check(client, token, path, mn, desc):
    h = {"Authorization": f"Bearer {token}"}
    try:
        r = await client.get(f"{API}{path}", headers=h, timeout=15)
        sc = r.status_code
        if sc in (401, 403): return ("FAIL", f"Auth error HTTP {sc}")
        if sc >= 500: return ("FAIL", f"Server error HTTP {sc} — {r.text[:80]}")
        if sc == 404: return ("FAIL", "HTTP 404")
        if mn == -1: return ("PASS" if sc < 400 else "FAIL", "OK")
        data = r.json(); n = extract_count(data)
        if sc >= 400: return ("FAIL", f"HTTP {sc}")
        if n == 0 or (n != -1 and n < mn): return ("WARN", f"{n} items (perlu seed?)")
        return ("PASS", f"{n} items")
    except httpx.TimeoutException: return ("FAIL", "TIMEOUT")
    except Exception as e: return ("FAIL", str(e)[:120])


async def run():
    print(f"\n{B}{'='*60}{X}\n  HEALTH CHECK  (API: {API})\n  {datetime.now():%Y-%m-%d %H:%M:%S}\n{B}{'='*60}{X}")
    async with httpx.AsyncClient(follow_redirects=True) as client:
        token = await get_token(client)
        if not token:
            print(f"{R}FATAL: tidak bisa login (backend up? sudah di-seed?).{X}"); return 1
        print(f"{G}  ✓ Login berhasil\n{X}")
        p = w = f = 0
        for path, mn, desc in CRITICAL_ENDPOINTS:
            tag, detail = await check(client, token, path, mn, desc)
            color = {"PASS": G, "WARN": Y, "FAIL": R}[tag]
            print(f"  {color}[{tag}]{X} {path:<34} {color}{detail}{X}")
            p += tag == "PASS"; w += tag == "WARN"; f += tag == "FAIL"
            await asyncio.sleep(0.03)
    print(f"\n{B}{'='*60}{X}\n  {G}PASS {p}{X} | {Y}WARN {w}{X} | {R}FAIL {f}{X}\n{B}{'='*60}{X}")
    return 1 if f else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(run()))
