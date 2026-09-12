"""Session-specific OpenWA re-verification tests (iteration 106).

Covers explicit review-request items:
- Owner login returns token
- /api/wa/config does NOT leak access_token (only access_token_set)
- /api/wa/openwa/status: running=true, installed=true (connected may be false)
- /api/wa/openwa/qr returns non-empty qr string
- Webhook auth: no key / wrong key → 403; correct key + empty payload → 200 {ok, received:0}
- /api/wa/simulate-inbound creates lead + conversation
- RBAC: driver forbidden on /api/wa/openwa/status (403)
"""
import os
import time
import uuid

import pytest
import requests


def _fe_env():
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.strip().startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return ""


BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or _fe_env()).rstrip("/")
API = f"{BASE_URL}/api"
OPENWA_KEY = "rahaza-openwa-key-2026"


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, r.text
    j = r.json()
    tok = j.get("access_token") or j.get("token")
    assert tok
    return tok


@pytest.fixture(scope="module")
def owner_token():
    return _login("owner@demo.local", "demo12345")


@pytest.fixture(scope="module")
def driver_token():
    return _login("driver@demo.local", "demo12345")


@pytest.fixture(scope="module")
def auth(owner_token):
    return {"Authorization": f"Bearer {owner_token}"}


# --- Login -----------------------------------------------------------------
def test_owner_login(owner_token):
    assert isinstance(owner_token, str) and len(owner_token) > 10


# --- wa/config does not leak secrets --------------------------------------
def test_wa_config_no_secret_leak(auth):
    r = requests.get(f"{API}/wa/config", headers=auth, timeout=15)
    assert r.status_code == 200
    d = r.json()
    assert d.get("provider") == "openwa", f"expected openwa provider, got {d.get('provider')}"
    meta = d.get("meta") or {}
    assert "access_token" not in meta, f"access_token leaked in meta: {meta}"
    assert "access_token_set" in meta
    assert isinstance(meta.get("access_token_set"), bool)
    assert "app_secret" not in meta
    assert "app_secret_set" in meta


# --- openwa status ---------------------------------------------------------
def test_openwa_status_running_installed(auth):
    data = {}
    deadline = time.time() + 45
    running = False
    while time.time() < deadline:
        r = requests.get(f"{API}/wa/openwa/status", headers=auth, timeout=20)
        assert r.status_code == 200
        data = r.json()
        if data.get("running"):
            running = True
            break
        time.sleep(3)
    assert data.get("installed") is True, data
    assert running, f"sidecar not running: {data}"
    # connected boleh false karena QR belum discan


# --- openwa qr -------------------------------------------------------------
def test_openwa_qr_non_empty(auth):
    qr = ""
    deadline = time.time() + 40
    while time.time() < deadline:
        r = requests.get(f"{API}/wa/openwa/qr", headers=auth, timeout=15)
        assert r.status_code == 200
        qr = r.json().get("qr") or ""
        if qr:
            break
        time.sleep(3)
    assert isinstance(qr, str) and len(qr) > 0, "QR string empty"


# --- webhook auth ----------------------------------------------------------
def test_openwa_webhook_no_key_403():
    r = requests.post(f"{API}/wa/openwa-webhook", json={}, timeout=10)
    assert r.status_code == 403


def test_openwa_webhook_wrong_key_403():
    r = requests.post(f"{API}/wa/openwa-webhook?key=WRONG", json={}, timeout=10)
    assert r.status_code == 403


def test_openwa_webhook_correct_key_empty_payload():
    r = requests.post(f"{API}/wa/openwa-webhook?key={OPENWA_KEY}", json={}, timeout=10)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("status") == "ok"
    assert body.get("received") == 0


# --- simulate-inbound creates lead + conversation --------------------------
def test_simulate_inbound_creates_lead_and_conversation(auth):
    phone = "6281299887" + str(uuid.uuid4().int)[:3]
    name = f"Tester QA {uuid.uuid4().hex[:4]}"
    r = requests.post(f"{API}/wa/simulate-inbound", headers=auth,
                      json={"from_phone": phone, "text": "Halo mau sewa hiace", "name": name},
                      timeout=20)
    assert r.status_code == 200, r.text
    # Verify lead
    time.sleep(1.5)
    lr = requests.get(f"{API}/leads", headers=auth, params={"q": phone}, timeout=15)
    assert lr.status_code == 200
    leads = lr.json()
    lst = leads if isinstance(leads, list) else leads.get("items") or leads.get("data") or []
    matched = [l for l in lst if phone in (l.get("phone") or "")]
    assert matched, f"lead not created for {phone}"

    # Verify conversation
    cr = requests.get(f"{API}/conversations", headers=auth, timeout=15)
    assert cr.status_code == 200
    convs = cr.json()
    cl = convs if isinstance(convs, list) else convs.get("items") or []
    found = None
    for c in cl:
        if phone in (c.get("contact_phone") or "") or name in (c.get("contact_name") or ""):
            found = c
            break
    assert found, f"conversation not created for {phone}/{name}"
    assert (found.get("channel") or "").lower() == "whatsapp"


# --- RBAC: driver forbidden -----------------------------------------------
def test_openwa_status_rbac_driver_forbidden(driver_token):
    r = requests.get(f"{API}/wa/openwa/status",
                     headers={"Authorization": f"Bearer {driver_token}"}, timeout=15)
    assert r.status_code == 403, f"expected 403 for driver, got {r.status_code}: {r.text}"


# --- Ensure provider tetap openwa (safety) ---------------------------------
def test_zz_provider_still_openwa(auth):
    r = requests.get(f"{API}/wa/config", headers=auth, timeout=15)
    assert r.status_code == 200
    assert r.json().get("provider") == "openwa"
