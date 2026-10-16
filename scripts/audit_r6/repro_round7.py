#!/usr/bin/env python3
"""Round 7 — empirical reproduction (READ + create test data only; report-only).
Q-BUG-1: convert_quotation does NOT check driver conflict (RC-07) -> driver double-book.
Q-BUG-2: convert_quotation NOT wrapped in vehicle_lock (B7) -> concurrent convert double-books vehicle.
PAY-RACE: concurrent approve_payout -> double gaji_driver expense.
"""
import requests, json, uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

API = "http://localhost:8001/api"
def login(e): return requests.post(f"{API}/auth/login", json={"email": e, "password": "demo12345"}).json()["token"]
OWN = {"Authorization": f"Bearer {login('owner@demo.local')}"}
now = datetime.now(timezone.utc)
def iso(d): return d.isoformat()
R = {}

veh = requests.get(f"{API}/vehicles", headers=OWN).json()
drv = requests.get(f"{API}/drivers", headers=OWN).json()
cus = requests.get(f"{API}/customers", headers=OWN).json()
print("vehicles:", len(veh), "drivers:", len(drv), "customers:", len(cus))

def mk_quotation(name, dest="Bandung"):
    r = requests.post(f"{API}/quotations", headers=OWN, json={
        "customer_name": name, "phone": "0812"+str(uuid.uuid4().int)[:8],
        "destination": dest, "items": [{"label": "Sewa", "amount": 2000000}]})
    q = r.json(); return q["id"]
def accept(qid):
    requests.post(f"{API}/quotations/{qid}/send", headers=OWN)
    requests.post(f"{API}/quotations/{qid}/accept", headers=OWN)

print("="*70); print("Q-BUG-1: convert_quotation ignores DRIVER conflict (RC-07)")
try:
    d1 = drv[0]["id"]; v1 = veh[0]["id"]; v2 = veh[1]["id"] if len(veh) > 1 else veh[0]["id"]
    s1, e1 = iso(now + timedelta(days=40, hours=1)), iso(now + timedelta(days=40, hours=8))
    # Booking B1: driver d1 busy on window (vehicle v1)
    b1 = requests.post(f"{API}/bookings", headers=OWN, json={
        "customer_id": cus[0]["id"], "vehicle_id": v1, "driver_id": d1,
        "start_datetime": s1, "end_datetime": e1, "base_price": 2000000})
    print("  create B1 (driver d1 busy) ->", b1.status_code, b1.json().get("code") if b1.status_code==200 else b1.text[:120])
    # sanity: creating another BOOKING with same driver overlapping should be 400 (existing guard)
    b2 = requests.post(f"{API}/bookings", headers=OWN, json={
        "customer_id": cus[0]["id"], "vehicle_id": v2, "driver_id": d1,
        "start_datetime": s1, "end_datetime": e1, "base_price": 2000000})
    print("  sanity create B2 same driver via /bookings (expect 400) ->", b2.status_code)
    # Now convert a quotation assigning SAME busy driver d1 on overlapping window, free vehicle v2
    qid = mk_quotation("Q-driver-conflict"); accept(qid)
    conv = requests.post(f"{API}/quotations/{qid}/convert", headers=OWN, json={
        "vehicle_id": v2, "driver_id": d1, "start_datetime": s1, "end_datetime": e1})
    print("  convert quotation w/ busy driver d1 (expect 400) ->", conv.status_code)
    R["Q-BUG-1_driver_conflict_on_convert"] = "BUG(200 double-book driver)" if conv.status_code == 200 else f"ok({conv.status_code})"
except Exception as ex:
    R["Q-BUG-1"] = "err "+str(ex); print("  ERR", ex)

print("="*70); print("Q-BUG-2: convert_quotation not under vehicle_lock (B7) -> concurrent vehicle double-book")
try:
    v3 = veh[2]["id"] if len(veh) > 2 else veh[-1]["id"]
    s2, e2 = iso(now + timedelta(days=60, hours=1)), iso(now + timedelta(days=60, hours=8))
    N = 6
    qids = []
    for i in range(N):
        q = mk_quotation(f"Q-race-{i}"); accept(q); qids.append(q)
    def do_convert(qid):
        try:
            r = requests.post(f"{API}/quotations/{qid}/convert", headers=OWN, json={
                "vehicle_id": v3, "start_datetime": s2, "end_datetime": e2}, timeout=30)
            return r.status_code
        except Exception as e:
            return "EXC"
    with ThreadPoolExecutor(max_workers=N) as ex:
        codes = list(ex.map(do_convert, qids))
    ok = sum(1 for c in codes if c == 200)
    print("  parallel convert same vehicle+window -> statuses:", codes)
    print(f"  successes={ok} (expect exactly 1 if protected)")
    R["Q-BUG-2_vehicle_toctou_on_convert"] = f"BUG({ok} success double-book)" if ok > 1 else f"ok({ok} success)"
    # verify overlapping confirmed bookings on v3
    bs = requests.get(f"{API}/bookings", headers=OWN, params={"vehicle_id": v3}).json()
    overlap = [b for b in bs if b.get("vehicle_id")==v3 and b.get("status")=="confirmed" and str(b.get("start_datetime",""))[:10]==s2[:10]]
    print("  confirmed bookings on v3 in window:", len(overlap))
except Exception as ex:
    R["Q-BUG-2"] = "err "+str(ex); print("  ERR", ex)

print("="*70); print("PAY-RACE: concurrent approve_payout -> double gaji_driver expense")
try:
    d1 = drv[0]["id"]
    ps, pe = (now - timedelta(days=200)).date().isoformat(), (now - timedelta(days=170)).date().isoformat()
    g = requests.post(f"{API}/payroll/payouts/generate", headers=OWN, json={
        "driver_id": d1, "period_type": "monthly", "period_start": ps, "period_end": pe})
    if g.status_code != 200:
        print("  generate payout ->", g.status_code, g.text[:140]); R["PAY-RACE"] = f"setup({g.status_code})"
    else:
        pid = g.json()["id"]; total = g.json().get("total")
        print("  payout generated:", pid, "total:", total)
        # need a positive total for expense; if 0, add a bonus
        if not total or total <= 0:
            requests.patch(f"{API}/payroll/payouts/{pid}", headers=OWN, json={"bonuses":[{"label":"x","amount":500000}]})
        def do_approve(_):
            try:
                return requests.post(f"{API}/payroll/payouts/{pid}/approve", headers=OWN, timeout=30).status_code
            except Exception: return "EXC"
        with ThreadPoolExecutor(max_workers=6) as ex:
            codes = list(ex.map(do_approve, range(6)))
        exps = requests.get(f"{API}/expenses", headers=OWN).json()
        gaji = [e for e in exps if e.get("payout_id")==pid]
        print("  approve statuses:", codes)
        print(f"  gaji_driver expenses created for this payout: {len(gaji)} (expect 1)")
        R["PAY-RACE_double_expense"] = f"BUG({len(gaji)} expenses)" if len(gaji) > 1 else f"ok({len(gaji)} expense)"
except Exception as ex:
    R["PAY-RACE"] = "err "+str(ex); print("  ERR", ex)

print("\n"+"="*70); print("SUMMARY:", json.dumps(R, indent=2))
