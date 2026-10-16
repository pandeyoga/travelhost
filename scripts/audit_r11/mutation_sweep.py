#!/usr/bin/env python3
"""
scripts/audit_r11/mutation_sweep.py — PUTARAN 11 comprehensive MUTATION harness.

Report-only audit tool (NON-production). Drives POST/PUT/PATCH/DELETE across the
whole API with (a) happy-path payloads (execute success branches) and (b) adversarial
payloads (execute validation/error/RBAC branches) so coverage.py can measure the write
paths that the GET-only Round-6 sweep never touched.

Records every call to scripts/audit_r11/mutation_matrix.json:
  {method, path, role, note, status, snippet}

Safe: operates on the seeded demo DB via HTTP; creates disposable records.
Credentials: owner/ops/driver @demo.local / demo12345 (from seed).
"""
import asyncio
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / "backend" / ".env")
except Exception:
    pass

import httpx

API = os.environ.get("API_BASE", "http://localhost:8001").rstrip("/")
OUT = Path(__file__).resolve().parent
CREDS = {
    "owner": {"email": "owner@demo.local", "password": "demo12345"},
    "ops": {"email": "ops@demo.local", "password": "demo12345"},
    "driver": {"email": "driver@demo.local", "password": "demo12345"},
}

RESULTS = []
TOKENS = {}
S = {}  # sample ids


def _iso(dt):
    return dt.astimezone(timezone.utc).isoformat()


def fut(days=0, hours=0):
    return _iso(datetime.now(timezone.utc) + timedelta(days=days, hours=hours))


def _hdr(role):
    t = TOKENS.get(role)
    return {"Authorization": f"Bearer {t}"} if t else {}


async def call(client, method, path, role="owner", *, json_body=None, files=None,
               data=None, note="", expect=None):
    """Fire a request, record result. Never raises."""
    url = API + path
    hdr = _hdr(role)
    try:
        kw = {"headers": hdr, "timeout": 40}
        if json_body is not None:
            kw["json"] = json_body
        if files is not None:
            kw["files"] = files
        if data is not None:
            kw["data"] = data
        resp = await client.request(method, url, **kw)
        sc = resp.status_code
        try:
            body = resp.json()
        except Exception:
            body = resp.text
        snip = json.dumps(body, default=str)[:220] if not isinstance(body, str) else body[:220]
    except Exception as e:  # noqa: BLE001
        sc = "EXC"
        snip = str(e)[:220]
        body = None
    RESULTS.append({"method": method, "path": path, "role": role,
                    "note": note, "status": sc, "snippet": snip})
    return sc, body


async def get_json(client, path, role="owner"):
    try:
        r = await client.get(API + path, headers=_hdr(role), timeout=30)
        if r.status_code != 200:
            return None
        return r.json()
    except Exception:
        return None


async def first_id(client, path, field="id", role="owner"):
    d = await get_json(client, path, role)
    if d is None:
        return None
    items = d if isinstance(d, list) else d.get("items", d.get("departures", []))
    if isinstance(items, list) and items:
        return items[0].get(field)
    return None


async def login_all(client):
    for role, creds in CREDS.items():
        try:
            r = await client.post(API + "/api/auth/login", json=creds, timeout=20)
            TOKENS[role] = r.json().get("token")
        except Exception:
            TOKENS[role] = None


async def resolve_samples(client):
    S["vehicle"] = await first_id(client, "/api/vehicles")
    S["driver"] = await first_id(client, "/api/drivers")
    S["customer"] = await first_id(client, "/api/customers")
    S["booking"] = await first_id(client, "/api/bookings")
    S["lead"] = await first_id(client, "/api/leads")
    S["trip"] = await first_id(client, "/api/trips")
    S["partner"] = await first_id(client, "/api/partners")
    S["workshop"] = await first_id(client, "/api/workshops")
    S["quotation"] = await first_id(client, "/api/quotations")
    S["invoice"] = await first_id(client, "/api/invoices")
    S["subcharter"] = await first_id(client, "/api/subcharters")
    S["conversation"] = await first_id(client, "/api/conversations")
    S["service_type"] = await first_id(client, "/api/service-types")
    S["user"] = await first_id(client, "/api/users")
    S["campaign"] = await first_id(client, "/api/crm/campaigns")
    S["segment"] = await first_id(client, "/api/crm/segments")
    S["sequence"] = await first_id(client, "/api/crm/sequences")
    # find a second free vehicle (VP or V-02/03) for conflict tests
    vehs = await get_json(client, "/api/vehicles") or []
    S["vehicles"] = [v.get("id") for v in (vehs if isinstance(vehs, list) else [])]
    drvs = await get_json(client, "/api/drivers") or []
    S["drivers"] = [d.get("id") for d in (drvs if isinstance(drvs, list) else [])]


# ============ MODULE SWEEPS ============
async def sweep_masterdata(client):
    # Vehicles CRUD
    sc, b = await call(client, "POST", "/api/vehicles", json_body={
        "name": "R11 Test Van", "plate_number": f"R11 {datetime.now().microsecond}",
        "type": "hiace", "capacity": 12, "status": "available", "odometer": 1000,
        "service_interval_km": 5000, "service_interval_days": 90,
    }, note="create vehicle happy")
    vid = (b or {}).get("id") if isinstance(b, dict) else None
    if vid:
        await call(client, "PATCH", f"/api/vehicles/{vid}", json_body={"notes": "patched", "odometer": 2000}, note="patch vehicle")
        await call(client, "DELETE", f"/api/vehicles/{vid}", note="delete vehicle")
    await call(client, "POST", "/api/vehicles", json_body={"name": ""}, note="create vehicle invalid (422)")
    await call(client, "POST", "/api/vehicles", role="driver", json_body={"name": "x", "plate_number": "y"}, note="RBAC driver create vehicle (403)")

    # Drivers CRUD + compensation
    sc, b = await call(client, "POST", "/api/drivers", json_body={"name": "R11 Driver", "phone": "081999000111", "status": "offline"}, note="create driver")
    did = (b or {}).get("id") if isinstance(b, dict) else None
    if did:
        await call(client, "PATCH", f"/api/drivers/{did}", json_body={"rating": 4.9, "status": "online"}, note="patch driver")
        await call(client, "PATCH", f"/api/drivers/{did}/compensation", json_body={
            "base_salary_monthly": 3000000, "commission_per_trip": 40000, "enable_base": True,
            "enable_commission_trip": True}, note="driver compensation")
        await call(client, "DELETE", f"/api/drivers/{did}", note="delete driver (no active trips)")

    # Customers CRUD
    sc, b = await call(client, "POST", "/api/customers", json_body={"name": "R11 Cust", "phone": "081900011122", "city": "Bandung"}, note="create customer")
    cid = (b or {}).get("id") if isinstance(b, dict) else None
    if cid:
        await call(client, "PATCH", f"/api/customers/{cid}", json_body={"notes": "vip", "email": "r11@mail.com"}, note="patch customer")
        await call(client, "DELETE", f"/api/customers/{cid}", note="delete customer")

    # Partners CRUD + settlement
    sc, b = await call(client, "POST", "/api/partners", json_body={"name": "R11 Partner", "phone": "0812000333", "city": "Jakarta"}, note="create partner")
    pid = (b or {}).get("id") if isinstance(b, dict) else None
    if pid:
        await call(client, "PATCH", f"/api/partners/{pid}", json_body={"rating": 4.2, "status": "active"}, note="patch partner")
        await call(client, "POST", f"/api/partners/{pid}/settlements", json_body={"amount": 500000, "method": "transfer", "note": "r11"}, note="partner settlement")
        await call(client, "POST", f"/api/partners/{pid}/settlements", json_body={"amount": -5}, note="settlement negative (422 gt=0)")
        await call(client, "DELETE", f"/api/partners/{pid}", note="delete partner")

    # Workshops CRUD
    sc, b = await call(client, "POST", "/api/workshops", json_body={"name": "R11 Bengkel", "city": "Bandung", "specialties": ["servis"]}, note="create workshop")
    wid = (b or {}).get("id") if isinstance(b, dict) else None
    if wid:
        await call(client, "PATCH", f"/api/workshops/{wid}", json_body={"active": False, "note": "closed"}, note="patch workshop")
        await call(client, "DELETE", f"/api/workshops/{wid}", note="delete workshop")

    # Service types CRUD
    sc, b = await call(client, "POST", "/api/service-types", json_body={"name": "R11 Service", "default_interval_km": 5000}, note="create service_type")
    stid = (b or {}).get("id") if isinstance(b, dict) else None
    if stid:
        await call(client, "PATCH", f"/api/service-types/{stid}", json_body={"active": False}, note="patch service_type")
        await call(client, "DELETE", f"/api/service-types/{stid}", note="delete service_type")

    # Users CRUD (owner-only)
    sc, b = await call(client, "POST", "/api/users", json_body={"name": "R11 Ops", "email": f"r11ops{datetime.now().microsecond}@demo.local", "password": "secret123", "role": "ops_admin"}, note="create user")
    uid = (b or {}).get("id") if isinstance(b, dict) else None
    if uid:
        await call(client, "PATCH", f"/api/users/{uid}", json_body={"phone": "0810000", "status": "active"}, note="patch user")
        await call(client, "PATCH", f"/api/users/{uid}", json_body={"role": "invalid_role"}, note="patch user invalid role")
    await call(client, "POST", "/api/users", role="ops", json_body={"name": "x", "email": "a@b.cd", "password": "xxxxxx"}, note="RBAC ops create user (403)")


async def sweep_bookings(client):
    cust = S.get("customer")
    vehs = S.get("vehicles") or []
    drvs = S.get("drivers") or []
    free_v = vehs[-1] if vehs else S.get("vehicle")  # partner unit (likely free)
    s1, e1 = fut(days=40), fut(days=41)
    # create booking happy
    sc, b = await call(client, "POST", "/api/bookings", json_body={
        "customer_id": cust, "vehicle_id": free_v, "driver_id": (drvs[1] if len(drvs) > 1 else None),
        "origin": "Bandung", "destination": "Bali", "start_datetime": s1, "end_datetime": e1,
        "base_price": 3000000, "add_ons": [{"label": "Tol", "amount": 200000}], "notes": "r11"},
        note="create booking happy")
    bid = (b or {}).get("id") if isinstance(b, dict) else None
    # adversarial: end<start
    await call(client, "POST", "/api/bookings", json_body={
        "customer_id": cust, "vehicle_id": free_v, "start_datetime": e1, "end_datetime": s1,
        "base_price": 1000}, note="booking end<start (400)")
    # adversarial: overlap conflict (same vehicle+window)
    await call(client, "POST", "/api/bookings", json_body={
        "customer_id": cust, "vehicle_id": free_v, "start_datetime": s1, "end_datetime": e1,
        "base_price": 1000}, note="booking overlap conflict (400)")
    if bid:
        await call(client, "PATCH", f"/api/bookings/{bid}", json_body={"notes": "edited", "origin": "Jakarta"}, note="patch booking")
        await call(client, "POST", f"/api/bookings/{bid}/confirm", note="confirm booking")
        await call(client, "POST", f"/api/bookings/{bid}/reschedule", json_body={
            "start_datetime": fut(days=50), "end_datetime": fut(days=51), "reason": "r11"}, note="reschedule booking")
        # reschedule invalid window
        await call(client, "POST", f"/api/bookings/{bid}/reschedule", json_body={
            "start_datetime": fut(days=51), "end_datetime": fut(days=50)}, note="reschedule end<start (400)")
        await call(client, "POST", f"/api/bookings/{bid}/cancel", json_body={
            "reason": "r11 test", "cancellation_fee": 100000, "refund_amount": 50000}, note="cancel booking")
    # group booking
    sc, b = await call(client, "POST", "/api/bookings/group", json_body={
        "customer_id": cust, "note": "r11 group", "units": [
            {"vehicle_id": free_v, "start_datetime": fut(days=60), "end_datetime": fut(days=61), "base_price": 2000000},
        ]}, note="group booking happy")
    # group with overlap between units
    await call(client, "POST", "/api/bookings/group", json_body={
        "customer_id": cust, "units": [
            {"vehicle_id": free_v, "start_datetime": fut(days=70), "end_datetime": fut(days=72), "base_price": 1000},
            {"vehicle_id": free_v, "start_datetime": fut(days=71), "end_datetime": fut(days=73), "base_price": 1000},
        ]}, note="group booking internal overlap (400)")
    # complete a nonexistent booking
    await call(client, "POST", "/api/bookings/NONEXISTENT/complete", note="complete missing booking (404)")


