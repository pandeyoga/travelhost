"""Helper manual (BUKAN test): siapkan 1 pesanan online berstatus 'pending' agar panel
'Pesanan Website Masuk' bisa diuji di UI, lalu pulihkan mode booking_flow.
Pakai: python tests/_i110_online_pending_setup.py setup|restore
"""
import sys
import uuid

import requests
from dotenv import dotenv_values

BASE = dotenv_values("/app/frontend/.env")["REACT_APP_BACKEND_URL"].rstrip("/")


def login():
    r = requests.post(f"{BASE}/api/auth/login",
                      json={"email": "owner@demo.local", "password": "demo12345"}, timeout=40)
    tok = r.json().get("access_token") or r.json().get("token")
    return {"Authorization": f"Bearer {tok}"}


def set_mode(h, mode):
    r = requests.patch(f"{BASE}/api/settings", headers=h,
                       json={"booking_flow": {"mode": mode}}, timeout=40)
    print("set mode", mode, r.status_code, r.text[:150])


def submit():
    for day in (6, 9, 13, 17, 20, 24, 27):
        s = requests.post(f"{BASE}/api/public/booking/search",
                          json={"service": "daily_rental",
                                "start_datetime": f"2026-11-{day:02d}T09:00:00",
                                "end_datetime": f"2026-11-{day:02d}T19:00:00", "pax": 4}, timeout=60)
        if s.status_code != 200:
            continue
        opts = [o for o in s.json().get("options", []) if o.get("available") is not False]
        if not opts:
            continue
        srch = s.json()["search"]
        uniq = uuid.uuid4().hex[:5]
        r = requests.post(f"{BASE}/api/public/booking/submit",
                          json={"service": "daily_rental", "vehicle_id": opts[0]["vehicle"]["id"],
                                "start_datetime": srch["start_datetime"],
                                "end_datetime": srch["end_datetime"], "pax": 4,
                                "name": f"Penjaga INV-ONL{uniq}", "phone": f"08000008{uniq[:3]}",
                                "origin": "Bandung", "destination": "Jakarta",
                                "idempotency_key": uuid.uuid4().hex}, timeout=90)
        print("submit", r.status_code, r.text[:200])
        if r.status_code == 200:
            return r.json().get("code")
    return None


if __name__ == "__main__":
    h = login()
    if sys.argv[1] == "setup":
        set_mode(h, "ops_approval")
        code = submit()
        print("CODE:", code)
        rows = requests.get(f"{BASE}/api/bookings?limit=300", headers=h, timeout=60).json()
        rows = rows if isinstance(rows, list) else rows.get("items", [])
        mine = [b for b in rows if b.get("code") == code]
        print("status/source:", [(b["status"], b.get("source")) for b in mine])
    else:
        set_mode(h, "hold_dp")
