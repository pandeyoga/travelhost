#!/usr/bin/env python3
"""Round 6C — empirical reproduction of candidate bugs (READ + create test data only).
Report-only: does NOT modify production code. Confirms whether each candidate is real.
"""
import requests, uuid, json, sys
from datetime import datetime, timedelta, timezone

API = "http://localhost:8001/api"
def login(email, pw="demo12345"):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=20)
    return r.json().get("token")

OWN = {"Authorization": f"Bearer {login('owner@demo.local')}"}
def H(t): return {"Authorization": f"Bearer {t}"}

def iso(dt): return dt.isoformat()
now = datetime.now(timezone.utc)
results = {}

print("="*70)
print("R6-2: Negative invoice amount")
try:
    bk = requests.get(f"{API}/bookings", headers=OWN, timeout=20).json()
    bid = bk[0]["id"] if bk else None
    r = requests.post(f"{API}/invoices", headers=OWN, json={"booking_id": bid, "amount": -5000000}, timeout=20)
    print("  POST /invoices amount=-5,000,000 ->", r.status_code)
    if r.status_code == 200:
        print("  RESULT amount stored =", r.json().get("amount"), " <-- BUG if negative")
        results["R6-2"] = ("BUG" if r.json().get("amount", 0) < 0 else "ok")
    else:
        results["R6-2"] = f"rejected({r.status_code})"
except Exception as e:
    print("  ERR", e); results["R6-2"] = "err"

print("="*70)
print("R6-3: Negative maintenance cost")
try:
    veh = requests.get(f"{API}/vehicles", headers=OWN, timeout=20).json()
    vid = veh[0]["id"] if veh else None
    r = requests.post(f"{API}/maintenance", headers=OWN, json={"vehicle_id": vid, "type": "servis", "cost": -3000000}, timeout=20)
    print("  POST /maintenance cost=-3,000,000 ->", r.status_code)
    if r.status_code == 200:
        print("  RESULT cost stored =", r.json().get("cost"), " <-- BUG if negative")
        results["R6-3"] = ("BUG" if r.json().get("cost", 0) < 0 else "ok")
    else:
        results["R6-3"] = f"rejected({r.status_code})"
except Exception as e:
    print("  ERR", e); results["R6-3"] = "err"

print("="*70)
print("R6-4: Segment preview 5xx on malformed criteria")
try:
    # bad min_value
    r = requests.post(f"{API}/crm/segments", headers=OWN, json={"name": "audit-bad-minvalue", "audience": "customer", "criteria": {"min_value": "abc"}}, timeout=20)
    sid = r.json().get("id") if r.status_code == 200 else None
    print("  create segment(min_value='abc') ->", r.status_code, sid)
    if sid:
        pr = requests.get(f"{API}/crm/segments/{sid}/preview", headers=OWN, timeout=20)
        print("  GET preview ->", pr.status_code, ("<-- 5xx BUG" if pr.status_code >= 500 else ""))
        results["R6-4a_min_value"] = ("BUG5xx" if pr.status_code >= 500 else f"ok({pr.status_code})")
        requests.delete(f"{API}/crm/segments/{sid}", headers=OWN, timeout=20)
    # bad last_activity_days
    r2 = requests.post(f"{API}/crm/segments", headers=OWN, json={"name": "audit-bad-lad", "audience": "lead", "criteria": {"last_activity_days": "xyz"}}, timeout=20)
    sid2 = r2.json().get("id") if r2.status_code == 200 else None
    if sid2:
        pr2 = requests.get(f"{API}/crm/segments/{sid2}/preview", headers=OWN, timeout=20)
        print("  GET preview(last_activity_days='xyz') ->", pr2.status_code, ("<-- 5xx BUG" if pr2.status_code >= 500 else ""))
        results["R6-4b_last_activity"] = ("BUG5xx" if pr2.status_code >= 500 else f"ok({pr2.status_code})")
        requests.delete(f"{API}/crm/segments/{sid2}", headers=OWN, timeout=20)