async def sweep_quotations(client):
    lead = S.get("lead")
    cust = S.get("customer")
    free_v = (S.get("vehicles") or [None])[-1]
    drvs = S.get("drivers") or []
    # create draft (auto price via pricing engine)
    sc, b = await call(client, "POST", "/api/quotations", json_body={
        "lead_id": lead, "customer_name": "R11 Quote", "phone": "0812777888",
        "destination": "Bromo", "vehicle_type": "hiace_premio", "days": 3, "distance_km": 300, "valid_days": 7},
        note="create quotation (auto-price)")
    qid = (b or {}).get("id") if isinstance(b, dict) else None
    # create with special chars for EXPORT-1 PDF test
    sc, b2 = await call(client, "POST", "/api/quotations", json_body={
        "customer_name": "PT A < B & <script>x</script>", "phone": "0812000999",
        "destination": "Bali", "notes": "unclosed <b> & amp",
        "items": [{"label": "Sewa <b>", "amount": 5000000}]}, note="create quotation w/ markup (EXPORT-1)")
    qid_markup = (b2 or {}).get("id") if isinstance(b2, dict) else None
    if qid_markup:
        await call(client, "GET", f"/api/quotations/{qid_markup}/pdf", note="EXPORT-1: PDF with <&markup (expect 500)")
    if qid:
        await call(client, "PATCH", f"/api/quotations/{qid}", json_body={"notes": "edited", "pax": 12}, note="patch quotation")
        await call(client, "GET", f"/api/quotations/{qid}/pdf", note="quotation PDF clean")
        await call(client, "POST", f"/api/quotations/{qid}/send", note="send quotation")
        await call(client, "POST", f"/api/quotations/{qid}/accept", note="accept quotation")
        # convert happy (own free vehicle)
        await call(client, "POST", f"/api/quotations/{qid}/convert", json_body={
            "vehicle_id": free_v, "driver_id": (drvs[1] if len(drvs) > 1 else None),
            "start_datetime": fut(days=80), "end_datetime": fut(days=81)}, note="convert quotation happy")
        # double convert (INV-19)
        await call(client, "POST", f"/api/quotations/{qid}/convert", json_body={
            "vehicle_id": free_v, "start_datetime": fut(days=82), "end_datetime": fut(days=83)}, note="double convert (400)")
    # another for reject path
    sc, b = await call(client, "POST", "/api/quotations", json_body={
        "customer_name": "R11 Reject", "phone": "0812111000", "items": [{"label": "x", "amount": 1000}]}, note="create quotation for reject")
    qid2 = (b or {}).get("id") if isinstance(b, dict) else None
    if qid2:
        await call(client, "POST", f"/api/quotations/{qid2}/reject", note="reject quotation")
    # convert nonexistent
    await call(client, "POST", "/api/quotations/NONE/convert", json_body={"vehicle_id": free_v, "start_datetime": fut(days=1), "end_datetime": fut(days=2)}, note="convert missing (404)")


async def sweep_dispatch_driver(client):
    # find a booking to assign (create a fresh confirmed booking with free vehicle)
    cust = S.get("customer")
    free_v = (S.get("vehicles") or [None])[-1]
    drvs = S.get("drivers") or []
    sc, b = await call(client, "POST", "/api/bookings", json_body={
        "customer_id": cust, "vehicle_id": free_v, "start_datetime": fut(days=90), "end_datetime": fut(days=91),
        "base_price": 2500000}, note="booking for dispatch")
    bid = (b or {}).get("id") if isinstance(b, dict) else None
    if bid:
        await call(client, "POST", f"/api/bookings/{bid}/confirm", note="confirm for dispatch")
        sc, t = await call(client, "POST", f"/api/dispatch/{bid}/assign", json_body={
            "driver_id": (drvs[1] if len(drvs) > 1 else drvs[0]), "vehicle_id": free_v}, note="dispatch assign happy")
        tid = (t or {}).get("trip", {}).get("id") if isinstance(t, dict) else None
        await call(client, "POST", f"/api/dispatch/{bid}/confirm-departure", note="confirm departure")
        if tid:
            await call(client, "POST", f"/api/dispatch/trips/{tid}/enroute", note="trip enroute")
            await call(client, "POST", f"/api/dispatch/trips/{tid}/arrived", note="trip arrived")
            await call(client, "POST", f"/api/dispatch/trips/{tid}/pod", data={"recipient_name": "Pak R11", "note": "diterima"}, note="trip POD (finalize)")
        # assign to cancelled/nonexistent
        await call(client, "POST", "/api/dispatch/NONE/assign", json_body={"driver_id": drvs[0], "vehicle_id": free_v}, note="assign missing booking (404)")

    # Driver surface: manager checkin/checkout on a fresh booking
    sc, b = await call(client, "POST", "/api/bookings", json_body={
        "customer_id": cust, "vehicle_id": free_v, "driver_id": drvs[0], "start_datetime": fut(days=100),
        "end_datetime": fut(days=101), "base_price": 1500000}, note="booking for driver checkin")
    bid2 = (b or {}).get("id") if isinstance(b, dict) else None
    if bid2:
        await call(client, "POST", f"/api/bookings/{bid2}/confirm", note="confirm for checkin")
        sc, t = await call(client, "POST", "/api/driver/checkin", role="owner", json_body={"booking_id": bid2, "odometer_start": 5000}, note="manager checkin")
        tid2 = (t or {}).get("id") if isinstance(t, dict) else None
        if tid2:
            await call(client, "POST", "/api/driver/checkout", role="owner", json_body={"trip_id": tid2, "odometer_end": 5250}, note="manager checkout")
    # driver role: view own trips then ack/arrived on own trip
    my = await get_json(client, "/api/driver/tasks", role="driver") or []
    if my:
        ttid = my[0].get("trip_id")
        if ttid:
            await call(client, "POST", f"/api/driver/tasks/{ttid}/ack", role="driver", note="driver ack task")
    await call(client, "POST", "/api/driver/checkin", role="driver", json_body={}, note="driver checkin no ids (400)")


async def sweep_finance(client):
    booking = S.get("booking")
    # payments (happy + adversarial)
    await call(client, "POST", "/api/payments", json_body={
        "booking_id": booking, "amount": 500000, "type": "settlement", "method": "transfer",
        "idempotency_key": f"r11-{datetime.now().microsecond}"}, note="create payment happy")
    await call(client, "POST", "/api/payments", json_body={"booking_id": booking, "amount": -100}, note="payment negative (422 gt=0)")
    # expenses
    await call(client, "POST", "/api/expenses", json_body={"booking_id": booking, "category": "bbm", "amount": 250000, "note": "r11"}, note="create expense happy")
    await call(client, "POST", "/api/expenses", json_body={"booking_id": booking, "category": "bbm", "amount": -1}, note="expense negative (422 gt=0)")
    # invoices — R6-2: negative amount accepted
    sc, b = await call(client, "POST", "/api/invoices", json_body={"booking_id": booking, "amount": 1000000, "notes": "r11"}, note="create invoice happy")
    iid = (b or {}).get("id") if isinstance(b, dict) else None
    await call(client, "POST", "/api/invoices", json_body={"booking_id": booking, "amount": -5000000}, note="R6-2: invoice NEGATIVE (expect 200 - bug)")
    if iid:
        await call(client, "PATCH", f"/api/invoices/{iid}", json_body={"status": "sent"}, note="invoice status sent")
        await call(client, "PATCH", f"/api/invoices/{iid}", json_body={"status": "paid"}, note="invoice status paid")
        await call(client, "PATCH", f"/api/invoices/{iid}", json_body={"status": "bogus"}, note="invoice status invalid")
    # finance AR + reconciliation
    await call(client, "POST", "/api/finance/ar/remind-all", note="AR remind all")
    if booking:
        await call(client, "POST", f"/api/finance/ar/{booking}/remind", note="AR remind one")
    await call(client, "POST", "/api/finance/reconciliation/sync", note="reconciliation sync")
    # analytics ad-spend
    await call(client, "PUT", "/api/analytics/ad-spend", json_body={"items": [{"channel": "website", "amount": 1000000}], "note": "r11"}, note="update ad-spend")


async def sweep_maintenance(client):
    veh = S.get("vehicle")
    free_v = (S.get("vehicles") or [None])[-1]
    sc, b = await call(client, "POST", "/api/maintenance", json_body={
        "vehicle_id": veh, "type": "servis", "title": "R11 servis", "cost": 500000, "odometer": 90000,
        "status": "scheduled", "scheduled_date": fut(days=5)}, note="create maintenance happy")
    mid = (b or {}).get("id") if isinstance(b, dict) else None
    # R6-3: negative cost accepted
    await call(client, "POST", "/api/maintenance", json_body={"vehicle_id": veh, "cost": -3000000, "title": "neg"}, note="R6-3: maintenance NEGATIVE cost (expect 200 - bug)")
    if mid:
        await call(client, "PATCH", f"/api/maintenance/{mid}", json_body={"cost": 600000, "status": "in_progress"}, note="patch maintenance")
        await call(client, "POST", f"/api/maintenance/{mid}/complete", json_body={"cost": 650000, "odometer": 90500, "note": "done"}, note="complete maintenance")
        await call(client, "DELETE", f"/api/maintenance/{mid}", note="delete maintenance")
    # preventive schedule
    if free_v:
        await call(client, "POST", f"/api/maintenance/preventive/{free_v}/schedule", json_body={}, note="preventive schedule")


