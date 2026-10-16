#!/usr/bin/env python3
"""Round 8 — empirical reproduction (report-only).
DISP-RACE: dispatch.assign_trip not under vehicle_lock -> concurrent assign double-books vehicle.
FIN-IMPACT: negative maintenance cost distorts /finance/pl-full; negative invoice distorts /finance/reconciliation.
CAMP-RACE: send_campaign non-atomic status guard -> double broadcast (best-effort).
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

print("="*70); print("DISP-RACE: concurrent dispatch assign to same free vehicle")
try:
    v1, v2, v3 = veh[0]["id"], veh[1]["id"], veh[2]["id"]
    d1 = drv[0]["id"]; d2 = drv[1]["id"] if len(drv) > 1 else drv[0]["id"]
    s, e = iso(now + timedelta(days=80, hours=1)), iso(now + timedelta(days=80, hours=9))
    # two confirmed bookings, overlapping window, different vehicles
    b1 = requests.post(f"{API}/bookings", headers=OWN, json={"customer_id": cus[0]["id"], "vehicle_id": v1, "start_datetime": s, "end_datetime": e, "base_price": 1000000}).json()
    b2 = requests.post(f"{API}/bookings", headers=OWN, json={"customer_id": cus[0]["id"], "vehicle_id": v2, "start_datetime": s, "end_datetime": e, "base_price": 1000000}).json()
    print("  B1", b1.get("code"), "B2", b2.get("code"))
    def assign(args):
        bid, did = args
        try:
            r = requests.post(f"{API}/dispatch/{bid}/assign", headers=OWN, json={"driver_id": did, "vehicle_id": v3}, timeout=30)
            return r.status_code
        except Exception: return "EXC"
    with ThreadPoolExecutor(max_workers=2) as ex:
        codes = list(ex.map(assign, [(b1["id"], d1), (b2["id"], d2)]))
    print("  concurrent assign to v3 -> statuses:", codes)
    # verify how many bookings now hold v3 in window
    allbk = requests.get(f"{API}/bookings", headers=OWN, params={"vehicle_id": v3}).json()
    hold = [b for b in allbk if b.get("vehicle_id")==v3 and b.get("status") in ("confirmed","ongoing") and str(b.get("start_datetime",""))[:10]==s[:10]]
    print("  bookings holding v3 in window:", len(hold), [b.get("code") for b in hold])
    R["DISP-RACE_vehicle_double_book"] = f"BUG({len(hold)} on same vehicle)" if len(hold) > 1 else f"ok({len(hold)})"
except Exception as ex:
    R["DISP-RACE"] = "err "+str(ex); print("  ERR", ex)

print("="*70); print("FIN-IMPACT: negative maintenance cost distorts /finance/pl-full")
try:
    period = now.strftime("%Y-%m")
    before = requests.get(f"{API}/finance/pl-full", headers=OWN, params={"period": period}).json()
    mb = before.get("maintenance_cost"); pb = before.get("profit")
    requests.post(f"{API}/maintenance", headers=OWN, json={"vehicle_id": veh[0]["id"], "type": "servis", "cost": -50000000})
    after = requests.get(f"{API}/finance/pl-full", headers=OWN, params={"period": period}).json()
    ma = after.get("maintenance_cost"); pa = after.get("profit")
    print(f"  maintenance_cost: {mb} -> {ma}  | profit: {pb} -> {pa}")
    R["FIN-IMPACT_neg_maint_in_plfull"] = f"BUG(maint {mb}->{ma}, profit {pb}->{pa})" if (ma is not None and mb is not None and ma < mb) else "ok"
except Exception as ex:
    R["FIN-IMPACT_maint"] = "err "+str(ex); print("  ERR", ex)

print("="*70); print("FIN-IMPACT: negative invoice distorts /finance/reconciliation total_invoiced")
try:
    rec_b = requests.get(f"{API}/finance/reconciliation", headers=OWN).json()
    ti_b = rec_b.get("summary", {}).get("total_invoiced")
    requests.post(f"{API}/invoices", headers=OWN, json={"booking_id": (requests.get(f'{API}/bookings',headers=OWN).json()[0]['id']), "amount": -30000000})
    rec_a = requests.get(f"{API}/finance/reconciliation", headers=OWN).json()
    ti_a = rec_a.get("summary", {}).get("total_invoiced")
    print(f"  total_invoiced: {ti_b} -> {ti_a}")
    R["FIN-IMPACT_neg_invoice_in_recon"] = f"BUG(total_invoiced {ti_b}->{ti_a})" if (ti_a is not None and ti_b is not None and ti_a < ti_b) else "ok"
except Exception as ex:
    R["FIN-IMPACT_invoice"] = "err "+str(ex); print("  ERR", ex)

print("="*70); print("CAMP-RACE: concurrent campaign send -> double broadcast (best-effort)")
try:
    # create a segment (all customers) + campaign
    seg = requests.post(f"{API}/crm/segments", headers=OWN, json={"name": "aud-all-"+uuid.uuid4().hex[:5], "audience": "customer", "criteria": {}}).json()
    camp = requests.post(f"{API}/campaigns", headers=OWN, json={"name": "aud-camp-"+uuid.uuid4().hex[:5], "segment_id": seg.get("id"), "audience": "customer", "message": "Halo {name}"}).json()
    cid = camp.get("id")
    print("  segment", seg.get("id"), "campaign", cid, "status", camp.get("status"))
    if cid:
        def send(_):
            try: return requests.post(f"{API}/campaigns/{cid}/send", headers=OWN, timeout=40).status_code
            except Exception: return "EXC"
        with ThreadPoolExecutor(max_workers=4) as ex:
            codes = list(ex.map(send, range(4)))
        recs = requests.get(f"{API}/campaigns/{cid}/recipients", headers=OWN)
        nrec = len(recs.json()) if recs.status_code == 200 else "n/a"
        print("  send statuses:", codes, "| recipient records:", nrec)
        R["CAMP-RACE"] = f"statuses={codes}, recipients={nrec} (double if recipients>customers)"
    else:
        R["CAMP-RACE"] = "setup-failed: "+json.dumps(camp)[:120]
except Exception as ex:
    R["CAMP-RACE"] = "err "+str(ex); print("  ERR", ex)

print("\n"+"="*70); print("SUMMARY:", json.dumps(R, indent=2))