except Exception as e:
    print("  ERR", e); results["R6-4"] = "err"

print("="*70)
print("R6-1: Subcharter PATCH bypasses overlap conflict re-check (double-book partner unit)")
try:
    # find partner + partner vehicle
    partners = requests.get(f"{API}/partners", headers=OWN, timeout=20).json()
    pid = partners[0]["id"] if partners else None
    veh = requests.get(f"{API}/vehicles", headers=OWN, timeout=20).json()
    pveh = [v for v in veh if v.get("ownership") == "partner"]
    print("  partners:", len(partners), "| partner vehicles:", len(pveh))
    bk = requests.get(f"{API}/bookings", headers=OWN, timeout=20).json()
    bid = bk[0]["id"] if bk else None
    if not (pid and pveh and bid):
        print("  SKIP: need partner+partner-vehicle+booking (pid=%s pveh=%d bid=%s)" % (pid, len(pveh), bid))
        results["R6-1"] = "skip(no partner vehicle)"
    else:
        vid = pveh[0]["id"]
        s1, e1 = iso(now + timedelta(days=10)), iso(now + timedelta(days=11))
        s2, e2 = iso(now + timedelta(days=20)), iso(now + timedelta(days=21))
        # SC #1 occupies window1
        c1 = requests.post(f"{API}/subcharters", headers=OWN, json={"booking_id": bid, "partner_id": pid, "vehicle_id": vid, "start_datetime": s1, "end_datetime": e1, "cost": 1000000}, timeout=20)
        # SC #2 occupies window2 (non-overlap)
        c2 = requests.post(f"{API}/subcharters", headers=OWN, json={"booking_id": bid, "partner_id": pid, "vehicle_id": vid, "start_datetime": s2, "end_datetime": e2, "cost": 1000000}, timeout=20)
        print("  create SC1 win1 ->", c1.status_code, "| create SC2 win2 ->", c2.status_code)
        # sanity: creating SC2 overlapping win1 should be rejected 400 (create path checks)
        c3 = requests.post(f"{API}/subcharters", headers=OWN, json={"booking_id": bid, "partner_id": pid, "vehicle_id": vid, "start_datetime": s1, "end_datetime": e1, "cost": 1000000}, timeout=20)
        print("  create SC overlapping win1 (expect 400) ->", c3.status_code)
        if c1.status_code == 200 and c2.status_code == 200:
            sc2_id = c2.json()["id"]
            # PATCH SC2 to overlap win1 -> should be rejected but likely 200 (BUG)
            p = requests.patch(f"{API}/subcharters/{sc2_id}", headers=OWN, json={"start_datetime": s1, "end_datetime": e1}, timeout=20)
            print("  PATCH SC2 -> win1 (overlap SC1). status:", p.status_code)
            print("     -> if 200, DOUBLE-BOOKING via PATCH confirmed (BUG). Stored:", p.json().get("start_datetime"), p.json().get("end_datetime"))
            results["R6-1"] = ("BUG(200 double-book)" if p.status_code == 200 else f"ok({p.status_code})")
            # R6-1b: PATCH end<=start (no validation)
            p2 = requests.patch(f"{API}/subcharters/{sc2_id}", headers=OWN, json={"start_datetime": e1, "end_datetime": s1}, timeout=20)
            print("  PATCH SC2 end<start (expect 400) ->", p2.status_code, ("<-- BUG accepts invalid window" if p2.status_code == 200 else ""))
            results["R6-1b_end_before_start"] = ("BUG(accepts)" if p2.status_code == 200 else f"ok({p2.status_code})")
            # cleanup
            for sid in (c1.json()["id"], sc2_id):
                requests.post(f"{API}/subcharters/{sid}/cancel", headers=OWN, timeout=20)
        else:
            results["R6-1"] = f"setup-failed(c1={c1.status_code},c2={c2.status_code}): {c1.text[:100]}"
except Exception as e:
    print("  ERR", e); results["R6-1"] = "err: "+str(e)

print("\n" + "="*70)
print("SUMMARY:", json.dumps(results, indent=2))