async def sweep_crm_growth(client):
    lead = S.get("lead")
    cust = S.get("customer")
    # leads lifecycle
    sc, b = await call(client, "POST", "/api/leads", json_body={
        "customer_name": "R11 Lead", "phone": "0812345678", "source": "manual", "destination": "Bali", "pax": 4, "value": 5000000},
        note="create lead")
    lid = (b or {}).get("id") if isinstance(b, dict) else None
    if lid:
        await call(client, "PATCH", f"/api/leads/{lid}", json_body={"value": 6000000, "message": "updated"}, note="patch lead")
        await call(client, "POST", f"/api/leads/{lid}/activities", json_body={"type": "note", "text": "called customer"}, note="lead activity")
        await call(client, "POST", f"/api/leads/{lid}/assign", json_body={"assigned_to": None}, note="lead assign round-robin")
        await call(client, "POST", f"/api/leads/{lid}/stage", json_body={"stage": "contacted"}, note="lead stage")
        await call(client, "POST", f"/api/leads/{lid}/stage", json_body={"stage": "bogus"}, note="lead stage invalid")
        await call(client, "POST", f"/api/leads/{lid}/convert", json_body={"note": "converted r11"}, note="lead convert")
    # segments — happy + R6-4 invalid criteria
    sc, b = await call(client, "POST", "/api/crm/segments", json_body={
        "name": "R11 Seg Valid", "audience": "customer", "criteria": {"min_value": 1000000}}, note="create segment valid")
    seg = (b or {}).get("id") if isinstance(b, dict) else None
    if seg:
        await call(client, "GET", f"/api/crm/segments/{seg}/preview", note="segment preview valid")
        await call(client, "PATCH", f"/api/crm/segments/{seg}", json_body={"description": "r11"}, note="patch segment")
    sc, b = await call(client, "POST", "/api/crm/segments", json_body={
        "name": "R11 Seg Bad", "audience": "customer", "criteria": {"min_value": "abc"}}, note="create segment bad criteria")
    segbad = (b or {}).get("id") if isinstance(b, dict) else None
    if segbad:
        await call(client, "GET", f"/api/crm/segments/{segbad}/preview", note="R6-4: segment preview bad (expect 500)")
    sc, b = await call(client, "POST", "/api/crm/segments", json_body={
        "name": "R11 Seg Days", "audience": "lead", "criteria": {"last_activity_days": "xyz"}}, note="create segment bad days")
    segbad2 = (b or {}).get("id") if isinstance(b, dict) else None
    if segbad2:
        await call(client, "GET", f"/api/crm/segments/{segbad2}/preview", note="R6-4b: segment preview bad days (expect 500)")
    # sequences
    sc, b = await call(client, "POST", "/api/crm/sequences", json_body={
        "name": "R11 Seq", "audience": "lead", "enabled": True, "steps": [
            {"delay_hours": 0, "action": "send_wa", "text": "Hi {name}"},
            {"delay_hours": 24, "action": "create_task", "text": "call"}]}, note="create sequence")
    seq = (b or {}).get("id") if isinstance(b, dict) else None
    if seq:
        await call(client, "PATCH", f"/api/crm/sequences/{seq}", json_body={"enabled": False}, note="patch sequence")
        sc, en = await call(client, "POST", f"/api/crm/sequences/{seq}/enroll", json_body={"target_id": lead}, note="enroll sequence")
        enid = (en or {}).get("id") if isinstance(en, dict) else None
        if enid:
            await call(client, "POST", f"/api/crm/enrollments/{enid}/stop", note="stop enrollment")
        await call(client, "DELETE", f"/api/crm/sequences/{seq}", note="delete sequence")
    # campaigns
    sc, b = await call(client, "POST", "/api/crm/campaigns", json_body={
        "name": "R11 Campaign", "audience": "customer", "criteria": {"min_value": 0}, "message": "Halo {name}, promo r11"}, note="create campaign")
    cmp = (b or {}).get("id") if isinstance(b, dict) else None
    if cmp:
        await call(client, "PATCH", f"/api/crm/campaigns/{cmp}", json_body={"message": "updated r11"}, note="patch campaign")
        await call(client, "POST", f"/api/crm/campaigns/{cmp}/send", note="send campaign")
        await call(client, "POST", f"/api/crm/campaigns/{cmp}/send", note="send campaign again (400 already sent)")
        await call(client, "DELETE", f"/api/crm/campaigns/{cmp}", note="delete campaign (may 400 if sent)")
    # growth config + recompute
    await call(client, "PATCH", "/api/crm/growth-config", json_body={"sla_first_response_hours": 4, "at_risk_days": 30}, note="patch growth config")
    await call(client, "POST", "/api/crm/recompute", note="crm recompute")


async def sweep_content(client):
    # destinations happy
    slug = f"r11-dest-{datetime.now().microsecond}"
    sc, b = await call(client, "POST", "/api/content/destinations", json_body={
        "slug": slug, "name": "R11 Dest", "region": "bali", "description": "d", "position": 5, "popular": True, "lat": -8.4, "lng": 115.1}, note="create destination")
    did = (b or {}).get("id") if isinstance(b, dict) else None
    if did:
        await call(client, "PUT", f"/api/content/destinations/{did}", json_body={"name": "R11 Dest Edit", "position": 6}, note="update destination")
        await call(client, "POST", f"/api/content/destinations/{did}/duplicate", note="duplicate destination")
        await call(client, "DELETE", f"/api/content/destinations/{did}", note="delete destination")
    # R6-5: non-numeric int field
    await call(client, "POST", "/api/content/destinations", json_body={"slug": f"bad-{datetime.now().microsecond}", "name": "Bad", "position": "abc"}, note="R6-5: content position=abc (expect 500)")
    await call(client, "POST", "/api/content/packages", json_body={"slug": f"pkg-{datetime.now().microsecond}", "name": "Bad Pkg", "price_from": "NaNstr"}, note="R6-5b: package price_from non-numeric (expect 500)")
    # packages/articles/promos/testimonials happy
    await call(client, "POST", "/api/content/packages", json_body={"slug": f"r11pkg-{datetime.now().microsecond}", "name": "R11 Pkg", "days": 3, "price_from": 4000000, "active": True}, note="create package")
    await call(client, "POST", "/api/content/articles", json_body={"slug": f"r11art-{datetime.now().microsecond}", "title": "R11 Art", "excerpt": "e", "body": "b", "read_minutes": 5, "published": True}, note="create article")
    await call(client, "POST", "/api/content/promos", json_body={"code": f"R11PROMO{datetime.now().microsecond}", "title": "R11 Promo", "discount_type": "percent", "discount_value": 10, "active": True}, note="create promo")
    await call(client, "POST", "/api/content/testimonials", json_body={"name": "R11 Tsti", "role": "Cust", "quote": "Great", "rating": 5, "approved": True}, note="create testimonial")
    # unknown resource
    await call(client, "POST", "/api/content/unknownres", json_body={"name": "x"}, note="content unknown resource (404)")


async def sweep_payroll(client):
    drv = S.get("driver")
    now = datetime.now(timezone.utc)
    p_start = now.replace(day=1).strftime("%Y-%m-%d")
    p_end = now.strftime("%Y-%m-%d")
    sc, b = await call(client, "POST", "/api/payroll/payouts/generate", json_body={
        "driver_id": drv, "period_type": "monthly", "period_start": p_start, "period_end": p_end}, note="payroll generate (may 400 overlap)")
    pid = (b or {}).get("id") if isinstance(b, dict) else None
    # bulk generate for a fresh (prev-prev) period to avoid overlap
    prev = (now.replace(day=1) - timedelta(days=1)).replace(day=1)
    prev2 = (prev - timedelta(days=1)).replace(day=1)
    b_start = prev2.strftime("%Y-%m-%d")
    b_end = (prev - timedelta(days=1)).strftime("%Y-%m-%d")
    await call(client, "POST", "/api/payroll/payouts/generate-bulk", json_body={
        "period_type": "monthly", "period_start": b_start, "period_end": b_end}, note="payroll generate-bulk")
    # find a draft payout to approve/pay/update
    payouts = await get_json(client, "/api/payroll/payouts") or []
    plist = payouts if isinstance(payouts, list) else payouts.get("items", [])
    draft = next((p for p in plist if p.get("status") == "draft"), None)
    if draft:
        did = draft.get("id")
        await call(client, "PATCH", f"/api/payroll/payouts/{did}", json_body={"bonuses": [{"label": "Bonus r11", "amount": 100000}], "deductions": [{"label": "Potong", "amount": 50000}]}, note="patch payout")
        await call(client, "PATCH", f"/api/payroll/payouts/{did}", json_body={"bonuses": [{"label": "neg", "amount": -100000}]}, note="O-6: payout negative bonus (expect 200)")
        await call(client, "POST", f"/api/payroll/payouts/{did}/approve", note="approve payout")
        await call(client, "POST", f"/api/payroll/payouts/{did}/pay", json_body={}, note="pay payout")
    # delete a draft if any remain
    payouts2 = await get_json(client, "/api/payroll/payouts") or []
    plist2 = payouts2 if isinstance(payouts2, list) else payouts2.get("items", [])
    d2 = next((p for p in plist2 if p.get("status") == "draft"), None)
    if d2:
        await call(client, "DELETE", f"/api/payroll/payouts/{d2.get('id')}", note="delete draft payout")


async def sweep_subcharters(client):
    booking = S.get("booking")
    partner = S.get("partner")
    sc, b = await call(client, "POST", "/api/subcharters", json_body={
        "booking_id": booking, "partner_id": partner, "vehicle_label": "Mitra Unit R11",
        "start_datetime": fut(days=3), "end_datetime": fut(days=5), "cost": 1500000, "note": "r11"}, note="create subcharter")
    scid = (b or {}).get("id") if isinstance(b, dict) else None
    if scid:
        # R6-1: PATCH bypasses conflict + accepts end<start
        await call(client, "PATCH", f"/api/subcharters/{scid}", json_body={"start_datetime": fut(days=5), "end_datetime": fut(days=3)}, note="R6-1: subcharter PATCH end<start (expect 200 - bug)")
        await call(client, "PATCH", f"/api/subcharters/{scid}", json_body={"cost": 1800000, "note": "edit"}, note="patch subcharter cost")
        await call(client, "POST", f"/api/subcharters/{scid}/confirm", note="confirm subcharter")
        await call(client, "POST", f"/api/subcharters/{scid}/settle", json_body={"amount": 1800000, "method": "transfer"}, note="settle subcharter")
    # cancel path on a fresh one
    sc, b = await call(client, "POST", "/api/subcharters", json_body={
        "booking_id": booking, "partner_id": partner, "vehicle_label": "R11 Cancel", "cost": 500000}, note="create subcharter for cancel")
    scid2 = (b or {}).get("id") if isinstance(b, dict) else None
    if scid2:
        await call(client, "POST", f"/api/subcharters/{scid2}/cancel", note="cancel subcharter")


async def sweep_inbox(client):
    cust = S.get("customer")
    sc, b = await call(client, "POST", "/api/conversations", json_body={
        "channel": "internal", "contact_name": "R11 Contact", "contact_phone": "0812999888",
        "subject": "R11 subject", "customer_id": cust, "message": "Halo r11"}, note="create conversation")
    cvid = (b or {}).get("id") if isinstance(b, dict) else None
    if cvid:
        await call(client, "POST", f"/api/conversations/{cvid}/messages", json_body={"body": "pesan r11", "internal": False}, note="conversation message")
        await call(client, "POST", f"/api/conversations/{cvid}/messages", json_body={"body": "catatan internal", "internal": True}, note="internal note")
        await call(client, "POST", f"/api/conversations/{cvid}/read", note="conversation read")
        await call(client, "POST", f"/api/conversations/{cvid}/wa-optin", note="wa optin")
        await call(client, "POST", f"/api/conversations/{cvid}/wa-optout", note="wa optout")
        await call(client, "PATCH", f"/api/conversations/{cvid}", json_body={"status": "closed"}, note="patch conversation")


