"""Cleanup data uji sesi RC (jalankan manual): batalkan booking uji + verifikasi tarif unit."""
import os

import requests
from dotenv import dotenv_values

BASE = (os.environ.get("REACT_APP_BACKEND_URL")
        or dotenv_values("/app/frontend/.env").get("REACT_APP_BACKEND_URL")).rstrip("/")
s = requests.Session()
s.headers.update({"Content-Type": "application/json"})
r = s.post(f"{BASE}/api/auth/login", json={"email": "owner@demo.local", "password": "demo12345"}, timeout=30)
s.headers.update({"Authorization": f"Bearer {r.json()['token']}"})

data = s.get(f"{BASE}/api/bookings", timeout=30).json()
rows = data.get("items") if isinstance(data, dict) else data
for b in rows:
    notes = (b.get("notes") or "")
    if b.get("status") in ("cancelled", "completed"):
        continue
    if "TEST_" in notes or b.get("code") == "BK-0074":
        res = s.post(f"{BASE}/api/bookings/{b['id']}/cancel", json={"reason": "TEST_cleanup"}, timeout=30)
        print("cancel", b.get("code"), res.status_code)

print("--- unit rates ---")
for x in s.get(f"{BASE}/api/pricing/unit-rates", timeout=30).json():
    print(x["code"], x["name"], x.get("day_rate"), x["effective_rate"], x["rate_basis"])
