#!/usr/bin/env python3
"""verify_patch_inv21.py — verifikasi presisi klaim testing agent:
"PATCH /api/maintenance/{id} tidak re-validasi INV-21".

Hipotesis: test agent membuat perawatan pada `vehicles[0]` lalu mem-PATCH ke window booking
aktif yang armadanya BEDA → tak ada tabrakan → 200 memang BENAR.

Di sini kita paksa SATU armada yang sama:
  1. Ambil booking AKTIF (punya vehicle_id + window).
  2. Buat perawatan pada ARMADA YANG SAMA di window bebas (+60..70 hari) → harus 200.
  3. PATCH window perawatan itu ke window booking tsb → HARUS 400 (INV-21).
  4. PATCH hanya `cost` → harus 200.
  5. Bersihkan.
Juga menguji ulang skenario "armada berbeda" untuk membuktikan 200 itu benar.
"""
from datetime import datetime, timedelta

import requests

BASE = "http://localhost:8001/api"
G, R, Y, X = "\033[92m", "\033[91m", "\033[93m", "\033[0m"
fails = []


def check(label, cond, extra=""):
    print(f"  {G}[OK]{X} {label} {extra}" if cond else f"  {R}[FAIL]{X} {label} {extra}")
    if not cond:
        fails.append(label)


def main():
    tok = requests.post(f"{BASE}/auth/login",
                        json={"email": "owner@demo.local", "password": "demo12345"}, timeout=20).json()["token"]
    H = {"Authorization": f"Bearer {tok}"}
    bookings = requests.get(f"{BASE}/bookings?limit=500", headers=H, timeout=30).json()
    vehicles = requests.get(f"{BASE}/vehicles", headers=H, timeout=30).json()
    active = next((b for b in bookings if b.get("status") in ("hold", "confirmed", "ongoing")
                   and b.get("vehicle_id") and b.get("start_datetime") and b.get("end_datetime")), None)
    assert active, "tidak ada booking aktif"
    bs = datetime.fromisoformat(active["start_datetime"].replace("Z", "+00:00"))
    be = datetime.fromisoformat(active["end_datetime"].replace("Z", "+00:00"))
    clash_start = (bs - timedelta(hours=1)).strftime("%Y-%m-%d")
    clash_end = (be + timedelta(hours=1)).strftime("%Y-%m-%d")
    now = datetime.now(bs.tzinfo)
    free_start = (now + timedelta(days=60)).strftime("%Y-%m-%d")
    free_end = (now + timedelta(days=70)).strftime("%Y-%m-%d")
    print(f"\nBooking acuan: {active['code']} veh={active.get('vehicle_name')} "
          f"({active['vehicle_id'][:12]}…) {clash_start} → {clash_end}")

    # === SKENARIO A: armada SAMA (harus 400 saat digeser ke window booking) ===
    print(f"\n{Y}SKENARIO A — perawatan pada ARMADA SAMA{X}")
    r = requests.post(f"{BASE}/maintenance", headers=H, timeout=30, json={
        "vehicle_id": active["vehicle_id"], "type": "servis", "title": "Uji PATCH INV-21 (armada sama)",
        "scheduled_date": free_start, "start_date": free_start, "end_date": free_end,
        "status": "scheduled", "cost": 150000})
    check("buat perawatan window bebas → 200", r.status_code == 200, f"(got {r.status_code})")
    mid = r.json().get("id") if r.status_code == 200 else None
    if mid:
        r2 = requests.patch(f"{BASE}/maintenance/{mid}", headers=H, timeout=30,
                            json={"start_date": clash_start, "end_date": clash_end})
        body = r2.json() if r2.headers.get("content-type", "").startswith("application/json") else {}
        check("PATCH geser ke window booking aktif → 400", r2.status_code == 400,
              f"(got {r2.status_code}: {str(body.get('detail'))[:90]})")
        check("pesan 400 menyebut kode booking",
              active["code"] in str(body.get("detail", "")), f"detail={str(body.get('detail'))[:90]}")
        # pastikan window TIDAK berubah (penolakan harus atomik)
        cur = requests.get(f"{BASE}/maintenance/{mid}", headers=H, timeout=20).json()
        check("window perawatan tidak berubah setelah 400", cur.get("start_date") == free_start,
              f"(start_date={cur.get('start_date')})")
        r3 = requests.patch(f"{BASE}/maintenance/{mid}", headers=H, timeout=30, json={"cost": 175000})
        check("PATCH field non-window (cost) → 200", r3.status_code == 200, f"(got {r3.status_code})")
        d = requests.delete(f"{BASE}/maintenance/{mid}", headers=H, timeout=20)
        print(f"       cleanup: {d.status_code}")

    # === SKENARIO B: armada BEDA (200 itu BENAR — bukan bug) ===
    other = next((v for v in vehicles if v["id"] != active["vehicle_id"]), None)
    print(f"\n{Y}SKENARIO B — perawatan pada ARMADA BERBEDA ({(other or {}).get('name')}){X}")
    if other:
        r = requests.post(f"{BASE}/maintenance", headers=H, timeout=30, json={
            "vehicle_id": other["id"], "type": "servis", "title": "Uji PATCH INV-21 (armada beda)",
            "scheduled_date": free_start, "start_date": free_start, "end_date": free_end,
            "status": "scheduled", "cost": 150000})
        mid2 = r.json().get("id") if r.status_code == 200 else None
        if mid2:
            r2 = requests.patch(f"{BASE}/maintenance/{mid2}", headers=H, timeout=30,
                                json={"start_date": clash_start, "end_date": clash_end})
            check("PATCH ke window booking milik ARMADA LAIN → 200 (benar, tak ada tabrakan)",
                  r2.status_code == 200, f"(got {r2.status_code})")
            requests.delete(f"{BASE}/maintenance/{mid2}", headers=H, timeout=20)

    print(f"\n{'=' * 60}")
    print(f"  {R}FAIL {len(fails)}{X}" if fails else f"  {G}SEMUA CEK LOLOS{X}")
    for f in fails:
        print(f"   - {f}")


if __name__ == "__main__":
    main()