async def sweep_whatsapp_automation_gps(client):
    veh = S.get("vehicle")
    free_v = (S.get("vehicles") or [None])[-1]
    # whatsapp config + templates + inbound + test
    await call(client, "PATCH", "/api/wa/config", json_body={"provider": "mock", "auto_reply_enabled": True, "auto_reply_text": "Halo r11"}, note="wa config patch")
    await call(client, "PUT", "/api/wa/templates/r11_tpl", json_body={"name": "R11", "language": "id", "category": "utility", "body": "Halo {name} r11"}, note="wa template upsert")
    await call(client, "POST", "/api/wa/simulate-inbound", json_body={"from_phone": "081200011122", "text": "Halo mau tanya", "name": "R11 Cust"}, note="wa simulate inbound")
    await call(client, "POST", "/api/wa/test-send", json_body={"to_phone": "081200011122", "text": "tes r11"}, note="wa test-send")
    await call(client, "DELETE", "/api/wa/templates/r11_tpl", note="wa template delete")
    # public webhooks (O-5 / O-5b) — no auth
    await call(client, "POST", "/api/wa/webhook", role="unauth", json_body={"entry": [{"changes": [{"value": {"messages": [{"from": "628123", "text": {"body": "hi"}, "type": "text"}]}}]}]}, note="O-5: wa webhook unauth (mock)")
    await call(client, "GET", "/api/wa/webhook?hub.mode=subscribe&hub.verify_token=x&hub.challenge=123", role="unauth", note="wa webhook verify GET")
    # automation rules
    sc, b = await call(client, "POST", "/api/automation/rules", json_body={
        "name": "R11 Rule", "event_type": "lead.created", "enabled": True,
        "conditions": [{"field": "source", "op": "eq", "value": "website"}],
        "actions": [{"type": "create_notification", "params": {"title": "New lead"}}]}, note="create automation rule")
    rid = (b or {}).get("id") if isinstance(b, dict) else None
    if rid:
        await call(client, "PATCH", f"/api/automation/rules/{rid}", json_body={"enabled": False}, note="patch automation rule")
        await call(client, "DELETE", f"/api/automation/rules/{rid}", note="delete automation rule")
    # gps devices
    if free_v:
        await call(client, "POST", f"/api/gps/devices/{free_v}/assign", json_body={"imei": "R11IMEI123456", "enabled": True}, note="gps device assign")
        await call(client, "DELETE", f"/api/gps/devices/{free_v}", note="gps device delete")
    await call(client, "POST", "/api/gps/webhook", role="unauth", json_body={"imei": "R11IMEI123456", "lat": -6.9, "lng": 107.6, "speed": 40}, note="gps webhook")
    # locations ingest
    await call(client, "POST", "/api/locations", json_body={"trip_id": S.get("trip"), "lat": -6.91, "lng": 107.61, "speed": 30}, note="location ingest")
    await call(client, "POST", "/api/locations", json_body={"lat": 999, "lng": 999}, note="location invalid coords (400)")


async def sweep_misc(client):
    trip = S.get("trip")
    # shares
    sc, b = await call(client, "POST", "/api/shares", json_body={"trip_id": trip, "label": "R11 share", "hours": 48}, note="create share")
    shid = (b or {}).get("id") if isinstance(b, dict) else None
    if shid:
        await call(client, "POST", f"/api/shares/{shid}/revoke", note="revoke share")
        await call(client, "DELETE", f"/api/shares/{shid}", note="delete share")
    # notifications
    await call(client, "POST", "/api/notifications/scan", note="notifications scan")
    notifs = await get_json(client, "/api/notifications") or []
    nlist = notifs if isinstance(notifs, list) else notifs.get("items", [])
    if nlist:
        nid = nlist[0].get("id")
        await call(client, "POST", f"/api/notifications/{nid}/read", note="notification read")
        await call(client, "POST", f"/api/notifications/{nid}/dismiss", note="notification dismiss")
    await call(client, "POST", "/api/notifications/read_all", note="notifications read_all")
    # onboarding
    await call(client, "POST", "/api/onboarding/complete", json_body={}, note="onboarding complete")
    await call(client, "POST", "/api/onboarding/dismiss", json_body={}, note="onboarding dismiss")
    await call(client, "POST", "/api/onboarding/reset", json_body={}, note="onboarding reset")
    # pricing quote
    await call(client, "POST", "/api/pricing/quote", json_body={"vehicle_type": "hiace_premio", "days": 3, "distance_km": 250, "start_date": fut(days=10)}, note="pricing quote")
    await call(client, "POST", "/api/pricing/quote", json_body={"vehicle_type": "unknown_type", "days": -5, "distance_km": -100}, note="pricing quote clamp negatives")
    # settings — SET-1 negative pricing rules (owner-only)
    await call(client, "PATCH", "/api/settings", json_body={"pricing_rules": {"day_rates": {"hiace_premio": -1000000}, "driver_fee_per_day": -250000, "fuel_per_km": 1800, "dp_percent": 30, "rounding": 1000}}, note="SET-1: negative pricing_rules (expect 200)")
    # restore sane pricing rules
    await call(client, "PATCH", "/api/settings", json_body={"pricing_rules": {"day_rates": {"hiace_premio": 1500000, "hiace": 1200000, "elf": 1600000}, "default_day_rate": 1200000, "driver_fee_per_day": 250000, "fuel_per_km": 1800, "toll_parking_per_day": 200000, "weekend_surcharge_percent": 20, "holiday_surcharge_percent": 30, "dp_percent": 30, "rounding": 1000}}, note="restore pricing_rules")
    await call(client, "PATCH", "/api/settings", json_body={"company_info": {"name": "Rahaza Travel"}}, note="settings company_info")
    # broadcasts (legacy CRM)
    sc, b = await call(client, "POST", "/api/broadcasts", json_body={"title": "R11 Broadcast", "message": "Promo r11", "segment_stage": "quoted"}, note="create broadcast")
    brid = (b or {}).get("id") if isinstance(b, dict) else None
    if brid:
        await call(client, "POST", f"/api/broadcasts/{brid}/send", note="send broadcast")


async def sweep_public(client):
    # public unauth surfaces (booking, chat, lead-ads, quotation, trip-estimate)
    await call(client, "POST", "/api/public/quotation", role="unauth", json_body={
        "name": "R11 Public", "phone": "081277766655", "destination": "Bali", "pax": 4, "message": "mau tanya"}, note="public quotation")
    await call(client, "POST", "/api/public/quotation", role="unauth", json_body={
        "name": "Bot", "phone": "0812", "hp": "spam"}, note="public quotation honeypot (rejected)")
    await call(client, "POST", "/api/public/trip-estimate", role="unauth", json_body={
        "origin": "Bandung", "destination": "Bali", "vehicle_type": "hiace_premio", "days": 3, "distance_km": 300}, note="public trip-estimate")
    await call(client, "POST", "/api/public/booking", role="unauth", json_body={
        "name": "R11 Web", "phone": "081200099988", "origin": "Bandung", "destination": "Bromo",
        "start_datetime": fut(days=120), "end_datetime": fut(days=121), "pax": 6}, note="public booking pending")
    await call(client, "POST", "/api/public/chat", role="unauth", json_body={
        "name": "R11 Chat", "phone": "081299900011", "message": "Halo mau tanya harga"}, note="public chat")
    await call(client, "POST", "/api/public/lead-ads/meta", role="unauth", json_body={
        "full_name": "R11 Ads Lead", "phone_number": "081200011199", "destination": "Bali"}, note="public lead-ads (mock)")
    # approve/reject the public pending booking via ops
    pend = await get_json(client, "/api/bookings?status=pending") or []
    plist = pend if isinstance(pend, list) else pend.get("items", [])
    free_v = (S.get("vehicles") or [None])[-1]
    if plist:
        pbid = plist[0].get("id")
        await call(client, "POST", f"/api/bookings/{pbid}/approve", json_body={"vehicle_id": free_v, "base_price": 3000000}, note="approve public booking")
    if len(plist) > 1:
        await call(client, "POST", f"/api/bookings/{plist[1].get('id')}/reject", json_body={}, note="reject public booking")


async def sweep_reads_exports(client):
    """GET-heavy sweep to cover export/report services (payroll_export, finance_export,
    analytics_export, driver_report) + finance_automation (pl-full/cashflow/recon)."""
    # finance rich reads (finance_automation)
    for p in ["/api/finance/profit-loss", "/api/finance/pl-full", "/api/finance/cashflow",
              "/api/finance/cashflow?months=12", "/api/finance/reconciliation", "/api/finance/summary",
              "/api/finance/ar", "/api/finance/ar/overdue"]:
        await call(client, "GET", p, note="finance read")
    # exports both formats
    for base in ["/api/finance/export", "/api/reports/export", "/api/reports/payroll/export",
                 "/api/reports/drivers/export", "/api/analytics/export"]:
        for fmt in ["excel", "pdf"]:
            await call(client, "GET", f"{base}?format={fmt}", note=f"export {fmt}")
    # report summaries
    for p in ["/api/reports/summary", "/api/reports/payroll", "/api/reports/drivers",
              "/api/payroll/summary", "/api/analytics/summary", "/api/analytics/funnel",
              "/api/analytics/channels", "/api/analytics/fleet", "/api/analytics/drivers",
              "/api/analytics/retention", "/api/analytics/forecast", "/api/analytics/ar-aging",
              "/api/analytics/forecast?metric=leads"]:
        await call(client, "GET", p, note="analytics/report read")
    # payout slip both formats
    payouts = await get_json(client, "/api/payroll/payouts") or []
    plist = payouts if isinstance(payouts, list) else payouts.get("items", [])
    if plist:
        pid = plist[0].get("id")
        for fmt in ["pdf", "excel"]:
            await call(client, "GET", f"/api/payroll/payouts/{pid}/slip?format={fmt}", note=f"payout slip {fmt}")
    # invoice export both formats
    inv = S.get("invoice")
    if inv:
        for fmt in ["pdf", "excel"]:
            await call(client, "GET", f"/api/invoices/{inv}/export?format={fmt}", note=f"invoice export {fmt}")
    # driver performance + vehicle trips + trip eta/track
    drv = S.get("driver")
    if drv:
        await call(client, "GET", f"/api/drivers/{drv}/performance", note="driver performance")
        await call(client, "GET", f"/api/drivers/{drv}/compensation", note="driver compensation read")
    veh = S.get("vehicle")
    if veh:
        await call(client, "GET", f"/api/vehicles/{veh}/trips", note="vehicle trips")
    trip = S.get("trip")
    if trip:
        await call(client, "GET", f"/api/trips/{trip}/eta", note="trip eta")
        await call(client, "GET", f"/api/trips/{trip}/track", note="trip track")
        await call(client, "POST", f"/api/trips/{trip}/status", json_body={"status": "on_trip"}, note="trip status update")
    # analytics with bad date ranges (O-8 observation)
    await call(client, "GET", "/api/analytics/summary?start=GARBAGE", note="analytics bad start (O-8)")
    await call(client, "GET", "/api/analytics/summary?start=2026-01-10&end=2026-01-01", note="analytics reversed range (O-8)")


async def sweep_public_reads(client):
    for p in ["/api/public/company", "/api/public/theme", "/api/public/stats",
              "/api/public/destinations", "/api/public/packages", "/api/public/promos",
              "/api/public/testimonials", "/api/public/articles", "/api/public/fleet"]:
        await call(client, "GET", p, role="unauth", note="public read")
    # detail endpoints (resolve a slug/id)
    dests = await get_json(client, "/api/public/destinations", role="unauth") or []
    dl = dests if isinstance(dests, list) else dests.get("items", [])
    if dl:
        slug = dl[0].get("slug")
        if slug:
            await call(client, "GET", f"/api/public/destinations/{slug}", role="unauth", note="public destination detail")
    arts = await get_json(client, "/api/public/articles", role="unauth") or []
    al = arts if isinstance(arts, list) else arts.get("items", [])
    if al:
        aslug = al[0].get("slug")
        if aslug:
            await call(client, "GET", f"/api/public/articles/{aslug}", role="unauth", note="public article detail")
    fleet = await get_json(client, "/api/public/fleet", role="unauth") or []
    fl = fleet if isinstance(fleet, list) else fleet.get("items", [])
    if fl:
        await call(client, "GET", f"/api/public/fleet/{fl[0].get('id')}", role="unauth", note="public fleet detail")
    await call(client, "GET", "/api/public/destinations/nonexistent-slug", role="unauth", note="public detail 404")


async def sweep_bookings_deep(client):
    """DP/hold + complete + cancel-with-refund + group auto-price flows."""
    cust = S.get("customer")
    free_v = (S.get("vehicles") or [None])[-1]
    drvs = S.get("drivers") or []
    # 1) require_dp -> hold; then DP payment -> auto-confirm
    sc, b = await call(client, "POST", "/api/bookings", json_body={
        "customer_id": cust, "vehicle_id": free_v, "start_datetime": fut(days=130), "end_datetime": fut(days=131),
        "base_price": 4000000, "require_dp": True, "hold_hours": 24}, note="booking require_dp -> hold")
    hbid = (b or {}).get("id") if isinstance(b, dict) else None
    if hbid:
        await call(client, "POST", "/api/payments", json_body={
            "booking_id": hbid, "amount": 1200000, "type": "dp", "method": "transfer",
            "idempotency_key": f"dp-{datetime.now().microsecond}"}, note="DP payment on hold -> auto-confirm")
        await call(client, "POST", f"/api/bookings/{hbid}/complete", note="complete hold->confirmed booking")
    # 2) create -> confirm -> pay -> cancel with refund+fee (hits refund/cfee ledger branches)
    sc, b = await call(client, "POST", "/api/bookings", json_body={
        "customer_id": cust, "vehicle_id": free_v, "start_datetime": fut(days=140), "end_datetime": fut(days=141),
        "base_price": 3000000}, note="booking for cancel-refund")
    cbid = (b or {}).get("id") if isinstance(b, dict) else None
    if cbid:
        await call(client, "POST", f"/api/bookings/{cbid}/confirm", note="confirm for cancel-refund")
        await call(client, "POST", "/api/payments", json_body={
            "booking_id": cbid, "amount": 1000000, "type": "dp", "method": "transfer",
            "idempotency_key": f"cr-{datetime.now().microsecond}"}, note="pay before cancel")
        await call(client, "POST", f"/api/bookings/{cbid}/cancel", json_body={
            "reason": "customer batal", "cancellation_fee": 300000, "refund_amount": 700000}, note="cancel with refund+fee (ledger)")
    # 3) plain create -> confirm -> complete (no trip path)
    sc, b = await call(client, "POST", "/api/bookings", json_body={
        "customer_id": cust, "vehicle_id": free_v, "start_datetime": fut(days=150), "end_datetime": fut(days=151),
        "base_price": 2000000}, note="booking for complete-no-trip")
    cpid = (b or {}).get("id") if isinstance(b, dict) else None
    if cpid:
        await call(client, "POST", f"/api/bookings/{cpid}/confirm", note="confirm for complete")
        await call(client, "POST", f"/api/bookings/{cpid}/complete", note="complete no-trip booking")
    # 4) group booking 2 units with base_price=0 (auto-price via pricing engine)
    vehs = S.get("vehicles") or []
    if len(vehs) >= 2:
        await call(client, "POST", "/api/bookings/group", json_body={
            "customer_id": cust, "note": "r11 group autoprice", "units": [
                {"vehicle_id": vehs[-1], "start_datetime": fut(days=160), "end_datetime": fut(days=162), "base_price": 0},
                {"vehicle_id": vehs[-2], "start_datetime": fut(days=160), "end_datetime": fut(days=162), "base_price": 0},
            ]}, note="group booking auto-price 2 units")


async def sweep_automation_deep(client):
    await call(client, "POST", "/api/automation/rules/reset-defaults", json_body={}, note="automation reset-defaults")
    # rules with varied action types, then trigger matching events
    for evt, action in [
        ("lead.created", {"type": "create_task", "params": {"title": "Follow up"}}),
        ("booking.confirmed", {"type": "create_notification", "params": {"title": "Booking baru", "target_role": "manager"}}),
        ("quotation.sent", {"type": "schedule_followup", "params": {"delay_hours": 24}}),
        ("lead.created", {"type": "assign_agent", "params": {}}),
    ]:
        await call(client, "POST", "/api/automation/rules", json_body={
            "name": f"R11 {evt} {action['type']}", "event_type": evt, "enabled": True,
            "conditions": [], "actions": [action]}, note=f"rule {action['type']}")
    # trigger events by creating a lead + quotation + booking
    sc, b = await call(client, "POST", "/api/leads", json_body={
        "customer_name": "R11 Auto Lead", "phone": "0812555000", "source": "website"}, note="lead to trigger automation")
    sc, q = await call(client, "POST", "/api/quotations", json_body={
        "customer_name": "R11 Auto Quo", "phone": "0812555111", "items": [{"label": "x", "amount": 1000}]}, note="quo to trigger")
    if isinstance(q, dict) and q.get("id"):
        await call(client, "POST", f"/api/quotations/{q['id']}/send", note="send quo -> event")


async def sweep_gps_deep(client):
    free_v = (S.get("vehicles") or [None])[-1]
    secret = os.environ.get("GPS_WEBHOOK_SECRET", "")
    imei = f"R11DEV{datetime.now().microsecond}"
    if free_v:
        await call(client, "POST", f"/api/gps/devices/{free_v}/assign", json_body={"imei": imei, "enabled": True, "note": "r11"}, note="gps assign for webhook")
    # traccar-style webhook (needs secret configured in harness env)
    payload = {"device": {"uniqueId": imei, "name": "R11 Tracker"},
               "position": {"latitude": -6.9, "longitude": 107.62, "speed": 20, "course": 90,
                            "valid": True, "fixTime": fut(hours=-1),
                            "attributes": {"ignition": True, "motion": True, "power": 12.4, "battery": 90, "sat": 8}}}
    if secret:
        await call(client, "POST", f"/api/gps/webhook?token={secret}", role="unauth", json_body=payload, note="gps webhook traccar (authed)")
        # invalid coord + unmapped imei branches
        await call(client, "POST", f"/api/gps/webhook?token={secret}", role="unauth", json_body={"device": {"uniqueId": imei}, "position": {"latitude": 999, "longitude": 999}}, note="gps webhook invalid coord")
        await call(client, "POST", f"/api/gps/webhook?token={secret}", role="unauth", json_body={"device": {"uniqueId": "UNMAPPED999"}, "position": {"latitude": -6.9, "longitude": 107.6}}, note="gps webhook unmapped imei")
    await call(client, "POST", "/api/gps/webhook", role="unauth", json_body=payload, note="gps webhook no token (401)")
    # reads
    for p in ["/api/gps/live", "/api/gps/devices", "/api/gps/summary"]:
        await call(client, "GET", p, note="gps read")
    if free_v:
        await call(client, "DELETE", f"/api/gps/devices/{free_v}", note="gps unassign after webhook")


async def sweep_campaign_reads(client):
    camps = await get_json(client, "/api/crm/campaigns") or []
    cl = camps if isinstance(camps, list) else camps.get("items", [])
    if cl:
        cid = cl[0].get("id")
        await call(client, "GET", f"/api/crm/campaigns/{cid}", note="campaign detail (incl recipients)")
    # sequence enrollments read
    seqs = await get_json(client, "/api/crm/sequences") or []
    sl = seqs if isinstance(seqs, list) else seqs.get("items", [])
    if sl:
        await call(client, "GET", f"/api/crm/sequences/{sl[0].get('id')}/enrollments", note="sequence enrollments")
    await call(client, "GET", "/api/crm/scoreboard", note="crm scoreboard")
    await call(client, "GET", "/api/crm/rfm", note="crm rfm")
    await call(client, "GET", "/api/crm/aging", note="crm aging")


async def sweep_auth_ratelimit(client):
    # me + logout (uses a throwaway login to avoid killing owner token)
    await call(client, "GET", "/api/auth/me", note="auth me")
    r = None
    try:
        r = await client.post(API + "/api/auth/login", json=CREDS["ops"], timeout=20)
        tok = r.json().get("token")
        if tok:
            await call(client, "POST", "/api/auth/logout", role="ops", note="auth logout")
    except Exception:
        pass
    # invalid login (wrong password) — failure path
    for i in range(3):
        await call(client, "POST", "/api/auth/login", role="unauth",
                   json_body={"email": "owner@demo.local", "password": "WRONGPASS"}, note="invalid login (401)")
    # ratelimit trigger: 9 failed logins for a distinct fake email -> 429
    for i in range(10):
        await call(client, "POST", "/api/auth/login", role="unauth",
                   json_body={"email": "bruteforce@demo.local", "password": f"x{i}"}, note="ratelimit brute (expect 429 after 8)")
    # missing fields
    await call(client, "POST", "/api/auth/login", role="unauth", json_body={}, note="login empty body")


async def sweep_driver_role(client):
    """Exercise DRIVER-role surface on driver's own trips (seed links driver@demo.local)."""
    trips = await get_json(client, "/api/driver/my-trips", role="driver") or []
    await call(client, "GET", "/api/driver/my-trips", role="driver", note="driver my-trips")
    await call(client, "GET", "/api/driver/summary", role="driver", note="driver summary")
    await call(client, "GET", "/api/driver/tasks", role="driver", note="driver tasks")
    if trips:
        # pick an active trip (on_trip/to_pickup) for ack/arrived/pod
        active = next((t for t in trips if t.get("status") in ("on_trip", "to_pickup", "standby", "arrived")), trips[0])
        tid = active.get("id")
        if tid:
            await call(client, "POST", f"/api/driver/tasks/{tid}/ack", role="driver", note="driver ack own trip")
            await call(client, "POST", f"/api/driver/tasks/{tid}/arrived", role="driver", note="driver arrived own trip")
            await call(client, "POST", f"/api/driver/tasks/{tid}/pod", role="driver",
                       data={"recipient_name": "Pak Driver", "note": "diterima driver"}, note="driver POD own trip")
        # RBAC: driver tries to ack a trip not owned
        await call(client, "POST", "/api/driver/tasks/trp_notowned/ack", role="driver", note="driver ack missing trip (404)")


async def sweep_scheduler_seed(client):
    """Create durable enrollments + a due scheduled campaign so the background scheduler
    (process_due / process_scheduled) exercises services/sequences.py + campaigns.py on its
    next tick (orchestrator waits ~125s at the end)."""
    lead = S.get("lead")
    # enabled sequence (do NOT delete) with immediate first step
    sc, b = await call(client, "POST", "/api/crm/sequences", json_body={
        "name": "R11 Sched Seq", "audience": "lead", "enabled": True, "steps": [
            {"delay_hours": 0, "action": "send_wa", "text": "Halo {name}, step-0 r11"},
            {"delay_hours": 0, "action": "create_notification", "text": "step-1"}]}, note="sched sequence")
    seq = (b or {}).get("id") if isinstance(b, dict) else None
    if seq and lead:
        await call(client, "POST", f"/api/crm/sequences/{seq}/enroll", json_body={"target_id": lead}, note="enroll lead (due now)")
    # enroll a whole segment (enroll_members path) — audience customer, all
    sc, sb = await call(client, "POST", "/api/crm/segments", json_body={
        "name": "R11 Sched Seg", "audience": "lead", "criteria": {}}, note="segment for member enroll")
    seg = (sb or {}).get("id") if isinstance(sb, dict) else None
    sc, b2 = await call(client, "POST", "/api/crm/sequences", json_body={
        "name": "R11 Sched Seq2", "audience": "lead", "enabled": True, "steps": [
            {"delay_hours": 0, "action": "send_wa", "text": "Hi {name}"}]}, note="sched sequence2")
    seq2 = (b2 or {}).get("id") if isinstance(b2, dict) else None
    if seq2 and seg:
        await call(client, "POST", f"/api/crm/sequences/{seq2}/enroll", json_body={"segment_id": seg}, note="enroll segment members")
    # scheduled campaign in the PAST -> process_scheduled sends it on next tick
    await call(client, "POST", "/api/crm/campaigns", json_body={
        "name": "R11 Scheduled Campaign", "audience": "customer", "criteria": {"min_value": 0},
        "message": "Promo terjadwal {name}", "scheduled_at": fut(days=-1)}, note="scheduled campaign (past)")


async def sweep_error_branches(client):
    """Trigger 404/400/422 guard branches cheaply across routers (defensive code paths)."""
    NX = "NONEXISTENT_ID_R11"
    cust = S.get("customer")
    free_v = (S.get("vehicles") or [None])[-1]
    # bookings create guards
    await call(client, "POST", "/api/bookings", json_body={"customer_id": NX, "vehicle_id": free_v, "start_datetime": fut(1), "end_datetime": fut(2), "base_price": 1000}, note="booking bad customer (400)")
    await call(client, "POST", "/api/bookings", json_body={"customer_id": cust, "vehicle_id": NX, "start_datetime": fut(1), "end_datetime": fut(2), "base_price": 1000}, note="booking bad vehicle (400)")
    await call(client, "POST", "/api/bookings", json_body={"customer_id": cust, "vehicle_id": free_v, "driver_id": NX, "start_datetime": fut(1), "end_datetime": fut(2), "base_price": 1000}, note="booking bad driver (400)")
    await call(client, "POST", "/api/bookings", json_body={"customer_id": cust, "vehicle_id": free_v, "base_price": 1000}, note="booking missing dates (400)")
    await call(client, "POST", "/api/bookings", json_body={"customer_id": cust, "vehicle_id": free_v, "start_datetime": "not-a-date", "end_datetime": "also-bad", "base_price": 1000}, note="booking bad date format (400)")
    await call(client, "POST", "/api/bookings/group", json_body={"customer_id": cust, "units": []}, note="group booking empty units (400)")
    await call(client, "POST", "/api/bookings/group", json_body={"customer_id": NX, "units": [{"vehicle_id": free_v, "start_datetime": fut(1), "end_datetime": fut(2), "base_price": 1}]}, note="group bad customer (400)")
    # detail/transition 404s
    for m, p, note in [
        ("GET", f"/api/bookings/{NX}", "booking 404"),
        ("PATCH", f"/api/bookings/{NX}", "booking patch 404"),
        ("POST", f"/api/bookings/{NX}/confirm", "confirm 404"),
        ("POST", f"/api/bookings/{NX}/cancel", "cancel 404"),
        ("POST", f"/api/bookings/{NX}/approve", "approve 404"),
        ("POST", f"/api/bookings/{NX}/reject", "reject 404"),
        ("POST", f"/api/bookings/{NX}/reschedule", "reschedule 404"),
        ("GET", f"/api/quotations/{NX}", "quotation 404"),
        ("GET", f"/api/quotations/{NX}/pdf", "quotation pdf 404"),
        ("POST", f"/api/quotations/{NX}/send", "quo send 404"),
        ("POST", f"/api/quotations/{NX}/accept", "quo accept 404"),
        ("POST", f"/api/quotations/{NX}/reject", "quo reject 404"),
        ("GET", f"/api/subcharters/{NX}", "subcharter 404"),
        ("PATCH", f"/api/subcharters/{NX}", "subcharter patch 404"),
        ("POST", f"/api/subcharters/{NX}/confirm", "subcharter confirm 404"),
        ("POST", f"/api/subcharters/{NX}/settle", "subcharter settle 404"),
        ("POST", f"/api/subcharters/{NX}/cancel", "subcharter cancel 404"),
        ("GET", f"/api/conversations/{NX}", "conversation 404"),
        ("PATCH", f"/api/conversations/{NX}", "conversation patch 404"),
        ("POST", f"/api/conversations/{NX}/read", "conversation read 404"),
        ("GET", f"/api/maintenance/{NX}", "maintenance 404"),
        ("PATCH", f"/api/maintenance/{NX}", "maintenance patch 404"),
        ("POST", f"/api/maintenance/{NX}/complete", "maintenance complete 404"),
        ("DELETE", f"/api/maintenance/{NX}", "maintenance delete 404"),
        ("GET", f"/api/trips/{NX}", "trip 404"),
        ("GET", f"/api/trips/{NX}/track", "trip track 404"),
        ("GET", f"/api/trips/{NX}/eta", "trip eta 404"),
        ("POST", f"/api/dispatch/{NX}/confirm-departure", "confirm-departure 404"),
        ("POST", f"/api/dispatch/trips/{NX}/enroute", "enroute 404"),
        ("POST", f"/api/dispatch/trips/{NX}/arrived", "arrived 404"),
        ("GET", f"/api/vehicles/{NX}/trips", "vehicle trips 404/empty"),
        ("GET", f"/api/drivers/{NX}/performance", "driver perf 404"),
        ("PATCH", f"/api/vehicles/{NX}", "vehicle patch 404"),
        ("DELETE", f"/api/vehicles/{NX}", "vehicle delete 404"),
        ("PATCH", f"/api/drivers/{NX}", "driver patch 404"),
        ("PATCH", f"/api/customers/{NX}", "customer patch 404"),
        ("PATCH", f"/api/partners/{NX}", "partner patch 404"),
        ("PATCH", f"/api/leads/{NX}", "lead patch 404"),
        ("POST", f"/api/leads/{NX}/convert", "lead convert 404"),
        ("PATCH", f"/api/users/{NX}", "user patch 404"),
        ("PATCH", f"/api/invoices/{NX}", "invoice patch 404"),
    ]:
        await call(client, m, p, json_body={} if m in ("POST", "PATCH") else None, note=note)
    # payment/expense/invoice against bad booking
    await call(client, "POST", "/api/payments", json_body={"booking_id": NX, "amount": 1000, "type": "dp", "idempotency_key": f"nx-{datetime.now().microsecond}"}, note="payment bad booking")
    await call(client, "POST", "/api/invoices", json_body={"booking_id": NX, "amount": 1000}, note="invoice bad booking")
    # trip status invalid
    trip = S.get("trip")
    if trip:
        await call(client, "POST", f"/api/trips/{trip}/status", json_body={"status": "bogus_status"}, note="trip status invalid")
    # locations reads + driver ingest
    await call(client, "GET", "/api/locations/live", note="locations live")
    await call(client, "GET", "/api/locations/history?trip_id=" + (trip or NX), note="locations history")


async def sweep_content_deep(client):
    ts = datetime.now().microsecond
    resources = {
        "articles": {"slug": f"art-{ts}", "title": "A", "excerpt": "e", "body": "b", "read_minutes": 3, "published": True},
        "packages": {"slug": f"pkg-{ts}", "name": "P", "days": 2, "price_from": 1000000, "active": True},
        "promos": {"code": f"PR{ts}", "title": "Promo", "discount_type": "percent", "discount_value": 5, "active": True},
        "testimonials": {"name": "T", "role": "Cust", "quote": "Nice", "rating": 4, "approved": True},
    }
    for res, body in resources.items():
        await call(client, "GET", f"/api/content/{res}", note=f"content list {res}")
        sc, b = await call(client, "POST", f"/api/content/{res}", json_body=body, note=f"content create {res}")
        iid = (b or {}).get("id") if isinstance(b, dict) else None
        if iid:
            await call(client, "PUT", f"/api/content/{res}/{iid}", json_body={**body, "active": False, "published": False}, note=f"content update {res}")
            await call(client, "POST", f"/api/content/{res}/{iid}/duplicate", note=f"content duplicate {res}")
            await call(client, "DELETE", f"/api/content/{res}/{iid}", note=f"content delete {res}")
    # 404s
    await call(client, "PUT", "/api/content/articles/NOPE", json_body={"title": "x"}, note="content update 404")
    await call(client, "DELETE", "/api/content/packages/NOPE", note="content delete 404")
    await call(client, "POST", "/api/content/promos/NOPE/duplicate", note="content duplicate 404")
    await call(client, "GET", "/api/content/unknownresource", note="content unknown resource GET (404)")


async def sweep_whatsapp_meta(client):
    """Cover MetaCloud provider not-ready branch + varied inbound routing, then revert to mock."""
    # switch to meta_cloud WITHOUT credentials -> send returns 'failed' (covers _ready False)
    await call(client, "PATCH", "/api/wa/config", json_body={"provider": "meta_cloud", "meta": {"api_version": "v21.0"}}, note="wa config -> meta_cloud (no creds)")
    await call(client, "POST", "/api/wa/test-send", json_body={"to_phone": "0812000111", "text": "meta test"}, note="wa test-send meta (failed no creds)")
    # varied inbound texts (keyword/auto-reply/opt-out routing)
    for txt in ["harga sewa hiace ke Bali", "STOP", "info lokasi kantor", "mau booking besok", "BERHENTI", "terima kasih"]:
        await call(client, "POST", "/api/wa/simulate-inbound", role="unauth", json_body={"from_phone": "081277700011", "text": txt, "name": "R11 WA"}, note=f"inbound '{txt[:14]}'")
    # inbound from an existing customer phone (covers customer-match branch)
    custs = await get_json(client, "/api/customers") or []
    cl = custs if isinstance(custs, list) else custs.get("items", [])
    if cl and cl[0].get("phone"):
        await call(client, "POST", "/api/wa/simulate-inbound", role="unauth", json_body={"from_phone": cl[0]["phone"], "text": "halo dari customer terdaftar"}, note="inbound from known customer")
    # empty inbound (ignored branch)
    await call(client, "POST", "/api/wa/simulate-inbound", role="unauth", json_body={"from_phone": "", "text": ""}, note="inbound empty (ignored)")
    # revert to mock so rest of system behaves
    await call(client, "PATCH", "/api/wa/config", json_body={"provider": "mock", "auto_reply_enabled": True, "away_reply_text": "Di luar jam kerja"}, note="wa config -> mock (revert)")


async def sweep_dispatch_subcharter_edges(client):
    cust = S.get("customer")
    free_v = (S.get("vehicles") or [None])[-1]
    drvs = S.get("drivers") or []
    partner = S.get("partner")
    booking = S.get("booking")
    # complete-with-active-trip (finalize path): create -> confirm -> assign -> complete
    sc, b = await call(client, "POST", "/api/bookings", json_body={
        "customer_id": cust, "vehicle_id": free_v, "start_datetime": fut(170), "end_datetime": fut(171), "base_price": 2000000}, note="booking for trip-finalize")
    bid = (b or {}).get("id") if isinstance(b, dict) else None
    if bid:
        await call(client, "POST", f"/api/bookings/{bid}/confirm", note="confirm for finalize")
        await call(client, "POST", f"/api/dispatch/{bid}/assign", json_body={"driver_id": drvs[0], "vehicle_id": free_v}, note="assign for finalize")
        # assign AGAIN (already assigned -> 400)
        await call(client, "POST", f"/api/dispatch/{bid}/assign", json_body={"driver_id": drvs[0], "vehicle_id": free_v}, note="assign already-assigned (400)")
        await call(client, "POST", f"/api/bookings/{bid}/complete", note="complete WITH active trip (finalize_trip_completion)")
    # approve with driver + base=0 (auto-price + driver branch): make a pending via public
    await call(client, "POST", "/api/public/booking", role="unauth", json_body={
        "name": "R11 Approve", "phone": "081200055500", "origin": "Bandung", "destination": "Bali",
        "start_datetime": fut(180), "end_datetime": fut(181), "pax": 4}, note="public pending for approve")
    pend = await get_json(client, "/api/bookings?status=pending") or []
    pl = pend if isinstance(pend, list) else pend.get("items", [])
    if pl:
        await call(client, "POST", f"/api/bookings/{pl[0].get('id')}/approve", json_body={
            "vehicle_id": free_v, "driver_id": drvs[0], "base_price": 0}, note="approve auto-price + driver")
    if len(pl) > 1:
        await call(client, "POST", f"/api/bookings/{pl[1].get('id')}/reject", json_body={}, note="reject pending")
    # subcharter edge: confirm then confirm again, settle then settle again, cancel a confirmed
    sc, b = await call(client, "POST", "/api/subcharters", json_body={
        "booking_id": booking, "partner_id": partner, "vehicle_label": "R11 Edge", "cost": 900000}, note="subcharter for edges")
    scid = (b or {}).get("id") if isinstance(b, dict) else None
    if scid:
        await call(client, "POST", f"/api/subcharters/{scid}/confirm", note="confirm subcharter edge")
        await call(client, "POST", f"/api/subcharters/{scid}/confirm", note="confirm again (idempotent/400)")
        await call(client, "POST", f"/api/subcharters/{scid}/settle", json_body={"amount": 900000, "method": "cash"}, note="settle subcharter edge")
        await call(client, "POST", f"/api/subcharters/{scid}/settle", json_body={"amount": 100, "method": "cash"}, note="settle again (400/over)")
        await call(client, "POST", f"/api/subcharters/{scid}/cancel", note="cancel settled (400?)")


async def sweep_automation_conditions(client):
    """Cover automation _match_one operators + _do_enroll_sequence + unknown action + skip paths."""
    # need a sequence id for enroll_sequence action
    seqs = await get_json(client, "/api/crm/sequences") or []
    sl = seqs if isinstance(seqs, list) else seqs.get("items", [])
    seq_id = sl[0].get("id") if sl else None
    conds_rules = [
        ([{"field": "source", "op": "eq", "value": "website"}], {"type": "create_task", "params": {"title": "eq match"}}),
        ([{"field": "source", "op": "ne", "value": "walk_in"}], {"type": "create_notification", "params": {"title": "ne"}}),
        ([{"field": "destination", "op": "contains", "value": "bali"}], {"type": "create_notification", "params": {"title": "contains"}}),
        ([{"field": "source", "op": "in", "value": ["website", "meta_ads"]}], {"type": "create_task", "params": {"title": "in"}}),
        ([{"field": "value", "op": "gt", "value": 1000}], {"type": "create_notification", "params": {"title": "gt"}}),
        ([{"field": "value", "op": "lt", "value": 999999999}], {"type": "create_notification", "params": {"title": "lt"}}),
        ([{"field": "phone", "op": "exists"}], {"type": "create_task", "params": {"title": "exists"}}),
        ([{"field": "customer.name", "op": "eq", "value": "x"}], {"type": "create_task", "params": {"title": "nested-miss"}}),
        ([{"field": "source", "op": "eq", "value": "IMPOSSIBLE_VALUE"}], {"type": "create_notification", "params": {"title": "wont-match"}}),
        ([], {"type": "totally_unknown_action_type", "params": {}}),
    ]
    if seq_id:
        conds_rules.append(([{"field": "phone", "op": "exists"}], {"type": "enroll_sequence", "params": {"sequence_id": seq_id}}))
    for conds, action in conds_rules:
        await call(client, "POST", "/api/automation/rules", json_body={
            "name": f"R11 cond {action['type']} {conds[0]['op'] if conds else 'none'}",
            "event_type": "lead.created", "enabled": True, "conditions": conds, "actions": [action]},
            note=f"cond rule {action['type']}")
    # trigger leads: one that matches most, one that won't (walk_in, low value)
    await call(client, "POST", "/api/leads", json_body={
        "customer_name": "R11 Match Lead", "phone": "0812600011", "source": "website",
        "destination": "Bali Trip", "pax": 5, "value": 5000000}, note="lead matching many conds")
    await call(client, "POST", "/api/leads", json_body={
        "customer_name": "R11 NoMatch", "phone": "0812600022", "source": "walk_in",
        "destination": "Bromo", "value": 100}, note="lead not matching (skip path)")


async def sweep_whatsapp_extra(client):
    # template send path via test-send with template_key
    await call(client, "PUT", "/api/wa/templates/r11_extra", json_body={
        "name": "R11 Extra", "language": "id", "category": "utility", "body": "Halo {name}, kode {code}"}, note="wa template for send")
    # send using template (covers send_template branch in send_wa)
    conv = None
    convs = await get_json(client, "/api/conversations") or []
    cvl = convs if isinstance(convs, list) else convs.get("items", [])
    if cvl:
        conv = cvl[0].get("id")
    # opt-out a conversation then attempt agent send (covers opt_out skip branch)
    if conv:
        await call(client, "POST", f"/api/conversations/{conv}/wa-optout", note="optout for skip test")
        await call(client, "POST", f"/api/conversations/{conv}/messages", json_body={"body": "pesan ke opted-out", "internal": False, "via_wa": True}, note="send to opted-out (skip)")
        await call(client, "POST", f"/api/conversations/{conv}/wa-optin", note="optin restore")
    await call(client, "DELETE", "/api/wa/templates/r11_extra", note="cleanup template")


async def sweep_final_edges(client):
    cust = S.get("customer")
    free_v = (S.get("vehicles") or [None])[-1]
    drvs = S.get("drivers") or []
    # --- quotations: list filters + PATCH re-price/items + convert error branches ---
    await call(client, "GET", "/api/quotations?status=draft", note="quotations filter status")
    await call(client, "GET", "/api/quotations?lead_id=" + (S.get("lead") or "x"), note="quotations filter lead")
    sc, b = await call(client, "POST", "/api/quotations", json_body={
        "customer_name": "R11 Reprice", "phone": "0812700011", "vehicle_type": "hiace_premio",
        "days": 2, "distance_km": 200}, note="quotation for reprice")
    qid = (b or {}).get("id") if isinstance(b, dict) else None
    if qid:
        await call(client, "PATCH", f"/api/quotations/{qid}", json_body={
            "items": [{"label": "Sewa 3 hari", "amount": 4500000}, {"label": "Tol", "amount": 300000}]}, note="quotation patch items (recompute)")
        await call(client, "PATCH", f"/api/quotations/{qid}", json_body={
            "vehicle_type": "elf_long", "days": 4, "distance_km": 500}, note="quotation patch re-price")
        await call(client, "POST", f"/api/quotations/{qid}/send", note="send repriced quo")
        await call(client, "POST", f"/api/quotations/{qid}/accept", note="accept repriced quo")
        await call(client, "POST", f"/api/quotations/{qid}/convert", json_body={
            "vehicle_id": "NONEXISTENT", "start_datetime": fut(1), "end_datetime": fut(2)}, note="convert bad vehicle (400)")
        # convert with driver conflict evidence (Q-BUG-1): use a driver already booked
        await call(client, "POST", f"/api/quotations/{qid}/convert", json_body={
            "vehicle_id": free_v, "driver_id": (drvs[0] if drvs else None),
            "start_datetime": fut(200), "end_datetime": fut(201)}, note="convert w/ driver (Q-BUG-1 path)")
    # --- public chat token + track token + existing-phone (identity dedup) ---
    sc, ch = await call(client, "POST", "/api/public/chat", role="unauth", json_body={
        "name": "R11 ChatTok", "phone": "0812700022", "message": "Halo, info harga?"}, note="public chat -> token")
    token = None
    if isinstance(ch, dict):
        token = ch.get("token") or ch.get("chat_token") or (ch.get("conversation") or {}).get("chat_token")
    if token:
        await call(client, "GET", f"/api/public/chat/{token}", role="unauth", note="public chat history by token")
        await call(client, "POST", f"/api/public/chat/{token}", role="unauth", json_body={"message": "lanjut chat"}, note="public chat reply by token")
    await call(client, "GET", "/api/public/chat/BADTOKEN", role="unauth", note="public chat bad token (404)")
    # existing-phone booking -> identity.ensure_customer dedup branch
    custs = await get_json(client, "/api/customers") or []
    cl = custs if isinstance(custs, list) else custs.get("items", [])
    if cl and cl[0].get("phone"):
        await call(client, "POST", "/api/public/booking", role="unauth", json_body={
            "name": cl[0].get("name") or "Existing", "phone": cl[0]["phone"], "origin": "Bandung",
            "destination": "Bali", "start_datetime": fut(210), "end_datetime": fut(211), "pax": 3}, note="public booking existing phone (dedup)")
    # trip share token public read
    trip = S.get("trip")
    if trip:
        sc, sh = await call(client, "POST", "/api/shares", json_body={"trip_id": trip, "hours": 24}, note="share for public track")
        tok2 = (sh or {}).get("token") if isinstance(sh, dict) else None
        if tok2:
            await call(client, "GET", f"/api/public/track/{tok2}", role="unauth", note="public track by token")
    # --- locations: driver ingest to active trip -> live/history compute ---
    mytrips = await get_json(client, "/api/driver/my-trips", role="driver") or []
    active = next((t for t in mytrips if t.get("status") in ("on_trip", "to_pickup")), None)
    if active:
        tid = active.get("id")
        for lat, lng in [(-6.90, 107.60), (-6.85, 107.55), (-6.80, 107.50)]:
            await call(client, "POST", "/api/locations", role="driver", json_body={
                "trip_id": tid, "lat": lat, "lng": lng, "speed": 45, "heading": 90}, note="driver location ingest")
        await call(client, "GET", f"/api/locations/history?trip_id={tid}", note="locations history w/ data")
        await call(client, "GET", f"/api/trips/{tid}/track", note="trip track w/ data")
        await call(client, "GET", f"/api/trips/{tid}/eta", note="trip eta w/ data")
    await call(client, "GET", "/api/locations/live", note="locations live w/ data")
    # --- maintenance: preventive/reminders/summary + complete-from-scheduled ---
    await call(client, "GET", "/api/maintenance/reminders", note="maintenance reminders")
    await call(client, "GET", "/api/maintenance/summary", note="maintenance summary")
    await call(client, "GET", "/api/maintenance/preventive", note="maintenance preventive list")
    veh = S.get("vehicle")
    if veh:
        await call(client, "POST", f"/api/maintenance/preventive/{veh}/schedule", json_body={"service_type": "servis_rutin"}, note="preventive schedule typed")
    # --- inbox: existing-phone conversation (merge) + richer patch ---
    if cl and cl[0].get("phone"):
        await call(client, "POST", "/api/conversations", json_body={
            "channel": "whatsapp", "contact_name": cl[0].get("name"), "contact_phone": cl[0]["phone"],
            "customer_id": cl[0].get("id"), "message": "reuse conv"}, note="conversation existing phone (merge)")
    # --- leads: list filters + activity variety + stage transitions ---
    await call(client, "GET", "/api/leads?stage=new", note="leads filter stage")
    await call(client, "GET", "/api/leads?assigned_to=me", note="leads filter assigned")
    sc, b = await call(client, "POST", "/api/leads", json_body={
        "customer_name": "R11 Lead Flow", "phone": "0812700033", "source": "referral", "destination": "Lombok"}, note="lead for flow")
    lid = (b or {}).get("id") if isinstance(b, dict) else None
    if lid:
        for atype, txt in [("call", "telepon"), ("whatsapp", "chat wa"), ("email", "kirim email"), ("meeting", "ketemu")]:
            await call(client, "POST", f"/api/leads/{lid}/activities", json_body={"type": atype, "text": txt}, note=f"lead activity {atype}")
        for stg in ["contacted", "quoted", "negotiation", "won"]:
            await call(client, "POST", f"/api/leads/{lid}/stage", json_body={"stage": stg}, note=f"lead stage {stg}")
    # --- subcharters: available-partners + richer patch ---
    await call(client, "GET", "/api/subcharters/available-partners?start=" + fut(1) + "&end=" + fut(2), note="subcharter available-partners")
    await call(client, "GET", "/api/subcharters/available-partners", note="subcharter available-partners no-args")


async def sweep_ceiling_push(client):
    """Final targeted batch for remaining reachable multi-line blocks."""
    secret = os.environ.get("GPS_WEBHOOK_SECRET", "")
    free_v = (S.get("vehicles") or [None])[-1]
    # --- identity.normalize_phone variants via public quotation (ensure_customer/lead) ---
    for i, ph in enumerate(["+62 812-3456-7890", "0812 3456 7891", "62812-3456-7892", "  0812.3456.7893  ", "812-3456-7894"]):
        await call(client, "POST", "/api/public/quotation", role="unauth", json_body={
            "name": f"R11 Phone {i}", "phone": ph, "destination": "Bali", "pax": 2, "message": "tanya"}, note=f"identity phone fmt {i}")
    # --- gps: assign device, send pings w/ alarm attributes, then live/summary compute ---
    imei = f"R11CEIL{datetime.now().microsecond}"
    if free_v and secret:
        await call(client, "POST", f"/api/gps/devices/{free_v}/assign", json_body={"imei": imei, "enabled": True}, note="gps assign ceiling")
        for lat, lng, extra in [
            (-6.90, 107.60, {"ignition": True, "motion": True, "speed": 60}),
            (-6.85, 107.55, {"ignition": True, "motion": False, "alarm": "sos"}),
            (-6.80, 107.50, {"ignition": False, "motion": False, "alarm": "overspeed", "speed": 120}),
        ]:
            await call(client, "POST", f"/api/gps/webhook?token={secret}", role="unauth", json_body={
                "device": {"uniqueId": imei}, "position": {
                    "latitude": lat, "longitude": lng, "speed": extra.get("speed", 0), "course": 45,
                    "valid": True, "fixTime": fut(hours=-1), "attributes": extra}}, note="gps ping w/ alarm")
        await call(client, "GET", "/api/gps/live", note="gps live after pings")
        await call(client, "GET", "/api/gps/summary", note="gps summary after pings")
        await call(client, "DELETE", f"/api/gps/devices/{free_v}", note="gps unassign ceiling")
    # --- dispatch today board ---
    await call(client, "GET", "/api/dispatch/today", note="dispatch today")
    await call(client, "GET", f"/api/dispatch/today?date={datetime.now().strftime('%Y-%m-%d')}", note="dispatch today dated")
    # --- inbox: internal channel + filters ---
    await call(client, "GET", "/api/conversations?status=open", note="conversations filter open")
    await call(client, "GET", "/api/conversations?channel=whatsapp", note="conversations filter channel")
    await call(client, "GET", "/api/conversations?unread=true", note="conversations filter unread")
    # --- maintenance: create scheduled then complete-from-scheduled (status transition) ---
    veh = S.get("vehicle")
    if veh:
        sc, b = await call(client, "POST", "/api/maintenance", json_body={
            "vehicle_id": veh, "type": "servis", "title": "R11 sched->complete", "cost": 400000,
            "status": "scheduled", "scheduled_date": fut(2), "odometer": 95000}, note="maint scheduled")
        mid = (b or {}).get("id") if isinstance(b, dict) else None
        if mid:
            await call(client, "PATCH", f"/api/maintenance/{mid}", json_body={"status": "in_progress"}, note="maint -> in_progress")
            await call(client, "POST", f"/api/maintenance/{mid}/complete", json_body={"cost": 450000, "odometer": 95100}, note="maint complete-from-progress")
    # --- payroll: summary with period + reports ---
    await call(client, "GET", "/api/payroll/summary?period_type=monthly", note="payroll summary period")
    # --- notifications with filters ---
    await call(client, "GET", "/api/notifications?status=pending", note="notifications filter")
    await call(client, "GET", "/api/notifications?type=maintenance", note="notifications filter type")


async def sweep_pod_reassign(client):
    """POD multipart photo (driver+dispatch), re-assign different vehicle, driver checkin-via-booking."""
    import base64
    PNG = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")
    cust = S.get("customer")
    vehs = S.get("vehicles") or []
    drvs = S.get("drivers") or []
    v1 = vehs[-1] if vehs else None
    v2 = vehs[-2] if len(vehs) >= 2 else v1
    # booking -> confirm -> assign(v1) -> RE-ASSIGN(v2) [covers prev-vehicle release] -> departure -> enroute -> arrived -> POD(photo)
    sc, b = await call(client, "POST", "/api/bookings", json_body={
        "customer_id": cust, "vehicle_id": v1, "start_datetime": fut(220), "end_datetime": fut(221), "base_price": 2500000}, note="booking for pod/reassign")
    bid = (b or {}).get("id") if isinstance(b, dict) else None
    if bid:
        await call(client, "POST", f"/api/bookings/{bid}/confirm", note="confirm pod/reassign")
        sc, t = await call(client, "POST", f"/api/dispatch/{bid}/assign", json_body={"driver_id": drvs[0], "vehicle_id": v1}, note="assign v1")
        if v2 and v2 != v1:
            sc, t = await call(client, "POST", f"/api/dispatch/{bid}/assign", json_body={"driver_id": drvs[0], "vehicle_id": v2}, note="RE-assign v2 (release prev vehicle)")
        tid = (t or {}).get("trip", {}).get("id") if isinstance(t, dict) else None
        await call(client, "POST", f"/api/dispatch/{bid}/confirm-departure", note="departure pod")
        if tid:
            await call(client, "POST", f"/api/dispatch/trips/{tid}/enroute", note="enroute pod")
            await call(client, "POST", f"/api/dispatch/trips/{tid}/arrived", note="arrived pod")
            # POD bad content-type (400)
            await call(client, "POST", f"/api/dispatch/trips/{tid}/pod",
                       files={"photo": ("x.txt", b"hello", "text/plain")},
                       data={"recipient_name": "Pak X"}, note="dispatch POD bad content-type (400)")
            # POD with valid PNG photo (covers ext+write+finalize)
            await call(client, "POST", f"/api/dispatch/trips/{tid}/pod",
                       files={"photo": ("pod.png", PNG, "image/png")},
                       data={"recipient_name": "Pak Terima", "note": "foto pod"}, note="dispatch POD photo (finalize)")
    # driver checkin via OWN booking_id (creates trip through driver path) — needs booking assigned to login-linked driver
    mine = await get_json(client, "/api/driver/my-trips", role="driver") or []
    # find the driver's own driver_id via an owned trip
    own_driver_id = mine[0].get("driver_id") if mine else None
    if own_driver_id:
        sc, b = await call(client, "POST", "/api/bookings", json_body={
            "customer_id": cust, "vehicle_id": v1, "driver_id": own_driver_id,
            "start_datetime": fut(230), "end_datetime": fut(231), "base_price": 1800000}, note="booking assigned to login-driver")
        dbid = (b or {}).get("id") if isinstance(b, dict) else None
        if dbid:
            await call(client, "POST", f"/api/bookings/{dbid}/confirm", note="confirm driver-owned")
            await call(client, "POST", "/api/driver/checkin", role="driver", json_body={"booking_id": dbid, "odometer_start": 12000}, note="driver checkin via own booking (creates trip)")
            # find the new trip and POD with photo as driver, then checkout
            nt = await get_json(client, "/api/driver/my-trips", role="driver") or []
            newt = next((t for t in nt if t.get("booking_id") == dbid), None)
            if newt:
                await call(client, "POST", f"/api/driver/tasks/{newt['id']}/pod", role="driver",
                           files={"photo": ("pod2.png", PNG, "image/png")},
                           data={"recipient_name": "Ibu Rina"}, note="driver POD photo")
                await call(client, "POST", "/api/driver/checkout", role="driver", json_body={"trip_id": newt["id"], "odometer_end": 12200}, note="driver checkout own trip")
    # driver checkin ownership violation (403): checkin a booking not owned
    other_bk = S.get("booking")
    if other_bk:
        await call(client, "POST", "/api/driver/checkin", role="driver", json_body={"booking_id": other_bk}, note="driver checkin not-owned (403/400)")


async def main():
    async with httpx.AsyncClient(follow_redirects=False) as client:
        await login_all(client)
        await resolve_samples(client)
        sweeps = [
            ("masterdata", sweep_masterdata), ("bookings", sweep_bookings),
            ("bookings_deep", sweep_bookings_deep),
            ("quotations", sweep_quotations), ("dispatch_driver", sweep_dispatch_driver),
            ("finance", sweep_finance), ("maintenance", sweep_maintenance),
            ("crm_growth", sweep_crm_growth), ("content", sweep_content),
            ("payroll", sweep_payroll), ("subcharters", sweep_subcharters),
            ("inbox", sweep_inbox), ("wa_auto_gps", sweep_whatsapp_automation_gps),
            ("automation_deep", sweep_automation_deep), ("gps_deep", sweep_gps_deep),
            ("campaign_reads", sweep_campaign_reads),
            ("auth_ratelimit", sweep_auth_ratelimit), ("driver_role", sweep_driver_role),
            ("scheduler_seed", sweep_scheduler_seed),
            ("content_deep", sweep_content_deep), ("whatsapp_meta", sweep_whatsapp_meta),
            ("whatsapp_extra", sweep_whatsapp_extra),
            ("automation_conditions", sweep_automation_conditions),
            ("dispatch_sub_edges", sweep_dispatch_subcharter_edges),
            ("error_branches", sweep_error_branches),
            ("final_edges", sweep_final_edges),
            ("ceiling_push", sweep_ceiling_push),
            ("pod_reassign", sweep_pod_reassign),
            ("reads_exports", sweep_reads_exports), ("public_reads", sweep_public_reads),
            ("misc", sweep_misc), ("public", sweep_public),
        ]
        for name, fn in sweeps:
            try:
                await fn(client)
                print(f"  [sweep] {name} OK")
            except Exception as e:  # noqa: BLE001
                print(f"  [sweep] {name} EXC {e}")

    # summarize
    by_status = {}
    fivexx = []
    for r in RESULTS:
        k = str(r["status"])
        by_status[k] = by_status.get(k, 0) + 1
        if isinstance(r["status"], int) and r["status"] >= 500:
            fivexx.append(r)
    (OUT / "mutation_matrix.json").write_text(json.dumps({
        "api": API, "total_calls": len(RESULTS), "by_status": by_status,
        "five_xx": fivexx, "results": RESULTS}, indent=2, default=str))
    print(f"\nTOTAL mutation calls: {len(RESULTS)}")
    print(f"By status: {json.dumps(by_status, sort_keys=True)}")
    print(f"5xx count: {len(fivexx)}")
    for r in fivexx:
        print(f"  5xx: {r['method']} {r['path']} [{r['role']}] -> {r['status']} :: {r['note']}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
